# H3.9.2 artifacts

This directory contains **tracked preregistration, baseline state, and compact content-addressed evidence references**. It does not treat cached test output as qualification evidence.

## Authoritative evidence

- Test/CI status: GitHub Actions workflow `.github/workflows/hadith-h392.yml`.
- Non-holdout source acquisition/index readiness: `NONHOLDOUT_ACQUISITION_EVIDENCE.json`, derived from the successful main acquisition workflow and containing hashes/counts only.
- Cumulative non-holdout primary evidence: `CUMULATIVE_PRIMARY_EVIDENCE_168.json`, derived from the successful schema-25 cumulative workflow and permanently binding the canonical primary prefix, outcome counts, cumulative-ledger hash, replacement-eligibility hash, and encrypted artifact identity.
- Dataset qualification: regenerate `validation-report.json` with `python -m benchmark_campaign validate`.
- Freeze evidence: generated only after the real 1,280-case population qualifies.
- Final evaluation evidence: generated only after model lock and one-shot sealed-holdout evaluation.

The acquisition evidence record is deliberately small and permanent because the underlying GitHub Actions artifact is temporary. It records the pinned main commit, workflow run, artifact digest, verified source count, index hash/count, and ephemeral Curator-task hash/count. It contains **no source text, segment text, Curator task payloads, or gold labels**.

The cumulative primary evidence record follows the same permanence rule. It records the canonical campaign run IDs, exact primary coverage, redacted outcome/reason counts, GitHub artifact digest, redacted-summary hash, encrypted cumulative bundle hash, cumulative-ledger hash, and replacement-eligibility hash. It contains **no source text, gold payloads, model identity, plaintext adjudication data, or plaintext reviewed records**. The source-bearing cumulative bundle remains encrypted.

Generated execution snapshots such as `SELF_TEST_REPORT.txt`, `PACKAGE_AUDIT.json`, and `validation-report.json` are intentionally not committed before a real freeze because they become stale as the validator and test suite evolve.

The checked-in status remains a red-state qualification record until the source-grounded cases are actually curated, independently verified/adjudicated, frozen, and evaluated.
