"""Human review of gold evaluation items against the real law text.

Run:  python scripts/review_gold.py
For each unreviewed item it shows the question and the proposed section(s) from OUR dataset.
Answer: y = labels correct, n = wrong (you can type the correct IDs), s = skip, q = quit.
Progress is saved after every answer, so you can stop and resume any time.
"""
import json
from pathlib import Path

from nyayasetu.schema import EvalItem

GOLD = Path("data/eval/gold.jsonl")
SECTIONS = {
    r["id"]: r
    for r in map(json.loads, Path("data/processed/sections.jsonl").read_text(encoding="utf-8").splitlines())
}
MAX_SECTION = {"BNS": 358, "BNSS": 531, "BSA": 170}


def load() -> list[EvalItem]:
    return [EvalItem(**json.loads(line)) for line in GOLD.read_text(encoding="utf-8").splitlines() if line.strip()]


def save(items: list[EvalItem]) -> None:
    GOLD.write_text("".join(item.model_dump_json() + "\n" for item in items), encoding="utf-8")


def show(item: EvalItem) -> None:
    print("\n" + "=" * 78)
    print(f"{item.id} [{item.qtype}, {item.difficulty}]  {item.question}")
    if item.notes:
        print(f"note: {item.notes}")
    if item.should_abstain:
        print(f"-> Expected behaviour: ABSTAIN (refuse). Sections per act: {MAX_SECTION}")
        return
    for sid in item.gold_sections:
        s = SECTIONS.get(sid)
        if s is None:
            print(f"-> {sid}: !! DOES NOT EXIST in our dataset")
            continue
        print(f"-> {sid}: {s['title']}   (Chapter {s['chapter']}: {s['chapter_title']})")
        print("   " + s["text"][:500].replace("\n", "\n   ") + (" [...]" if len(s["text"]) > 500 else ""))


def ask_corrected_ids() -> list[str] | None:
    raw = input("   Correct section IDs, comma-separated (e.g. BNS-318,BNS-319), or Enter to reject: ").strip()
    if not raw:
        return None
    ids = [x.strip().upper() for x in raw.split(",") if x.strip()]
    missing = [x for x in ids if x not in SECTIONS]
    if missing:
        print(f"   Not in dataset: {missing}. Item rejected; fix it later.")
        return None
    return ids


def main() -> None:
    items = load()
    for i, item in enumerate(items):
        if item.status != "unreviewed":
            continue
        show(item)
        answer = input("Labels correct? [y]es / [n]o / [s]kip / [q]uit: ").strip().lower()
        if answer == "q":
            break
        if answer == "y":
            items[i] = item.model_copy(update={"status": "accepted"})
        elif answer == "n":
            ids = None if item.should_abstain else ask_corrected_ids()
            if ids:
                items[i] = item.model_copy(update={"gold_sections": ids, "status": "accepted",
                                                   "notes": (item.notes + " | label corrected in review").strip(" |")})
            else:
                items[i] = item.model_copy(update={"status": "rejected"})
        save(items)

    counts: dict[str, int] = {}
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1
    print(f"\nReview status: {counts}")


if __name__ == "__main__":
    main()
