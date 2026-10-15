import json

from fastapi.testclient import TestClient
import pytest

from knowledge.schema import write_jsonl
from knowledge.unified_build import build_unified, split_text
from knowledge.unified_search import UnifiedSearch
from naming.catalog import Catalog, NameQuery
from rag.context_builder import ContextBuilder


@pytest.fixture
def unified_inputs(tmp_path, corpus):
    sources = tmp_path / "sources"
    write_jsonl(sources / "online.jsonl", corpus.records)
    curated = tmp_path / "curated"
    # Deliberately duplicate content on two pages: both citations must survive.
    write_jsonl(
        curated / "bangaru_nanelu/quality_chunks.jsonl",
        [
            {
                "chunk_id": f"old-{n}",
                "unit_id": f"page_{n:03d}",
                "text": "వెన్నెల చంద్రుని వెలుగు — dictionary fixture, not real source evidence.",
            }
            for n in (3, 4)
        ],
    )
    books = tmp_path / "books"
    books.mkdir()
    source = {
        "source_id": "fixture_book",
        "title": "Book fixture",
        "filename": "test.pdf",
        "sha256": "a" * 64,
        "pages": 2,
        "edition": "TEST ONLY",
        "reuse_status": "TEST ONLY",
    }
    (books / "source_manifest.json").write_text(
        json.dumps({"sources": [source], "fingerprint": "b" * 64})
    )
    write_jsonl(
        books / "page_records/fixture_book.jsonl",
        [
            {
                "source_id": "fixture_book",
                "pdf_page": n,
                "source_sha256": source["sha256"],
                "fingerprint": "b" * 64,
                "status": "completed",
                "ocr_text": "సంధి గురించిన పరీక్ష వాక్యము; grammar fixture only.",
                "quality_flags": ["reading_order_not_verified"],
            }
            for n in (1, 2)
        ],
    )
    write_jsonl(
        books / "review/page_review_notes.jsonl",
        [
            {
                "source_id": "fixture_book",
                "pdf_page": 2,
                "disposition": "historical_script_needs_review",
            }
        ],
    )
    return {"sources_dir": sources, "curated": curated, "books": books}


@pytest.fixture
def unified(tmp_path, unified_inputs):
    output = tmp_path / "unified"
    build_unified(output, **unified_inputs)
    return UnifiedSearch(output)


def test_all_sources_and_old_evidence_ids_survive(unified, corpus):
    assert {r.id for r in corpus.records} <= {r.id for r in unified.records}
    old = unified.find("వెన్నెల", 10, source_ids=["bangaru_nanelu"])
    assert len(old) == 1
    assert {e.pdf_page for e in old[0][0].evidence} == {3, 4}
    book = unified.find("సంధి", 5, source_ids=["fixture_book"])
    assert book and book[0][0].evidence[0].pdf_page == 1
    assert book[0][0].text_status == "ocr_unreviewed"
    assert not book[0][0].public_release_allowed
    assert all(not r.training_allowed for r in unified.records)
    assert unified.find("సంధి", reviewed_only=True) == []
    assert unified.find("వెన్నెల", source_ids=["absent"]) == []


def test_problem_pages_are_quarantined_not_returned(unified):
    assert unified.manifest["quarantined_items"] == 1
    assert not any(
        e.source_id == "fixture_book" and e.pdf_page == 2
        for r in unified.records
        for e in r.evidence
    )


def test_source_hash_failure_preserves_current(tmp_path, unified_inputs):
    root = tmp_path / "unified"
    build_unified(root, **unified_inputs)
    before = (root / "CURRENT").read_text()
    source = unified_inputs["books"] / "page_records/fixture_book.jsonl"
    source.write_text(source.read_text().replace('"' + "a" * 64 + '"', '"wrong"'))
    with pytest.raises(ValueError, match="provenance"):
        build_unified(root, **unified_inputs)
    assert (root / "CURRENT").read_text() == before


def test_missing_book_inputs_cannot_silently_shrink_corpus(tmp_path, unified_inputs):
    root = tmp_path / "unified"
    build_unified(root, **unified_inputs)
    before = (root / "CURRENT").read_text()
    incomplete = {**unified_inputs, "books": None}
    with pytest.raises(ValueError, match="would remove sources"):
        build_unified(root, **incomplete)
    assert (root / "CURRENT").read_text() == before


@pytest.mark.parametrize("filename", ["records.jsonl", "word_vectors.npz"])
def test_tampering_is_detected(tmp_path, unified_inputs, filename):
    root = tmp_path / "unified"
    manifest = build_unified(root, **unified_inputs)
    path = root / "versions" / manifest["version"] / filename
    if filename.endswith("jsonl"):
        path.write_text(path.read_text().replace("grammar fixture", "altered fixture"))
    else:
        path.write_bytes(path.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="fingerprint"):
        UnifiedSearch(root)


def test_chunk_offsets_and_overlap_preserve_normalized_text():
    text = " ".join(["తెలుగు సంధి పదములు"] * 100)
    chunks = list(split_text(text, size=120, overlap=20))
    assert len(chunks) > 1
    assert chunks[-1][2] == len(text)
    for piece, start, end in chunks:
        assert piece == text[start:end].strip()
        assert len(piece) <= 120
    assert all(b[1] <= a[2] for a, b in zip(chunks, chunks[1:]))


def test_approved_catalog_stays_compatible(unified, catalog, tmp_path):
    path = tmp_path / "names.jsonl"
    write_jsonl(path, [n.model_dump() for n in catalog.names])
    updated = Catalog(path, unified)
    assert updated.version == catalog.version
    assert updated.knowledge.version != catalog.knowledge.version
    assert [r["name_en"] for r in updated.recommend(NameQuery(query="moonlight"))] == [
        "Vennela"
    ]
    assert updated.recommend(NameQuery(query="ocean")) == []


def test_api_uses_one_version_and_exposes_source_pages(
    unified, catalog, tmp_path, store, monkeypatch
):
    from api import main

    path = tmp_path / "names.jsonl"
    write_jsonl(path, [n.model_dump() for n in catalog.names])
    updated = Catalog(path, unified)
    main.app.dependency_overrides.update(
        {
            main.get_knowledge: lambda: unified,
            main.get_retriever: lambda: unified,
            main.get_catalog: lambda: updated,
            main.get_feedback: lambda: store,
        }
    )
    monkeypatch.setattr(main, "get_catalog", lambda: updated)
    monkeypatch.setattr(main, "get_feedback", lambda: store)
    monkeypatch.setattr(
        main.Generator, "generate", lambda self, query, context: "Test answer [1]"
    )
    try:
        with TestClient(main.app) as client:
            ready = client.get("/ready").json()
            assert ready["knowledge_version"] == unified.version
            assert ready["public_launch_ready"] is False
            assert client.get("/knowledge").json()["records"] == len(unified.records)
            response = client.post(
                "/search", json={"query": "సంధి", "source_ids": ["fixture_book"]}
            )
            assert response.status_code == 200
            hit = response.json()["results"][0]
            assert hit["metadata"]["evidence"][0]["pdf_page"] == 1
            assert hit["metadata"]["knowledge_version"] == unified.version
            detail = client.get(f"/knowledge/records/{hit['chunk_id']}").json()
            assert detail["record"]["text_status"] == "ocr_unreviewed"
            assert client.get("/knowledge/records/missing").status_code == 404
            names = client.post("/names", json={"query": "moonlight"}).json()
            assert names["knowledge_version"] == unified.version
            assert names["results"][0]["name_en"] == "Vennela"
            answer = client.post(
                "/ask", json={"query": "సంధి", "source_ids": ["fixture_book"]}
            ).json()
            assert answer["warnings"]
            assert "PDF page 1" in answer["context_preview"]
    finally:
        main.app.dependency_overrides.clear()


def test_context_preserves_each_selected_source_label(unified):
    retrieved = unified.retrieve("వెన్నెల", 5)
    context = ContextBuilder().build(retrieved, max_chars=1500)
    assert len(context) <= 1500
    for number in range(1, len(retrieved["ids"][0]) + 1):
        assert f"[{number}]" in context
