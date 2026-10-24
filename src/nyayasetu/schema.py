"""Data contracts for NyayaSetu. Every record must satisfy these rules or the build fails."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SectionRecord(BaseModel):
    """One section of one act: the basic unit for retrieval and citation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str                                   # stable citation ID, e.g. "BNS-103"
    act: Literal["BNS", "BNSS", "BSA"]
    number: int = Field(ge=1)
    title: str = Field(min_length=3)          # e.g. "Punishment for murder"
    chapter: str                              # Roman numeral, e.g. "VI"
    chapter_title: str | None
    heading: str | None                       # centred sub-heading, e.g. "Of offences affecting life"
    text: str = Field(min_length=20)
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    act_refs: list[str]                       # other Acts cited in the margin, e.g. "45 of 1860"
    source: str                               # which source the PDF came from (provenance)

    @model_validator(mode="after")
    def _check_consistency(self) -> "SectionRecord":
        if self.id != f"{self.act}-{self.number}":
            raise ValueError(f"id {self.id!r} does not match act/number {self.act}-{self.number}")
        if self.page_end < self.page_start:
            raise ValueError(f"page_end {self.page_end} is before page_start {self.page_start}")
        return self


EVAL_ID_PATTERN = r"^(BNS|BNSS|BSA)-\d+$"


class EvalItem(BaseModel):
    """One gold evaluation question with human-verified expected section(s)."""

    model_config = ConfigDict(extra="forbid")

    id: str                                    # e.g. "q001"
    question: str = Field(min_length=10)
    qtype: Literal["topic", "scenario", "procedure", "evidence",
                   "trap_nonexistent", "out_of_scope", "old_to_new"]
    gold_sections: list[str]                   # acceptable section IDs, e.g. ["BNS-319", "BNS-318"]
    should_abstain: bool                       # True for traps / out-of-scope questions
    key_facts: list[str] = []                  # facts a correct answer must contain (filled in later)
    difficulty: Literal["easy", "medium", "hard"]
    origin: Literal["seed_assistant", "synthetic_llm", "handwritten_user"]
    status: Literal["unreviewed", "accepted", "rejected"] = "unreviewed"
    split: Literal["dev", "test"] | None = None
    notes: str = ""

    @model_validator(mode="after")
    def _check_labels(self) -> "EvalItem":
        import re
        if self.should_abstain and self.gold_sections:
            raise ValueError(f"{self.id}: abstain items must have no gold sections")
        if not self.should_abstain and not self.gold_sections:
            raise ValueError(f"{self.id}: answerable items need at least one gold section")
        for sid in self.gold_sections:
            if not re.match(EVAL_ID_PATTERN, sid):
                raise ValueError(f"{self.id}: bad section id {sid!r}")
        return self
