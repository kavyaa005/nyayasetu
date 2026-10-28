"""Change the gold sections or status of one eval item after review or audit.

Run:  python scripts/set_gold.py s044 BNSS-59,BNSS-48      (set acceptable sections)
      python scripts/set_gold.py s029 --reject             (remove item from the evaluation)
"""
import json
import sys
from pathlib import Path

from nyayasetu.schema import EvalItem

GOLD = Path("data/eval/gold.jsonl")
SECTION_IDS = {json.loads(l)["id"] for l in Path("data/processed/sections.jsonl").read_text(encoding="utf-8").splitlines()}

item_id, value = sys.argv[1], sys.argv[2]
items = [EvalItem(**json.loads(l)) for l in GOLD.read_text(encoding="utf-8").splitlines() if l.strip()]
for i, item in enumerate(items):
    if item.id != item_id:
        continue
    if value == "--reject":
        items[i] = item.model_copy(update={"status": "rejected", "notes": item.notes + " | rejected in audit"})
    else:
        ids = [x.strip().upper() for x in value.split(",")]
        missing = [x for x in ids if x not in SECTION_IDS]
        if missing:
            sys.exit(f"Not in dataset: {missing}")
        items[i] = item.model_copy(update={"gold_sections": ids, "status": "accepted",
                                           "notes": item.notes + " | gold edited in audit"})
    print(f"{item_id}: {items[i].status} {items[i].gold_sections}")
    break
else:
    sys.exit(f"No item with id {item_id}")
GOLD.write_text("".join(it.model_dump_json() + "\n" for it in items), encoding="utf-8")