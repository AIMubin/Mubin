# Quran Engine

Current internal milestone: `Q0.3` **in progress** — not accepted or released.
Mubin system version remains `0.1.0-alpha`.

## Source-connected components

- [Tafsir Center pinned importer](../../corpus/import_tafsircenter.py) (6,236 verse IDs, five tafsir sources)
- [Quran read-only retrieval](../../corpus/query.py) (derived text by default; optional verbatim pin-checked Tanzil witness)
- [Linked SQLite audit](../../corpus/audit_linked.py)
- [Conservative witness difference triage](../../corpus/triage_quran.py)
- [Editorial tafsir-quality audit](../../corpus/audit_tafsir_quality.py)
- [11-item manual review queue](../../corpus/reviews/q03-tafsir-review-queue.json)
- [Import/quality workflow](../../.github/workflows/import-quran-tafsir.yml)
- [Q0.2 baseline contracts](../../corpus/Q0.2.md)

## Measured import status

A real staging SQLite artifact has been inspected independently: 6,236 **derived**, unvocalized verse strings and 31,180 nonempty tafsir entries. All five tafsir keys cover every verse ID. Seven al-Tabari entries have only HTML markup; four al-Baghawi texts are exactly 32,767 characters and need source-edition verification. A prior literal comparison to a Tanzil Uthmani witness was 0/6,236; classification by Unicode marks, spacing and writing variants has not yet completed. Additional review of the imported SQLite SHA-256 `a1bd1811ab1b3a4a0373b6499f916f8c379df64ad77fbaf1988e08d34a1814a0` found 364 derived verses with 371 literal `/` marks, for example `2:21` contains `يا/أيها`. These are unacceptable as a canonical display rendering. See [derived text safety review](../../corpus/reviews/q03-derived-quran-observations.json).

**Hard gate:** Nothing in Q0.3 proves Quranic canonicality, authenticity of any modern tafsir edition, complete tafsir coverage beyond database keys, or authorization to redistribute each edition. Use pinned verbatim Quran witness for provisional reading only, preserve provenance, and require independent scholarly and rights review for a release.

**Fail-closed read path:** `python -m corpus.query 2 21` returns tafsir references but `text=null` when no pinned Tanzil witness is supplied. Pass `--reference corpus-data/reference/tanzil-uthmani.txt` for a pinned witness; `--allow-unverified-derived-text` is reserved for diagnostic use. `python -m corpus.audit_quran_derived` records reconstruction anomalies. Never patch scripture by stripping `/` automatically.
