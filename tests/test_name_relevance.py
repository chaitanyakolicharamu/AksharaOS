import json

import pytest

from knowledge.schema import digest, write_jsonl
from naming.catalog import BASELINE_WEIGHTS, FEATURE_NAMES, Catalog, NameQuery


def test_reviewed_meaning_is_searchable_without_a_matching_source_gloss(
    catalog, corpus, tmp_path
):
    rows = [n.model_dump() for n in catalog.names]
    rows[0]["meaning"] = "Lunar radiance"
    path = tmp_path / "reviewed.jsonl"
    write_jsonl(path, rows)
    candidate = Catalog(path, corpus)
    assert [r["name_en"] for r in candidate.recommend(NameQuery(query="radiance"))] == [
        "Vennela"
    ]


@pytest.mark.parametrize("query", ["ocean", "asdfzzxq", "ringworm"])
def test_unsupported_topic_cannot_fall_back_to_popular_names(query, catalog):
    assert catalog.recommend(NameQuery(query=query)) == []


def test_matching_topic_does_not_include_zero_relevance_names(catalog):
    rows = catalog.recommend(NameQuery(query="moonlight"))
    assert [r["name_en"] for r in rows] == ["Vennela"]
    assert len(catalog.recommend(NameQuery())) == 3


def test_prior_scoring_ranker_cannot_load_with_reviewed_meaning_features(
    catalog, corpus, tmp_path
):
    path = tmp_path / "names.jsonl"
    write_jsonl(path, catalog.names)
    model = tmp_path / "old-model.json"
    model.write_text(
        json.dumps(
            {
                "feature_names": FEATURE_NAMES,
                "weights": BASELINE_WEIGHTS,
                "catalog_version": digest([n.model_dump() for n in catalog.names])[:20],
                "knowledge_version": corpus.version,
                "promoted": True,
                "evaluation": {"passed": True},
                "version": "old-source-only-model",
            }
        )
    )
    with pytest.raises(ValueError, match="incompatible"):
        Catalog(path, corpus, model)


def test_name_requests_preserve_theme_and_generic_filters(api_client):
    generic = api_client.post(
        "/ask", json={"query": "Please suggest pure Telugu girl names"}
    ).json()
    assert [r["name_en"] for r in generic["results"]] == ["Vennela"]
    themed = api_client.post(
        "/ask", json={"query": "Give me girl names meaning moonlight"}
    ).json()
    assert [r["name_en"] for r in themed["results"]] == ["Vennela"]
    missing = api_client.post(
        "/ask", json={"query": "Give me girl names meaning ocean"}
    ).json()
    assert missing["status"] == "no_reviewed_matches"
