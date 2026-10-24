"""Automated checks for the processed dataset. Run:  pytest -v"""
import json
from pathlib import Path

import pytest

from nyayasetu.ingestion.build import normalize_text, normalize_title
from nyayasetu.ingestion.sections import SECTION_RE
from nyayasetu.schema import SectionRecord

DATA = Path(__file__).resolve().parents[1] / "data" / "processed" / "sections.jsonl"
EXPECTED = {"BNS": 358, "BNSS": 531, "BSA": 170}
KNOWN_TITLES = [
    ("BNS", 103, "Punishment for murder"),
    ("BNS", 318, "Cheating"),
    ("BNS", 358, "Repeal and savings"),
    ("BNSS", 35, "When police may arrest without warrant"),
    ("BNSS", 531, "Repeal and savings"),
    ("BSA", 63, "Admissibility of electronic records"),
    ("BSA", 170, "Repeal and savings"),
]
GAZETTE_ARTIFACTS = ["GAZETTE OF INDIA", "Secretary to the Gov", "EXTRAORDINARY"]


@pytest.fixture(scope="module")
def records() -> list[dict]:
    if not DATA.exists():
        pytest.skip("dataset not built: run `python -m nyayasetu.ingestion.build`")
    return [json.loads(line) for line in DATA.read_text(encoding="utf-8").splitlines()]


# ---- Unit tests: small functions -------------------------------------------

def test_section_regex_handles_missing_space():
    m = SECTION_RE.match("2.In this Sanhita")
    assert m.group(1) == "2"
    assert m.group(2) == "In this Sanhita"


def test_normalize_adds_space_after_marker():
    assert normalize_text("(2)When a group") == "(2) When a group"


def test_normalize_title_strips_period():
    assert normalize_title("Cheating.") == "Cheating"


# ---- Regression tests: the dataset ------------------------------------------

@pytest.mark.parametrize("act,expected", EXPECTED.items())
def test_section_counts(records, act, expected):
    assert sum(1 for r in records if r["act"] == act) == expected


def test_numbers_are_contiguous(records):
    for act, total in EXPECTED.items():
        numbers = sorted(r["number"] for r in records if r["act"] == act)
        assert numbers == list(range(1, total + 1)), f"{act} has gaps or duplicates"


def test_ids_are_unique(records):
    ids = [r["id"] for r in records]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("act,number,title", KNOWN_TITLES)
def test_known_titles(records, act, number, title):
    record = next(r for r in records if r["act"] == act and r["number"] == number)
    assert record["title"] == title


def test_every_record_matches_schema(records):
    for r in records:
        SectionRecord(**r)   # raises if any rule is broken


def test_no_gazette_artifacts_in_text(records):
    for r in records:
        for artifact in GAZETTE_ARTIFACTS:
            assert artifact not in r["text"], f"{r['id']} contains '{artifact}'"
