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
