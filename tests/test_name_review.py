from copy import deepcopy
import json
from pathlib import Path

import pytest

from knowledge.schema import digest
from naming.catalog import Catalog, NameQuery
from naming.review import (
    compile_decisions,
    decision_template,
    prepare,
    render_report,
    write_candidate,
)


@pytest.fixture
def review_batch(corpus):
    # Synthetic review data, confined to the temporary test corpus.
    return prepare(
        [
            {
                "name_te": "వెన్నెల",
                "name_en": "Vennela",
                "meaning": "Moonlight",
                "gender": "girl",
                "origin": "telugu",
                "status": "established",
                "flags": ["test_flag"],
                "notes": "TEST FIXTURE ONLY",
            }
        ],
        corpus,
    )


def approved_document(batch):
    doc = decision_template(batch)
    doc.update(reviewer="TEST FIXTURE ONLY", reviewed_at="2026-10-13")
    doc["decisions"][0].update(
        decision="approve",
        meaning_checked=True,
        name_usage_checked=True,
        origin_checked=True,
        acknowledged_flags=["test_flag"],
    )
    return doc


def test_unreviewed_template_cannot_create_catalog(review_batch, corpus, tmp_path):
    output = tmp_path / "candidate"
    with pytest.raises(ValueError, match="No human-approved"):
        write_candidate(output, review_batch, decision_template(review_batch), corpus)
    assert not output.exists()


def test_compile_preserves_review_and_filters_unknown_origin(
    review_batch, corpus, tmp_path
):
    doc = approved_document(review_batch)
    doc["decisions"][0]["origin"] = "unknown"
    result = write_candidate(tmp_path / "candidate", review_batch, doc, corpus)
    assert result["activated"] is False
    catalog = Catalog(Path(result["catalog"]), corpus)
    assert catalog.recommend(NameQuery(pure_telugu=True)) == []
    assert catalog.recommend(NameQuery(gender="boy")) == []
    assert catalog.recommend(NameQuery(starts_with="S")) == []
    assert len(catalog.recommend(NameQuery(gender="girl", starts_with="V"))) == 1
    audit = json.loads((tmp_path / "candidate" / "review.json").read_text())
    assert audit["review"]["reviewer"] == "TEST FIXTURE ONLY"
    with pytest.raises(ValueError, match="already exists"):
        write_candidate(tmp_path / "candidate", review_batch, doc, corpus)


@pytest.mark.parametrize(
    "field", ["meaning_checked", "name_usage_checked", "origin_checked"]
)
def test_each_human_confirmation_is_required(field, review_batch, corpus):
    doc = approved_document(review_batch)
    doc["decisions"][0][field] = False
    with pytest.raises(ValueError, match="explicit review"):
        compile_decisions(review_batch, doc, corpus)


@pytest.mark.parametrize(
    "change", ["reviewer", "date", "gender", "flags", "duplicate", "unknown"]
)
def test_incomplete_or_invalid_decisions_fail(change, review_batch, corpus):
    doc = approved_document(review_batch)
    if change == "reviewer":
        doc["reviewer"] = "  "
    elif change == "date":
        doc["reviewed_at"] = None
    elif change == "gender":
        doc["decisions"][0]["gender"] = None
    elif change == "flags":
        doc["decisions"][0]["acknowledged_flags"] = []
    elif change == "duplicate":
        doc["decisions"].append(deepcopy(doc["decisions"][0]))
    else:
        doc["decisions"][0]["candidate_id"] = "not-in-batch"
    with pytest.raises(ValueError):
        compile_decisions(review_batch, doc, corpus)


def test_stale_and_modified_evidence_fail(review_batch, corpus):
    doc = approved_document(review_batch)
    stale = deepcopy(review_batch)
    stale["knowledge_version"] = "another-version"
    stale["batch_id"] = digest({k: v for k, v in stale.items() if k != "batch_id"})[:20]
    with pytest.raises(ValueError, match="another knowledge version"):
        compile_decisions(stale, doc, corpus)
    modified = deepcopy(review_batch)
    modified["items"][0]["evidence"][0]["text"] = "Changed source meaning"
    modified["batch_id"] = digest(
        {k: v for k, v in modified.items() if k != "batch_id"}
    )[:20]
    with pytest.raises(ValueError, match="evidence differs"):
        compile_decisions(modified, doc, corpus)


def test_rejected_and_pending_entries_are_not_approved(review_batch, corpus):
    for status in ("reject", "pending"):
        doc = approved_document(review_batch)
        doc["decisions"][0]["decision"] = status
        with pytest.raises(ValueError, match="No human-approved"):
            compile_decisions(review_batch, doc, corpus)


def test_batch_requires_exact_evidence_and_report_has_citations(corpus, review_batch):
    draft = deepcopy(review_batch["items"][0]["proposal"])
    draft["name_te"] = "అజ్ఞాతం"
    with pytest.raises(ValueError, match="No exact source"):
        prepare([draft], corpus)
    report = render_report(review_batch)
    assert "pending human review" in report
    assert "https://te.wiktionary.org/" in report
    assert "revision 1" in report


def test_name_api_keeps_reviewer_identity_in_server_audit(api_client):
    response = api_client.post("/names", json={"query": "moonlight"})
    assert response.status_code == 200
    rows = response.json()["results"]
    assert rows
    assert all("reviewed_by" not in row and "reviewed_at" not in row for row in rows)
    assert all(row["sources"] for row in rows)
