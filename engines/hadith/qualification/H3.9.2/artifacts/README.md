# H3.9.2 artifacts

This directory contains **tracked preregistration and baseline state**, not cached claims of test success.

## Authoritative evidence

- Test/CI status: GitHub Actions workflow `.github/workflows/hadith-h392.yml`.
- Dataset qualification: regenerate `validation-report.json` with `python -m benchmark_campaign validate`.
- Freeze evidence: generated only after the real 1,280-case population qualifies.
- Final evaluation evidence: generated only after model lock and one-shot sealed-holdout evaluation.

Generated execution snapshots such as `SELF_TEST_REPORT.txt`, `PACKAGE_AUDIT.json`, and `validation-report.json` are intentionally not committed before a real freeze because they become stale as the validator and test suite evolve.

The checked-in red-state manifests/status files document that the campaign is not yet populated or qualified; they are not substitutes for runtime evidence.
