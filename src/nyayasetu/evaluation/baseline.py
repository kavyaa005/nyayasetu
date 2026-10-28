"""Experiment E1: ask an LLM legal questions WITHOUT our dataset, and score its citations.

Run:  python -m nyayasetu.evaluation.baseline --provider groq --model openai/gpt-oss-120b
Results are saved per question to experiments/e1_no_rag/<provider>__<model>.jsonl (resumable),
and a summary is printed and saved as <provider>__<model>.summary.json.
"""
import argparse
import json
import re
import time

from nyayasetu.generation.llm import chat
from nyayasetu.ingestion.layout import PROJECT_ROOT

GOLD_PATH = PROJECT_ROOT / "data" / "eval" / "gold.jsonl"
SECTIONS_PATH = PROJECT_ROOT / "data" / "processed" / "sections.jsonl"
OUT_DIR = PROJECT_ROOT / "experiments" / "e1_no_rag"

SYSTEM_PROMPT = """You are a legal research assistant for Indian criminal law. The laws in force are the Bharatiya Nyaya Sanhita, 2023 (BNS), the Bharatiya Nagarik Suraksha Sanhita, 2023 (BNSS) and the Bharatiya Sakshya Adhiniyam, 2023 (BSA).

Answer the user's question briefly. If the question is not covered by these three laws, or you are not sure, say so instead of guessing.

End your reply with exactly one final line in this format:
CITATIONS: BNS-318, BNSS-35
listing every section of these three laws your answer relies on, or
CITATIONS: NONE
if you cite no section."""

CITATION_LINE = re.compile(r"CITATIONS:\s*(.+)", re.I)
ID_RE = re.compile(r"\b(BNSS|BNS|BSA)\s*[-\u2013 ]?\s*(?:s(?:ection)?\.?\s*)?(\d{1,3})\b", re.I)


def load_jsonl(path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def extract_citations(answer: str) -> tuple[list[str], bool]:
    """Return (cited section IDs, whether the model used the required CITATIONS line)."""
    matches = list(CITATION_LINE.finditer(answer))
    if matches:
        text = matches[-1].group(1)
        if text.strip().upper().startswith("NONE"):
            return [], True
        found, format_ok = ID_RE.findall(text), True
    else:
        found, format_ok = ID_RE.findall(answer), False
    ids = list(dict.fromkeys(f"{act.upper()}-{int(num)}" for act, num in found))
    return ids, format_ok


def score(item: dict, cited: list[str], valid_ids: set[str]) -> dict:
    nonexistent = [c for c in cited if c not in valid_ids]
    if item["should_abstain"]:
        return {"abstain_item": True, "abstained": not cited, "nonexistent": nonexistent, "n_cited": len(cited)}
    gold = set(item["gold_sections"])
    return {
        "abstain_item": False,
        "hit": any(c in gold for c in cited),
        "n_cited": len(cited),
        "n_correct": sum(c in gold for c in cited),
        "wrong": [c for c in cited if c in valid_ids and c not in gold],
        "nonexistent": nonexistent,
    }


def pct(num: int, den: int) -> str:
    return f"{num}/{den} ({100 * num / den:.1f}%)" if den else "n/a"


def summarize(records: list[dict]) -> dict:
    summary = {}
    scopes = {"all": records, "dev": [r for r in records if r["split"] == "dev"],
              "test": [r for r in records if r["split"] == "test"]}
    for origin in sorted({r["origin"] for r in records}):
        scopes[f"origin={origin}"] = [r for r in records if r["origin"] == origin]
    for name, recs in scopes.items():
        ans = [r for r in recs if not r["abstain_item"]]
        abst = [r for r in recs if r["abstain_item"]]
        cited = sum(r["n_cited"] for r in recs)
        summary[name] = {
            "questions": len(recs),
            "correct_citation_rate": pct(sum(r["hit"] for r in ans), len(ans)),
            "citation_precision": pct(sum(r["n_correct"] for r in ans), sum(r["n_cited"] for r in ans)),
            "fabricated_citation_rate": pct(sum(len(r["nonexistent"]) for r in recs), cited),
            "abstention_accuracy": pct(sum(r["abstained"] for r in abst), len(abst)),
            "format_compliance": pct(sum(r["format_ok"] for r in recs), len(recs)),
        }
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="groq")
    ap.add_argument("--model", required=True)
    ap.add_argument("--splits", default="dev,test")
    ap.add_argument("--sleep", type=float, default=2.0)
    ap.add_argument("--max-tokens", type=int, default=3000)
    args = ap.parse_args()

    valid_ids = {r["id"] for r in load_jsonl(SECTIONS_PATH)}
    splits = set(args.splits.split(","))
    items = [r for r in load_jsonl(GOLD_PATH) if r["status"] == "accepted" and r["split"] in splits]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = f"{args.provider}__{args.model.replace('/', '_')}"
    out_path = OUT_DIR / f"{slug}.jsonl"
    done = {r["id"] for r in load_jsonl(out_path)}

    for item in items:
        if item["id"] in done:
            continue
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": item["question"]}]
        try:
            res = chat(args.provider, args.model, messages, temperature=0.0, max_tokens=args.max_tokens)
        except Exception as exc:
            print(f"[fail] {item['id']}: {type(exc).__name__}: {str(exc)[:100]}")
            time.sleep(args.sleep)
            continue
        cited, format_ok = extract_citations(res.text)
        record = {
            "id": item["id"], "split": item["split"], "qtype": item["qtype"], "origin": item["origin"],
            "question": item["question"], "gold": item["gold_sections"], "should_abstain": item["should_abstain"],
            "answer": res.text, "cited": cited, "format_ok": format_ok,
            **score(item, cited, valid_ids),
            "provider": args.provider, "model": args.model, "latency_s": res.latency_s,
            "prompt_tokens": res.prompt_tokens, "completion_tokens": res.completion_tokens,
        }
        with out_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        if record["abstain_item"]:
            mark = "ok " if record["abstained"] else "BAD"
        else:
            mark = "ok " if record["hit"] else "BAD"
        if record["nonexistent"]:
            mark = "FAB"
        print(f"[{mark}] {item['id']:5} cited={cited} gold={item['gold_sections'] or 'ABSTAIN'}")
        time.sleep(args.sleep)

    records = load_jsonl(out_path)
    summary = summarize(records)
    (OUT_DIR / f"{slug}.summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nE1 summary for {args.provider}/{args.model} ({len(records)} answered questions)")
    for scope, metrics in summary.items():
        print(f"\n[{scope}]")
        for key, value in metrics.items():
            print(f"  {key:26} {value}")


if __name__ == "__main__":
    main()