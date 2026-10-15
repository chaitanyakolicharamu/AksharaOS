import json

from knowledge.build import build
from knowledge.schema import write_jsonl
from rag.build_multi_vector_store import load_all_chunks


def test_combined_loader_preserves_source_roles_and_evidence(corpus, tmp_path):
    curated = tmp_path / "curated"
    folder = curated / "telugu_english_dictionary"
    folder.mkdir(parents=True)
    row = {"chunk_id": "legacy-1", "text": "తెలుగు dictionary text"}
    (folder / "quality_chunks.jsonl").write_text(
        json.dumps(row) + "\n", encoding="utf-8"
    )
    sources = tmp_path / "sources"
    write_jsonl(sources / "source.jsonl", corpus.records)
    index = tmp_path / "index-combined"
    build(sources, index)
    ids, docs, metadata = load_all_chunks(curated, index)
    assert len(ids) == len(set(ids)) == 4
    assert metadata[0]["source_role"] == "meaning_dictionary"
    assert json.loads(metadata[1]["evidence_json"])[0]["source_id"] == "te_wiktionary"
    assert len(docs) == 4
