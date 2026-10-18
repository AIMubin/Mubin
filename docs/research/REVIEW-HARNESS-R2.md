# R2 — Live GitHub read-only observation and risk-tiered parallel workflow

**Intent:** remove manual receipt entry as the bottleneck. Branch R2 is stacked
on draft R1 PR #71, not merged or enabled as a branch-protection rule.

## Concrete operation

- In pull-request CI, an allowlisted read-only HTTPS client retrieves an exact
  PR (head/base repo+sha, open status), changed-file list (100-file cap, including
  `previous_filename` for renames) and latest available workflow-run metadata
  queried by exact head SHA. Identity and workflow path/name/event/repository/URL
  are cross-checked before calling a named run successful.
- The snapshot records `github_https_read_only` only for built-in read-only
  transport; injectable local test doubles produce `injected_unverified` and
  can never cause `ci_head_verified=true`.
- `T0/T1` may be placed on the **advisory** fast lane after the selected CI
  workflows are green. This does not imply authorized merging; PR reviewers and
  branch protections remain authoritative. A test double yields only
  `FAST_LANE_CANDIDATE`, not a verified clearance.
- `T2/T3` continue **parallel engineering** in `PARALLEL_REVIEW_QUEUE` while
  source verification, independent specialist assessment and release gates
  proceed separately. Failures remain `FAIL_REPORTED`, incomplete or running
  CI remains `WAIT_FOR_CI`, not false green.
- Unknown, renamed-sensitive, large (>100 changed files) or API-inaccessible
  inputs fail closed or receive conservative risk tiers. R2 intentionally
  does not fetch or expose complete diffs, CI job logs or source-corpus bytes.
  All permissions are `contents:read`, `pull-requests:read`, `actions:read`.

## CLI

`python -m core.review_harness.github_cli --pr 72 --expected-head SHA --require-p0 --json`

- `GITHUB_TOKEN` may be supplied by GitHub Actions as a read-only credential;
  never print token or response body. If no token exists, API read access might
  work for public repository only, and rate limits may prevent results.
- Exit `0` means a valid GitHub observation, including `WAIT_FOR_CI` or reported
  failure. Exit `2` means provider, integrity, or identity failure.
- The workflow does **not** post comments, change labels, request review,
  auto-merge, execute agents, approve rights, qualify hadith or make a fatwa.

## R3 integration (not delivered in R2)

1. Attach independently verifiable CI job/check-suite execution and changed-code
   patch custody, not just matching workflow-run metadata.
2. Launch actual AI reviewers via authenticated isolated execution receipts;
   test their ability to catch independently replayable issues on pre/post-fix
   code using disjoint non-H3.9.2 material. No fabricated reviewer identities.
3. Only after measured reliability, create carefully permission-scoped
   automatically actionable T0/T1 policies; keep human release and domain
   authority gates where they are required, without blocking research work.

R2 metadata read does not prove tests or reviewers were independent, source
texts were authenticated, third-party rights exist or any juristic claim is true.
