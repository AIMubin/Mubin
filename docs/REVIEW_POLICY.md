# Mubin Repository Review Policy — Maintainer First

Applies to **every** Mubin PR: architecture, evidence ingestion, Quran, Hadith, Usul, Fiqh, CI, security, documentation and evaluation.

## Mandatory sequence

1. **Freeze exact candidate HEAD and scope.** Inspect the current base/head SHAs, complete diff and dependent files; distinguish system versions from engine milestones. Re-check after any change.
2. **Primary maintainer engineering review — before any new Codex review request.** Deeply inspect algorithms and invariants, JSON Schema vs runtime semantics, external-source provenance, attack/failure modes, identity and trust boundaries, CLI return codes and error handling, negative/positive tests, CI workflow paths/permissions and documentation claims.
3. **Reproduce / falsify.** For each material issue, first specify how the original code fails or could pass incorrectly; add a targeted regression test that would have caught it. Keep review findings in the PR or versioned audit record.
4. **Correct and validate on HEAD.** Run syntax and unit/integration tests, CI, and any relevant threat-model scenarios; verify actual outcomes, not job existence or assertions about success. Tests are not independent religious certification. Do not silently lower qualification thresholds to turn red into green.
5. **Secondary Codex review only now.** Request Codex **after** the maintainer's evidence-backed review and clean latest-HEAD CI. Review its complete comments/threads and resolve every material finding; any fix restarts primary review and CI before another optional Codex pass.
6. **Quota/unavailability fallback.** If Codex is unavailable (including exhausted review quota), record `codex_review=unavailable`, state the reason, perform an explicit additional adversarial **maintainer-only** review with concrete scenarios and CI proof. Do not call it independent second-party approval.
7. **Merge decision.** Reconfirm exact HEAD, diff scope, latest CI, all actionable findings, published audit and any repository protection rules. Merge only when no known correctness, scientific-integrity or trust-boundary blocker remains. Verify postmerge `main` and CI.

## Special scientific boundaries

- Maintainer code review, automated tests, AI agents and Codex **cannot** replace the independent qualified human signoffs required by frozen H3.9.2 Schema-31 protocols.
- `structurally_checked` cannot be represented as source authenticity, verified usul semantics, correct hadith grade or valid fatwa.
- If a system claim requires evidence the team cannot independently verify, label its claim scope and the verification gap. Prefer `undetermined` to implied certainty.

## PR audit checklist

Document in every PR:

- `base_sha`, `reviewed_head_sha`, changed paths and trust-boundary assessment.
- Concrete invariants tested, failure-mode scenarios, adversarial cases and remaining known limitations.
- Exact test commands, latest run IDs and conclusions, including any transient failures and their fixes.
- Codex review status for that same HEAD (or honest fallback reason), comment/thread resolution status.
- Why merge is allowed or blocked; follow-up items must not disguise unresolved release-critical defects.

A self-review is not an independent review, even when conducted twice. Where no external reviewer exists, disclosure and carefully bounded evidence are mandatory.
