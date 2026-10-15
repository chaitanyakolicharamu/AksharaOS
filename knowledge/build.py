"""Validate sources, deduplicate evidence, and fit a versioned local TF-IDF index."""

import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import tempfile

import numpy as np
from scipy.sparse import save_npz
from sklearn.feature_extraction.text import TfidfVectorizer

from knowledge.schema import Record, digest, load_sources, write_jsonl

VECTORIZER_OPTIONS = dict(
    analyzer="char_wb",
    ngram_range=(2, 5),
    sublinear_tf=True,
    lowercase=True,
    max_features=100000,
)
WORD_OPTIONS = dict(
    analyzer="word",
    token_pattern=r"[a-zA-Z]+|[\u0c00-\u0c7f]+",
    ngram_range=(1, 2),
    sublinear_tf=True,
    lowercase=True,
    max_features=100000,
)


def fit_index(documents, options, folder, prefix=""):
    vectorizer = TfidfVectorizer(**options)
    vectors = vectorizer.fit_transform(documents).astype(np.float32)
    save_npz(folder / f"{prefix}vectors.npz", vectors)
    (folder / f"{prefix}vectorizer.json").write_text(
        json.dumps(
            {
                "vocabulary": {k: int(v) for k, v in vectorizer.vocabulary_.items()},
                "idf": vectorizer.idf_.tolist(),
                "options": options,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def collect(paths, sources):
    records = {}
    rejected = []
    for path in sorted(paths):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            try:
                record = Record.model_validate_json(line).canonicalize()
                for ev in record.evidence:
                    source = sources.get(ev.source_id)
                    if not source or not source.enabled or not source.reuse_approved:
                        raise ValueError("unknown, disabled, or unapproved source")
                    if (
                        ev.license != source.license
                        or ev.license_url != source.license_url
                    ):
                        raise ValueError("source license mismatch")
                if record.id in records:
                    current = records[record.id]
                    seen = {(e.source_id, e.url, e.revision) for e in current.evidence}
                    for ev in record.evidence:
                        key = (ev.source_id, ev.url, ev.revision)
                        if key not in seen:
                            current.evidence.append(ev)
                            seen.add(key)
                else:
                    records[record.id] = record
            except (ValueError, TypeError) as exc:
                rejected.append(
                    {"file": str(path), "line": number, "reason": str(exc)[:300]}
                )
    return sorted(records.values(), key=lambda r: r.id), rejected


def build(input_dir: Path, output_dir: Path, config=Path("configs/sources.yaml")):
    records, rejected = collect(input_dir.glob("*.jsonl"), load_sources(config))
    if not records:
        raise ValueError("No approved evidence records; current index is unchanged")
    if rejected:
        # Fail closed rather than quietly train on a partially invalid snapshot.
        raise ValueError(
            f"Rejected {len(rejected)} records. First errors: {rejected[:3]}"
        )
    rows = [r.model_dump() for r in records]
    corpus_hash = digest(rows)
    version = digest(
        [corpus_hash, VECTORIZER_OPTIONS, WORD_OPTIONS, "hybrid-tfidf-v2"]
    )[:20]
    counts = Counter(ev.source_id for r in records for ev in r.evidence)
    manifest = {
        "version": version,
        "corpus_sha256": corpus_hash,
        "records": len(records),
        "source_evidence_counts": dict(sorted(counts.items())),
        "unique_titles": len({r.title for r in records}),
        "training": "TF-IDF retrieval fitted on source text; no LLM or name-preference training",
        "schema_version": 2,
        "retrieval_weights": {"word": 0.75, "character": 0.25},
        "quality_rejected": len(rejected),
    }
    versions = output_dir / "versions"
    versions.mkdir(parents=True, exist_ok=True)
    destination = versions / version
    if not destination.exists():
        staging = Path(tempfile.mkdtemp(prefix="build-", dir=versions))
        try:
            # A bilingual entry places its Telugu lemma and English gloss in the same vector.
            documents = [f"{r.title} {r.title} {r.text}" for r in records]
            fit_index(documents, VECTORIZER_OPTIONS, staging)
            fit_index(documents, WORD_OPTIONS, staging, "word_")
            write_jsonl(staging / "records.jsonl", rows)
            write_jsonl(
                staging / "quality_chunks.jsonl",
                [
                    {
                        "chunk_id": r.id,
                        "text": f"{r.title}: {r.text}",
                        "document_id": "multisource",
                        "source_role": (
                            "meaning_dictionary"
                            if r.kind == "lexical"
                            else "literary_reference"
                        ),
                        "unit_type": r.kind,
                        "unit_id": r.id,
                        "language": "te",
                        "quality_score": 1,
                        "evidence": [e.model_dump() for e in r.evidence],
                    }
                    for r in records
                ],
            )
            # This is an unlabelled review queue, never positive training examples.
            write_jsonl(
                staging / "name_review_queue.jsonl",
                [
                    {
                        "name_te": title,
                        "evidence_ids": [r.id for r in records if r.title == title],
                        "review_status": "pending",
                        "suitable_as_name": None,
                        "gender": "unknown",
                        "origin": "unknown",
                        "meaning_review": None,
                    }
                    for title in sorted(
                        {r.title for r in records if r.kind == "lexical"}
                    )
                ],
            )
            (staging / "manifest.json").write_text(
                json.dumps(manifest, indent=2), encoding="utf-8"
            )
            staging.rename(destination)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
    pointer = output_dir / "CURRENT.tmp"
    pointer.write_text(version, encoding="utf-8")
    pointer.replace(output_dir / "CURRENT")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/knowledge/sources"))
    parser.add_argument("--output", type=Path, default=Path("data/knowledge/index"))
    parser.add_argument("--config", type=Path, default=Path("configs/sources.yaml"))
    args = parser.parse_args()
    print(json.dumps(build(args.input, args.output, args.config), indent=2))


if __name__ == "__main__":
    main()
