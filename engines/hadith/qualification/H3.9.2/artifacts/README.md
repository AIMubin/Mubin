# H3.9.2 artifacts

This directory contains **tracked preregistration, baseline state, and compact content-addressed evidence references**. It does not treat cached test output as qualification evidence.

## Authoritative evidence

- Test/CI status: GitHub Actions workflow `.github/workflows/hadith-h392.yml`.
- Non-holdout source acquisition/index readiness: `NONHOLDOUT_ACQUISITION_EVIDENCE.json`, derived from the successful main acquisition workflow and containing hashes/counts only.
- Historical cumulative checkpoint: `CUMULATIVE_PRIMARY_EVIDENCE_168.json`, permanently binding the canonical 0..167 prefix and its schema-25 cumulative ledger.
- Final external-critical-commentary primary batch evidence: `PRIMARY_BATCH_EVIDENCE_168_210.json`, binding successful campaign run `37426135905`, all six shard artifact digests, exact 168..209 coverage, and the redacted aggregate summary.
- Authoritative 210-primary cumulative evidence: `CUMULATIVE_PRIMARY_EVIDENCE_210.json`, derived from successful cumulative run `37471731102` and permanently binding the exact 0..209 prefix, normalized cumulative outcome/reason counts, cumulative-ledger SHA-256, replacement-eligibility SHA-256, and encrypted artifact identity.
- Schema-26 post-consolidation preparation evidence is **not yet checked in**. After the preparation workflow succeeds, only its redacted binding/summary hashes and encrypted private-map identity should be frozen here; raw task IDs, slot IDs, nonces, or plaintext private maps must never be committed.
- Dataset qualification: regenerate `validation-report.json` with `python -m benchmark_campaign validate`.
- Freeze evidence: generated only after the real 1,280-case population qualifies.
- Final evaluation evidence: generated only after model lock and one-shot sealed-holdout evaluation.

The acquisition evidence record is deliberately small and permanent because the underlying GitHub Actions artifact is temporary. It records the pinned main commit, workflow run, artifact digest, verified source count, index hash/count, and ephemeral Curator-task hash/count. It contains **no source text, segment text, Curator task payloads, or gold labels**.

The cumulative primary evidence record follows the same permanence rule. It records the canonical campaign run IDs, exact primary coverage, redacted outcome/reason counts, GitHub artifact digest, redacted-summary hash, encrypted cumulative bundle hash, cumulative-ledger hash, and replacement-eligibility hash. It contains **no source text, gold payloads, model identity, plaintext adjudication data, or plaintext reviewed records**. The source-bearing cumulative bundle remains encrypted.

The primary-batch evidence record preserves the successful 42-task campaign boundary separately from cumulative evidence. Its `40 promoted / 129 adjudication / 41 skipped` totals were pre-consolidation accounting. `CUMULATIVE_PRIMARY_EVIDENCE_210.json` now independently reproduces those totals from the provenance-bound cumulative ledger and establishes **41 replacement-eligible terminal primaries** while keeping all **129 pending adjudications** replacement-ineligible. Reserve reconciliation remains disabled.

Generated execution snapshots such as `SELF_TEST_REPORT.txt`, `PACKAGE_AUDIT.json`, and `validation-report.json` are intentionally not committed before a real freeze because they become stale as the validator and test suite evolve.

The checked-in status remains a red-state qualification record until the source-grounded cases are actually curated, independently verified/adjudicated, frozen, and evaluated.
