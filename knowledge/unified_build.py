"""Build one private, versioned corpus from every available extracted source.

Original inputs and the old indexes are never modified. Book OCR is searchable
as unreviewed evidence, not silently promoted to a verified name or training row.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import unicodedata

from knowledge.build import collect, fit_index, VECTORIZER_OPTIONS, WORD_OPTIONS
from knowledge.schema import digest, load_sources, normalize, write_jsonl
from knowledge.unified_schema import Citation, UnifiedRecord

DEFAULT_ROOT = Path("data/knowledge/unified")
DEFAULT_INPUTS = Path("data/private/knowledge_inputs")
BUILD_SCHEMA = "unified-v1"
CHUNK_SIZE = 1200
OVERLAP = 120
# Rare headwords and English glosses must survive when large Telugu books are
# added. A frequency cap otherwise removes exactly these useful search terms.
UNIFIED_WORD_OPTIONS = {**WORD_OPTIONS, "max_features": None}
LEGACY_SOURCES = {
    "bangaru_nanelu": ("Bangaru Nanelu", "pure_telugu_reference", "bangaru_nanelu.pdf"),
    "telugu_paryaya_nighantuvu": (
        "Telugu Paryaya Nighantuvu",
        "synonym_dictionary",
        "telugu_paryaya.pdf",
    ),
    "telugu_english_dictionary": (
        "Telugu–English dictionary",
        "meaning_dictionary",
        "telugu_english_dictionary.pdf",
    ),
}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_jsonl(path):
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                yield json.loads(line)
            except ValueError as exc:
                raise ValueError(f"Invalid JSON: {path.name} line {n}") from exc


def clean_ocr(text):
    # Preserve Telugu vowel marks, virama and joiners; never guess missing letters.
    text = "".join(" " if unicodedata.category(c) == "Cc" else c for c in text)
    return normalize(text)


def split_text(text, size=CHUNK_SIZE, overlap=OVERLAP):
    """Word-boundary chunks with offsets in the normalized page, never across pages."""
    if not 0 <= overlap < size or size < 50:
        raise ValueError("Invalid chunk size/overlap")
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start + size // 2, end)
            if boundary > start:
                end = boundary
        value = text[start:end].strip()
        if value:
            yield value, start, end
        if end == len(text):
            break
        candidate = max(start + 1, end - overlap)
        boundary = text.find(" ", candidate, end)
        start = boundary + 1 if boundary >= 0 else end


def add_record(records, record):
    previous = records.get(record.id)
    if previous is None:
        records[record.id] = record
        return
    if (previous.text, previous.title, previous.kind) != (
        record.text,
        record.title,
        record.kind,
    ):
        raise ValueError("Conflicting canonical record IDs")
    citations = {digest(e.model_dump()): e for e in previous.evidence + record.evidence}
    previous.evidence = [citations[k] for k in sorted(citations)]
    previous.quality_flags = sorted(set(previous.quality_flags + record.quality_flags))
    previous.public_release_allowed &= record.public_release_allowed


def add_passage(
    records,
    text,
    citation,
    *,
    flags,
    structured=None,
    kind="passage",
    title=None,
    text_status="ocr_unreviewed",
    language="te",
):
    title = title or text[:100]
    record = UnifiedRecord(
        id=digest([BUILD_SCHEMA, kind, language, title, text])[:24],
        title=title,
        text=text,
        kind=kind,
        language=language,
        evidence=[citation],
        text_status=text_status,
        quality_flags=sorted(set(flags)),
        structured_data=structured or {},
    )
    add_record(records, record)


def import_online(records, inventory, sources_dir, config):
    sources = load_sources(config)
    rows, rejected = collect(Path(sources_dir).glob("*.jsonl"), sources)
    if rejected or not rows:
        raise ValueError(f"Online source validation failed: {rejected[:3]}")
    for row in rows:
        # Preserve all original record IDs: approved name evidence remains valid.
        payload = row.model_dump()
        payload["evidence"] = [
            {**ev.model_dump(), "source_title": sources[ev.source_id].title}
            for ev in row.evidence
        ]
        add_record(
            records,
            UnifiedRecord(
                **payload, text_status="source_text", public_release_allowed=True
            ),
        )
    for key in sorted({ev.source_id for r in rows for ev in r.evidence}):
        source = sources[key]
        inventory[key] = {
            "source_id": key,
            "title": source.title,
            "role": "lexical_reference",
            "status": "included",
            "reuse_status": source.license,
        }


def import_legacy(records, inventory, quarantine, curated):
    for source_id, (title, role, filename) in LEGACY_SOURCES.items():
        path = Path(curated) / source_id / "quality_chunks.jsonl"
        inventory[source_id] = {
            "source_id": source_id,
            "title": title,
            "role": role,
            "status": "included" if path.exists() else "awaiting_extraction",
            "reuse_status": "not established from supplied copy",
        }
        if not path.exists():
            continue
        extraction_hash = sha256(path)
        for row in read_jsonl(path):
            text = clean_ocr(row["text"])
            page = re.search(r"page_(\d+)", row.get("unit_id", row["chunk_id"]))
            if not page:
                raise ValueError(f"No source page for {row['chunk_id']}")
            if len(text) < 20 or "\ufffd" in text:
                quarantine.append(
                    {
                        "source_id": source_id,
                        "record_id": row["chunk_id"],
                        "reason": "short_or_corrupt_text",
                    }
                )
                continue
            citation = Citation(
                source_id=source_id,
                source_title=title,
                filename=filename,
                pdf_page=int(page[1]),
                original_record_id=row["chunk_id"],
                extraction_sha256=extraction_hash,
                locator=f"book:{source_id}#pdf-page={int(page[1])}",
                attribution=f"{title}; supplied scan; edition attribution pending",
            )
            add_passage(
                records,
                text,
                citation,
                flags=["legacy_ocr_requires_review"],
                structured={"source_role": role},
            )


def import_books(records, inventory, quarantine, root):
    root = Path(root)
    manifest = json.loads((root / "source_manifest.json").read_text())
    source_map = {s["source_id"]: s for s in manifest["sources"]}
    notes_file = root / "review/page_review_notes.jsonl"
    notes = (
        {(r["source_id"], r["pdf_page"]): r for r in read_jsonl(notes_file)}
        if notes_file.exists()
        else {}
    )
    seen_pages = set()
    for source_id, source in source_map.items():
        inventory[source_id] = {
            "source_id": source_id,
            "title": source["title"],
            "role": "book_reference",
            "status": "included",
            "reuse_status": source["reuse_status"],
            "source_sha256": source["sha256"],
            "pages": source["pages"],
        }
        pages = list(read_jsonl(root / "page_records" / f"{source_id}.jsonl"))
        if sorted(p["pdf_page"] for p in pages) != list(range(1, source["pages"] + 1)):
            raise ValueError(f"Missing or repeated pages: {source_id}")
        for row in pages:
            page = row["pdf_page"]
            if (
                row["source_id"] != source_id
                or row["source_sha256"] != source["sha256"]
                or row["fingerprint"] != manifest["fingerprint"]
                or row["status"] != "completed"
            ):
                raise ValueError(f"Unverified OCR provenance: {source_id} page {page}")
            seen_pages.add((source_id, page))
            text = clean_ocr(row["ocr_text"])
            note = notes.get((source_id, page))
            if note or len(text) < 20 or "\ufffd" in text:
                quarantine.append(
                    {
                        "source_id": source_id,
                        "pdf_page": page,
                        "reason": (
                            note["disposition"] if note else "short_or_corrupt_text"
                        ),
                        "locator": f"book:{source_id}#pdf-page={page}",
                    }
                )
                continue
            flags = list(row.get("quality_flags", [])) + ["book_ocr_requires_review"]
            for number, (piece, start, end) in enumerate(split_text(text), 1):
                citation = Citation(
                    source_id=source_id,
                    source_title=source["title"],
                    filename=source["filename"],
                    source_sha256=source["sha256"],
                    extraction_sha256=manifest["fingerprint"],
                    normalized_page_start=start,
                    normalized_page_end=end,
                    pdf_page=page,
                    original_record_id=f"{source_id}:page:{page}:chunk:{number}",
                    locator=f"book:{source_id}#pdf-page={page}",
                    attribution=f"{source['title']}; {source['edition']}",
                )
                add_passage(
                    records,
                    piece,
                    citation,
                    flags=flags,
                )
    import_book_candidates(records, root, source_map)
    return len(seen_pages)


def import_book_candidates(records, root, source_map):
    for filename, kind in [
        ("grammar_transcriptions.jsonl", "grammar"),
        ("deity_association_candidates.jsonl", "deity_candidate"),
        ("naming_table_candidates.jsonl", "naming_candidate"),
    ]:
        path = root / "review" / filename
        if not path.exists():
            continue
        for row in read_jsonl(path):
            ev = row["evidence"]
            source = source_map[ev["source_id"]]
            if ev["source_sha256"] != source["sha256"]:
                raise ValueError("Candidate evidence source fingerprint mismatch")
            if kind == "grammar":
                text = row["text"]
                title = text
            elif kind == "deity_candidate":
                title = row["name_as_printed"]
                text = f"{title}: {row['source_fragment']}. {row['note']}"
            else:
                title = row["nakshatra_label_read_from_image"]
                sound = row.get("sound_cluster_transcription")
                text = (
                    f"{title}: {sound or 'Uncertain reading; no sound supplied'}. "
                    "Unvalidated naming-table transcription; pada mapping is not established."
                )
            citation = Citation(
                source_id=ev["source_id"],
                source_title=source["title"],
                filename=source["filename"],
                source_sha256=source["sha256"],
                pdf_page=ev["pdf_page"],
                printed_page=ev.get("printed_page"),
                original_record_id=row["record_id"],
                locator=f"book:{ev['source_id']}#pdf-page={ev['pdf_page']}",
                attribution=f"{source['title']}; {source['edition']}",
            )
            structured = {
                k: v
                for k, v in row.items()
                if k not in {"raw_page_ocr", "raw_row_ocr", "evidence"}
            }
            add_passage(
                records,
                normalize(text),
                citation,
                kind=kind,
                title=title,
                flags=["human_review_pending", "fact_validation_pending"],
                structured=structured,
                text_status="assistant_transcription",
            )


def import_research(records, inventory, quarantine, root):
    root = Path(root)
    manifest = json.loads((root / "manifest.json").read_text())
    sources = {
        s["source_id"]: s
        for s in json.loads((root / "source_catalog.json").read_text())
    }
    for filename, kind in [
        ("grammar_rule_excerpts.unreviewed.jsonl", "grammar"),
        ("deity_associations.unreviewed.jsonl", "deity_candidate"),
    ]:
        rel = f"data/{filename}"
        if sha256(root / rel) != manifest["sha256"][rel]:
            raise ValueError(f"Research input fingerprint mismatch: {filename}")
        for row in read_jsonl(root / rel):
            sid = row["source_id"]
            source = sources[sid]
            inventory[sid] = {
                "source_id": sid,
                "title": source["title"],
                "role": source["role"],
                "status": "included",
                "reuse_status": source["reuse_status"],
            }
            if "quarantin" in str(row.get("review_status", "")).lower():
                inventory[sid]["status"] = "quarantined"
                quarantine.append(
                    {
                        "source_id": sid,
                        "record_id": row["record_id"],
                        "reason": row["review_status"],
                    }
                )
                continue
            if kind == "grammar":
                text = row["source_text"]
                title = f"{row['section_te']} — {row['rule_number']}"
            else:
                title = row["observed_form"]
                text = (
                    f"{title}: observed in a hymn addressed to {row['deity_context']}. "
                    "Association candidate only; literal meaning and naming suitability unverified."
                )
            ev = Citation(
                source_id=sid,
                source_title=source["title"],
                url=row["source_url"],
                revision=row["source_revision"],
                license=row.get(
                    "transcription_license", row.get("license", "REVIEW-REQUIRED")
                ),
                license_url=row["license_url"],
                attribution=row["attribution"],
                retrieved_at=row["retrieved_at"],
                original_record_id=row["record_id"],
            )
            add_passage(
                records,
                normalize(text),
                ev,
                kind=kind,
                title=title,
                language=row["source_language"],
                text_status="source_text",
                flags=["human_review_pending", "fact_validation_pending"],
                structured=row,
            )


def build_unified(
    output=DEFAULT_ROOT,
    *,
    sources_dir=Path("data/knowledge/sources"),
    config=Path("configs/sources.yaml"),
    curated=Path("data/curated"),
    books=None,
    research=None,
    allow_source_removal=False,
):
    records, inventory, quarantine = {}, {}, []
    import_online(records, inventory, sources_dir, config)
    import_legacy(records, inventory, quarantine, curated)
    pages = import_books(records, inventory, quarantine, books) if books else 0
    if research:
        import_research(records, inventory, quarantine, research)
    ordered = [records[k] for k in sorted(records)]
    rows = [r.model_dump() for r in ordered]
    counts = Counter(ev.source_id for r in ordered for ev in r.evidence)
    for sid, source in inventory.items():
        source["citation_count"] = counts[sid]
        source["record_count"] = sum(
            any(e.source_id == sid for e in r.evidence) for r in ordered
        )
    inventory_rows = [inventory[k] for k in sorted(inventory)]
    output = Path(output)
    current = output / "CURRENT"
    if current.exists() and not allow_source_removal:
        previous_version = current.read_text().strip()
        if not re.fullmatch(r"[a-f0-9]{20}", previous_version):
            raise ValueError("Invalid current unified version")
        previous = json.loads(
            (output / "versions" / previous_version / "manifest.json").read_text()
        )
        missing = set(previous["source_evidence_counts"]) - set(counts)
        if missing:
            raise ValueError(
                f"Rebuild would remove sources {sorted(missing)}. Restore their inputs; CURRENT is unchanged. Intentional removal requires --allow-source-removal."
            )
    corpus_hash = digest(rows)
    config_hash = digest(
        [VECTORIZER_OPTIONS, UNIFIED_WORD_OPTIONS, CHUNK_SIZE, OVERLAP, BUILD_SCHEMA]
    )
    version = digest([corpus_hash, inventory_rows, quarantine, config_hash])[:20]
    manifest = {
        "version": version,
        "schema_version": BUILD_SCHEMA,
        "corpus_sha256": corpus_hash,
        "records": len(rows),
        "sources": inventory_rows,
        "included_source_count": len(counts),
        "source_evidence_counts": dict(sorted(counts.items())),
        "book_pages_processed": pages,
        "quarantined_items": len(quarantine),
        "text_status_counts": dict(Counter(r.text_status for r in ordered)),
        "kind_counts": dict(Counter(r.kind for r in ordered)),
        "reviewed_records": sum(r.review_status == "reviewed" for r in ordered),
        "retrieval": "word + character TF-IDF over one canonical corpus",
        "dense_embeddings_built": False,
        "model_fine_tuned": False,
        "training_allowed_records": 0,
        "public_launch_ready": False,
        "build_config_sha256": config_hash,
        "book_inputs_present": bool(books),
        "research_inputs_present": bool(research),
    }
    versions = output / "versions"
    versions.mkdir(parents=True, exist_ok=True)
    destination = versions / version
    if not destination.exists():
        staging = Path(tempfile.mkdtemp(prefix="unified-", dir=versions))
        try:
            docs = [f"{r.title} {r.title} {r.text}" for r in ordered]
            fit_index(docs, VECTORIZER_OPTIONS, staging)
            fit_index(docs, UNIFIED_WORD_OPTIONS, staging, "word_")
            write_jsonl(staging / "records.jsonl", rows)
            write_jsonl(staging / "quarantine.jsonl", quarantine)
            manifest["index_sha256"] = {
                name: sha256(staging / name)
                for name in [
                    "vectors.npz",
                    "vectorizer.json",
                    "word_vectors.npz",
                    "word_vectorizer.json",
                ]
            }
            (staging / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2)
            )
            staging.rename(destination)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
    else:
        saved = json.loads((destination / "manifest.json").read_text())
        saved_rows = list(read_jsonl(destination / "records.jsonl"))
        if saved["corpus_sha256"] != corpus_hash or digest(saved_rows) != corpus_hash:
            raise ValueError("Existing unified version fingerprint mismatch")
        expected_files = {
            "vectors.npz",
            "vectorizer.json",
            "word_vectors.npz",
            "word_vectorizer.json",
        }
        if set(saved.get("index_sha256", {})) != expected_files:
            raise ValueError("Incomplete existing index fingerprint manifest")
        for name, checksum in saved["index_sha256"].items():
            if sha256(destination / name) != checksum:
                raise ValueError("Existing unified index fingerprint mismatch")
        manifest = saved
    pointer = output / "CURRENT.tmp"
    pointer.write_text(version)
    pointer.replace(output / "CURRENT")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--sources", type=Path, default=Path("data/knowledge/sources"))
    parser.add_argument("--curated", type=Path, default=Path("data/curated"))
    parser.add_argument("--books", type=Path)
    parser.add_argument("--research", type=Path)
    parser.add_argument(
        "--allow-source-removal",
        action="store_true",
        help="Explicitly allow rebuilding without previously indexed sources",
    )
    args = parser.parse_args()
    books = args.books or (
        DEFAULT_INPUTS / "book_ocr" if (DEFAULT_INPUTS / "book_ocr").is_dir() else None
    )
    research = args.research or (
        DEFAULT_INPUTS / "research" if (DEFAULT_INPUTS / "research").is_dir() else None
    )
    result = build_unified(
        args.output,
        sources_dir=args.sources,
        curated=args.curated,
        books=books,
        research=research,
        allow_source_removal=args.allow_source_removal,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
