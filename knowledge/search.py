import json
from pathlib import Path
import re

import numpy as np
from scipy.sparse import load_npz
from sklearn.feature_extraction.text import TfidfVectorizer

from knowledge.schema import Record, digest, normalize
from rag.query_router import QueryRouter


def load_index(folder, count, prefix=""):
    params = json.loads(
        (folder / f"{prefix}vectorizer.json").read_text(encoding="utf-8")
    )
    params["options"]["ngram_range"] = tuple(params["options"]["ngram_range"])
    vectorizer = TfidfVectorizer(**params["options"], vocabulary=params["vocabulary"])
    vectorizer.idf_ = np.asarray(params["idf"])
    vectors = load_npz(folder / f"{prefix}vectors.npz")
    if vectors.shape != (count, len(params["idf"])):
        raise ValueError("Knowledge index dimensions do not match records")
    return vectorizer, vectors


class KnowledgeSearch:
    def __init__(self, root=Path("data/knowledge/index")):
        root = Path(root)
        version = (root / "CURRENT").read_text(encoding="utf-8").strip()
        if not re.fullmatch(r"[a-f0-9]{20}", version):
            raise ValueError("Invalid knowledge version")
        folder = root / "versions" / version
        self.manifest = json.loads(
            (folder / "manifest.json").read_text(encoding="utf-8")
        )
        self.records = [
            Record.model_validate_json(line)
            for line in (folder / "records.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        if (
            digest([r.model_dump() for r in self.records])
            != self.manifest["corpus_sha256"]
        ):
            raise ValueError("Knowledge corpus fingerprint mismatch; rebuild the index")
        self.vectorizer, self.vectors = load_index(folder, len(self.records))
        self.word_index = (
            load_index(folder, len(self.records), "word_")
            if self.manifest["schema_version"] >= 2
            else None
        )
        self.version = version

    def find(self, query, top_k=5):
        query = normalize(query)
        if not query or not 1 <= top_k <= 50:
            raise ValueError("Nonempty query and top_k 1..50 required")
        vector = self.vectorizer.transform([query])
        scores = (self.vectors @ vector.T).toarray().ravel()
        if self.word_index:
            words, word_vectors = self.word_index
            word_scores = (word_vectors @ words.transform([query]).T).toarray().ravel()
            scores = 0.25 * scores + 0.75 * word_scores
        # An exact lemma lookup should reliably precede fuzzy text matches.
        exact = np.asarray(
            [normalize(r.title).casefold() == query.casefold() for r in self.records]
        )
        order = np.argsort(-(scores + exact.astype(float)), kind="stable")
        return [
            (self.records[i], float(scores[i]))
            for i in order[:top_k]
            if scores[i] >= 0.10 or exact[i]
        ]

    def retrieve(self, query, top_k=5):
        found = self.find(query, top_k)
        return {
            "mode": QueryRouter().detect_mode(query),
            "documents": [[f"{r.title}: {r.text}" for r, _ in found]],
            "ids": [[r.id for r, _ in found]],
            "scores": [[score for _, score in found]],
            "metadatas": [
                [
                    {
                        "title": r.title,
                        "knowledge_version": self.version,
                        "kind": r.kind,
                        "review_status": r.review_status,
                        "evidence": [e.model_dump() for e in r.evidence],
                    }
                    for r, _ in found
                ]
            ],
        }
