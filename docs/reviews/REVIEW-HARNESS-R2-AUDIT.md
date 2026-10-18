# R2 primary maintainer audit — live GitHub observation without approval laundering

**Date:** 2026-10-18. **Development PR:** #72 (draft, stacked on open R1 #71).
**Base HEAD:** R1 `3ded57a44ea2fa1bab5a9a4e30a191f17f07eab9`.
**Reviewed implementation HEAD:** `a154baa0db17b90fa357cf938d7d82a814cf8814`.
**Project version:** `0.1.0-alpha` on untouched `main` SHA `567e55858a9911a23430ef81f1e41b7a5f26480e`.
**Formal scientific/rights/merge authority:** none. Secondary Codex review not performed for this R2 HEAD; prior U0.2 #67 recorded quota exhaustion. This is maintainer-only adversarial audit, not an independently approved security test.

## Diff and project boundaries

Changed files before this audit: `core/review_harness/github_live.py`, `core/review_harness/github_cli.py`, `core/tests/test_review_harness_r2.py`, `.github/workflows/mubin-review-harness-r2.yml`, `docs/research/REVIEW-HARNESS-R2.md`.

No modifications to H3.9.2 sealed data, source rights/editions, P0 inference graphs, Usul U0.1–U0.5, system `VERSION.yaml` or `main`. The record-of-work remains `/Mubin/PROJECT_STATUS.md` in ChatGPT Library, not GitHub.

## Primary algorithm/semantics/security review

- **Trust boundary:** live observations are retrieved from allowlisted `https://api.github.com/repos/AIMubin/Mubin/...` GET endpoints, exclusively for the requested same-repo open PR. `expected_head_sha` binds a workflow event to the exact PR HEAD, rejects stale events or base/head aliases, and checks the PR's canonical numeric identity.
- **Least privilege:** client makes no writes. Workflow permissions are `contents:read`, `pull-requests:read`, `actions:read`, and does not submit comments, dispatch agents, or enable auto merge. Redirects and off-domain paths are forbidden; requests time out in 8s, bound response JSON to 1 MiB, reject duplicate members/nonfinite numbers/invalid UTF-8/cycles/overdeep objects. Secrets, diff code bodies and raw workflow logs are never printed by the CLI.
- **Complete changed paths within R2 bound:** all changed filenames must exactly match provider-declared `changed_files` (1..100), and rename source+destination paths are both classified. Renaming a protected H3.9.2 holdout into an innocuous-looking `.md` still yields T3. Overlong PRs are not silently clipped to a low-risk decision; they receive explicit unsupported/hold disposition.
- **Workflow identity binding:** exact expected HEAD, name, path, PR event, source and head repo, integer run ID, and canonical GitHub run URL are checked. A reported success requires `completed/success` from the observed run. The latest run by ID wins; missing/running/inconclusive runs never green. Run-page truncation suppresses successful verification. An actual GitHub workflow-run success is **not** evidence of successful underlying test semantics, source authentication or review independence.
- **Tier policy:** T0/T1 have advisory `FAST_LANE_READY` only after observed, matching selected workflow metadata. Injected fixtures can only yield `FAST_LANE_CANDIDATE`, never an attested CI result. T2/T3 continue in `PARALLEL_REVIEW_QUEUE` as **research/development**, not authorized release. A failed selected workflow becomes `FAIL_REPORTED`, missing/running CI becomes `WAIT_FOR_CI` but still permits independent engineering. Every result hardcodes `eligible_for_auto_merge=false`, `eligible_for_release=false`, no AI invocations, no legal/scholarly/H3.9.2 authority.
- **Process-local provenance safeguard:** primary red-green finding: R2 originally trusted a mutable `metadata_provenance` string in a caller-supplied snapshot, allowing a mock to claim `ci_head_verified=true`. The repaired code issues a non-serializable, process-local live transport capability only on the built-in GitHub client path. Forged/copyable JSON strings cannot mint that capability. This is *not* a cryptographic signed receipt and does not protect from code-level process compromise or an untrusted runner.
- **Scientific/adjudication boundaries:** nothing in R2 establishes a valid Qur'an/Hadith/Usul/Fiqh rule, source/edition, legal reuse right, reviewer identity, institutional approval or a human decision under frozen H3.9.2 Schema-31.

## RED → GREEN evidence from real GitHub Actions

1. Test-only HEAD `cb6c9e6ff31dee4ed7f15e0a2004b0d494ed6604`: [P0 RED #39107773313](https://github.com/AIMubin/Mubin/actions/runs/39107773313) — import failure for the deliberately missing `core.review_harness.github_live` module, **92 tests / 1 expected import error**.
2. Implementation HEAD `f3e5b0580330cbd3d82258a4ecfc941aa411b968`: [R2 CI #39108285787](https://github.com/AIMubin/Mubin/actions/runs/39108285787), [R1 CI #39108285771](https://github.com/AIMubin/Mubin/actions/runs/39108285771) and [P0 CI #39108285674](https://github.com/AIMubin/Mubin/actions/runs/39108285674) succeeded. R2 executed **16 focused and 107 cumulative tests** and successfully made actual GitHub API reads: PR #72, HEAD, changed paths, workflow statuses. Because P0 was running at lookup time it accurately returned `WAIT_FOR_CI`, not false green.
3. Maintainer attack test-only HEAD `254666a6f8af7175bafeac80b76ecb78114680ff`: [R2 RED #39108445188](https://github.com/AIMubin/Mubin/actions/runs/39108445188) reproduced a **provenance label spoof** (`17 tests / 1 expected failure`); P0 and R1 likewise RED.
4. Repaired implementation `a154baa0db17b90fa357cf938d7d82a814cf8814`: [R2 CI #39108540248](https://github.com/AIMubin/Mubin/actions/runs/39108540248), [R1 CI #39108540230](https://github.com/AIMubin/Mubin/actions/runs/39108540230), and [P0 CI #39108540397](https://github.com/AIMubin/Mubin/actions/runs/39108540397) succeeded: **17 focused, 108 cumulative tests**, live GitHub API still working and faithfully reporting temporarily pending P0.
5. On the **audit file commit HEAD**, recheck full R2/R1/P0 CI before claiming complete exact-head verification. Prior HEAD success is not an admission after a new commit.

## What remains and nonblocking continuation

- **R3:** exact GitHub check-job/step evidence and patch-bounded reads, actual isolated model reviewer execution with authenticated provider/model/config/time receipts, independently replayed defect detections on source/family-disjoint non-H3.9.2 challenge sets, escalation calibration. No performance metrics for AI detection have yet been measured.
- **Technical exception:** for current R2, a PR with >100 changed GitHub files is unsupported; per-file file list overcounts not silently truncated. Fork PRs are also unsupported. Both are explicit scope boundaries, not hidden fast-lane passes.
- **Portfolio priority:** further review-framework construction should not block Quran Q0.1/P1 source-verification integration, H4 research or Fiqh sandbox development on separate branches. Real scholarly/legal publication authority remains a separate release gate; engineering milestones may proceed without it.
- **No direct merge:** both R1 #71 and R2 #72 stay draft and unmerged until independent/code-policy merge prerequisites (incl. Issue #54 branch protection) are handled. Do not fabricate a Codex second-party review if unavailable.