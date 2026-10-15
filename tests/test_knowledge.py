import json

import pytest

from knowledge.build import build, collect
from knowledge.ingest import (
    definitions,
    ingest,
    wiki_pages,
    wikidata_records,
    wiktionary_records,
)
from knowledge.schema import Record, load_sources, write_jsonl
from knowledge.search import KnowledgeSearch
from rag.query_router import QueryRouter


@pytest.mark.parametrize(
    "query,expected",
    [
        ("I want a Telugu girl name", "name"),
        ("అచ్చతెలుగు అమ్మాయిల పేర్లు", "name"),
        ("accha telugu ammayi perlu", "name"),
        ("అచ్చ తెలుగు మాట", "pure_telugu"),
        ("namespace", "synonym"),
        ("ఆకాశము", "synonym"),
    ],
)
def test_name_routing(query, expected):
    assert QueryRouter().detect_mode(query) == expected


def test_parser_excludes_other_languages_quotes_and_unknown_templates():
    text = "==English==\n# wrong\n==Telugu==\n===Noun===\n# [[moonlight]]\n#: a lyric\n# {{l|te|వెలుగు}}\n# {{unhandled|invented}}\n==Hindi==\n# wrong too"
    assert definitions(text, "wiktionary_en") == ["moonlight", "వెలుగు"]
    text = "==అర్థ వివరణ==\nచంద్రుని కాంతి\n==పద ప్రయోగాలు==\nmodern song quote\n==అనువాదాలు==\n*[[ఇంగ్లీషు]]: [[moonlight]]"
    assert definitions(text, "wiktionary_te") == [
        "చంద్రుని కాంతి",
        "English: moonlight",
    ]


def test_pagination_and_revision_evidence():
    source = load_sources()["te_wiktionary"]

    class Client:
        def __init__(self):
            self.calls = []

        def get(self, url, params):
            self.calls.append(params)
            page = {
                "title": "వెన్నెల",
                "revisions": [
                    {
                        "revid": 42,
                        "slots": {"main": {"content": "==అర్థ వివరణ==\nmoonlight"}},
                    }
                ],
            }
            if len(self.calls) == 1:
                return {
                    "query": {"pages": [page]},
                    "continue": {"gcmcontinue": "next", "continue": "gcmcontinue||"},
                }
            return {"query": {"pages": [page]}}

    client = Client()
    records = list(
        wiktionary_records(wiki_pages(client, source, 2), source, "2026-10-13")
    )
    assert client.calls[1]["gcmcontinue"] == "next"
    assert records[0].evidence[0].revision == "42"
    assert "oldid=42" in records[0].evidence[0].url


def test_wikidata_filters_language_and_extracts_senses():
    source = load_sources()["wikidata_te"]

    class Client:
        def get(self, url, params):
            if "query" in params:
                assert "Q8097" in params["query"]
                return {
                    "results": {
                        "bindings": [
                            {"lexeme": {"value": "http://www.wikidata.org/entity/L1"}}
                        ]
                    }
                }
            return {
                "entities": {
                    "L1": {
                        "id": "L1",
                        "language": "Q8097",
                        "lastrevid": 5,
                        "lemmas": {"te": {"value": "వెన్నెల"}},
                        "senses": [
                            {"id": "L1-S1", "glosses": {"en": {"value": "moonlight"}}}
                        ],
                    },
                    "L2": {
                        "id": "L2",
                        "language": "Q809",
                        "lemmas": {"te": {"value": "తప్పు"}},
                    },
                }
            }

    rows = list(wikidata_records(Client(), source, 10, "2026-10-13"))
    assert len(rows) == 1 and rows[0].text == "moonlight"
    assert rows[0].evidence[0].url.endswith("#L1-S1")


def test_failed_refresh_keeps_old_snapshot(tmp_path):
    target = tmp_path / "records.jsonl"
    target.write_text("previous data", encoding="utf-8")

    class Offline:
        def get(self, *args):
            raise RuntimeError("offline")

    with pytest.raises(RuntimeError):
        ingest(load_sources()["te_wiktionary"], target, client=Offline())
    assert target.read_text() == "previous data"
    with pytest.raises(ValueError, match="reuse approval"):
        ingest(load_sources()["andhra_bharati"], target)


def test_unicode_quality_and_roundtrip(corpus):
    row = corpus.records[0].model_dump()
    row["text"] = "à° corrupt తెలుగు"
    with pytest.raises(ValueError, match="mojibake"):
        Record(**row)
    assert corpus.find("moonlight")[0][0].title == "వెన్నెల"
    assert corpus.find("సిరి")[0][0].title == "సిరి"
    assert corpus.find("zzzzzzzzzzzz") == []
    assert corpus.retrieve("wealth")["metadatas"][0][0]["evidence"]


def test_duplicates_preserve_one_evidence_and_conflicting_senses(corpus, tmp_path):
    r = corpus.records[0]
    second = r.model_copy(deep=True)
    second.evidence[0].retrieved_at = "2026-10-14"
    conflict = r.model_copy(deep=True)
    conflict.text = "different source sense"
    path = tmp_path / "duplicate.jsonl"
    write_jsonl(path, [r, second, conflict])
    rows, rejected = collect([path], load_sources())
    assert len(rows) == 2 and not rejected
    assert all(len(row.evidence) == 1 for row in rows)


def test_build_is_repeatable_and_rejects_unlicensed_input(corpus, tmp_path):
    source = tmp_path / "input"
    write_jsonl(source / "data.jsonl", corpus.records)
    dest = tmp_path / "build"
    first = build(source, dest)
    assert build(source, dest) == first
    row = corpus.records[0].model_copy(deep=True)
    row.evidence[0].license = "UNKNOWN"
    write_jsonl(source / "bad.jsonl", [row])
    with pytest.raises(ValueError, match="license mismatch"):
        build(source, dest)
    assert (dest / "CURRENT").read_text() == first["version"]
    record_file = dest / "versions" / first["version"] / "records.jsonl"
    data = [json.loads(line) for line in record_file.read_text().splitlines()]
    data[0]["text"] = "tampered knowledge"
    write_jsonl(record_file, data)
    with pytest.raises(ValueError, match="fingerprint"):
        KnowledgeSearch(dest)
