"""Assign a fixed dev/test split to accepted gold items, stratified by question type.

Run:  python scripts/split_gold.py
Items that already have a split are never moved, so the split stays frozen as the set grows.
"""
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from nyayasetu.schema import EvalItem

GOLD = Path("data/eval/gold.jsonl")
DEV_SHARE = 0.4
SEED = 7

items = [EvalItem(**json.loads(l)) for l in GOLD.read_text(encoding="utf-8").splitlines() if l.strip()]

groups = defaultdict(list)
for i, item in enumerate(items):
    if item.status == "accepted" and item.split is None:
        groups[item.qtype].append(i)

rng = random.Random(SEED)
for qtype in sorted(groups):
    idxs = groups[qtype]
    rng.shuffle(idxs)
    n_dev = round(len(idxs) * DEV_SHARE)
    for k, i in enumerate(idxs):
        items[i] = items[i].model_copy(update={"split": "dev" if k < n_dev else "test"})

GOLD.write_text("".join(it.model_dump_json() + "\n" for it in items), encoding="utf-8")

accepted = [it for it in items if it.status == "accepted"]
print("Items per split:", dict(Counter(it.split for it in accepted)))
for split in ("dev", "test"):
    print(f"  {split}: " + ", ".join(f"{q}={n}" for q, n in sorted(Counter(it.qtype for it in accepted if it.split == split).items())))