# Quran Q0.1 — first executable text-locating slice

**Date:** 2026-10-18. **Q0.1 (internal PR milestone)**, overall system remains `0.1.0-alpha`, `Q0.0` on unmodified main. **Not a qualified complete digital mushaf.**

## Actual deliverable

- Deterministic, **offline** Quran verse index over *externally supplied* byte-pinned UTF-8 snapshots, with exactly numbered verse references `sura:aya` (Hafs/Kufan numbering).
- JSON manifest declares `source_id`, reading, script, provenance URL, `coverage`, raw-file SHA-256 and count. Verifier checks byte-for-byte SHA-256 of **the same exact opened file**, sorted unique verse references, bounds, Arabic letters, and 114-sura/6236-aya verse-numbering topology if `coverage=complete_hafs_kufan`. No Quran content is embedded apart from the explicitly **synthetic** test fixture.
- `get` returns the **unmodified stored text**. `find` supports exact substring or **Arabic-mark-insensitive query/index comparison only**. It does not normalize, alter, re-vowel, or export modified stored Quran text. The insensitive mode strips Arabic combining marks only in *search comparisons* (not hamza/alef variants and not the delivered text).
- Fail-closed unknown fields, invalid references, missing/duplicate/out-of-order records, nonfinite JSON, duplicate JSON keys, Unicode surrogates/bidi controls, oversized inputs, symlinks/nonregular files, unbounded result counts, wrong coverage claims and mismatched raw source hash.
- Returned `source_authenticated=false`, `rights_verified=false`, `canonical_corpus_qualified=false`, `eligible_for_religious_ruling=false` are fixed. A complete numeric structure is **not** a guarantee of text identity or orthographic authenticity.

## Candidate primary data providers — evaluation, not ingestion

**Tanzil v1.1**: the published [Tanzil Text License](https://tanzil.net/docs/Text_License) allows verbatim copying/use in sites and applications with attribution and a link to Tanzil, and forbids modifying the text. The [official download page](https://tanzil.net/pub/download/index.php) offers configurations for Uthmani text, bismillah markers etc. A precise text variant, authoritative file digest, release identity, source-specific rights checks and display attribution must be fixed **before** a real corpus is ingested. [Tanzil's bismillah note](https://tanzil.net/docs/a_note_on_bismillah) emphasizes that plain-text verse 1 may combine a non-verse basmala in one line; do not strip or secretly split it.

**King Fahd Glorious Quran Printing Complex**: its [developer platform](https://qurancomplex.gov.sa/en/techquran/dev/) documents Uthmani Hafs text and separate `aya_text_emlaey` field for search, plus JSON/CSV/SQL download options and release corrections. Full per-file permission and hash/version provenance would be checked before a downloaded digital edition becomes a data artifact in Mubin; Q0.1 does not automatically declare those verified.

**Quran Foundation APIs**: current [developer terms](https://api-docs.quran.com/legal/developer-terms/) impose provider-specific offline syncing/redistribution and storage limitations. We have **not** fetched/stored their API corpus, and must not treat standard API responses as a permanent redistributable dataset. Their terms are not equivalent to Tanzil's text license.

Reference topology: [Tanzil Quran Metadata](https://tanzil.net/docs/Quran_Metadata), Hafs/Kufan 114 surahs / 6236 numbered ayahs. The numerical topology alone does not verify source text, translation, tafsir, basmala placement or recitation.

## Next stage without human bottleneck

1. Prepare **one explicitly permitted, reproducibly pinned full text variant**, leave unmodified, record retrieval/rights/attribution evidence, independently compare a sampled set of sensitive verses and basmala handling. Do not re-use development fixtures as external gold.
2. Add the source-specific converter/adapter in a separate PR with **deterministic replay**; its output must retain provider/source version identity and never silently relabel altered text as its origin.
3. Provide real verse query and search CLI/API to a user-visible vertical slice, and only then add independently sourced tafsir retrieval. Different tafsir schools and interpretations must stay distinct from the original Quran text.
4. Build source-identity and exact quote receipts under P1, run source-disjoint checks, maintain source updates without corrupting frozen benchmarks.

The Q0.1 gate is engineering-only. No Hadith Schema-31 human reviews, U0.5 approval slots, or frozen H3.9.2 holdouts are modified or opened.
