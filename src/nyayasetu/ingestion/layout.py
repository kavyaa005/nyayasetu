"""Split each PDF page into body lines and margin notes, using word positions.

Run:  python -m nyayasetu.ingestion.layout          (all acts)
      python -m nyayasetu.ingestion.layout bns      (one act)
Writes a human-readable debug file per act to data/interim/<act>_layout.txt
"""
import sys
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
INTERIM_DIR = PROJECT_ROOT / "data" / "interim"

# Measured with scripts/probe_layout.py and the v2 debug output (A4 page: 595 x 842 points).
# Body text starts at x~142 on odd pages and x~118 on even pages; left margin notes start ~58.
HEADER_BOTTOM = 75      # running page header sits above this y
LEFT_MARGIN_X = 114     # a word starting left of this x belongs to the left margin
RIGHT_MARGIN_X = 485    # a word starting right of this x belongs to the right margin
LINE_TOL = 3            # words whose tops differ by <= this are on the same line
MARGIN_JOIN_GAP = 14    # margin lines closer than this (vertically) may be one note


@dataclass
class Line:
    page: int
    top: float   # y position (distance from top of page)
    x0: float    # x position of the line's left edge
    text: str
    kind: str    # "body", "margin_left" or "margin_right"


def _group_lines(words: list[dict]) -> list[list[dict]]:
    """Group words into lines by vertical position; each line sorted left to right."""
    lines: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if lines and abs(w["top"] - lines[-1][0]["top"]) <= LINE_TOL:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(line, key=lambda w: w["x0"]) for line in lines]


def _make_line(words: list[dict], kind: str, page_no: int) -> Line:
    return Line(page_no, words[0]["top"], words[0]["x0"], " ".join(w["text"] for w in words), kind)


def _merge_margin(lines: list[Line]) -> list[Line]:
    """Glue multi-line margin notes into one. A line ending in '.' closes the current note."""
    merged: list[Line] = []
    prev_top = None
    note_open = False
    for ln in sorted(lines, key=lambda l: l.top):
        close_enough = prev_top is not None and ln.top - prev_top <= MARGIN_JOIN_GAP
        if merged and note_open and close_enough:
            merged[-1].text += " " + ln.text
        else:
            merged.append(Line(ln.page, ln.top, ln.x0, ln.text, ln.kind))
        note_open = not ln.text.endswith(".")
        prev_top = ln.top
    return merged


def extract_page(page, page_no: int) -> list[Line]:
    """Return body lines and merged margin notes for one page, in reading order."""
    words = [w for w in page.extract_words() if w["top"] >= HEADER_BOTTOM]
    body: list[Line] = []
    left: list[Line] = []
    right: list[Line] = []

    for line in _group_lines(words):
        left_words = [w for w in line if w["x0"] < LEFT_MARGIN_X]
        right_words = [w for w in line if w["x0"] > RIGHT_MARGIN_X]
        body_words = [w for w in line if LEFT_MARGIN_X <= w["x0"] <= RIGHT_MARGIN_X]
        if left_words:
            left.append(_make_line(left_words, "margin_left", page_no))
        if right_words:
            right.append(_make_line(right_words, "margin_right", page_no))
        if body_words:
            body.append(_make_line(body_words, "body", page_no))

    all_lines = body + _merge_margin(left) + _merge_margin(right)
    # Sort top-to-bottom; on the same line, show the margin note before the body text.
    return sorted(all_lines, key=lambda l: (round(l.top), l.kind == "body"))


def extract_act(name: str) -> list[Line]:
    lines: list[Line] = []
    with pdfplumber.open(RAW_DIR / f"{name}.pdf") as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            lines.extend(extract_page(page, page_no))
    return lines


def write_debug(name: str, lines: list[Line]) -> Path:
    """Write a readable file: body lines prefixed with their x position, margin notes flagged."""
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    path = INTERIM_DIR / f"{name}_layout.txt"
    with path.open("w", encoding="utf-8") as f:
        current_page = None
        for ln in lines:
            if ln.page != current_page:
                f.write(f"\n===== page {ln.page} =====\n")
                current_page = ln.page
            if ln.kind == "body":
                f.write(f"[{ln.x0:3.0f}] {ln.text}\n")
            else:
                f.write(f"      >> {ln.kind.upper()}: {ln.text}\n")
    return path


def main() -> None:
    names = sys.argv[1:] or ["bns", "bnss", "bsa"]
    for name in names:
        lines = extract_act(name)
        n_margin = sum(ln.kind != "body" for ln in lines)
        path = write_debug(name, lines)
        print(f"{name}: {len(lines)} lines, {n_margin} margin notes -> {path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
