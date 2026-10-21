# U0.1 — W2 three-view receipt arithmetic / digest erratum

Current status: **PRIVATE EVIDENCE RECONCILIATION REQUIRED**.

The historical final-audit receipt at
corpus/reviews/u01-w2-three-representations-final-audit.json is immutable.
The independent private replay recorded in the later failed receipt at
corpus/reviews/u01-w2-three-representations-reconciliation-erratum.json
found a **historical, manually inferred field**: 1700 LF-only bytes.
The privately measured value is **1696** (10 LF linefeeds) and its SHA-256
matches the independently frozen hardened W2 section pin.

Observed true accounting:

| representation | bytes | difference |
| --- | ---: | --- |
| Stage06 HTMLParser | 1702 | 6 extra LF relative to hardened |
| Legacy full-book Windows file | 1706 | 10 CR bytes added by Windows text-mode write |
| Legacy full-book LF-only serialization | 1696 | byte-identical to hardened |
| Hardened full-book LF-only serialization | 1696 | independently frozen digest |

The *old* receipt incorrectly said legacy LF-only was 1700, which created
a false arithmetic narrative of 6 CR + 4 LF formatting bytes. The actual
source replay proves **10 CR + 0 LF formatting bytes**, plus Stage06's
separate 6 LF extra paragraph separators.

**Do not mutate the historical record.** The reconciler now permits only
this exact documented 1700→1696 error, and only if the private audit JSON
matches an independently replayed pinned W2 HTML source and its original
private-report digest matches the frozen receipt. The addendum preserves
both recorded and corrected values and publishes full SHA-256 values.

## What is now automated

A pure stdlib verifier plus source replay is in
engines/usul/pilots/waraqat_w2_receipt_reconcile.py.

The verifier:

- Reads the PRIVATE pinned original W2 HTML and recomputes the three-view
  audit rather than trusting reported booleans.
- Compares the recomputed JSON data against the original private audit JSON.
- Checks the exact private audit file SHA-256 against the original archived
  receipt, protecting the chain of provenance.
- Verifies 1702/1706/1696 against the 1696-byte **measured** legacy LF
  serialization, 10 LF→CRLF translations and both independent full
  pinned Stage06/Hardened digests. The historical 1700 field is preserved
  as evidence of the error, not treated as truth.
- Checks all 3 pairwise token, nonempty-line and nonwhitespace codepoint
  equality profiles.
- Requires 64-digit SHA-256 for the reconstructed Legacy Windows digest
  and all other digests.
- Creates a NEW metadata-only erratum. The original receipt stays untouched.
- Fails closed to a status-only output on any mismatch.

## Operator run on private files

From the up-to-date feature branch, while in the repository root:

    $root = "D:\MubinSources\waraqat"
    python -m engines.usul.pilots.waraqat_w2_receipt_reconcile --raw-html "$root\witness2-original.html" --private-audit "$root\w2-three-representations.audit.json" --previous-receipt "corpus\reviews\u01-w2-three-representations-final-audit.json" --out "$root\u01-w2-three-representations-reconciliation-erratum.json"
    if ($LASTEXITCODE -ne 0) { throw "Evidence reconciliation failed" }

Expected status: EVIDENCE_RECONCILIATION_PASS.

Inspect the metadata-only output. It must show measured_cr_added=10,
legacy_lf_minus_hardened=0, legacy_windows_minus_hardened=10,
stage06_minus_hardened=6, archived_legacy_lf_only_bytes=1700,
measured_legacy_lf_only_bytes=1696 and all three full SHA-256 digests.

After verifying no source text or private locations were included, copy ONLY
this JSON receipt to:

    corpus/reviews/u01-w2-three-representations-reconciliation-erratum.json

Commit the new additive receipt to the feature branch. Do NOT revise the old
report silently; retain its provenance for auditability.

## Final approval gate

Re-run Usul and Corpus/core tests and verify both GitHub CI jobs succeed on
the final commit. Update PR #79's stale title/body to cite the complete
reconciliation receipt, leaving it Draft and not merged until explicit
maintainer approval.

Scholarly and semantic qualifications remain false. The 16 chapters with
textual differences are a separate textual research docket.
