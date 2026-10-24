# Quran single-PR merge-readiness advisory v2

**Research/engineering only.** The original #73 → #74 → #75 → #76 stacked-chain readiness audit is *historical*. PR #73 and #74 merged, the Q0.1c content was incorporated into main, and the Q0.1d comparator was extracted into independently reviewed PR #89 and merged as `69f9c823ef14495218bf08ec86e28b1187a4fe89`. Do not use the original hard-coded chain to decide readiness for the newer decomposition PRs.

## Purpose

`qa.quran_merge_readiness` now evaluates **one explicitly numbered pull request** targeting `main`. It is advisory-only and read-only. This is not a GitHub Rulesets evaluator, merge bot, branch-protection substitute, repository release gate, scripture source audit, or independent scholarly review.

The local deterministic `assess_pr(snapshot, number)` function treats caller-supplied JSON as **untrusted** and always returns `merge_ready=false`, `eligible_for_auto_merge=false`. Even a crafted snapshot with all green CI and an independent approval cannot turn those fields true. `fetch_live` retrieves current GitHub metadata through a fixed host and restricted GET paths, rejects redirects, bounds JSON and rechecks both the main SHA and PR head/base/status at the end of the live fetch. A concurrently changed PR is refused rather than silently evaluated against an obsolete head. The CLI labels the live source only after retrieval.

### Checks covered

- Requested PR number, open/non-draft status, own-repository head and base, direct target `main`, and exact current main SHA.
- Fresh `main...head` compare: no behind commits, at least one ahead.
- Bounded complete first-page GitHub check-run list: all **observed** check runs must report `completed/success` against the head SHA.
- Fresh exact-HEAD `APPROVED` review by somebody other than the PR author (advisory only).
- Notices about `main.protected`, missing independent approvals, duplicate check names, and unverified Rulesets/review-thread state.

**Important limitations:** A list of successful checks cannot prove that every *required* check was configured or executed. `REQUIRED_CHECK_COVERAGE_NOT_ATTESTED` always appears when the check list is otherwise usable. Real branch rulesets, unresolved inline threads, CODEOWNERS, and Codex review-summary comments must be consulted separately. `conditionally_unblocked` only means this narrowly observed subset has no blockers, never permission to merge.

### Run

```bash
python -m unittest core.tests.test_quran_merge_readiness -v
python -m qa.quran_merge_readiness --pr 89 --json
```

Use an **open** PR number for the second command; #89 is an example of the historic identifier and may already be merged, in which case the tool should report that it is not eligible for open-PR assessment. `GITHUB_TOKEN` is optional; if used, keep it in the process environment and do not print it. The tool performs no GitHub writes, source downloads or modifications and never echoes HTTP error bodies.

On GitHub Actions, synthetic tests run on Windows and Ubuntu. A separate read-only live advisory is allowed to fail without blocking unrelated engineering because API rate limits and permissions can make the snapshot temporarily unavailable. For manual dispatch, provide the PR number. Exact-HEAD project CI and the required independent reviews still need to be checked before any actual merge.

**No promotion:** `source_authenticated=false`, `scholarly_verified=false`, `rights_verified=false`, `juristic_inference_allowed=false`, `public_fatwa_authorized=false`. No system version change from `0.1.0-alpha`.
