"""Canonical records for one knowledge base, with honest source/review metadata."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from knowledge.schema import normalize


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    source_title: str = ""
    url: str | None = None
    revision: str = ""
    license: str = "REVIEW-REQUIRED"
    license_url: str | None = None
    attribution: str = ""
    retrieved_at: str = ""
    filename: str | None = None
    source_sha256: str | None = None
    pdf_page: int | None = Field(default=None, ge=1)
    printed_page: str | None = None
    original_record_id: str = ""
    extraction_sha256: str | None = None
    normalized_page_start: int | None = Field(default=None, ge=0)
    normalized_page_end: int | None = Field(default=None, ge=0)
    locator: str = ""

    @model_validator(mode="after")
    def attributable(self):
        if not self.url and not self.locator:
            raise ValueError("Citation needs a source URL or local source locator")
        if self.url and not self.url.startswith(("https://", "http://")):
            raise ValueError("Citation URL must use HTTP(S)")
        return self


class UnifiedRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str = Field(min_length=1)
    text: str = Field(min_length=2)
    kind: Literal[
        "lexical", "passage", "grammar", "deity_candidate", "naming_candidate"
    ]
    language: str = "te"
    script: str = "Telugu"
    etymological_origin: str | None = None
    evidence: list[Citation] = Field(min_length=1)
    review_status: Literal["unreviewed", "reviewed"] = "unreviewed"
    text_status: Literal["source_text", "ocr_unreviewed", "assistant_transcription"]
    quality_flags: list[str] = Field(default_factory=list)
    structured_data: dict = Field(default_factory=dict)
    public_release_allowed: bool = False
    # Retrieval ingestion never confers permission to train a naming model.
    training_allowed: Literal[False] = False

    @model_validator(mode="after")
    def normalized_text(self):
        if self.text != normalize(self.text):
            raise ValueError("Canonical text must be NFC and whitespace normalized")
        return self
