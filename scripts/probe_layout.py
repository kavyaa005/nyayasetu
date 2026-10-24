"""Show where text sits horizontally on a PDF page, to find body vs margin columns.

Run:  python scripts/probe_layout.py data/raw/bns.pdf 1
Each output line:  y | [x_start-x_end] text || [x_start-x_end] text ...
A '||' means a big horizontal gap: likely a separate column (e.g. a margin note).
"""
import sys

import pdfplumber

GAP = 12        # points; a gap wider than this between words starts a new segment
MAX_LINES = 45  # keep output readable

path = sys.argv[1]
page_no = int(sys.argv[2]) if len(sys.argv) > 2 else 1

with pdfplumber.open(path) as pdf:
    page = pdf.pages[page_no - 1]
    print(f"page {page_no}: width={page.width:.0f} height={page.height:.0f}")
    words = page.extract_words()

    # Group words into lines by their vertical position (rounded to 3 points).
    lines = {}
    for w in words:
        lines.setdefault(round(w["top"] / 3), []).append(w)

    for key in sorted(lines)[:MAX_LINES]:
        line = sorted(lines[key], key=lambda w: w["x0"])
        segments, current = [], [line[0]]
        for w in line[1:]:
            if w["x0"] - current[-1]["x1"] > GAP:
                segments.append(current)
                current = [w]
            else:
                current.append(w)
        segments.append(current)

        parts = [
            f"[{seg[0]['x0']:.0f}-{seg[-1]['x1']:.0f}] " + " ".join(w["text"] for w in seg)[:60]
            for seg in segments
        ]
        print(f"{line[0]['top']:5.0f} | " + " || ".join(parts))
