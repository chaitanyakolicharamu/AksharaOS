import json
from types import SimpleNamespace

import pytest

from naming.catalog import Catalog, NameQuery
from naming.train import preference_pairs, promote, train


def cast_vote(
    store, token, impression, candidate, value=1, consent=True, reason="preference"
):
    return store.vote(token, impression, candidate, value, reason, consent)


def test_feedback_ownership_consent_moderation_and_withdrawal(store, catalog):
    query = NameQuery(gender="girl")
    candidates = catalog.recommend(query)
    impression = store.record_impression("owner", query, candidates, catalog)
    a, b = candidates[0]["candidate_id"], candidates[1]["candidate_id"]
    with pytest.raises(ValueError, match="Unknown"):
        cast_vote(store, "other", impression, a)
    with pytest.raises(ValueError, match="Unknown"):
        cast_vote(store, "owner", impression, "invented-candidate")
    good = cast_vote(store, "owner", impression, a)
    bad = cast_vote(store, "owner", impression, b, -1, False)
    assert not store.training_rows(catalog.version, catalog.knowledge.version)
    store.moderate(good, "approved", "tester")
    store.moderate(bad, "approved", "tester")
    assert len(store.training_rows(catalog.version, catalog.knowledge.version)) == 1
    # Repeat vote replaces the old one and invalidates its moderation.
    assert cast_vote(store, "owner", impression, a, -1) == good
    assert not store.training_rows(catalog.version, catalog.knowledge.version)
    store.moderate(good, "approved", "tester")
    cast_vote(store, "owner", impression, b, 1, True, "meaning_incorrect")
    store.moderate(bad, "approved", "tester")
    assert len(store.training_rows(catalog.version, catalog.knowledge.version)) == 1
    store.withdraw("owner")
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM votes").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM shown").fetchone()[0] == 0


def test_later_nonconsent_never_resurrects_older_vote(store, catalog):
    query = NameQuery()
    rows = catalog.recommend(query)
    for consent in [True, False]:
        impression = store.record_impression("owner", query, rows, catalog)
        vote = cast_vote(
            store, "owner", impression, rows[0]["candidate_id"], consent=consent
        )
        store.moderate(vote, "approved", "tester")
    assert not store.training_rows(catalog.version, catalog.knowledge.version)


def test_no_cross_request_pairs_or_single_vote_training(store, catalog, tmp_path):
    query = NameQuery()
    rows = catalog.recommend(query)
    for i, value in enumerate([1, -1]):
        impression = store.record_impression("owner", query, rows, catalog)
        vote = cast_vote(store, "owner", impression, rows[i]["candidate_id"], value)
        store.moderate(vote, "approved", "tester")
    assert not preference_pairs(
        store.training_rows(catalog.version, catalog.knowledge.version)
    )
    output = tmp_path / "model.json"
    with pytest.raises(ValueError, match="Not enough reviewed human feedback"):
        train(store, catalog.version, catalog.knowledge.version, output)
    assert not output.exists()


def test_api_feedback_flow_and_validation(api_client, store):
    for request in [
        {"query": " "},
        {"query": "word", "top_k": 0},
        {"query": "word", "top_k": 1000},
    ]:
        assert api_client.post("/search", json=request).status_code == 422
    response = api_client.post(
        "/names", json={"gender": "girl", "starts_with": "V", "pure_telugu": True}
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 1 and body["results"][0]["name_te"] == "వెన్నెల"
    assert "features" not in body["results"][0]
    vote = {
        "impression_id": body["impression_id"],
        "candidate_id": body["results"][0]["candidate_id"],
        "vote": "like",
    }
    result = api_client.post("/feedback", json=vote)
    assert result.status_code == 200 and not result.json()["training_consent"]
    assert (
        api_client.post("/feedback", json={**vote, "features": [1000]}).status_code
        == 422
    )
    assert api_client.delete("/feedback").status_code == 200
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM votes").fetchone()[0] == 0
    assert api_client.post("/feedback", json=vote).status_code == 400


def test_ask_preserves_definition_and_uses_reviewed_name_route(api_client):
    result = api_client.post("/ask", json={"query": "వెన్నెల"}).json()
    assert "moonlight" in result["answer"]
    result = api_client.post(
        "/ask", json={"query": "అచ్చతెలుగు అమ్మాయిల పేర్లు"}
    ).json()
    assert result["mode"] == "name"
    assert result["results"] and all(
        row["origin"] == "telugu" for row in result["results"]
    )


def test_catalog_gates_and_hard_filters(catalog, corpus, tmp_path):
    assert Catalog(tmp_path / "missing.jsonl", corpus).recommend(NameQuery()) == []
    catalog.weights = [1000, -2000, -3000, 9999]
    assert [
        r["name_te"]
        for r in catalog.recommend(NameQuery(gender="girl", pure_telugu=True))
    ] == ["వెన్నెల"]
    assert catalog.recommend(NameQuery(gender="boy", starts_with="V")) == []
    bad = catalog.names[0].model_dump()
    bad["evidence_ids"] = ["invented"]
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown evidence"):
        Catalog(path, corpus)
    model = tmp_path / "unapproved.json"
    model.write_text(json.dumps({"promoted": False}), encoding="utf-8")
    with pytest.raises(ValueError, match="unapproved"):
        Catalog(tmp_path / "missing.jsonl", corpus, model)


def test_rate_limit_and_pruning(store, catalog):
    query = NameQuery()
    candidates = catalog.recommend(query)
    for _ in range(60):
        store.record_impression("one-browser", query, candidates, catalog)
    with pytest.raises(ValueError, match="Session limit"):
        store.record_impression("one-browser", query, candidates, catalog)
    with store.connect() as db:
        db.execute("UPDATE impressions SET created_at=0")
    assert store.prune() == 60


def test_pairwise_training_holdout_and_explicit_promotion(store, tmp_path):
    # Synthetic records exist only in this isolated test DB. This checks the
    # algorithm and gates, NOT real-world name quality or measured user preferences.
    fake = SimpleNamespace(
        version="test-catalog",
        knowledge=SimpleNamespace(version="test-kb"),
        model_version="baseline-v1",
    )
    candidates = [
        {"candidate_id": "long-name", "features": [0, 0.1, 1, 0.2]},
        {"candidate_id": "short-name", "features": [0, 0.5, 1, 0.2]},
    ]
    for user in range(12):
        for group in range(12):
            token = f"test-user-{user}"
            impression = store.record_impression(
                token, NameQuery(query=f"test-context-{group}"), candidates, fake
            )
            for candidate, value in [("long-name", 1), ("short-name", -1)]:
                vote = cast_vote(store, token, impression, candidate, value)
                store.moderate(vote, "approved", "TEST FIXTURE")
    path = tmp_path / "candidate.json"
    model = train(store, fake.version, fake.knowledge.version, path)
    assert model["pairs"] == 144
    assert model["evaluation"]["train_query_groups"] == 9
    assert model["evaluation"]["validation_query_groups"] == 3
    assert model["evaluation"]["passed"]
    assert not model["promoted"]
    active = tmp_path / "active.json"
    promote(path, active)
    assert json.loads(active.read_text())["promoted"]
    model["evaluation"]["passed"] = False
    path.write_text(json.dumps(model), encoding="utf-8")
    with pytest.raises(ValueError, match="failed evaluation"):
        promote(path, active)
