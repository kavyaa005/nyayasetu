"""Sub-heading statistics: distinct headings per act and sections whose text ends with a leaked heading.

Run:  python scripts/heading_stats.py            (current dataset)
      python scripts/heading_stats.py HEAD~1     (dataset as it was one commit ago)
"""
import json
import re
import subprocess
import sys

LEAK = re.compile(r"[.;:]\s+Of [a-z][a-z ,-]+$")   # text ending with e.g. ". Of fraudulent deeds and ..."
PATH = "data/processed/sections.jsonl"

if len(sys.argv) > 1:
    revision = sys.argv[1]
    raw = subprocess.run(["git", "show", f"{revision}:{PATH}"], capture_output=True, check=True).stdout
    lines = raw.decode("utf-8").splitlines()
    print(f"(dataset at git revision {revision})")
else:
    lines = open(PATH, encoding="utf-8").read().splitlines()

records = [json.loads(line) for line in lines if line.strip()]
for act in ("BNS", "BNSS", "BSA"):
    subset = [r for r in records if r["act"] == act]
    headings = {r["heading"] for r in subset if r["heading"]}
    leaks = [r["id"] for r in subset if LEAK.search(r["text"])]
    print(f"{act}: {len(headings)} distinct sub-headings, {len(leaks)} sections ending with a leaked heading {leaks[:10]}")
