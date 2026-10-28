"""Keyword search over the parsed sections (titles first, then text).

Run:  python scripts/search_sections.py dowry
      python scripts/search_sections.py "anticipatory bail"
"""
import json
import sys
from pathlib import Path

query = " ".join(sys.argv[1:]).lower()
records = [json.loads(line) for line in Path("data/processed/sections.jsonl").read_text(encoding="utf-8").splitlines()]

title_hits = [r for r in records if query in r["title"].lower()]
text_hits = [r for r in records if query in r["text"].lower() and r not in title_hits]

print(f"'{query}': {len(title_hits)} title matches, {len(text_hits)} text matches\n")
for r in title_hits:
    print(f"  [title] {r['id']:10} {r['title']}")
for r in text_hits[:15]:
    print(f"  [text]  {r['id']:10} {r['title']}")
if len(text_hits) > 15:
    print(f"  ... and {len(text_hits) - 15} more text matches")
