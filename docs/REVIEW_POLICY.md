# Mubin Repository Review Policy — Maintainer First

Applies to Mubin engineering PRs. **Scholarly review is NOT a blanket engineering-merge requirement.** For action-specific source, rights and religious-claim decisions see [Risk-based assurance](RISK_BASED_ASSURANCE.md). Historical frozen H3.9.2 human qualification remains unchanged.

## Mandatory sequence

1. **Freeze exact candidate HEAD and scope.** Inspect the current base/head SHAs, complete diff and dependent files; distinguish system versions from engine milestones. Re-check after any change.
2. **Primary maintainer engineering review — before any new Codex review request.** Deeply inspect algorithms and invariants, JSON Schema vs runtime semantics, external-source provenance, attack/failure modes, identity and trust boundaries, CLI return codes and error handling, negative/positive tests, CI workflow paths/permissions and documentation claims.
3. **Reproduce / falsify.** For each material issue, first specify how the original code fails or could pass incorrectly; add a targeted regression test that would have caught it. Keep review findings in the PR or versioned audit record.
4. **Correct and validate on HEAD.** Run syntax and unit/integration tests, CI, and any relevant threat-model scenarios; verify actual outcomes, not job existence or assertions about success. Tests are not independent religious certification. Do not silently lower qualification thresholds to turn red into green.
5. **Optional secondary Codex review, proportional to risk.** For high-impact trust-boundary or scientific-integrity changes, prefer Codex **after** the maintainer's evidence-backed review and clean latest-HEAD CI. For routine low-impact documentation/engineering work, a second AI reviewer is not mandatory. Never describe this as scholarly signoff. If Codex reports material findings, review and resolve them; any fix restarts relevant tests.
6. **High-impact fallback.** If Codex is relevant but unavailable, record `codex_review=unavailable`, the reason and an adversarial maintainer-only assessment with concrete failure scenarios. For low-impact changes record `codex_review=not_required_by_risk`. Neither is independent scholarly certification.
7. **Merge decision.** Reconfirm exact HEAD, diff scope, latest CI, relevant actionable findings and repository protection rules. Merge when no known **scope-relevant** correctness, security or trust-boundary blocker remains. Independently tracked human scholarship/reproduction-rights holds block only the content/claim actions requiring them, not unrelated engineering changes. Verify postmerge `main` and CI.

## Special scientific boundaries

- Maintainer code review, automated tests, AI agents and Codex **cannot** replace the independent qualified human signoffs required by frozen H3.9.2 Schema-31 protocols.
- `structurally_checked` cannot be represented as source authenticity, verified usul semantics, correct hadith grade or valid fatwa.
- If a system claim requires evidence the team cannot independently verify, label its claim scope and the verification gap. Prefer `undetermined` to implied certainty.

## PR audit checklist

Document in every PR:

- For high-impact changes, `base_sha`, `reviewed_head_sha`, changed paths and trust-boundary assessment; compact metadata suffices for routine changes.
- Concrete invariants tested, failure-mode scenarios, adversarial cases and remaining known limitations.
- Exact test commands, latest run IDs and conclusions, including any transient failures and their fixes.
- Codex review status if used; otherwise state `not_required_by_risk` or the honest fallback for high-impact changes.
- Why merge is allowed or blocked; follow-up items must not disguise unresolved release-critical defects.

A self-review is not an independent review, even when conducted twice. Where no external reviewer exists, disclosure and carefully bounded evidence are mandatory.
