# Mubin Roadmap — P0–P7

**Current Mubin version:** `0.1.0-alpha`. **Target only after integration evidence:** `0.2.0-alpha`. Subsystem milestones are independent.

| Stage | Implementation | Acceptance evidence |
| --- | --- | --- |
| **P0** | Architecture, shared typed contracts, fail-closed graph validator, CI | orphan/digest/cycle/methodology/qiyas/objection/historical-negation tests |
| **P1** | Evidence and provenance, pinned source identity, edition and locator verification | reproducible source/quote match; source rights and licensing checks |
| **P2** | Quran Q0.1 text/verse lookup, separate sourced tafsir | canonical integrity, deterministic retrieval and citations |
| **P3** | Hadith operational engine: narrator, isnad, matn, independent routes; progressive 'ilal | sourced route-level analyses, explicit uncertain states and counterexamples |
| **P4** | Usul U0.1 typed rule language, formal executor, qiyas with 'illah/mani'/farq checks | replayable rule execution and invalid analogy tests |
| **P5** | Scholar–Evidence Historical Graph and evidence-reachability counterfactuals | historical unknown is not non-reachability; counterfactuals clearly labeled |
| **P6** | Fiqh F0.1 bounded integration | question → cited sources → rule → inference → criticism/abstention |
| **P7** | Evaluation, robustness, release audit | preregistered source/family-disjoint tests, provenance and limitations |

P1/P2 can run in parallel with design and controlled technical implementation of P3/P4. **A human scholarly signoff is not a general engineering milestone gate.** Operative reasoning served as an authoritative conclusion still depends on verified evidence, methodology and action-specific scholarly approval. See [risk-based assurance](RISK_BASED_ASSURANCE.md). The initial 90-day plan is a *pilot target*, not a promise of complete Hadith 'ilal or universal fiqh.

### Preserved research program

- H3.9.2 Schema 31 stays frozen: 158 pending human decisions; no reviewers currently available. **No machine may impersonate a reviewer or auto-promote pending rows to gold.**
- H4.0 **development** may proceed, but H4.0 **qualification/release** retains benchmark/architecture requirements.
- Machine-only evaluation, if introduced, is a separately versioned, preregistered `source_attributed`/formal-testing track, never a backdoor into the old human-reviewed pool.
- **Avoid unnecessary reviewer bottlenecks:** structural progress, source discrepancy investigations and guarded prototypes may complete by reproducible machine tests. Human/editorial decisions are requested only for particular publication or scientifically authoritative assertions.
- No system version bump until an end-to-end, evidence-bound vertical slice succeeds.

### P0 release checklist

Typed source/evidence/claim/rule/inference/proof/objection/historical-availability schema; a negative-test-heavy structural validator; a separate CI workflow; no changes to Hadith qualification assets; risk-based maintainer engineering review; optional Codex second-pass for high-impact changes.

## P0 maintainer review exit conditions

The PR cannot merge solely on passing its original 19 tests. Maintainer-originated adversarial additions must exercise qiyas-rule laundering, forced-empty bundles, open and falsely answered objections, source-verified digest changes, distinct claim modality, mismatched historical identities, CI execution and CLI failure exit codes. For high-impact changes Codex may provide a **second engineering pass after** maintainer review and fixes; if unavailable or quota-limited, record an explicit maintainer-only fallback audit rather than fabricate a second approval.


## Parallel public preview launch lane — without research-stage blockers (2026-10-21)

**A separately scoped, non-authoritative metadata preview** is now implemented under [docs/index.html](index.html) and checked by [dedicated cross-OS preview CI](../.github/workflows/public-preview.yml). [Launch runbook](PUBLIC_PREVIEW_LAUNCH.md). It presents only versioned capabilities, original digital-witness links and source-attributed aggregate research metadata (Stage07/08), without Quran/Tafsir/Hadith body text or juristic inference.

- **Launch engineering gate:** reproducible metadata JSON from frozen Stage07/08 and Q0.3 review receipts, no new rights/scholarly assertions, passing public preview tests and JavaScript syntax checks. The build must fail closed when frozen source identities or public scope change.
- **Hosting gate:** repo administrator enables GitHub Pages main /docs (or equivalent static hosting) and confirms the live URL, links and mobile display. Public hosting is NOT attested by CI.
- **Feature-level holds only:** canonical Quran display, rights-sensitive modern editorial text, H3.9.2 frozen human gold, real-world legal inference and Fiqh remain excluded pending their separate requirements.
- **Not blocking metadata launch:** unreviewed 158 Hadith decisions; wider Usul section ingestion; complete historical-witness comparison; new Stage09 P0 citation bindings; Fiqh Engine; organization-wide scholarly signoff.
- **Version:** project remains 0.1.0-alpha. A research-only metadata preview is NOT the full P0–P7 system release and cannot be used to infer subsystem qualification.

Stage09 [typed citation proposal contract](../engines/usul/typed_evidence_binding.py) is deliberately parallel. It can validate an EXACT source/P0 excerpt byte correspondence inside private research without turning P0 verification labels or a lexical match into scholarly authority or a public content permission.
