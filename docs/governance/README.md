# Mubin \`main\` governance rollout: bootstrap before strict checks

**Status: templates only; neither JSON file changes GitHub settings.**
Tracking: [Issue #54](https://github.com/AIMubin/Mubin/issues/54).
Observed 2026-11-13: \`main.protected=false\`, and the repository rulesets
collection was empty. The connected GitHub integration supports code and PR
writes, **not** repository ruleset writes.

## Why two stages are necessary

PR [#142](https://github.com/AIMubin/Mubin/pull/142) adds the baseline
checks. PR [#146](https://github.com/AIMubin/Mubin/pull/146) adds the
publication checks. Requiring all four before their workflow definitions
are merged risks a deadlock: a PR may have no check of a name that does
not yet exist on its branch/base merge ref. Do **not** turn on the strict
required-status-check ruleset before all four checks run and pass on new
PRs against the updated \`main\`.

## Phase 1: bootstrap existing reviewable PRs

As a repository administrator, from a trusted, locally authenticated
\`gh\` CLI session:

\`\`\`bash
gh auth status
gh api -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2026-03-10" \
  repos/AIMubin/Mubin/rulesets \
  --input docs/governance/main-bootstrap.ruleset.json
gh api repos/AIMubin/Mubin/rulesets
gh api repos/AIMubin/Mubin/rules/branches/main
\`\`\`

Alternatively, use Settings > Rules > Rulesets and import
\`main-bootstrap.ruleset.json\`. **Review the imported values before
activation**. This template requires PRs and resolves review threads,
prevents deletion and non-fast-forward updates, and uses **zero mandatory
approvals only for bootstrap**. It does **not** represent an independent
review or a completed CI requirement. Avoid bypass actors and direct
updates to \`main\`.

## Phase 2: merge in the safe order

1. Obtain genuine maintainer reviews and resolve threads for PR #142;
   recheck all its exact-head tests; then squash-merge #142 via GitHub.
2. Update PR #146 onto the new \`main\`, rerun its publication/P0 tests
   and the now-available baseline checks; review and squash-merge it.
   Do not assume earlier green checks cover the changed merge base.
3. After #142 is merged, retarget stacked PR #144 from the old
   \`fix/repository-baseline-contracts-20261110\` branch to \`main\`.
   Update to the latest \`main\`, rerun full checks, review and squash
   merge. If #146 was merged in between, run checks against that base.
4. Merge this governance-template PR only after review and any base
   update. Verify \`main\` post-merge CI and that source-rights, H3.9.2
   holdouts and the historical-incident issue #145 remain unchanged.

**Critical**: the branch may be mergeable in GitHub while lacking required
external review; never describe self-review as independent.

## Phase 3: strict protection (only after checks exist)

Check that each exact check name below has run on a new PR with current
\`main\` as base; these are **job names**, not workflow display names:

- \`Baseline contracts and public-preview (ubuntu-latest)\`
- \`Baseline contracts and public-preview (windows-latest)\`
- \`Public tracked-artifact safety (ubuntu-latest)\`
- \`Public tracked-artifact safety (windows-latest)\`

When a second independent reviewer with repository write permission is
available, replace the bootstrap policy with
\`main-strict.ruleset.json\`. It requires one approval, newest-push
independence, up-to-date heads, the four checks, linear history, resolved
threads, no branch deletion and no force pushes. To update the bootstrap
ruleset after reviewing its actual ruleset ID:

\`\`\`bash
gh api repos/AIMubin/Mubin/rulesets
gh api -X PUT \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2026-03-10" \
  repos/AIMubin/Mubin/rulesets/REPLACE_WITH_VERIFIED_RULESET_ID \
  --input docs/governance/main-strict.ruleset.json
gh api repos/AIMubin/Mubin/rules/branches/main
\`\`\`

The rule ID is deliberately not invented. If no independent reviewer is
available, **do not silently reduce the production rule's one-approval
requirement**: either onboard an authorized reviewer or document a
maintainer-only temporary exception in issue #54 with its assurance
limits. GitHub organization and repository bypass policies must be
reviewed in GitHub itself, not inferred from these files.

This configuration does not license project code or external source corpora,
authenticate Qur'anic witnesses, qualify Hadith benchmarks, resolve the
historical source-exposure issue, or authorize a public fatwa.

Official API contract:
https://docs.github.com/en/rest/repos/rules#create-a-repository-ruleset
