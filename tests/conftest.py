import json

import pytest

from feedback.store import FeedbackStore
from knowledge.build import build
from knowledge.schema import Evidence, Record, load_sources, write_jsonl
from knowledge.search import KnowledgeSearch
from naming.catalog import Catalog


@pytest.fixture
def corpus(tmp_path):
    source = load_sources()["te_wiktionary"]
    rows = []
    for title, text in [
        ("వెన్నెల", "చంద్రుని వెలుగు; moonlight"),
        ("సిరి", "సంపద; wealth prosperity"),
        ("కిరణము", "వెలుగు; ray of light"),
    ]:
        ev = Evidence(
            source_id=source.id,
            url="https://te.wiktionary.org/w/index.php?oldid=1",
            revision="1",
            license=source.license,
            license_url=source.license_url,
            attribution=source.attribution,
            retrieved_at="2026-10-13T00:00:00Z",
        )
        rows.append(Record(title=title, text=text, evidence=[ev]).canonicalize())
    inputs = tmp_path / "source"
    write_jsonl(inputs / "source.jsonl", rows)
    build(inputs, tmp_path / "index")
    return KnowledgeSearch(tmp_path / "index")


@pytest.fixture
def catalog(corpus, tmp_path):
    # Test-only labels. These fixtures must never enter production training.
    specs = [
        ("వెన్నెల", "Vennela", "girl", "telugu"),
        ("సిరి", "Siri", "girl", "unknown"),
        ("కిరణము", "Kiranamu", "boy", "sanskrit"),
    ]
    records = {r.title: r for r in corpus.records}
    rows = [
        {
            "name_te": te,
            "name_en": en,
            "meaning": records[te].text,
            "gender": gender,
            "origin": origin,
            "status": "established",
            "evidence_ids": [records[te].id],
            "reviewed_by": "TEST FIXTURE ONLY",
            "reviewed_at": "2026-10-13",
        }
        for te, en, gender, origin in specs
    ]
    path = tmp_path / "names.jsonl"
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8"
    )
    return Catalog(path, corpus)


@pytest.fixture
def store(tmp_path):
    return FeedbackStore(tmp_path / "feedback.sqlite3")


@pytest.fixture
def api_client(corpus, catalog, store, monkeypatch):
    from fastapi.testclient import TestClient
    from api import main

    main.app.dependency_overrides[main.get_retriever] = lambda: corpus
    main.app.dependency_overrides[main.get_knowledge] = lambda: corpus
    main.app.dependency_overrides[main.get_catalog] = lambda: catalog
    main.app.dependency_overrides[main.get_feedback] = lambda: store
    monkeypatch.setattr(main, "get_catalog", lambda: catalog)
    monkeypatch.setattr(main, "get_feedback", lambda: store)
    with TestClient(main.app) as client:
        yield client
    main.app.dependency_overrides.clear()
