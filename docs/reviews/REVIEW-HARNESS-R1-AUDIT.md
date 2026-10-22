# R1 Primary review and adversarial security audit — automated review packet harness

**Date:** 2026-10-18. **Branch:** `feat/automated-review-harness-r1-20261018`.
**Base:** `main` `567e55858a9911a23430ef81f1e41b7a5f26480e`.
**Reviewed implementation HEAD before this audit file:** `5801a0c6c53ee47b3d9f6c8e5315238b3df03dd9`.
**Project context:** PR #71 (draft). No merge or release requested.

## Functionality and exact trust bounds

- R1 is an **offline, deterministic reader and review-plan generator**. It does not call LLMs, fetch an actual PR diff or checks from GitHub, invoke Codex, grade a historical Islamic text, adjudicate a reviewer identity, or authorize main-branch merges.
- JSON Schema Draft 2020-12, exact builtin-container checks, bounded depth/count/string limits, escaped-path controls, and Linux no-follow regular file reads are applied before deriving statuses. Duplicate JSON object members and nonfinite numbers are rejected.
- `inferred_tier` is a **minimum tier derived from untrusted declared paths and impact labels**. Protected H3.9.2 paths and authoritative/rights/release/identity tags force T3 even if the packet claims only documentation. Actual Git diff scope is unverified, so tiers cannot serve as approval evidence.
- `claimed_run_url` and reviewer-envelope fields are **unverified assertions**, despite syntax and HEAD binding. `PASS_SCOPED_UNVERIFIED` is structural packet completeness only; `FAIL_REPORTED` is a claim, not an independently reproduced failure.
- Every outcome retains `eligible_for_auto_merge=false`, `eligible_for_release=false`, `eligible_for_engine=false`, `rights_verified=false`, `scholarly_authority_verified=false`, `independent_execution_verified=false`, `ci_head_verified=false`, and `h392_gold_eligible=false`.
- The `--mode plan` task list is a non-executable contract for three future isolated external review channels; no reviewed model result or agent execution occurs here.
- Public U0.2–U0.5 defect classes are illustrative *development* examples. They are not a held-out review benchmark, don't replay broken code, and cannot substantiate reviewer detection recall.

## RED-first evidence and correction

1. First test-only commit `a017cec49688be56431790149c910aa9fdaa0e48` intentionally imported a missing package. [P0 CI #39105467493](https://github.com/AIMubin/Mubin/actions/runs/39105467493) failed as planned, **51 discovered tests / 1 import error** (`ModuleNotFoundError: core.review_harness`).
2. Initial implementation `fd368b149980c19347291b27e52cd01031e33404` passed [R1 CI #39105538889](https://github.com/AIMubin/Mubin/actions/runs/39105538889) and [P0 #39105538725](https://github.com/AIMubin/Mubin/actions/runs/39105538725): **40 R1 tests** plus core tests.
3. Primary maintainer found Python regex `$` can permit a final `\n` in nominally exact SHA, run URL, and attempt IDs. RED-only test commit `f63270e46f2f8891d6243272e1830cb0f37f7f6c` reproduced the defect in [R1 CI #39105660189](https://github.com/AIMubin/Mubin/actions/runs/39105660189): **41 R1 tests, 2 failures**; [P0 #39105660154](https://github.com/AIMubin/Mubin/actions/runs/39105660154) also failed. Real findings were observed before repair.
4. Repair commit `5801a0c6c53ee47b3d9f6c8e5315238b3df03dd9` added `re.fullmatch` controls for the exact commit hash, claimed CI URL and attempt IDs. It also corrected the public U0.4 calibration case to point to the *actual digest/parent-state error* instead of incorrectly describing a speaker-role fix as a RED defect. [R1 CI #39105781764](https://github.com/AIMubin/Mubin/actions/runs/39105781764) succeeded: **41/41 focused tests**, and **91/91 core tests**; [P0 #39105781741](https://github.com/AIMubin/Mubin/actions/runs/39105781741) passed.
5. After adding this audit document, **verify the new exact HEAD** in both workflows. Do not claim the implementation-only HEAD run validates the amended audit HEAD.

## Remaining gaps and non-goals (explicit NO-GO for auto-accept)

- No authenticated git diff, branch protection/ruleset verification, model execution receipt, reviewer independence proof, real second-party code review, or dynamic fuzzing of live PR code is implemented. Multiple envelopes claiming different channels can originate from one adversary; they cannot authorize merges.
- No source corpus was downloaded or qualified; no quote, printed edition, copyright license, fiqh ruling or religious authority was validated. H3.9.2 Schema-31 and its 158 pending human decisions remain unchanged.
- The CLI's Linux `O_NOFOLLOW` protection is not a cross-platform attestation or substitute for actual CI/GitHub protection. The validator cannot prove that the submitted changed paths are complete. Review descriptions and external evidence strings may be adversarial.
- The public calibration cases are training examples, not independent detection results. Future R2 requires trusted GitHub facts, isolated real model invocations, reproducible counterexamples, and a separate non-H3 holdout test set.
- Project status remains in the ChatGPT Mubin Library (`/Mubin/PROJECT_STATUS.md`); GitHub stores implementation evidence only.

**Independent review status:** `codex_review=not_performed_for_r1_head`; Codex is not an available connected review action in this session. Historical quota exhaustion on U0.2 does not mean this R1 HEAD was externally reviewed. This is an extra **maintainer-only** adversarial audit, not a second-party security assessment.

**Disposition:** R1 may be used as a **non-authoritative local research/engineering intake tool only**, contingent upon passing exact final-HEAD CI. Keep PR #71 a draft, do not merge into the unprotected `main`, and do not represent the tool as a fully autonomous AI review system.
