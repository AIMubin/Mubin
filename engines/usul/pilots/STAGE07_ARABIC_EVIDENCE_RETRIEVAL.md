# U0.1 Stage 07 — Arabic Evidence Retrieval across pinned Waraqat witnesses

**Current status:** `STAGE07_DUAL_WITNESS_ARABIC_RETRIEVAL_PASS` was **reported by the private Windows operator** and preserved in [the Stage07 metadata-only closing receipt](../../../corpus/reviews/u01-stage07-waraqat-arabic-retrieval.json). The independently observed GitHub CI verifies synthetic engineering behavior on Windows and Ubuntu, not a second replay of the private HTML captures. Stage 06's established source-replay gate is **reused**, not reopened.

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

For any future rerun, execute twice on the frozen files, compare byte-identical JSON, and revalidate every match against the private original sections. **The operator reported completing this exact replay** with two-run SHA-256 `5978af72c27a6835bf04a5e32c1eeff038c57008effd7459d914870b5e92bdc0`; the original HTML/UTF-8 bytes remain outside GitHub. Stage07 counts cannot be inferred from Stage05's W1-only literal search.

## CI, limitations and future work

```bash
python -m unittest discover -s engines/usul/tests -v
python -m unittest discover -s core/tests -v
```

[Generic regression suite](../tests/test_arabic_evidence_retrieval.py) and [real-runner contract tests](../tests/test_waraqat_stage07.py) use synthetic Arabic; they check UTF-8 byte offsets, reassembled indexes, stable report hashes, source-coordinate bases, hamza-safe diagnostics, harakat and editorial bracket matching, token-join candidates, negation integrity, malformed input, duplicate identifiers, and the non-circular frozen Stage06 gate.

**Not implemented or claimed:** morphology/stemming, orthographic equivalence adjudication, alternative edition authenticity, cross-line retrieval, semantic `qarīnah` classification, scholarly approval, fiqh inference, citation text republication rights, or broader work coverage. `scholarly_verified=false`, `redistribution_approved=false`, `semantic_qarinah_verified=false`, and `juristic_inference_allowed=false` throughout. Mubin remains `0.1.0-alpha` and `U0.1` remains `experimental_prototype_not_qualified`. Q0.3 and H3.9.2 are untouched.


## 2026-10-21 — closure on the locally pinned W1 and W2 captures

The [Stage07 metadata-only closing receipt](../../../corpus/reviews/u01-stage07-waraqat-arabic-retrieval.json), committed in [`0d2cf97`](https://github.com/AIMubin/Mubin/commit/0d2cf97d7a63e471322e7c39a272a9669f809749), records the real-source runner status `STAGE07_DUAL_WITNESS_ARABIC_RETRIEVAL_PASS`, after W1 and W2 Stage06 strict HTML-to-section replay. It records SHA-256s of both raw captures and pinned chapters, W1 index of **22 lines/1,232 bytes** and W2 index of **16 lines/1,702 bytes**, original coordinate-basis distinctions, negative tests and repeatable JSON.

Operator-reported literal counts for six queries:

| Query | W1 literal | W2 literal | W2 fold-only candidates by selected profile |
| --- | ---: | ---: | --- |
| الأمر | 6 | 1 | 5 / 5 / 5 |
| القرينة | 1 | 0 | 1 / 1 |
| الوجوب | 1 | 0 | 1 / 1 |
| الندب | 1 | 0 | 1 / 1 |
| الإباحة | 1 | 0 | 1 / 1 |
| و أما | 1 | 0 | 0 / 0 / 1 |

There were **12 literal occurrences total (W1 11; W2 1)**. Fold candidate counts are **per profile** and overlap; adding the 5/5/5 numbers does not represent 15 distinct source occurrences. The single W2 `و أما` word-join candidate arose **only after the spaces fold**, as expected for a word-boundary diagnostic and never a lexical/semantic equivalence certification.

The [`bbeefb353` source baseline](https://github.com/AIMubin/Mubin/commit/bbeefb35320fd67d124837f00caa9351991726a3) passed [Usul CI 39548101731](https://github.com/AIMubin/Mubin/actions/runs/39548101731) with **160/160 tests on both Ubuntu and Windows**. The closure-only [`0d2cf97` commit](https://github.com/AIMubin/Mubin/commit/0d2cf97d7a63e471322e7c39a272a9669f809749), touching only `corpus/reviews`, passed [Corpus CI 39550460703](https://github.com/AIMubin/Mubin/actions/runs/39550460703) **62/62 on both OSes**. GitHub's path-filtered Usul workflow did not execute on that review-only commit.

**Acceptance boundary:** The Stage07 *source capture → frozen extraction → literal and folded retrieval* workflow is locally attested. Synthetic public CI independently tests its software. Source edition and rights, full book coverage, equivalence of the two witnesses, semantic qarīnah identification and legal deduction remain **unverified**: `scholarly_verified=false`, `redistribution_approved=false`, `semantic_qarinah_verified=false`, `juristic_inference_allowed=false`, `public_fatwa_authorized=false`. A hash pinned by an operator is not a cryptographic signature and not independent scholarly authentication.

**Stage 08 handoff — Evidence Context & Citation Graph:** assemble source-addressed, context-limited evidence nodes and edges tied to verified original section spans, with the retrieved textual occurrence kept separate from normalized search candidates, P0 rule bindings, objections and semantic attestations. No absent-match→absent-qarīnah inference. Keep scope on Bab al-Amr until independently pinned chapter snapshots are available for expanded coverage.
