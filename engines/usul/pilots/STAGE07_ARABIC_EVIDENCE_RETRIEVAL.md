# U0.1 Stage 07 — Arabic Evidence Retrieval across pinned Waraqat witnesses

**Current status:** `ENGINEERING_IMPLEMENTED_SYNTHETIC_CI_PASS` once CI is green; **real private two-witness Stage07 replay not yet recorded**. Stage 06's source-replay gate remains closed independently and is **reused** rather than reopened.

## Reference sources

- W1: *الورقات في أصول الفقه* — Imam al-Haramayn al-Juwayni, Bab al-Amr; <https://www.islamicbook.ws/asol/alwrqat.html>. Original HTML SHA-256 `66ec33c1825acdf82b3720f89d89aac15aa6e993356c0d90b41e53fe9a2fa044`, section SHA-256 `20879bade7a4a831a0020e1bae51806ca015d7803be42fdb44e580a9055581ab`. 22 lines, 1,232 bytes, W1 full UTF-8 export bytes [3735, 4967).
- W2: Digital comparator <https://www.islam.ms/ar/كتاب-ورقات-أصول-فقه-إسلامي-إمام-حرمين-عبد-الملك-الجويني/>. Original HTML SHA-256 `3c4de1baa99bad782b5fba066523ca9f12798525907edede93bd1046ef36f0fa`, extracted section SHA-256 `db181b1d9466389d2b5aeaf50362dd57e716cc1e36d041948777e3fe0c9c9358`, 1,702 bytes. W2 offsets refer **only to its pinned extracted section**, NOT the raw HTML or an imagined full-work text index.

The [local Stage06 closing receipt](../../../corpus/reviews/u01-stage06-waraqat-dual-witness-alignment.json) and its sources identify the independent capture/digest decisions. Stage07 [strict runner](waraqat_stage07.py) uses these frozen hashes, first invokes Stage06 with `verify_secondary_extraction=True`, then indexes both section files. An alternate source file or a freshly invented W2 hash cannot bypass that gate.

## Engine and explicitly separate results

[Arabic retrieval engine](../arabic_evidence_retrieval.py) has two output classes **for each query, in each witness**:

1. **`literal_exact_v1`**: strict, Unicode-sensitive text found directly in the original pinned UTF-8 section. No normalization.
2. **`ORTHOGRAPHIC_CANDIDATE_ONLY`**: additional possible matches discovered by explicitly selected, versioned transformations. Every match includes **original source byte offsets**, source line, column, original bytes SHA-256, line SHA-256 and profile ID. It is not proof of lexeme identity, shared meaning, a legal exception, or lack thereof.

| Optional fold profile | Changes used for a *diagnostic search only* |
| --- | --- |
| `ignore_arabic_marks_v1` | Ignores specified vocalization marks, **not** combining hamza above/below or madda |
| `ignore_arabic_marks_and_brackets_v1` | Above, plus removes literal `[` and `]` **delimiters only**, never words inside |
| `ignore_arabic_marks_brackets_and_spaces_v1` | Above, plus deletes a bounded set of whitespace characters for word-join **candidates** (e.g., `و أما` versus `وأما`) |

Profiles never normalize alef/hamza or tamper with negation, tatweel, word order, or bracket contents. Even harakat stripping can destroy meaning (for example, active versus passive forms). **Positive folded matches are just recall-oriented leads for later review**, and zero exact/folded matches do not mean `qarīnah` absent.

No source text, excerpts, or query literals appear as match content in output. The query's SHA and matches' original-span SHA permit private local replay. Source work/section locator metadata are deliberately retained; text appearing incidentally in a section title must not be interpreted as a returned excerpt.

Search is deliberately **single-line only**, so cross-line phrase matches are not inferred. It finds overlapping occurrences. If a query normalizes to empty, a matched set would exceed the hard bound, or metadata is invalid, it **fails closed**; it never silently truncates results.

### Position terminology

- `section_byte_start` and `section_byte_end_exclusive`: offsets from the beginning of the exact pinned **chapter file**.
- `source_byte_start` and `source_byte_end_exclusive`: for W1, the same original byte range plus the verified section-export base `3735`; for W2, offsets still refer to its **extracted section** only (base `0`).
- `section_line_number`: 1-based line inside the chapter file.
- `source_line_number`: W1 starts at line `86` of the original UTF-8 book export; W2 starts at line `1` of its dedicated section export.
- **No Stage07 offset claims to locate a corresponding byte in either source HTML.** HTML-to-text offsets require a separate extractor-level character provenance map.

## Local Windows execution using existing private Stage04–06 files

From `C:\AI\Mubin`, after `git pull --ff-only`, run:

```powershell
$root = "D:\MubinSources\waraqat"

python -m engines.usul.pilots.waraqat_stage07 `
  --primary-html "$root\waraqat-original.html" `
  --primary-export "$root\waraqat-private-utf8.txt" `
  --primary-manifest "$root\waraqat-draft-manifest.json" `
  --primary-section "$root\waraqat-bab-amr-private.txt" `
  --secondary-html "$root\witness2-original.html" `
  --secondary-section "$root\witness2-bab-amr-private.txt" `
  --queries "engines\usul\pilots\data\waraqat-stage07-queries.json" `
  --report "$root\stage07-arabic-retrieval-report.json"

Write-Host "Stage07 exit code: $LASTEXITCODE"
```

The published [Stage07 queries](data/waraqat-stage07-queries.json) are only short Arabic search keywords, plus a word-boundary diagnostic; they are **not** a complete taxonomy of diverting indicators. They use the exact `id/literal/candidate_profiles` schema. The optional profiles must appear in the documented order.

On real PASS: `STAGE07_DUAL_WITNESS_ARABIC_RETRIEVAL_PASS` (exit 0), with both Stage06 HTML-to-section replay checks true, and separate query match arrays for W1 and W2. Missing private captures: `PENDING_PRIVATE_WITNESS_FILES` (exit 3). Any changed source/hash, malformed query, ambiguous section or verification error: `FAIL` (exit 1). **These exit statuses concern engineering operations only.**

Run twice on the same frozen files. Check byte-for-byte identical JSON, verify every match's original bytes and hash using direct reads of the *private* section files, and check absence of source excerpts before publishing only a metadata-only closing receipt. **Do not fabricate the real-source match counts from Stage05's W1-only lexical results**; Stage07 profile effects and W2 may differ.

## CI, limitations and future work

```bash
python -m unittest discover -s engines/usul/tests -v
python -m unittest discover -s core/tests -v
```

[Generic regression suite](../tests/test_arabic_evidence_retrieval.py) and [real-runner contract tests](../tests/test_waraqat_stage07.py) use synthetic Arabic; they check UTF-8 byte offsets, reassembled indexes, stable report hashes, source-coordinate bases, hamza-safe diagnostics, harakat and editorial bracket matching, token-join candidates, negation integrity, malformed input, duplicate identifiers, and the non-circular frozen Stage06 gate.

**Not implemented or claimed:** morphology/stemming, orthographic equivalence adjudication, alternative edition authenticity, cross-line retrieval, semantic `qarīnah` classification, scholarly approval, fiqh inference, citation text republication rights, or broader work coverage. `scholarly_verified=false`, `redistribution_approved=false`, `semantic_qarinah_verified=false`, and `juristic_inference_allowed=false` throughout. Mubin remains `0.1.0-alpha` and `U0.1` remains `experimental_prototype_not_qualified`. Q0.3 and H3.9.2 are untouched.
