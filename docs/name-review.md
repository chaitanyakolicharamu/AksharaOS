# Review names before the internal pilot

The [first batch](../reports/name_review/README.md) contains eight AI-prepared
proposals, exact source revisions, and unresolved questions. Vennela, Tara and
Deepthi have explicit given-name evidence in the linked source pages. The project
owner confirmed the displayed three-name table on 2026-10-13, including the
spellings, intended meanings and origin labels. This is owner confirmation for
internal testing, not an independent expert certification.

The default internal catalog now contains those **three confirmed names**. The
other five remain pending. No real public feedback or preference model has been
created. Dictionary grammatical gender must not be used as a person's name
gender, and writing a word in Telugu does not establish native Telugu origin.
See [the current pilot status](../reports/name_review/pilot_activation.json).

## The first decisions

| Confirmed pilot name | Intended meaning | Name gender | Origin | Review result |
| --- | --- | --- | --- | --- |
| వెన్నెల / Vennela | Moonlight | Girl | Telugu | Confirmed for the internal pilot |
| తార / Tara | Star | Girl | Sanskrit | Star sense confirmed; excluded from pure-Telugu results |
| దీప్తి / Deepthi | Radiance; brightness | Girl | Sanskrit | Deepthi spelling confirmed; excluded from pure-Telugu results |

Siri, Lahari, Kanti and Kaluva require further origin or name-usage review.
Taamara is held because the same Telugu word also has an unfavorable non-floral
meaning. These are research triage decisions, not human accept/reject labels.

## Reproduce a batch

```bash
python -m knowledge.unified_build
python -m naming.review prepare --shortlist configs/name_review_shortlist.json --output reports/name_review_next
```

The batch embeds the exact lexical records, source observations and a fingerprint
of the proposals. The generated decision template begins with a blank reviewer,
no review date, all confirmations false, and every decision pending. A different
knowledge version or altered evidence requires a fresh batch.
The original committed batch belongs to the earlier online-only index. Prepare
a new batch before recording decisions against the unified knowledge base.

## Record the review

Copy `reports/name_review/decisions_template.json` into `data/private/` and edit
that private copy after a real person checks the evidence:

- Supply the reviewer's identifier and actual ISO review date (`YYYY-MM-DD`).
- For each accepted entry, set `decision` to `approve`, confirm or correct the
  English spelling, meaning, gender, origin and established/coined status.
- Set `meaning_checked`, `name_usage_checked`, and `origin_checked` to true only
  for checks actually performed. `unknown` is an acceptable origin when evidence
  is insufficient; it cannot pass the pure-Telugu filter.
- Acknowledge each applicable flag explicitly in `acknowledged_flags`. Record
  the reasoning in `note`, especially when resolving an alternate meaning.
- Leave unresolved entries `pending`, or mark unsuitable ones `reject`.

This is an offline operator workflow. The supplied reviewer identifier is an
audit record, not identity verification. Do not fill it with invented reviewers,
machine guesses, or an assistant's claim to be a human. It is not a public
approval endpoint or an automated guarantee of linguistic correctness.

```bash
python -m naming.review compile --batch reports/name_review/batch.json --decisions data/private/name_decisions.json --output data/private/name_pilot_001
```

Compilation checks the batch/version, source evidence, explicit review, complete
name fields and acknowledged flags. Pending and rejected proposals never become
catalog entries. An unmodified template fails without writing a catalog. The
output must be a new directory; an existing catalog is never overwritten.

The new bundle contains `catalog.jsonl` and its `review.json` audit. It is a
standalone candidate catalog, not an automatic merge with an existing catalog.
Review any omissions before switching a running service. Keep real reviewer
notes and identities private; they do not need to be committed to GitHub.

## Test a reviewed candidate catalog locally

The three-name pilot is already available at the default path
`data/names/reviewed.jsonl`. Start the API normally to use it. For later candidate
bundles, after their decisions have been recorded and compiled:

```bash
AKSHARA_NAME_CATALOG=data/private/name_pilot_001/catalog.jsonl uvicorn api.main:app --host 127.0.0.1 --port 8000
```

On Windows PowerShell, set `$env:AKSHARA_NAME_CATALOG` to the candidate catalog
path before starting Uvicorn. Open `http://127.0.0.1:8000/docs` to exercise the API.
Check `/ready`, `/search`, `/names`, and session feedback. Name results should
honor gender, Telugu/English prefixes, and pure-Telugu origin filters, including
empty results when no reviewed candidate matches.

Meaning searches include the confirmed name text, not just dictionary glosses.
`radiance` and `brightness` find Deepthi even when those English words were not
present in the source snapshot. Names with no topic relevance are excluded.
The catalog version includes the scoring schema so earlier feature values or
rankers cannot silently carry over to this revised retrieval behavior.

Use a separate `AKSHARA_FEEDBACK_DB` path for exploratory tests. Test votes are
not authentic public preference data and must never be promoted into training.
The existing synthetic tests write only to temporary directories.

Public launch, LLM fine-tuning, preference-model promotion and merging the draft
PR remain separate steps. Human review of this batch authorizes only the named
catalog entries, not public deployment.
