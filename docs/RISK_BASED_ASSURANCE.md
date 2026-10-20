# Mubin — risk-proportionate assurance, no blanket human-review gate

**Effective:** 2026-10-20. **System:** \`0.1.0-alpha\`. **Quran Engine:** \`Q0.3\` in progress until its *engineering* exit criteria are actually met.

## Principle

Separate these statements, and never substitute one for another:

1. **Engineering checks passed** — algorithms, imports, negative tests and reproducibility for the stated scope.
2. **Source fidelity verified** — bytes/text match an explicitly identified pinned witness; not proof that the witness is an authentic/complete edition.
3. **Scholarly approval obtained** — a qualified reviewer has approved a *specified scholarly claim or editorial decision*. No blanket inference from AI, CI or a source hash.
4. **Redistribution authorized** — lawful permission for the specific published material and intended distribution. Separate from scholarly quality.
5. **System release qualified** — integration tests, provenance, rights and applicable publication conditions for the *shipped features*, not a union of every research queue.

**A human scientific signoff is not a prerequisite for implementation, reproducible defect reports, structural validation, internal diagnostic experiments or ordinary engineering milestone closure.** Humans are called in when a particular assertion requires an accountable editorial decision, a novel authoritative ruling or the frozen H3.9.2 human-labelled protocol.

## Operational decision matrix

| Action | Automated qualification | Human/rights exception |
| --- | --- | --- |
| Code/CI/infrastructure change | Tested, no known safety blocker | Ordinary responsible review per engineering risk, not scholarly signoff |
| Publish metadata-only defect report | Pinned provenance, reproducible measurements, unmodified source | No scholarly signoff; disclose uncertainty |
| Authorized internal raw-text diagnostics | Restricted-access provenance, non-public | Do not infer publication rights |
| Publish **unchanged** tafsir/hadith edition text | Identity/quote fidelity verified, per-edition rights, no known safety blocker | No automatic blanket scholar approval; contentious attribution/edition ambiguity is escalated |
| Publish canonical Quran witness | Pinned, verified full witness/riwayah/numbering and specific display integrity; rights checked | Do not auto-repair text (including the 364 slash-derived anomalies) |
| Publish an editorial **completion or reconstruction** | Document source alignment, text boundaries, approval of the particular editorial alteration, rights | Accountable editorial reviewer when judgment is involved; never silently alter Quran text |
| Publish *an original scholarly conclusion* as authoritative | Source/methodology/proof chain + scientific quality | Qualified scholarly review or classify as non-authoritative research hypothesis |
| Promote historical Hadith \`H3.9.2\` Schema-31 gold | Frozen original benchmark protocol **and** independent-human requirements | **Do not alter 158 pending decisions or relabel AI-sourced answers as gold** |
| Mubin system release | Integrated evaluation and relevant content-level gates | Not blocked by unrelated pending cases; no automatic promotion of scholarly or rights flags |

A separate implementation in [core/review_gate.py](../core/review_gate.py) validates *declared* prerequisites and returns \`ELIGIBLE\` / \`BLOCKED\`. It is a **policy triage**, not an external attestation service. Its boolean assertions must be supplied from independently checked evidence; a self-declared \`true\` never authenticates a source, transfers rights, or constitutes a human signoff.

## Q0.3 concrete split

### Accepted as engineering evidence

- 31,180 source tafsir text fields match their pinned upstream values (operator report and machine-readable records).
- Four Baghawi upstream fields end at 32,767 characters, with independent digital/image continuation evidence.
- The 18:10 high-resolution scan reads \`ثلاثمائة\` and \`أتى\`, while mechanical suffix alignment remains \`NOT_ALIGNED\`; original SQLite is unchanged.
- The **corrected** private evidence ZIP v2 passed 19/19 member-hash checks; original v1's manifest remains defective.
- Default query hides suspect Baghawi entries; four-case tests and other-source regression tests pass.

These findings permit engineering and metadata milestones **without waiting for a scholarly committee**. Label source editions and observations by their actual verification scope.

### Not yet authorized or not proven

- Canonical Quran display from the 364 slash-affected derived verse records. A pinned, complete independently verified Quran witness must be used for public scripture display.
- Public republication of modern editorial tafsir editions with unresolved rights.
- Silent filling/replacing any of the four suspect Baghawi fields, or treating a 32,767-character source value as complete.
- A new scholarly fatwa or binding qiyas classification from model output.
- Historical H3.9.2 gold promotion without its still-frozen quorum.

These are *feature/action-specific* holds. They do **not** halt work on Quran Q0.3 engineering, Usul U0.1 design, or Hadith H4 development.

## How to close a milestone without bottlenecks

1. Declare the **engineering scope** and regression/evidence checklist before evaluating. Identify exact source versions and test commands.
2. Run deterministic checks in CI (Linux/Windows where relevant). Record hashes and observable results, not just the presence of a report.
3. For any defect, state the bounded effect: \`quarantined\`, \`exposed with uncertainty\`, or \`release blocker\`. A quarantined optional tafsir entry is not a reason to block unrelated engineering.
4. Mark \`engineering_qualified\` for that *narrow workstream* only if all stated technical checks pass; leave \`scholarly_verified=false\` and \`redistribution_approved=false\` where no direct proof exists.
5. Run scholarly/editorial or rights review **asynchronously per contested publication action**, not as an undifferentiated gate on every commit.
6. For an integrated public release, evaluate the actual features included. No project-wide version increment solely on Quran/ Hadith internal milestones.

## Process guardrails

- Never invent reviewers, rights grants, edition identities, source checks, or diagnostic matches.
- Multiple AI agents or Codex reviews do **not** constitute independent qualified scholarly approval.
- If a human check is required but unavailable, publish only the safer permitted operation (e.g. the source locator or diagnostic *status*, without unpublished source content or an authoritative legal opinion).
- **Existing H3.9.2 Schema-31 acceptance thresholds and 158 pending cases remain frozen.** Changing their qualification protocol would require a separate explicit, auditable protocol version, never an implicit policy migration.
- This policy does not automatically relax [corpus.registry.can_publish](../corpus/registry.py), the existing conservative registry publication function. A separate action-specific source-publication implementation and external attestation checks are needed before deploying broader read access.
