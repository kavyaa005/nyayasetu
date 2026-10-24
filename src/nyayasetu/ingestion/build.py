"""Build the final validated dataset from the raw PDFs.

Run:  python -m nyayasetu.ingestion.build
Writes data/processed/sections.jsonl and data/processed/build_report.json
"""
import json
import re
from datetime import datetime, timezone

from pydantic import ValidationError

from nyayasetu.ingestion.layout import PROJECT_ROOT, RAW_DIR, extract_act
from nyayasetu.ingestion.sections import EXPECTED_SECTIONS, parse_sections
from nyayasetu.schema import SectionRecord

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT = PROCESSED_DIR / "sections.jsonl"
REPORT = PROCESSED_DIR / "build_report.json"
ACTS = ["bns", "bnss", "bsa"]

# "(2)When" -> "(2) When": a paragraph marker at line start glued to the next word.
MARKER_NO_SPACE = re.compile(r"^(\(\w{1,5}\))(?=\S)", re.MULTILINE)
MULTI_SPACE = re.compile(r"[ \t]{2,}")


def normalize_text(text: str) -> str:
    """Safe, meaning-preserving clean-ups of section text."""
    text = text.replace("\u2013\u2013", "\u2014")   # double en-dash -> em-dash
    text = MARKER_NO_SPACE.sub(r"\1 ", text)
    text = MULTI_SPACE.sub(" ", text)
    return text.strip()


def normalize_title(title: str | None) -> str | None:
    """'Cheating.' -> 'Cheating'"""
    return title.strip().rstrip(".").strip() if title else title


def dedupe(items: list[str]) -> list[str]:
    """Remove duplicates while keeping the original order."""
    return list(dict.fromkeys(items))


def build() -> None:
    manifest_path = RAW_DIR / "sources.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    records: list[SectionRecord] = []
    errors: list[str] = []
    summary: dict[str, dict] = {}

    for name in ACTS:
        sections, issues = parse_sections(name, extract_act(name))
        expected = EXPECTED_SECTIONS[name]
        if len(sections) != expected:
            raise SystemExit(f"{name}: parsed {len(sections)} sections, expected {expected}. Fix the parser first.")

        source = manifest.get(name, {}).get("source", "unknown")
        act = name.upper()
        for s in sections:
            data = {
                "id": f"{act}-{s.number}",
                "act": act,
                "number": s.number,
                "title": normalize_title(s.title),
                "chapter": s.chapter,
                "chapter_title": s.chapter_title,
                "heading": s.heading,
                "text": normalize_text(s.text),
                "page_start": s.page_start,
                "page_end": s.page_end,
                "act_refs": dedupe(s.act_refs),
                "source": source,
            }
            try:
                records.append(SectionRecord(**data))
            except ValidationError as exc:
                errors.append(f"{data['id']}: {exc}")
        summary[name] = {"sections": len(sections), "source": source, "sequence_warnings": len(issues)}

    if errors:
        print("Validation failed:")
        for e in errors:
            print("  " + e)
        raise SystemExit(1)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(rec.model_dump_json() + "\n")

    report = {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_sections": len(records),
        "acts": summary,
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    for name, info in summary.items():
        print(f"[ok] {name}: {info['sections']} sections (source: {info['source']})")
    print(f"\nWrote {len(records)} validated records to {OUTPUT.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    build()
