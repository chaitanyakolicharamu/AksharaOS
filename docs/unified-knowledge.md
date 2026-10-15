# One shared Telugu knowledge base

The previous application default searched the 825 online reference records while
the older Chroma database contained a different snapshot of two dictionaries.
The new builder imports current source text into a single canonical corpus. The
API, RAG CLI, name-review CLI and evaluation CLI all use that corpus.

## What the full private build contains

| Material | Canonical records |
| --- | ---: |
| Bangaru Nanelu | 2,052 |
| Telugu Paryaya Nighantuvu | 1,590 |
| Telugu/English Wiktionary and Wikidata references | 825 |
| Three recent books, including 46 draft review candidates | 1,504 |
| Classical grammar and Saraswati/Vishnu association research | 131 |
| **Total** | **6,102** |

There are 11 included sources. The inventory also records a Telugu–English PDF
awaiting extraction and a Lakshmi source held for transcription problems. It
does not count catalogued-but-unimported sources as searchable data.

All 857 recent PDF pages were accounted for. Six page items (one blank, two
complex tables, and three rotated charts/map pages) are withheld from prose
search. Eight previously quarantined Lakshmi candidates remain withheld. The
14 dispositions are in `quarantine.jsonl`; the original files are preserved.

The corpus contains reference passages, not 6,102 approved baby names. No corpus
record is promoted to expert-reviewed or training-approved by this import. The
separate three-name catalog remains owner-confirmed for internal testing.

## Build and run

From the repository root:

```bash
pip install -r requirements-core.txt
python -m knowledge.unified_build
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

The builder automatically includes private inputs when these folders exist:

- `data/private/knowledge_inputs/book_ocr/`: the contents of the previously
  supplied `aksharaos_book_ocr` extraction folder.
- `data/private/knowledge_inputs/research/`: the source/training starter-pack
  folder containing its manifest, source catalog and data files.

Explicit paths work too:

```bash
python -m knowledge.unified_build --books /path/to/aksharaos_book_ocr --research /path/to/aksharaos_source_and_training_starter_pack
```

The corpus lives at `data/knowledge/unified/versions/<version>/`. `CURRENT` selects
one version. A failed build does not replace that pointer. Record and index
fingerprints are checked when loading. Duplicate passages retain their original
citations. Original online evidence IDs remain valid for approved name records.
Rebuilding without a previously included source fails and preserves the current
version. Restore missing inputs; use `--allow-source-removal` only for an intentional
removal. Page text offsets belong to individual citations, so deduplication does
not attach one page's offsets to another page.

No source PDF, old index, feedback database or approved name file is overwritten.
Restart an already running API after a successful build to load its new version.
`AKSHARA_KNOWLEDGE_DIR` can select another complete unified-index root.
`AKSHARA_RETRIEVAL_BACKEND=legacy` no longer changes the API's knowledge source.

## Inspect or ask

Open `http://127.0.0.1:8000/docs` after starting the API.

- `GET /ready`: active knowledge/catalog versions and internal-testing status.
- `GET /knowledge`: source inventory, counts, exclusions and retrieval method.
- `POST /search`: search every included source; return passage previews and citations.
- `GET /knowledge/records/{record_id}`: complete record, including structured draft fields.
- `POST /ask`: use the same retrieval; name requests use the reviewed catalog.
- `POST /names`: return only approved catalog entries; extra source text does not
  silently become approved name suggestions.

Example search body:

```json
{"query": "సంధి", "top_k": 5}
```

To inspect a particular source, add `"source_ids": ["gouru_pedda_bala_siksha"]`.
`"reviewed_only": true` filters corpus facts by their actual review status; it
currently produces no results because no extracted corpus records have expert
approval. That is separate from owner approval of three naming examples.

Each book citation retains the PDF filename, PDF page and available printed page.
`book:<source_id>#pdf-page=<n>` is a portable source locator, not a public URL.
Recent scans include their SHA-256; older processed extracts include their JSONL
fingerprint because their original scan-to-extraction checksum was not recorded.
Old heuristic OCR quality scores are not represented as measured accuracy.

The general `/ask` generator still needs local Ollama with its configured model.
Search, source inspection and reviewed-name recommendations work without Ollama.
Generated text quality was not validated merely by running retrieval tests.

## Search and quality limits

This version uses combined word and character TF-IDF vectors. It is a single
searchable knowledge base, but not a rebuilt BGE-M3 semantic index. English
definitions and bilingual research notes support some English queries; semantic
paraphrases, transliteration and difficult OCR still require evaluation and work.
Word features are not frequency-capped: adding books must not discard rare names
or English meaning words. Character features retain the bounded fuzzy-match index.

Adding a dense model later must use the same canonical records and version, with
evaluated keyword/vector fusion. Reusing the old Chroma vectors would be wrong:
many of their passages differ from the current extracted text. There is no LLM
fine-tuning or public-feedback model training in this build.

Source passages are evidence to inspect, not automatically correct facts. Deity
associations remain separate from literal meanings; Sanskrit written in Telugu
script remains Sanskrit. Naming-table transcriptions are not validated four-pada
mappings. Birth-time calculations are still a separate unimplemented component.

Validation of this change passed 61 automated tests, Black and Ruff. The full
private build passed 32 integration/source-coverage checks. On the existing 18
development retrieval queries, 16 found a relevant result at rank 1 and 17 within
the first 5 results. These checks are not independent linguistic review or a
held-out naming-quality benchmark. Detailed results are in
`reports/knowledge/unified_validation.json` and `unified_retrieval.json`.

Before public use, correct and review important passages, resolve source reuse
status, expand the approved naming catalog, evaluate naming results independently,
and implement the birth-detail/deity preference features. Public readiness stays
false. The archive is for internal project work.

## Restore and deploy privately

The downloadable unified build contains `unified/CURRENT` and its version folder.
Copy that `unified` folder into `data/knowledge/`, then start the API. An existing
unified folder can retain its old version directories; replace `CURRENT` only
when deliberately selecting the restored version.

Private corpus artifacts and book inputs are excluded from Git and Docker build
context. A Docker build therefore creates a repository-only corpus. To run the
full private corpus, mount its index read-only:

```bash
docker run --rm -p 127.0.0.1:8000:8000 -v "$PWD/data/knowledge/unified:/app/data/knowledge/unified:ro" aksharaos
```

The naming catalog and feedback stores remain separate application data. Their
separation preserves approval and consent while all source knowledge is searched
through one corpus. Tests and validation reports do not constitute a public launch.
