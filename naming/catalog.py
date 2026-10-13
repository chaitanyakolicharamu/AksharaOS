import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from knowledge.schema import digest, normalize, Record

FEATURE_NAMES = ["relevance", "brevity", "established", "source_diversity"]
BASELINE_WEIGHTS = [1.0, 0.15, 0.15, 0.10]


class Name(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name_te: str = Field(min_length=1, max_length=80)
    name_en: str = Field(min_length=1, max_length=100)
    meaning: str = Field(min_length=2, max_length=1000)
    gender: Literal["girl", "boy", "unisex"]
    origin: Literal["telugu", "sanskrit", "other", "unknown"] = "unknown"
    status: Literal["established", "coined"]
    evidence_ids: list[str] = Field(min_length=1)
    reviewed_by: str = Field(min_length=1)
    reviewed_at: str = Field(min_length=10)

    @field_validator("name_te")
    @classmethod
    def valid_telugu(cls, value):
        return Record.telugu_title(Record.clean_text(value))

    @property
    def id(self):
        return digest([normalize(self.name_te), normalize(self.meaning)])[:24]


class NameQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(default="", max_length=500)
    gender: Literal["girl", "boy", "unisex"] | None = None
    starts_with: str = Field(default="", max_length=30)
    pure_telugu: bool = False
    top_k: int = Field(default=10, ge=1, le=20)

    @field_validator("query", "starts_with")
    @classmethod
    def normalized(cls, value):
        return normalize(value)


class Catalog:
    def __init__(self, path: Path, knowledge, model_path: Path | None = None):
        self.knowledge = knowledge
        self.evidence = {r.id: r for r in knowledge.records}
        self.names = (
            [
                Name.model_validate_json(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            if path.exists()
            else []
        )
        if len({n.id for n in self.names}) != len(self.names):
            raise ValueError("Duplicate reviewed names")
        for name in self.names:
            if any(key not in self.evidence for key in name.evidence_ids):
                raise ValueError(f"Unknown evidence for {name.name_te}")
        self.version = digest([n.model_dump() for n in self.names])[:20]
        self.weights = BASELINE_WEIGHTS
        self.model_version = "baseline-v1"
        if model_path:
            model = json.loads(model_path.read_text(encoding="utf-8"))
            if (
                model.get("feature_names") != FEATURE_NAMES
                or not model.get("promoted")
                or not model.get("evaluation", {}).get("passed")
                or model.get("catalog_version") != self.version
                or model.get("knowledge_version") != knowledge.version
                or len(model.get("weights", [])) != len(FEATURE_NAMES)
            ):
                raise ValueError(
                    "Ranker is unapproved, incompatible, or trained on another catalog/KB"
                )
            import math

            if not all(
                isinstance(w, (int, float)) and math.isfinite(w)
                for w in model["weights"]
            ):
                raise ValueError("Invalid ranker weights")
            self.weights = model["weights"]
            self.model_version = model["version"]

    def recommend(self, query: NameQuery):
        relevance = (
            {r.id: score for r, score in self.knowledge.find(query.query, 50)}
            if query.query
            else {}
        )
        ranked = []
        for name in self.names:
            if query.gender and name.gender not in {query.gender, "unisex"}:
                continue
            prefix = query.starts_with.casefold()
            if prefix and not any(
                normalize(s).casefold().startswith(prefix)
                for s in (name.name_te, name.name_en)
            ):
                continue
            if query.pure_telugu and name.origin != "telugu":
                continue
            # Keep facts and hard constraints outside the learned score.
            sources = sorted(
                {
                    ev.source_id
                    for key in name.evidence_ids
                    for ev in self.evidence[key].evidence
                }
            )
            features = [
                max((relevance.get(key, 0) for key in name.evidence_ids), default=0),
                1.0 / max(len(name.name_en), 1),
                float(name.status == "established"),
                min(len(sources), 5) / 5,
            ]
            score = sum(x * w for x, w in zip(features, self.weights))
            ranked.append(
                {
                    "candidate_id": name.id,
                    **name.model_dump(),
                    "score": score,
                    "features": features,
                    "sources": [
                        ev.model_dump()
                        for key in name.evidence_ids
                        for ev in self.evidence[key].evidence
                    ],
                }
            )
        ranked.sort(key=lambda r: (-r["score"], r["candidate_id"]))
        # One spelling per response, even when the catalog contains different senses.
        result, seen = [], set()
        for row in ranked:
            if row["name_te"] not in seen:
                result.append(row)
                seen.add(row["name_te"])
            if len(result) == query.top_k:
                break
        return result
