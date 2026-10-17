# Stage A heritage-first routing — primary maintainer audit

**Reviewed:** 2026-10-17. **GitHub account:** Alajmah. **Base:** `567e55858a9911a23430ef81f1e41b7a5f26480e`. **Reviewed pre-audit implementation HEAD:** `3f443c38ba41f35ddb82a9ad3261a9a605f5534f`. Primary review precedes any new Codex request. The audit-document commit must be checked separately at its own exact HEAD.

## Actual diff and bounded delivery

The complete compare with base before this audit contains **seven changed paths**: `core/source_policy/rights.py`, `core/source_policy/__init__.py`, `core/tests/test_heritage_rights_routing.py`, `docs/governance/HERITAGE_FIRST_SOURCE_POLICY.md`, `RIGHTS_NOTICE.md`, `.github/ISSUE_TEMPLATE/rights-report.yml` and `.github/workflows/mubin-inference-foundation.yml`.

This PR **adapts** the U0.6 archive's source-use declaration routing contract into a **minimal independent Stage A**. It is not a byte-for-byte transfer of the entire cumulative ZIP. It imports **no** `usage_log.py`, `intake.py`, Usul AST/rulebook, real source text, H3.9.2 artifact, P1 evidence, or reviewer credential.

## Invariants personally inspected

- A request declares `source_id`, `asset_layer`, claimed `basis`, evidence reference, intended use, purpose conditions and source-specific claim state; all facts remain **operator declarations only**.
- `public_domain` applies only to a distinctly identified, independently transcribed original text. A modern critical edition, database or private annotation never inherits the historical author's classification.
- The generic non-profit/statutory route permits only proportionate declared purposes. Full-text publication and dataset redistribution are **not authorized** under this route.
- `explicit_license` has an explicit scope tuple; merely having a `license:` label or old authorship does not grant further purposes.
- A pending/substantiated complaint returns `source_hold` for the **identified source**, while unrelated sources are processed independently. The module has **no corpus-acquisition or ingestion action**.
- `metadata_reference` is limited to public bibliographic **facts and links**. It does not clear transfer of an entire rights-protected data set.
- Input validation is bounded by declared field sizes, exact bool types, finite allowed enumerations, duplicate scope rejection, and rejection of Unicode control, unpaired surrogate, and directional-format controls that can visually spoof identifiers. Responses do not echo legal evidence.
- Output assurance is always `operator_declarations_only`. The word `proceed` is a **policy route**, not a verified copyright fact, publisher clearance, source custody receipt, scholarly attestation, AI event receipt or executable Usul rule.
- CI `pull_request` and `push` path filters include `core/**`, `docs/reviews/**`, `docs/governance/**`, `RIGHTS_NOTICE.md` and `.github/ISSUE_TEMPLATE/**`. The added regression test checks both event path lists.

## Reproduced failures and repairs

1. **Test-only commit `995ffd00e284bc19986b52f6a9e2460e957ee9b3`:** [Actions 39055563619](https://github.com/AIMubin/Mubin/actions/runs/39055563619) failed intentionally because `core.source_policy` did not yet exist (51 tests, 1 import error). The implementation and package were then added; [run 39055657553](https://github.com/AIMubin/Mubin/actions/runs/39055657553) passed **61/61**.
2. **Unicode spoofing negative test `399566f942544ef947a65f2cb1b1758a992e50ea`:** [run 39055761123](https://github.com/AIMubin/Mubin/actions/runs/39055761123) failed intentionally (62 tests, 3 subtest failures) on bidi/format/DEL controls in source/evidence IDs. `unicodedata.category` rejection fixed it in `7980acbbd76f3dac8a1ccf5ae3a7a4af041ab550` ([run 39055815717](https://github.com/AIMubin/Mubin/actions/runs/39055815717): green).
3. **Document-only change trigger test `dee8f7cc62cb0429a5513a9424b215b8a9711f63`:** [run 39056034208](https://github.com/AIMubin/Mubin/actions/runs/39056034208) failed intentionally (63 tests, 3 subtest failures): governance, notice and complaint template were absent in CI path filters. Updated both PR/push lists in `3f443c38ba41f35ddb82a9ad3261a9a605f5534f`; [run 39056081740](https://github.com/AIMubin/Mubin/actions/runs/39056081740) passed **63/63**.

## Threat model and residual gaps

- Caller can forge `basis`, `evidence_ref`, `source_attribution` or the `lawful_copy_provenance` bool; the helper cannot independently validate them. Production ingestion **must not** treat `proceed` as a trusted authorization signal.
- Legal jurisdiction and edition-specific rights are outside the unit-test scope; no particular book has been established as lawful to download, train on or redistribute. No full source corpus obtained.
- GitHub issue reporting is public and must not solicit confidential contracts, personally identifiable evidence or protected texts.
- The focus is synthetic contracts. Tests passing is **not** H3.9.2 human review or a valid fiqh inference. The source/family-disjoint frozen holdout gates remain untouched.
- The portable U0.6 archive also contains `intake.py`, POSIX private `usage_log.py`, and U0.1–U0.6 Usul engines/tests. They are **not in this PR** and must be imported as separate reviewed stages with their own CI.
- CI path filter coverage is asserted structurally; a **docs-only** or **template-only** future change still needs an empirical trigger check when available, as the workflow may be altered independently.

**Disposition:** The Stage A source-use **declaration routing only** is technically supportable for a secondary code review once the final audit HEAD's CI is green. Do **not merge** pending independent review, repository governance, and verification that no downstream code mistakes declarations for permission. The main version remains `0.1.0-alpha`.
