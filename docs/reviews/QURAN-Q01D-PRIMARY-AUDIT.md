> Historical self-review from the original PR #76 branch, retained for traceability. Its reviewed HEAD `4c538a9` is **not** the new isolated extraction HEAD. The extracted PR must undergo new exact-head tests and review before merge. This document does not attest that new review.

# Quran Q0.1d — first-party maintainer engineering audit

**Review date:** 2026-10-18. **Reviewed implementation HEAD:** `4c538a90415519a5cb2ab98cb66f4e68a80a6af7`.
**Branch:** `feat/quran-q01d-source-comparator-20261018`; **PR:** [#76](https://github.com/AIMubin/Mubin/pull/76), draft and unmerged; **base:** Q0.1c PR #75 at `c1963bbc0def8c75a511d7c64b0d62f98b9848bb`.
**Mubin overall release:** `0.1.0-alpha`; canonical `main` unchanged by this PR.

## Scope and limitations

`engines/quran/q01d/compare.py` is a **read-only, offline, bounded comparison mechanism** between an independently Q0.1b byte/Git-blob pinned *unverified GitHub mirror* and a second **untrusted, operator-supplied** UTF-8 source-like file. The comparator does not make network requests or generate new source files. Output contains sha256 digests, coordinate-only changed references (bounded; total count untruncated), and three result classes: `byte_identical`, `verse_equal_bytes_different`, `verse_text_differs`. A mismatched, duplicate, missing or reordered verse structure **fails closed**; it is never silently adjusted.

No official text supplied directly by Tanzil was downloaded, independently pinned, or matched in this stage. The developer cannot infer that a user-supplied second file is an official publisher export from its name, footer, content, hash, URL or assertion. Even **exact byte equality** means only `candidate==already_pinned_mirror` and all results set `source_authenticated=false`, `official_candidate_attested=false`, `candidate_publisher_provenance_verified=false`, `rights_verified=false` and `eligible_for_religious_ruling=false`.

This tool is not a legal license auditor, a recitation validator, a verified mushaf, a tafsir tool, a fiqh/Usul rule authorizer or a human scholarly review. Do not include downloaded Quran text in repository commits, CI artifacts, request logs or developer fixtures. The existing Tanzil attribution/copyright footer is preserved in the original mirror bytes and should be shown in the existing local reader, not re-authored by Q0.1d.

## Primary review — attacks, invariants, possible deferrals

- **Mirror custody:** `load_raw` enforces the versioned Q0.1b mirror manifest, exact raw size, SHA-256, and Git-blob SHA-1. A malicious operator cannot label a synthetic file the fixed GitHub mirror by swapping only a SHA-256 field.
- **Candidate input:** byte size bounded to 4 MiB; strict UTF-8; no BOM, CRLF or absent terminal LF. Verse rows use three delimited fields with strict increasing canonical numbers, no duplicates, Arabic text requirement and length caps. A terminal comment block is accepted only after source rows, with footer line and blank-line count limits. **Header comments** are rejected for this `txt-2`-like format; other official export presets may need a versioned adapter instead of heuristic parsing.
- **No editorial laundering:** mismatch reports show coordinates and digests only, never silently normalized Arabic, corrected words, empty conclusion as authenticated official text, or text content in CI. Differing sources may reflect exporter options (pause signs, sajda, rub, tatweel, basmala and copyright footer) rather than corrupted scripture. A raw equality boolean is not independent edition authenticity.
- **Untrusted identity:** user-provided source does not become official when matching the pinned *mirror*. No registration of real human scholars, human credentials, provider signatures, or AI reviewer signoffs. No use of frozen H3.9.2 assets.
- **Safe CLI:** bounded regular-file reads inherited from Q0.1b, exit `0` for *structurally comparable*, `1` invalid comparison, `2` unsafe/missing local file. No downloader, data write endpoint, auto-merge, public networking or verdict about Quran source rights.
- **Known residual:** the comparison cannot verify operator custody/HTTPS/Tanzil export settings; official-source external download is still absent. Header comments/alternative official formats intentionally fail closed until specified. Browser-level UI tests are a different test domain and are **not performed** by this PR. CI checks a *self-comparison only*, not a verified official-vs-mirror pair.

## RED-first and exact implementation CI

1. Test-only `eb093391d53e6e229a9a6b623e22cf0e3eaaf0f4`: [P0 run 39137629427](https://github.com/AIMubin/Mubin/actions/runs/39137629427) **failed as intended** at import `ModuleNotFoundError: No module named 'engines.quran.q01d'`; 109 tests / one missing-module error before implementation.
2. Implementation `4c538a90415519a5cb2ab98cb66f4e68a80a6af7`: [Q0.1d 39137933575](https://github.com/AIMubin/Mubin/actions/runs/39137933575), [Q0.1 39137933446](https://github.com/AIMubin/Mubin/actions/runs/39137933446) and [P0 39137933445](https://github.com/AIMubin/Mubin/actions/runs/39137933445) **all successful**. Q0.1d runner reported **118/118 core tests** and 6,236-verse **self-comparison** `byte_identical` with SHA-256 `f64fe7657dbe2e185e9995e14f7a67ee6cf1a30773f39184883d7a763d70fb19`, with `candidate_publisher_provenance_verified=false`, `rights_verified=false`.
3. **Audit-document final HEAD requires its own fresh CI.** Do not cite earlier green test runs as evidence for a later changed HEAD; record final runs after this document is committed in the PR body and external portfolio register.

## Review status and merge decision

Primary maintainer inspection only; `codex_review=unavailable`, consistent with the separately recorded project quota limitation. No independently executed secondary AI review, no external scholarly certification. Keep **draft/unmerged** until ordinary engineering PR review and branch protection requirements; do not change `VERSION.yaml` or protected Hadith qualification gates.

Next steps proceed **in parallel**, not as blocking requirements for Quran reader feature development: operator-provided exact official Tanzil v1.1 text export with recorded preset and source custody, run this comparator against the pinned mirror, and inspect any reported differences; separately test the local RTL browser in a real browser. Official source validation may require a distinct signed/attested provenance chain and a rights check before external publication.