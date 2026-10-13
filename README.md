# AksharaOS · Bangaru Palukulu

A source-backed Telugu language and naming platform. Dictionaries and lexemes
provide the knowledge base; reviewed names and human preferences will support
better naming results.

This working version is for **internal testing before a public launch**.

## New source and learning workflow

- Three live source importers: Telugu Wiktionary, English Wiktionary's Telugu
  entries, and Wikidata Telugu lexemes.
- **825 source records / 716 distinct Telugu words** in reproducible, attributed
  snapshots. A registry also supports approved Brown dictionary and literary imports.
- Versioned word + character TF-IDF retrieval fitted on the combined source data.
- Reviewed-name filtering, session-bound likes/dislikes, training consent, offline
  moderation, and a candidate ranker with holdout evaluation and explicit promotion.
- English, Telugu, and common Romanized name-intent routing; no invented human votes.

```bash
pip install -r requirements-core.txt
python -m knowledge.build
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Use `/search` for source evidence, `/ask` for the existing answer flow, `/names` for
reviewed suggestions, and `/feedback` for preferences. `/health` checks process
liveness; `/ready` reports data versions and the internal-testing stage.

The first internal catalog contains **three owner-confirmed girl names**:
Vennela (moonlight), Tara (star), and Deepthi (radiance/brightness). Vennela is
classified as Telugu-origin; Tara and Deepthi are Sanskrit-origin and are excluded
by the pure-Telugu filter. Five other proposals remain pending.

Name retrieval searches the confirmed spellings and meanings as well as the
dictionary evidence. Unsupported topics return `no_reviewed_matches`.
Retrieval fitting is complete; no LLM fine-tuning or real-feedback preference
training has been performed. This three-name pilot is not a public launch.

[First name-review batch: eight candidates and source checks](reports/name_review/README.md)
· [Record review decisions and test a candidate catalog](docs/name-review.md)
· [Current pilot status](reports/name_review/pilot_activation.json)

[Full workflow: sources, knowledge builds, name review, training, and rollout](docs/knowledge-and-feedback.md)

[Source attribution and dataset terms](data/knowledge/README.md) ·
[Development retrieval results](reports/knowledge/hybrid_retrieval.json)

## Tests

```bash
pip install -r requirements-core.txt pytest black ruff httpx
pytest -q
black --check .
ruff check .
```

Tests run offline with small fixtures and never load BGE-M3 or call Ollama.
The existing OCR and Chroma pipelines remain available with `requirements.txt`.
To add the new records to the original Chroma corpus, follow the combined-index
instructions in the workflow document. A rebuild uses a new output directory
instead of deleting the active vector store.
