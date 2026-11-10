# Review: public source exposure and Git history scope (2026-11-10)

Project: Mubin `0.1.0-alpha`. Review status: **historical exposure confirmed,
legal and scientific implications UNASSESSED**. Tracking issue:
[issue #145](https://github.com/AIMubin/Mubin/issues/145).

## What was actually observed

- In PR #140's original commit
  [`4b4d4869`](https://github.com/AIMubin/Mubin/commit/4b4d4869d7c09d52608a1cf47be5ca46f9770058),
  the tracked JSON file
  `research/b02b/b02c6-witness-prep-6-145-v1.json` contained an Arabic
  45-codepoint string at
  `negative_control.shared_span_containment_check.shared_span_folded`.
  This review **does not reproduce the string**.
- The subsequent PR commit
  [`134952a8`](https://github.com/AIMubin/Mubin/commit/134952a8121a07877c390de107c5fa23c9234f7f)
  redacted that value, recording its SHA-256 and sizes instead.
- The current `main` commit
  [`571d67e`](https://github.com/AIMubin/Mubin/commit/571d67e7895578ef6eea3bbebf68dff1d58a3c59)
  has the redacted structure. **The original PR commit is still fetchable**
  through GitHub. A squash merge is not history erasure.

No conclusion about a leaked password, a copyright infringement, the
identity of a narration, or the legal necessity to purge has been established
by this structural comparison. Those questions require separate evidence.

## Prospective containment

`qa/publication_guard.py` rejects dangerous **tracked filenames**, including
local source-vault directories, databases and obvious credential containers.
It also invokes the existing B02-C.6 metadata validator (which protects
digest consistency, text exclusion and scientific non-promotion).
The CI workflow runs on every PR and main push, for Windows and Ubuntu.
`.gitignore` is defense in depth only.

The `--history` option examines versions of this **one known receipt** that
are reachable from refs **actually fetched** into the checkout. It reports
counts only, never the text itself. It neither scans every source artifact
nor checks every deleted branch, old original PR head, fork, release asset,
provider cache or independent clone. A zero count is not proof of erasure,
and a green prospective gate never closes issue #145.

## Decision needed for historical material

An authorized maintainer and rights/security reviewer should establish
the original edition/rights and disclosure classification, identify
affected refs/copies, and record a decision. Do **not** force-push rewritten
history or delete Git objects without a reviewed recovery plan for
signed evidence, hashes, tags, open PRs, collaborators and external copies.
Do not paste original excerpts into audit logs, issues or CI output.

Research source admission remains private and purpose-limited; no change to
Quran canonical display, H3.9.2 benchmark gates, scholarly verification,
human adjudication or Fiqh/financial/public-fatwa release authorization.
