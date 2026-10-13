# Source knowledge, reviewed names, and preference training

This branch is for internal testing. It does not deploy a public website, change
`main`, or activate a preference model. The committed snapshots contain real
dictionary/lexeme evidence. There are no invented public votes or human name labels.

## What is implemented

1. Bounded, repeatable importers for Telugu Wiktionary, English Wiktionary's Telugu
   definitions, and Wikidata Telugu lexeme senses (language **Q8097**).
2. A registry and JSONL import path for approved local dictionary/literary extracts.
   Brown's specified 1853 edition is registered. Other editions, selected Wikisource
   works, Andhra Bharati compilations, and community contributions require their own
   reuse/permission records. These are **not downloaded** by the current snapshots.
3. Unicode validation, stable record IDs, duplicate removal, preserved conflicting
   senses, original page/revision links, licenses, attribution, and retrieval dates.
4. A local word + character TF-IDF retrieval model, fitted on source text. Artifacts
   use JSON and sparse NPZ, rather than executable pickle objects. Versioned builds
   preserve the previous index and switch `CURRENT` only after a successful build.
5. A name-review queue, a separately reviewed name catalog, and hard gender,
   starting-letter, and Telugu-origin filters before ranking.
6. Session-bound name impressions and like/dislike events, explicit training
   consent, offline moderation, deletion, and a pairwise ranker training command.

**Fitting a retrieval index is not training an LLM.** This provides immediately
searchable source knowledge. A dedicated generator remains a later stage, after
reviewed names and authentic preference data are available. No preference model
is trained on this branch's real data because no reviewed human votes exist yet.

## Run locally

From the repository root, with Python 3.11 or later:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-core.txt
python -m knowledge.build
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

On Windows activate with `.venv\Scripts\activate`. The new knowledge workflow does
not require a GPU, OCR installation, Chroma, or Ollama. `/search` returns evidence;
the existing generative `/ask` path for non-name, non-synonym requests still needs
local Ollama. Name requests always go through the reviewed catalog.

`/health` is process liveness. `/ready` reports knowledge and catalog versions and
explicitly reports the internal-testing stage. It is not public-launch approval.
The default internal catalog now contains the three owner-confirmed names
Vennela, Tara and Deepthi. `/names` returns `no_reviewed_matches` when the confirmed
catalog has no result for the topic or hard filters. The other five first-batch
proposals remain pending. Arbitrary dictionary words do not become names.

## Refresh sources and fit the retrieval model

The committed snapshots reproduce the initial experiment without network access.
Refreshing intentionally changes the snapshot/version, and may change results.
Each successful fetch replaces only its specified snapshot; errors or empty
results leave the earlier file intact.

```bash
python -m knowledge.ingest --source te_wiktionary --limit 500
python -m knowledge.ingest --source en_wiktionary_te --limit 500
python -m knowledge.ingest --source wikidata_te --limit 500
python -m knowledge.ingest --source te_wiktionary --titles configs/knowledge_seed_titles.txt --output data/knowledge/sources/te_wiktionary_themes.jsonl
python -m knowledge.ingest --source en_wiktionary_te --titles configs/knowledge_seed_titles.txt --output data/knowledge/sources/en_wiktionary_te_themes.jsonl
python -m knowledge.build
python -m knowledge.evaluate --output reports/knowledge/hybrid_retrieval.json
```

Limits count source pages/lexemes considered, not guaranteed output records. The
conservative Wiktionary parser skips unresolved templates and non-Telugu sections.
Telugu Wiktionary extraction uses meaning sections and English gloss lines, not
usage quotations, song lyrics, or a blanket scrape of page text. Wikidata coverage
is limited to available Telugu/English senses. Source entries remain unreviewed
linguistic evidence; preserve ambiguity and seek expert review where sources differ.

For a page-checked Brown extract, create UTF-8 JSONL records with `title` (Telugu
headword), `text`, `url` (the exact edition and page), `revision` (edition/page or
source checksum), and `kind` (`lexical` or `passage`). Then run:

```bash
python -m knowledge.ingest --source brown_1853 --input /path/to/checked_extracts.jsonl
python -m knowledge.build
```

Do not label the existing repository PDFs as this edition without checking them.
For another literary work, add a separate approved registry entry with its actual
license and attribution. Disabled/unapproved sources and mismatched licenses fail
validation. The registry is an operator-controlled import policy, not legal advice
or an automatic determination of copyright status.

## Preserve and extend the existing Chroma pipeline

The old OCR chunks and vector store remain in place. The default API now uses the
new attributed local index. The legacy BGE-M3 backend remains available with the
full requirements installed and `AKSHARA_RETRIEVAL_BACKEND=legacy`.

To combine the existing curated chunks and new source records in Chroma:

```bash
pip install -r requirements.txt
python -m rag.build_multi_vector_store --knowledge-index data/knowledge/index --output data/curated/vector_store_next
```

The builder refuses an existing destination instead of deleting the active store.
Evaluate the new store, then set `AKSHARA_RETRIEVAL_BACKEND=legacy` and
`AKSHARA_VECTOR_DB=data/curated/vector_store_next` when starting the API. This does
not establish reuse permission for legacy PDFs; review their provenance before
including them in a public deployment. Citation arrays are kept as `evidence_json`
in Chroma's scalar metadata. The new local API returns structured `evidence` arrays.

## Review names before serving them

Use the [first cited review batch](../reports/name_review/README.md) and the
[decision workflow](name-review.md) to prepare a candidate catalog. AI source
observations are separate from human approvals. The compiler requires explicit
checks, current evidence, a reviewer and date; it never activates a catalog.

The build creates `name_review_queue.jsonl` under its version directory. It is an
unlabelled queue, not name-training data. A Telugu reviewer should select suitable
names, choose a supported meaning, verify transliteration and origin, and supply
`data/names/reviewed.jsonl` (or `AKSHARA_NAME_CATALOG`). Each line follows
`naming.catalog.Name`: `name_te`, `name_en`, `meaning`, `gender`, `origin`, `status`,
`evidence_ids`, `reviewed_by`, and `reviewed_at`.

`gender` is `girl`, `boy`, or `unisex`; `origin` is `telugu`, `sanskrit`, `other`, or
`unknown`; `status` is `established` or `coined`. A reviewer must verify coined
names too. Unknown origin cannot satisfy the `pure_telugu` filter. Do not make up
reviewer names or mark machine guesses as reviewed. The test fixtures are explicitly
synthetic and are written only to temporary test directories.

Use `/names`' explicit JSON fields for reliable hard filters:

```json
{"query":"moonlight", "gender":"girl", "starts_with":"V", "pure_telugu":true, "top_k":10}
```

The free-text query provides lexical relevance, not arbitrary natural-language
constraint parsing. Romanized prefixes use the reviewer's English spelling; general
Romanized transliteration, audio, nakshatra filters, and the public interface are
future work. `/ask` detects common English, Telugu, and Romanized name requests and
basic gender/purity terms. Broad generation is never a substitute for name review.

## Feedback and training after testing

`/names` returns an `impression_id` and candidate IDs, and sets an HttpOnly session
cookie. Keep that cookie when posting a vote:

```json
{"impression_id":"ID_FROM_NAMES", "candidate_id":"ID_FROM_NAMES", "vote":"like", "reason":"sound", "training_consent":true}
```

`POST /feedback` accepts only suggestions actually shown to that session. A changed
vote updates the existing event and resets moderation. Votes default to no training
consent. The server logs features and model/catalog/knowledge versions, not client
scores or arbitrary client training labels. It stores a hashed session identifier
and a normalized query hash, not raw prompts, names of voters, IPs, or email addresses.

`DELETE /feedback` deletes that browser session's impressions and votes. This removes
them from future training; it does not retroactively untrain an already released
model. If such a model exists, retire/retrain it under the release process. Losing
the session cookie loses this self-service deletion handle.

Moderation and model changes are offline operator actions:

```bash
python -m feedback.manage pending
python -m feedback.manage approve --id VOTE_ID --reviewer REVIEWER_ID
python -m naming.train fit --catalog-version CATALOG_VERSION --knowledge-version KNOWLEDGE_VERSION
python -m naming.train promote --candidate models/candidate_ranker.json
```

Training requires at least 100 usable like/dislike pairs, 10 distinct browser
sessions, and 10 query groups. A pair must come from the same impression and session.
Only the latest vote for a session/query/candidate counts, with explicit consent and
approved moderation. Meaning-error reports go to review and are excluded from
preference training. The model never changes meanings or overrides hard filters.

There is at most one pair per impression, a cap of 20 pairs per session, and equalized
session weighting. Split by normalized query/filters before mirroring pairs. At least
20 validation pairs are required. Promotion requires validation accuracy of at least
55% and an improvement of at least two percentage points over the fixed baseline.
These are initial development gates, not statistical proof of product quality.

Training writes a **candidate** model; it never changes the running API. Explicit
promotion followed by `AKSHARA_RANKER=models/active_ranker.json` and a restart is
required. Mismatched knowledge/catalog versions are rejected. Keep the previous
artifact or remove `AKSHARA_RANKER` to restore the baseline.

## Public rollout remains a separate step

Before a public pilot: finish Telugu name/meaning review, evaluate on independently
written prompts and real reviewers, exercise the user interface and consent flow,
and run the deployed service under HTTPS with `AKSHARA_SECURE_COOKIES=true`.
The included per-session limit is for internal testing; browser sessions are not
verified people and can be reset. Add deployment-level rate limits and an identity
or abuse-review policy before collecting public training votes.

Mount `data/private` on persistent private storage, restrict its filesystem access,
back it up, and run `python -m feedback.manage prune --days 90` under the chosen
retention schedule. Neither private votes nor trained models belong in git or the
container image. SQLite supports this single-service prototype; reassess concurrency
and persistence before a larger launch.

The development retrieval report includes misses and is not a held-out benchmark.
No claim of better human name quality is made from parser tests or synthetic training
fixtures. Review → test → limited public pilot → moderated feedback → candidate
training → held-out evaluation → explicit release remains the sequence.
