# P0 Maintainer-first engineering audit — PR #48

**Original inspected HEAD:** `eea3318552ff4ce0a3a9474cec62cf76eef23d9b`.  
**Scope:** GitHub PR #48 P0-only modified files; schema semantics, runtime invariants, CLI, CI, tests, documentation, and H3.9.2 non-mutation.  
**Sequence:** independent maintainer audit → fixes and reproducible negative tests → clean CI → **only then** secondary Codex review (quota-exhausted fallback: record explicitly that no independent second review occurred).  
**Assurance level:** structural consistency of small inference bundles **only**. No scholarly ruling, quotation authenticity, actual rule execution or expert-gold adjudication.

## Findings and closures

| ID | Severity | Maintainer finding | Closure and regression |
| --- | --- | --- | --- |
| MR-01 | P1 | `deduction` inference could consume `qiyas` rule without four-element qiyas trace | require kind-matched rule and disallow kind laundering; tests for both directions and auxiliary constraints |
| MR-02 | P1 | Claims lacked separate modality, permitting hypothetical scholar response to appear as an actual historical conclusion | explicit `modality=actual|counterfactual`, counterfactual context bound to scholar/history/evidence, identity verification in validator |
| MR-03 | P1 | Completely empty structural bundle passed prior schema | minimum one source, evidence, methodology, claim, rule, inference and proof |
| MR-04 | P1 | `contested` and `undetermined` confused derivation origin with epistemic state | separate `conclusion_kind` from `assessment_status`; checked proof rejects unresolved conclusions **and all unresolved premises** |
| MR-05 | P1 | Hypothetical source premise could launder a counterfactual into a checked actual conclusion | reject actual inferred claim directly dependent on a counterfactual; require separately marked conditional result |
| MR-06 | P2 | `answered` objection required no explicit evidence-backed answer | schema requires a rationale and supporting evidence references; validator resolves reference integrity |
| MR-07 | P2 | No CLI, exit-code contract, malformed input or payload-size handling | `python -m core.inference FILE`; 0 structural pass, 1 invalid bundle, 2 input errors, 5 MiB size cap and regression tests |
| MR-08 | P2 | Arbitrarily deep or oversized graph could exhaust recursive validation | P0 hard caps: at most 5000 entities and 128 dependency levels; negative tests |
| MR-09 | P2 | Historical availability assertion could refer to unverified target evidence | state other than `unknown` requires verified target and verified basis evidence |
| MR-10 | P2 | End-of-string ID matching was permissive of a final line-break under Python regex `$` | reject trailing line-break aliases using end-of-string assertion; negative test |
| MR-11 | P2 | Unbounded direct test dependency ranges could drift across CI runs | pin direct `jsonschema==4.25.1`; further dependency lock/hash reproducibility deferred |

## Schema, CLI and test controls

P0 schema and validator agree on cross-references, unique IDs, exact evidence excerpt byte digests, qiyas slots, source-anchored derived claims, exceptions, required evidence-bound objection responses, methodology boundaries, explicit counterfactual modalities, historical reachability and unresolved states. CLI rejects malformed UTF-8/JSON, missing and oversized files, and structural errors. CI compiles Python modules, runs the CLI help and all regression tests on Python 3.12.

Run:
```bash
python -m pip install -r core/requirements-test.txt
python -m unittest discover -s core/tests -v
python -m core.inference --help
```

GitHub workflow: `.github/workflows/mubin-inference-foundation.yml`. Record successful HEAD-specific workflow run before merging; green CI from an older HEAD is not sufficient.

## Deliberately deferred: do not misstate as P0 solved

1. **P1:** independently verify that a quoted excerpt *actually exists* in the claimed edition and at the claimed locator; P0 merely checks an internally supplied digest. Upstream `verification_status=verified` remains an **assertion**, not a source audit.
2. **P4:** prove faithfulness of encoded Usul principles and execute them in a formally defined semantics. `expression` is non-executable text; `structurally_checked` does not certify valid qiyas, valid 'illah, or correct fatwa.
3. **P5:** verify scholar identity, dated historical testimony, and chronology. P0 can only check IDs, kinds and evidence reference structure; absence of a citation is **never** evidence of non-reachability.
4. **P7:** independent scholarly precedent evaluation with source/family-disjoint holdouts, sensitivity analyses, disagreement measurement and tested abstention behavior.
5. **H3.9.2:** 158 Schema-31 human signoffs remain outstanding; machine-only assertions cannot satisfy the frozen expert-human qualification gates.

## Reviewer-order policy

No automated review agent is used as an exploratory discovery stage in future Mubin PRs. Primary maintainer review must produce its own change-specific findings and regression checks *before* Codex is requested. Codex can act as the independent second opinion **only after** the maintainer's tests and CI pass. If Codex quota or availability prevents that, the primary reviewer must perform a second explicit, adversarial, evidence-backed pass and record **independent_review_unavailable**, never claim Codex approved.

**Merge blocker:** all discovered P1/P2 bugs above corrected and verified on latest PR HEAD; CI green; no unresolved second-review finding. The maintainer audit alone does not authorize modifying H3.9.2 qualification gates.

## Follow-on independent second-review findings and maintainer verification

Secondary Codex review at `4cfa3bf12e7f6c814412ee02c249b13341ef4321` completed with **four concrete unresolved findings**, all reviewed against the implementation and reproduced with adversarial tests **before** correction. The original branch CI was green but insufficient.

| ID | Review severity | Verified defect | Closure / regression |
|---|---|---|---|
| SR-01 | P1 | Historical counterfactual could assume evidence that appeared nowhere in the claim/rule inference ancestry | `trace_evidence` now walks only applied claim/rule source references in the relevant closure; `test_counterfactual_assumed_evidence_must_occur_in_inference_trace` |
| SR-02 | P2 | An open objection could coexist with `assessment_status=no_recorded_objection` if proof was blocked or absent | require a contested/undetermined status for the targeted conclusion; additionally propagate outstanding objections into dependent claim states; direct/descendant negative and contested-positive tests |
| SR-03 | P2 | Memoizing only a boolean allowed a source-first chain deeper than 128 nodes to bypass the global cap | cache both rootedness and absolute longest path; source-first 130-link regression |
| SR-04 | P2 | A proof with >128 shallow siblings was mistaken for >128 depth because the traversal counted globally visited nodes | proof-reachability traversal is iterative, deduplicated and width-independent; 150-sibling valid regression |

**Pre-fix evidence:** GitHub run `37806836269` failed exactly four newly introduced tests (44 total), prior to correction. Another self-identified transitive-objection gap was reproduced by run `37807240630` (one of 46 tests failed) before its correction. **Post-fix evidence must use the latest HEAD CI, not these earlier runs.**

Scientific limits remain unchanged: this checks structural source references and model-data provenance only; does not verify real-world quotations, formalize actual fiqh or authenticate hadith. No `H3.9.2` asset, Schema-31 human-attestation rule, or system `VERSION.yaml` was changed.

### Review-order note

Prior to the new review policy, the first Codex review of this PR ran ahead of the formal maintainer audit. The maintainer-first review and associated fixes were then completed, followed by the second Codex review; its four findings received reproductions and code fixes. For all future changes, maintain the sequence `maintainer audit -> fixes -> tests -> CI -> Codex secondary -> merge decision`. Codex completion with findings is **not** a clean approval.
