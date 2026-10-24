"""Parse positioned layout lines into sections.

Run:  python -m nyayasetu.ingestion.sections          (all acts)
      python -m nyayasetu.ingestion.sections bns      (one act)
Writes data/interim/<act>_sections.jsonl and data/interim/<act>_report.txt
"""
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from nyayasetu.ingestion.layout import INTERIM_DIR, PROJECT_ROOT, Line, extract_act

# Known totals, used as an acceptance test for the parser.
EXPECTED_SECTIONS = {"bns": 358, "bnss": 531, "bsa": 170}

CHAPTER_RE = re.compile(r"^CHAPTER\s+([IVXLC]+[A-Z]?)\s*$")
PART_RE = re.compile(r"^PART\s+([IVX]+)\s*$")
SECTION_RE = re.compile(r"^(\d+)\.\s*(.*)$")
ACT_REF_RE = re.compile(r"^\d+\s+of\s+\d{4}\.?$")
# Lines that start a new paragraph inside a section's text.
PARA_RE = re.compile(r"^(\(\w{1,5}\)|Explanation|Illustrations?\b|Exception|Provided)")
# Where the law text ends: Schedules, or the signature block of the Gazette.
END_RE = re.compile(
    r"^(THE\s+)?((FIRST|SECOND)\s+)?SCHEDULE\s*$"
    r"|Secretary to the Gov"
    r"|^DR\.\s+[A-Z]"
    r"|^[\u2014\u2013-]{4,}$"
)
TITLE_MAX_DY = 60          # a title must be within this many points of its section's first line
HEADING_MIN_OFFSET = 30    # headings start further right than paragraph indents (24pt)
HEADING_LOOKAHEAD = 2      # a heading is followed by its section within this many body lines


@dataclass
class Section:
    act: str
    number: int
    title: str | None
    chapter: str | None
    chapter_title: str | None
    heading: str | None          # centred sub-heading, e.g. "Of hurt"
    text: str
    page_start: int
    page_end: int
    top: float                   # y position of the section's first line
    act_refs: list[str] = field(default_factory=list)


def _page_base(page: int) -> float:
    """Left edge of continuation lines: even pages are shifted 24pt left of odd pages."""
    return 118 if page % 2 == 0 else 142


def _section_starts_soon(seq: list[Line], idx: int, expected: int) -> bool:
    """True if the next expected section starts within the next few body lines."""
    seen = 0
    for nxt in seq[idx + 1:]:
        if nxt.kind != "body":
            continue
        m = SECTION_RE.match(nxt.text)
        if m and int(m.group(1)) == expected:
            return True
        seen += 1
        if seen >= HEADING_LOOKAHEAD:
            return False
    return False


def _is_heading(seq: list[Line], idx: int, expected: int) -> bool:
    ln = seq[idx]
    text = ln.text
    if ln.x0 - _page_base(ln.page) <= HEADING_MIN_OFFSET:
        return False
    if not text[:1].isupper() or PARA_RE.match(text) or text.startswith("Illustration"):
        return False
    return _section_starts_soon(seq, idx, expected)


def parse_sections(name: str, lines: list[Line]) -> tuple[list[Section], list[str]]:
    issues: list[str] = []
    start = next(i for i, ln in enumerate(lines) if ln.kind == "body" and CHAPTER_RE.match(ln.text))
    seq = lines[start:]

    sections: list[Section] = []
    notes: list[Line] = []       # margin notes that may be section titles
    current: Section | None = None
    expected = 1
    chapter = chapter_title = heading = None
    reading_chapter_title = False
    prev_was_heading = False

    for idx, ln in enumerate(seq):
        text = ln.text

        # Margin notes: Act references go to the current section; the rest are title candidates.
        if ln.kind != "body":
            if ACT_REF_RE.match(text):
                if current:
                    current.act_refs.append(text.rstrip("."))
            else:
                notes.append(ln)
            continue

        if END_RE.search(text):
            break

        m = CHAPTER_RE.match(text)
        if m:
            chapter, chapter_title, heading = m.group(1), "", None
            reading_chapter_title = True
            prev_was_heading = False
            continue
        if reading_chapter_title and text.isupper():
            chapter_title = f"{chapter_title} {text}".strip()
            continue
        reading_chapter_title = False

        if PART_RE.match(text):
            continue

        m = SECTION_RE.match(text)
        if m and int(m.group(1)) == expected:
            current = Section(
                act=name, number=expected, title=None, chapter=chapter,
                chapter_title=chapter_title or None, heading=heading,
                text=m.group(2).strip(), page_start=ln.page, page_end=ln.page, top=ln.top,
            )
            sections.append(current)
            expected += 1
            prev_was_heading = False
            continue
        if m and int(m.group(1)) > expected:
            issues.append(f"p{ln.page}: saw '{m.group(1)}.' while expecting {expected}: {text[:70]}")

        if _is_heading(seq, idx, expected):
            heading = f"{heading} {text}" if prev_was_heading else text
            prev_was_heading = True
            continue
        prev_was_heading = False

        if current is None:
            continue

        separator = "\n" if PARA_RE.match(text) else " "
        current.text += separator + text
        current.page_end = ln.page

    _attach_titles(sections, notes)
    return sections, issues


def _attach_titles(sections: list[Section], notes: list[Line]) -> None:
    """Give each section the closest unused margin note on the same page."""
    used: set[int] = set()
    for s in sections:
        best, best_dy = None, None
        for j, note in enumerate(notes):
            if j in used or note.page != s.page_start:
                continue
            dy = abs(note.top - s.top)
            if dy <= TITLE_MAX_DY and (best_dy is None or dy < best_dy):
                best, best_dy = j, dy
        if best is not None:
            used.add(best)
            s.title = notes[best].text
    for j, n in enumerate(notes):
        if j not in used:
            n.kind = "unused_note"    # marked so the report can list them


def write_outputs(name: str, sections: list[Section], issues: list[str], notes_unused: list[Line]) -> None:
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    with (INTERIM_DIR / f"{name}_sections.jsonl").open("w", encoding="utf-8") as f:
        for s in sections:
            f.write(json.dumps(asdict(s), ensure_ascii=False) + "\n")

    expected = EXPECTED_SECTIONS.get(name)
    no_title = [s.number for s in sections if not s.title]
    with (INTERIM_DIR / f"{name}_report.txt").open("w", encoding="utf-8") as f:
        f.write(f"{name}: {len(sections)} sections parsed, expected {expected}\n\n")
        f.write(f"Sections without a title ({len(no_title)}): {no_title}\n\n")
        f.write(f"Sequence warnings ({len(issues)}):\n")
        f.writelines(f"  {i}\n" for i in issues)
        f.write(f"\nUnused margin notes ({len(notes_unused)}):\n")
        f.writelines(f"  p{n.page} y={n.top:.0f}: {n.text}\n" for n in notes_unused)


def main() -> None:
    names = sys.argv[1:] or ["bns", "bnss", "bsa"]
    for name in names:
        lines = extract_act(name)
        sections, issues = parse_sections(name, lines)
        unused = [ln for ln in lines if ln.kind == "unused_note"]
        write_outputs(name, sections, issues, unused)

        expected = EXPECTED_SECTIONS.get(name)
        status = "PASS" if len(sections) == expected else "CHECK"
        no_title = sum(1 for s in sections if not s.title)
        n_headings = len({s.heading for s in sections if s.heading})
        print(
            f"[{status}] {name}: {len(sections)}/{expected} sections, {n_headings} sub-headings, "
            f"{no_title} without title, {len(issues)} sequence warnings, {len(unused)} unused notes"
            f" -> {Path(INTERIM_DIR / f'{name}_report.txt').relative_to(PROJECT_ROOT)}"
        )


if __name__ == "__main__":
    main()
