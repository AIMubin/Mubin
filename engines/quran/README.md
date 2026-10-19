# Quran Engine

Current internal milestone: `Q0.3` **in progress** — not accepted or released.
Mubin system version remains `0.1.0-alpha`.

## Source-connected components

- [Tafsir Center pinned importer](../../corpus/import_tafsircenter.py) (6,236 verse IDs, five tafsir sources)
- [Quran read-only retrieval](../../corpus/query.py) (no Quran text by default; explicit pinned Tanzil witness required for display, derived text requires developer diagnostic opt-in)
- [Linked SQLite audit](../../corpus/audit_linked.py)
- [Conservative witness difference triage (legacy raw rows)](../../corpus/triage_quran.py)
- [Boundary-aware independent Quran witness analysis](../../corpus/quran_witness_analysis.py)
- [Editorial tafsir-quality audit](../../corpus/audit_tafsir_quality.py)
- [Upstream-to-import byte-exact tafsir comparison](../../corpus/audit_tafsir_upstream.py)
- [Measured real-data witness findings](../../corpus/reviews/q03-quran-witness-analysis.json)
- [11-item manual review queue](../../corpus/reviews/q03-tafsir-review-queue.json)
- [Import/quality workflow](../../.github/workflows/import-quran-tafsir.yml)
- [Q0.2 baseline contracts](../../corpus/Q0.2.md)

## Measured import status

A real staging SQLite artifact has been inspected independently: 6,236 **derived**, unvocalized verse strings and 31,180 nonempty tafsir entries. All five tafsir keys cover every verse ID. Seven al-Tabari entries have only HTML markup; four al-Baghawi texts are exactly 32,767 characters and need source-edition verification. A legacy raw-row comparison found 0/6,236 byte-exact matches. A new analysis of the pinned verbatim Tanzil txt-2 witness identifies 112 first-verse records with prefixed surah-opening basmala (suras 95 and 97 have alternate opening diacritics). Once these *record* prefixes are separated by literal substring boundaries, candidate comparisons across 6,236 ayahs yield 1 exact match, 436 marks-only candidates, 829 alef-variant candidates, 917 additional-script candidates and 4,053 differences not resolved by those simple transforms. These groupings are **not** Quranic equivalence judgments; the data includes 364 derived records with slash artifacts. Additional review of the imported SQLite SHA-256 `a1bd1811ab1b3a4a0373b6499f916f8c379df64ad77fbaf1988e08d34a1814a0` found 364 derived verses with 371 literal `/` marks, for example `2:21` contains `يا/أيها`. These are unacceptable as a canonical display rendering. See [derived text safety review](../../corpus/reviews/q03-derived-quran-observations.json).

**Hard gate:** Nothing in Q0.3 proves Quranic canonicality, authenticity of any modern tafsir edition, complete tafsir coverage beyond database keys, or authorization to redistribute each edition. Use pinned verbatim Quran witness for provisional reading only, preserve provenance, and require independent scholarly and rights review for a release.

**Fail-closed read path:** `python -m corpus.query 2 21` returns tafsir references but `text=null` when no pinned Tanzil witness is supplied. Pass `--reference corpus-data/reference/tanzil-uthmani.txt` for a pinned witness; `--allow-unverified-derived-text` is reserved for diagnostic use. `python -m corpus.audit_quran_derived` records reconstruction anomalies. Never patch scripture by stripping `/` automatically.

For first-ayah retrieval outside al-Fatihah and al-Tawbah, the pinned witness may carry an unnumbered surah-opening basmala in the same raw record. `corpus.query` now returns that literal opening separately as `opening_basmala` and uses only the unchanged verse substring for `text`; it fails closed on unknown first-verse layouts. Original witness bytes and provenance remain preserved.
