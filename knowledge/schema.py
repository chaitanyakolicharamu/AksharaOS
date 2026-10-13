import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


def normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    title: str
    adapter: Literal["wiktionary_te", "wiktionary_en", "wikidata", "local"]
    url: str
    license: str
    license_url: str
    attribution: str
    enabled: bool = False
    reuse_approved: bool = False
    category: str = ""
    notes: str = ""


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str
    url: str = Field(pattern=r"^https?://")
    revision: str = Field(min_length=1)
    license: str = Field(min_length=1)
    license_url: str = Field(pattern=r"^https?://")
    attribution: str = Field(min_length=1)
    retrieved_at: str = Field(min_length=1)


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = ""
    title: str = Field(min_length=1, max_length=250)
    text: str = Field(min_length=2, max_length=20000)
    kind: Literal["lexical", "passage"] = "lexical"
    language: Literal["te"] = "te"
    evidence: list[Evidence] = Field(min_length=1)
    # Dictionary evidence is NOT an endorsement of a word as a baby name.
    review_status: Literal["unreviewed", "reviewed"] = "unreviewed"

    @field_validator("title", "text")
    @classmethod
    def clean_text(cls, value):
        value = normalize(value)
        if "\ufffd" in value or any(x in value for x in ("à°", "à±", "Ã", "Â")):
            raise ValueError("corrupt Unicode or mojibake")
        if any(unicodedata.category(c) == "Cc" for c in value):
            raise ValueError("control characters")
        return value

    @field_validator("title")
    @classmethod
    def telugu_title(cls, value):
        if not re.search(r"[\u0c05-\u0c39\u0c58-\u0c61]", value):
            raise ValueError("title must contain Telugu letters")
        return value

    def canonicalize(self):
        self.id = digest([self.language, self.kind, self.title, self.text])[:24]
        return self


def load_sources(path=Path("configs/sources.yaml")) -> dict[str, Source]:
    rows = yaml.safe_load(Path(path).read_text(encoding="utf-8"))["sources"]
    sources = [Source(**row) for row in rows]
    if len({s.id for s in sources}) != len(sources):
        raise ValueError("duplicate source IDs")
    return {s.id: s for s in sources}


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        for row in rows:
            if isinstance(row, BaseModel):
                row = row.model_dump()
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(path)
