# Attributed Telugu source snapshots

These JSONL snapshots are reference evidence, not a reviewed baby-name dataset.
The initial combined build retains 825 records across 716 distinct titles:

| Source | Retained evidence records | Terms |
| --- | ---: | --- |
| Telugu Wiktionary | 283 | CC BY-SA 4.0 |
| English Wiktionary, Telugu sections | 458 | CC BY-SA 4.0 |
| Wikidata Telugu lexeme senses | 84 | CC0 1.0 |

The source files contain 827 rows before duplicate removal. Theme snapshots overlap
with two English category records. Re-fetching the same page does not increase its
evidence count. Every row retains its source ID, permanent revision URL, license URL,
attribution to that project's contributors, and retrieval time. Follow the revision
link/history for individual authors. Preserve these fields when sharing derived data.

Wiktionary definitions have been converted from wikitext to plain text and selectively
extracted; they are adapted content. The Wiktionary-derived records remain under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Wikidata structured
lexical data is [CC0](https://www.wikidata.org/wiki/Wikidata:Licensing). These content
terms do not assign a license to unrelated repository code or legacy PDFs.

Rebuild locally with `python -m knowledge.build`; generated indices are ignored by
git. See `reports/knowledge/manifest.json` for the fingerprint and
`docs/knowledge-and-feedback.md` for imports, review, testing, and training.

Known limits: conservative parsing skips templates it cannot interpret, source
senses can conflict, snapshots are bounded rather than exhaustive, and no human
name-suitability labels, pronunciation audio, or verified word-origin labels have
been added. Cross-source entries can share underlying dictionary material, so their
count is not a count of independent scholarly confirmations.
