"""Check a real unified build without training, publishing, or retaining votes."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile

from fastapi.testclient import TestClient

from api import main as api
from feedback.store import FeedbackStore
from knowledge.schema import Record
from knowledge.unified_build import read_jsonl
from knowledge.unified_search import UnifiedSearch
from naming.catalog import Catalog

SOURCE_QUERIES = {
    "bangaru_nanelu": "నక్షత్రం",
    "telugu_paryaya_nighantuvu": "అశ్విని",
    "te_wiktionary": "వెన్నెల",
    "en_wiktionary_te": "moonlight",
    "wikidata_te": "భాష",
    "pedda_bala_siksha": "సరస్వతి",
    "gouru_pedda_bala_siksha": "సంధి",
    "telugu_bhasha_charitra": "తెలుగు భాష",
    "balavyakaranam_1911": "సంధి",
    "saraswati_dvadasha": "Saraswati",
    "vishnu_sahasranama": "Vishnu",
}


def validate(root, catalog_path):
    knowledge = UnifiedSearch(root)
    catalog = Catalog(catalog_path, knowledge)
    checks = []

    def check(label, passed, detail=None):
        checks.append({"check": label, "passed": bool(passed), "detail": detail})

    included = {e.source_id for r in knowledge.records for e in r.evidence}
    for source, query in SOURCE_QUERIES.items():
        if source not in included:
            continue
        found = knowledge.find(query, 3, source_ids=[source])
        check(
            f"Search source: {source}",
            bool(found),
            {
                "query": query,
                "record_ids": [r.id for r, _ in found],
                "pdf_pages": [e.pdf_page for r, _ in found for e in r.evidence],
            },
        )
    for query in ["వెన్నెల", "అశ్విని"]:
        found = knowledge.find(query, 5)
        sources = sorted({e.source_id for r, _ in found for e in r.evidence})
        check(f"Combined source retrieval: {query}", len(sources) >= 2, sources)

    old_ids = {
        Record.model_validate(row).canonicalize().id
        for path in Path("data/knowledge/sources").glob("*.jsonl")
        for row in read_jsonl(path)
    }
    check(
        "Existing online evidence IDs retained",
        old_ids <= set(knowledge.by_id),
        len(old_ids),
    )
    check(
        "No extraction auto-approved for training",
        all(not r.training_allowed for r in knowledge.records),
    )
    check(
        "Quarantined Lakshmi candidates excluded", "lakshmi_ashtottara" not in included
    )
    check(
        "Draft records remain unreviewed",
        all(
            r.review_status == "unreviewed"
            for r in knowledge.records
            if r.text_status != "source_text"
        ),
    )

    original_overrides = dict(api.app.dependency_overrides)
    original_catalog, original_feedback = api.get_catalog, api.get_feedback
    try:
        with tempfile.TemporaryDirectory(prefix="akshara-unified-check-") as temporary:
            store = FeedbackStore(Path(temporary) / "feedback.sqlite3")
            api.app.dependency_overrides.update(
                {
                    api.get_knowledge: lambda: knowledge,
                    api.get_retriever: lambda: knowledge,
                    api.get_catalog: lambda: catalog,
                    api.get_feedback: lambda: store,
                }
            )
            api.get_catalog = lambda: catalog
            api.get_feedback = lambda: store
            with TestClient(api.app) as client:
                ready = client.get("/ready").json()
                check(
                    "API uses the unified version",
                    ready["knowledge_version"] == knowledge.version,
                    ready,
                )
                check(
                    "Public readiness stays false",
                    ready["public_launch_ready"] is False,
                )
                inventory = client.get("/knowledge").json()
                check(
                    "API source inventory matches corpus",
                    inventory["included_source_count"] == len(included),
                )
                for topic, expected in [
                    ("moonlight", "Vennela"),
                    ("star", "Tara"),
                    ("radiance", "Deepthi"),
                ]:
                    response = client.post("/names", json={"query": topic}).json()
                    names = [r["name_en"] for r in response["results"]]
                    check(
                        f"Approved naming example: {topic}", names == [expected], names
                    )
                    check(
                        f"Name evidence version: {topic}",
                        response["knowledge_version"] == knowledge.version,
                    )
                for topic in ["ocean", "asdfzzxq"]:
                    response = client.post("/names", json={"query": topic}).json()
                    check(
                        f"No unsupported approved names: {topic}",
                        response["results"] == [],
                    )
                response = client.post(
                    "/ask", json={"query": "Give me pure Telugu girl names"}
                ).json()
                check(
                    "Name routing keeps origin filter",
                    [r["name_en"] for r in response["results"]] == ["Vennela"],
                )
                hits = client.post(
                    "/search", json={"query": "సరస్వతి", "top_k": 5}
                ).json()["results"]
                book_hits = [
                    r
                    for r in hits
                    if any(e.get("pdf_page") for e in r["metadata"]["evidence"])
                ]
                check("API returns book page citations", bool(book_hits))
                if book_hits:
                    detail = client.get(
                        f"/knowledge/records/{book_hits[0]['chunk_id']}"
                    ).json()
                    check(
                        "Complete book record accessible",
                        detail["record"]["id"] == book_hits[0]["chunk_id"],
                    )
            with store.connect() as connection:
                votes = connection.execute("SELECT COUNT(*) FROM votes").fetchone()[0]
            check("No real or synthetic votes created", votes == 0)
    finally:
        api.app.dependency_overrides.clear()
        api.app.dependency_overrides.update(original_overrides)
        api.get_catalog, api.get_feedback = original_catalog, original_feedback

    return {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "knowledge_version": knowledge.version,
        "records": len(knowledge.records),
        "included_sources": len(included),
        "passed": sum(r["passed"] for r in checks),
        "total": len(checks),
        "checks": checks,
        "scope": "Internal integration and source-coverage checks; not expert linguistic review, held-out naming evaluation, or generated-answer evaluation.",
        "llm_generation_tested": False,
        "model_fine_tuned": False,
        "dense_embeddings_built": knowledge.manifest["dense_embeddings_built"],
        "public_deployment": False,
        "feedback": "Temporary impressions only; temporary database removed, no votes created.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=Path("data/knowledge/unified"))
    parser.add_argument(
        "--catalog", type=Path, default=Path("data/names/reviewed.jsonl")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("reports/knowledge/unified_validation.json")
    )
    args = parser.parse_args()
    report = validate(args.index, args.catalog)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "checks"}, indent=2))
    if report["passed"] != report["total"]:
        raise SystemExit("Some unified knowledge checks failed; inspect the report")


if __name__ == "__main__":
    main()
