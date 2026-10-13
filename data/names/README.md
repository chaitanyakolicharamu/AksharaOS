# Internal pilot name catalog

`reviewed.jsonl` contains the three girl names confirmed by the project owner on
2026-10-13: వెన్నెల / Vennela (moonlight), తార / Tara (star), and దీప్తి / Deepthi
(radiance; brightness). The confirmation covers the displayed spellings, meanings
and origin labels for internal testing. It is not an independent expert review.

Vennela is classified as Telugu-origin. Tara and Deepthi are Sanskrit-origin;
the `pure_telugu` filter excludes them. Five other first-batch proposals remain
pending. No public preference model has been trained or activated.

Each entry references exact evidence IDs in the knowledge corpus. The
[source-review batch](../../reports/name_review/README.md) supplies the source
URLs, revisions, attribution, and remaining qualifications. Adapted Wiktionary
meaning text remains available under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), attributed to the
English and Telugu Wiktionary contributors linked there. The owner confirmation
does not replace that attribution.

`project-owner` is an audit identifier, not a publicly verified identity.
The private review record contains the conversation confirmation; it is excluded
from git and the container. The name API omits reviewer identifiers and dates.

The API loads this catalog by default. Use `AKSHARA_NAME_CATALOG` to test a later
candidate separately. [Pilot status and checks](../../reports/name_review/pilot_activation.json)
record the current versions; [review instructions](../../docs/name-review.md)
describe how to compile additional confirmed names without overwriting this file.
