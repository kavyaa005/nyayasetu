"""Sub-heading statistics: distinct headings per act and sections whose text ends with a leaked heading.

Run:  python scripts/heading_stats.py
"""
import json
import re

LEAK = re.compile(r"[.;:]\s+Of [a-z][a-z ,-]+$")   # text ending with e.g. ". Of fraudulent deeds and ..."

records = [json.loads(line) for line in open("data/processed/sections.jsonl", encoding="utf-8")]
for act in ("BNS", "BNSS", "BSA"):
    subset = [r for r in records if r["act"] == act]
    headings = {r["heading"] for r in subset if r["heading"]}
    leaks = [r["id"] for r in subset if LEAK.search(r["text"])]
    print(f"{act}: {len(headings)} distinct sub-headings, {len(leaks)} sections ending with a leaked heading {leaks[:10]}")
