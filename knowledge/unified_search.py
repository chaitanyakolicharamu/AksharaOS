"""One search interface for dictionary, book, grammar and candidate evidence."""

import hashlib
import json
from pathlib import Path
import re

import numpy as np

from knowledge.schema import digest, normalize
from knowledge.search import load_index
from knowledge.unified_schema import UnifiedRecord
from rag.query_router import QueryRouter


class UnifiedSearch:
    def __init__(self, root=Path("data/knowledge/unified")):
        root = Path(root)
        self.version = (root / "CURRENT").read_text().strip()
        if not re.fullmatch(r"[a-f0-9]{20}", self.version):
            raise ValueError("Invalid unified knowledge version")
        folder = root / "versions" / self.version
        self.manifest = json.loads((folder / "manifest.json").read_text())
        if (
            self.manifest["schema_version"] != "unified-v1"
            or self.manifest["version"] != self.version
        ):
            raise ValueError("Unsupported or inconsistent unified manifest")
        self.records = [
            UnifiedRecord.model_validate_json(line)
            for line in (folder / "records.jsonl").read_text().splitlines()
            if line.strip()
        ]
        if len({r.id for r in self.records}) != len(self.records):
            raise ValueError("Duplicate unified record IDs")
        if (
            len(self.records) != self.manifest["records"]
            or digest([r.model_dump() for r in self.records])
            != self.manifest["corpus_sha256"]
        ):
            raise ValueError("Unified corpus fingerprint mismatch")
        expected = {
            "vectors.npz",
            "vectorizer.json",
            "word_vectors.npz",
            "word_vectorizer.json",
        }
        if set(self.manifest.get("index_sha256", {})) != expected:
            raise ValueError("Incomplete index fingerprint manifest")
        for filename, checksum in self.manifest["index_sha256"].items():
            if hashlib.sha256((folder / filename).read_bytes()).hexdigest() != checksum:
                raise ValueError("Unified search index fingerprint mismatch")
        self.vectorizer, self.vectors = load_index(folder, len(self.records))
        self.word_vectorizer, self.word_vectors = load_index(
            folder, len(self.records), "word_"
        )
        self.by_id = {r.id: r for r in self.records}

    def find(self, query, top_k=5, *, source_ids=None, reviewed_only=False):
        query = normalize(query)
        if not query or not 1 <= top_k <= 50:
            raise ValueError("Nonempty query and top_k 1..50 required")
        chars = (self.vectors @ self.vectorizer.transform([query]).T).toarray().ravel()
        words = (
            (self.word_vectors @ self.word_vectorizer.transform([query]).T)
            .toarray()
            .ravel()
        )
        scores = 0.25 * chars + 0.75 * words
        exact = np.asarray(
            [r.title.casefold() == query.casefold() for r in self.records]
        )
        order = np.argsort(-(scores + exact.astype(float)), kind="stable")
        found = []
        requested = set(source_ids or [])
        for i in order:
            row = self.records[i]
            if scores[i] < 0.10 and not exact[i]:
                continue
            if reviewed_only and row.review_status != "reviewed":
                continue
            if requested and not requested.intersection(
                e.source_id for e in row.evidence
            ):
                continue
            found.append((row, float(scores[i])))
            if len(found) == top_k:
                break
        return found

    def retrieve(self, query, top_k=5, *, source_ids=None, reviewed_only=False):
        found = self.find(
            query, top_k, source_ids=source_ids, reviewed_only=reviewed_only
        )
        return {
            "mode": QueryRouter().detect_mode(query),
            "documents": [
                [
                    f"{r.title}: {r.text}" if r.title != r.text[:100] else r.text
                    for r, _ in found
                ]
            ],
            "ids": [[r.id for r, _ in found]],
            "scores": [[score for _, score in found]],
            "metadatas": [
                [
                    {
                        "title": r.title,
                        "knowledge_version": self.version,
                        "kind": r.kind,
                        "language": r.language,
                        "script": r.script,
                        "etymological_origin": r.etymological_origin,
                        "review_status": r.review_status,
                        "text_status": r.text_status,
                        "quality_flags": r.quality_flags,
                        "public_release_allowed": r.public_release_allowed,
                        "training_allowed": r.training_allowed,
                        "evidence": [
                            e.model_dump(exclude_none=True) for e in r.evidence
                        ],
                    }
                    for r, _ in found
                ]
            ],
        }
