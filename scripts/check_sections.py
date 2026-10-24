"""Inspect parsed sections: length statistics plus selected sections in full.

Run:  python scripts/check_sections.py bns 103 318 358
"""
import json
import statistics
import sys
from pathlib import Path

act = sys.argv[1]
wanted = [int(n) for n in sys.argv[2:]]
path = Path("data/interim") / f"{act}_sections.jsonl"
sections = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

lengths = sorted((len(s["text"]), s["number"]) for s in sections)
print(f"{act}: {len(sections)} sections")
print(f"  text length (characters): min={lengths[0][0]}  "
      f"median={statistics.median(l for l, _ in lengths):.0f}  max={lengths[-1][0]}")
print(f"  3 shortest: {[f's.{n} ({l} chars)' for l, n in lengths[:3]]}")
print(f"  3 longest:  {[f's.{n} ({l} chars)' for l, n in lengths[-3:]]}")

by_number = {s["number"]: s for s in sections}
for n in wanted:
    s = by_number[n]
    print("\n" + "=" * 70)
    print(f"Section {n}: {s['title']}")
    print(f"Chapter {s['chapter']}: {s['chapter_title']} | heading: {s['heading']}")
    print(f"Pages {s['page_start']}-{s['page_end']} | act refs: {s['act_refs']}")
    print("-" * 70)
    text = s["text"]
    print(text if len(text) <= 600 else text[:400] + "\n   [...]\n" + text[-200:])
