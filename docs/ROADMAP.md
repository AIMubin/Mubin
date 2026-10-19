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

P1/P2 can partly run in parallel with the design of P3/P4, but operational reasoning depends on verified evidence and a defined methodology. The initial 90-day plan is a *pilot target*, not a promise of complete Hadith 'ilal or universal fiqh.

### Preserved research program

- H3.9.2 Schema 31 stays frozen: 158 pending human decisions; no reviewers currently available. **No machine may impersonate a reviewer or auto-promote pending rows to gold.**
- H4.0 **development** may proceed, but H4.0 **qualification/release** retains benchmark/architecture requirements.
- Machine-only evaluation, if introduced, is a separately versioned, preregistered `source_attributed`/formal-testing track, never a backdoor into the old human-reviewed pool.
- No system version bump until an end-to-end, evidence-bound vertical slice succeeds.

### P0 release checklist

Typed source/evidence/claim/rule/inference/proof/objection/historical-availability schema; a negative-test-heavy structural validator; a separate CI workflow; no changes to Hadith qualification assets; Codex review of the new PR.

## P0 maintainer review exit conditions

The PR cannot merge solely on passing its original 19 tests. Maintainer-originated adversarial additions must exercise qiyas-rule laundering, forced-empty bundles, open and falsely answered objections, source-verified digest changes, distinct claim modality, mismatched historical identities, CI execution and CLI failure exit codes. Codex is an **independent second pass after** maintainer review and fixes; if unavailable or quota-limited, record an explicit maintainer-only fallback audit rather than fabricate a second approval.

## P1 staged delivery

- **P1.0 — offline snapshot provenance pilot:** Byte-exact anchored quotations against operator-selected local UTF-8 snapshots; deterministic unsigned receipts, rights declaration as an explicit gate, and adversarial CI. Implementation in `core/provenance`. **Does not meet the full P1 exit condition.**
- **P1.1 — source trust & corpus qualification:** Authoritative acquisition channel, version/edition identity, externally verifiable digests or signed manifests, actual text-position/citation verification, licensing determination, and source-disjoint evidence holdouts. No real Quran/Hadith/fiqh corpus is claimed by the P1.0 synthetic tests.
