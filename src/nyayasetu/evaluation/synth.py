"""Generate candidate gold questions from sampled sections with an LLM.

Run:  python -m nyayasetu.evaluation.synth                 (60 questions, default model)
      python -m nyayasetu.evaluation.synth --sleep 6
Each question is appended to data/eval/gold.jsonl as 'unreviewed'. Re-running skips sections already done.
"""
import argparse
import json
import random
import re
import time

from nyayasetu.generation.llm import chat
from nyayasetu.ingestion.layout import PROJECT_ROOT
from nyayasetu.schema import EvalItem

SECTIONS_PATH = PROJECT_ROOT / "data" / "processed" / "sections.jsonl"
GOLD_PATH = PROJECT_ROOT / "data" / "eval" / "gold.jsonl"

SKIP_TITLE = re.compile(r"short title|definition|repeal|saving|construction of references|interpretation", re.I)
SHARES = {"BNS": 25, "BNSS": 25, "BSA": 10}          # questions per act
MAX_CHARS = 1500                                      # keep prompts small for free-tier token limits
QTYPES = {"BNS": ["topic", "scenario"], "BNSS": ["procedure"], "BSA": ["evidence"]}
ACT_NAMES = {
    "BNS": "Bharatiya Nyaya Sanhita, 2023 (criminal offences and punishments)",
    "BNSS": "Bharatiya Nagarik Suraksha Sanhita, 2023 (criminal procedure)",
    "BSA": "Bharatiya Sakshya Adhiniyam, 2023 (law of evidence)",
}
STYLE = {
    "scenario": "Describe a short real-life situation and ask what offence or punishment applies.",
    "topic": "Ask directly about the offence, rule or punishment.",
    "procedure": "Ask what the police, a court or a person can or must do in a situation.",
    "evidence": "Ask what can be proved or used as evidence in court, and how.",
}
PROMPT = """You write test questions for an Indian criminal-law assistant.

Below is one section of the {act_name}. Write ONE question that an ordinary person (not a lawyer) might ask, which this section answers.

Rules:
- Use everyday words. Do not copy phrases from the section text.
- Do not mention the section number or the name of the Act.
- {style}
- The question must be answerable from this section.

Return ONLY a JSON object and nothing else:
{{"question": "...", "difficulty": "easy or medium or hard"}}

SECTION TITLE: {title}
SECTION TEXT:
{text}"""


def load_jsonl(path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sample_sections(seed: int) -> list[dict]:
    """Pick a fixed number of eligible sections per act, reproducibly."""
    eligible = [r for r in load_jsonl(SECTIONS_PATH)
                if not SKIP_TITLE.search(r["title"]) and len(r["text"]) >= 150]
    rng = random.Random(seed)
    chosen = []
    for act, count in SHARES.items():
        pool = [r for r in eligible if r["act"] == act]
        chosen += rng.sample(pool, count)
    return chosen


def parse_json(text: str) -> dict:
    """Extract the JSON object from a model reply (ignoring any thinking or extra text)."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        raise ValueError("no JSON object in reply")
    return json.loads(match.group(0))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="groq")
    ap.add_argument("--model", default="qwen/qwen3.8-27b")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--sleep", type=float, default=4.0, help="seconds to wait between calls")
    args = ap.parse_args()

    existing = load_jsonl(GOLD_PATH)
    done = {m.group(1) for r in existing if (m := re.search(r"source=([A-Z]+-\d+)", r.get("notes", "")))}
    next_num = 1 + max((int(r["id"][1:]) for r in existing if r["id"].startswith("s")), default=0)
    rng = random.Random(args.seed)

    added = failed = skipped = 0
    for sec in sample_sections(args.seed):
        qtype = rng.choice(QTYPES[sec["act"]])
        if sec["id"] in done:
            skipped += 1
            continue
        prompt = PROMPT.format(act_name=ACT_NAMES[sec["act"]], style=STYLE[qtype],
                               title=sec["title"], text=sec["text"][:MAX_CHARS])
        try:
            result = chat(args.provider, args.model, [{"role": "user", "content": prompt}],
                          temperature=0.7, max_tokens=1500)
            data = parse_json(result.text)
            difficulty = data.get("difficulty") if data.get("difficulty") in ("easy", "medium", "hard") else "medium"
            item = EvalItem(
                id=f"s{next_num:03d}", question=str(data["question"]).strip(), qtype=qtype,
                gold_sections=[sec["id"]], should_abstain=False, difficulty=difficulty,
                origin="synthetic_llm", notes=f"source={sec['id']}; generator={args.provider}/{args.model}",
            )
        except Exception as exc:
            failed += 1
            print(f"[fail] {sec['id']}: {type(exc).__name__}: {str(exc)[:120]}")
            time.sleep(args.sleep)
            continue

        with GOLD_PATH.open("a", encoding="utf-8") as f:
            f.write(item.model_dump_json() + "\n")
        next_num += 1
        added += 1
        print(f"[ok]   {item.id} <- {sec['id']} ({sec['title'][:35]}): {item.question}")
        time.sleep(args.sleep)

    print(f"\nAdded {added}, failed {failed}, already done {skipped}.")


if __name__ == "__main__":
    main()