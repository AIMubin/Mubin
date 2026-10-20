# U0.1 Stage 05 — Evidence Retrieval & Lexical Analysis

**Status:** `ENGINEERING_IMPLEMENTED_SYNTHETIC_CI_PASS`; **private real-witness replay pending**. This is an exact-text evidence locator, not a semantic `qarīnah` detector or fiqh ruling engine.

## Source and release boundary

Stage 04's metadata-only [al-Waraqat receipt](../../../corpus/reviews/u01-stage04-waraqat-source-link.json) fixes one digital witness, not a printed edition:

- Book: *الورقات في أصول الفقه* — Imam al-Haramayn al-Juwayni.
- Witness URL: https://www.islamicbook.ws/asol/alwrqat.html
- Raw HTML SHA-256: `66ec33c1825acdf82b3720f89d89aac15aa6e993356c0d90b41e53fe9a2fa044`
- Extracted UTF-8 SHA-256: `9ce9de30f1af3ef32b2bf55b0473c9459e0cf530e3b557535744b284c760f4df`
- Trusted manifest SHA-256: `5bf586787dbb9f84d03fc21c62ee32619b66b474c66a6c890aeb813219f853cf`
- باب الأمر section SHA-256: `20879bade7a4a831a0020e1bae51806ca015d7803be42fdb44e580a9055581ab`, **lines 86–107 inclusive / 108 exclusive; 22 lines and 1,232 bytes**.

The [Stage05 private operator runner](waraqat_stage05.py) hard-pins these exact values. A different snapshot, index, chapter, or altered original HTML is not a successful replay of that witness. Neither the source text nor the original HTML/manifest is committed.

## What the code verifies

[Source lexical indexer](../source_lexical_index.py):

1. Re-runs `source_snapshot_coverage.audit()` using an independent manifest digest. Source size, source hash, section hash, heading boundaries, and section line count must pass.
2. Re-reads the UTF-8 text and rejects any intervening changes. It requires exact byte reconstruction of the pinned section and indexes **every line in the declared section**, including empty or heading lines.
3. Optionally reads the raw witness HTML with an **independently frozen raw SHA-256** and regenerates the entire UTF-8 export using `waraqat-extract/1.0.0`. The dedicated al-Waraqat runner makes this step mandatory.
4. Executes `literal_exact_v1` case-sensitive and Unicode-exact substring queries. **No Unicode normalization, diacritic stripping, stemming, morphological parsing, or meaning inference.**
5. Returns **all matches** with original absolute UTF-8 byte offsets, original line number, zero-based code-point column, SHA-256 of the matching bytes, plus source/book/edition and section metadata. No source or query text is included in the emitted report.

If there are no matches, `NO_EXACT_LITERAL_MATCH_IN_PINNED_SECTION` means **only that the exact bytes for that literal string were not found inside this section**. It never means an exception or diverting evidence does not exist. No hit result is promoted into a truth-value assertion in the Usul engine.

A profile other than `literal_exact_v1`, malformed query IDs, control characters, extremely long strings, overlarge query arrays, unmatched source pins, or too many matches causes a failure; the engine does not truncate silently.

## Run on the Windows host with the real private snapshot

From `C:\AI\Mubin` after `git pull --ff-only`, use the source snapshot already captured in Stage 04:

```powershell
python -m engines.usul.pilots.waraqat_stage05 `
  --raw-html "D:\MubinSources\waraqat\waraqat-original.html" `
  --source "D:\MubinSources\waraqat\waraqat-private-utf8.txt" `
  --manifest "D:\MubinSources\waraqat\waraqat-draft-manifest.json" `
  --queries "engines\usul\pilots\data\waraqat-stage05-queries.json" `
  --report "D:\MubinSources\waraqat\stage05-lexical-report.json"
```

The [default query file](data/waraqat-stage05-queries.json) contains only short unprotected search keywords (e.g. `الأمر`, `القرينة`), not copied historical passages. It is a research search plan, not a library of all legal exception classes. Private query files with the same schema can be used, but no query's semantics are attested.

**Exit codes:**
- `0` — `STAGE05_REAL_SOURCE_LEXICAL_REPLAY_PASS`: every known Stage04 digest and chapter boundary matched and lexical search finished. Zero query matches is still technically valid.
- `3` — `PENDING_PRIVATE_STAGE04_FILES`: original HTML, export or manifest bytes are unavailable.
- `1` — `FAIL`: digest, chapter, query or source replay mismatch. No partial source-index acceptance.

The JSON report may be retained locally. It is *metadata-only*: author, title, digital source URL, chapter, source and index SHA-256, query SHA-256, byte/line locators, classifications and match counts. Do not share any private raw book bytes or derived full-text indices by default.

## Test and qualification plan

```bash
python -m unittest discover -s engines/usul/tests -v
python -m unittest discover -s core/tests -v
```

Cross-OS CI uses **synthetic Arabic UTF-8 files**. Tests include multi-hit byte offsets, match hashes, no-hit semantics, exact vs unaccented spelling, source/manifest tampering, absent sections, missing private files, raw HTML re-extraction mismatch, bounded query schema, deterministic results, and Windows ASCII-safe CLI JSON output.

**Stage05 real-source data acceptance is not granted by CI alone.** The local operator must run the dedicated runner on the private Stage04-pinned source and return the metadata-only report. The report can be added to GitHub only after confirming no protected text is included.

**Deferred by design:** comparison with the islam.ms witness (needs independently pinned source), broader book coverage (one section per accepted manifest entry), Arabic morphological search, semantic exceptions, qiyās, tarjīḥ, and rights-cleared excerpt display. All require their own evidence contracts; none block this limited lexical engineering task. `scholarly_verified=false`, `redistribution_approved=false`, `valid_juristic_ruling=false`.
