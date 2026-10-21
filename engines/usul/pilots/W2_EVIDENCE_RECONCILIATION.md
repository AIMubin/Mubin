# U0.1 — W2 three-view receipt arithmetic / digest erratum

Current status: **PRIVATE EVIDENCE RECONCILIATION REQUIRED**.

The historical final-audit receipt
corpus/reviews/u01-w2-three-representations-final-audit.json is immutable
historical evidence but has two verifiable recording errors:

1. Legacy Windows section: 1706 bytes; legacy LF-only section: 1700 bytes.
   Therefore **exactly 6 bytes of added CR**, not 10.
2. The 1706 vs 1696 overall delta is 10 bytes: **6 CRLF bytes + 4 LF-only
   legacy-vs-hardened formatting bytes**. Stage06 vs hardened: 1702−1696=6.
   The old "10 CR" narrative must not be used for merge approval.
3. The historical receipt truncates the Legacy Windows and Hardened SHA-256
   fields to 16 hex characters. Full 64-hex digests are mandatory for the
   new evidence receipt, never guessed. The complete Hardened source pin
   already exists in the earlier W1/W2 closure receipt.

## What is now automated

A pure stdlib verifier plus source replay is in
engines/usul/pilots/waraqat_w2_receipt_reconcile.py.

The verifier:

- Reads the PRIVATE pinned original W2 HTML and recomputes the three-view
  audit rather than trusting reported booleans.
- Compares the recomputed JSON data against the original private audit JSON.
- Checks the exact private audit file SHA-256 against the original archived
  receipt, protecting the chain of provenance.
- Verifies 1702/1706/1696 and 1700 arithmetic and both independent full
  pinned Stage06/Hardened digests.
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

Inspect the metadata-only output. It must show corrected_cr_added=6,
legacy_lf_minus_hardened=4, legacy_windows_minus_hardened=10,
stage06_minus_hardened=6, and all three full SHA-256 digests.

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
