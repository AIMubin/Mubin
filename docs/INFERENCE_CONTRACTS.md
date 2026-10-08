# P0 Inference Contracts

**Contract version:** `0.1.0`. **Schema:** `schemas/inference-foundation.schema.json`. **Checker:** `core.inference.validator.validate_bundle`.

## Source of truth and assurance limits

Sources bind work, edition, locator, and a declared content SHA256. Evidence carries a verbatim excerpt and its own SHA256, verification status/method, and source reference. P0 checks digest consistency **against submitted excerpt bytes only**; P1 must independently re-fetch the pinned edition to prove external source correspondence. The label `verified` records an **upstream assertion**, not an independently witnessed source check.

Every methodology is versioned and grounded in source-evidence IDs. A Rule includes source evidence, explicit preconditions/exceptions and `formalization_status`. Its `expression` is human-readable text **not executable formal logic yet**.

A source-attributed Claim must anchor in verified evidence. An inferred Claim links exactly one Inference, which references premise Claims, source-grounded Rules, and one Methodology. The same methodological ID must be applied throughout; P0 rejects silent school/profile mixing, even if an AI requests an exception. Derived claims must recursively reach verified source-grounded premises and rules, with no premise cycles.

Qiyas records four separate premise links: `asl`, `far`, `hukm_al_asl`, and `illah`. These slots are necessary **but not sufficient** to establish a sound analogy. Exception checks are attestations in P0, not independently run rules. Open/sustained Objections or unresolved/triggered exception checks block a proof's structural-check label.

A Proof requires `verification_scope=structural_only`. The `structurally_checked` state means **only** well-formed, consistent, referenced trace data. It cannot establish an authentic hadith grade, valid 'illah, sound jurisprudence, consensus, or accepted fatwa.

HistoricalAvailability tracks `attested_reached`, `attested_not_reached`, or `unknown`. Explicit non-reachability requires contemporaneous attestation or demonstrable chronological impossibility backed by source evidence; **absence of a reference from a scholar's works is never sufficient**. Claims about what a scholar *would have decided* are hypothetical, not biographical fact.

## Separate measurement layers

1. Source authenticity and verbatim quotation location (P1).
2. Fidelity of formalized methodological rules (P4).
3. Runtime application of those rules (P4).
4. Alignment and disagreement with frozen scholarly precedents (P7).

Machine-only checks can establish structural invariants but **never replace the H3.9.2 Schema-31 independent-human quorum**. Keep the historical 158 cases and all H3.9.2 gates unchanged. Mubin system stays at `0.1.0-alpha` until an integrated evaluation-backed release.

## Review hardening: inference, modality, assessment

`Claim.conclusion_kind` is now **derivation provenance only**: `source_derived`, `rule_derived`, or `qiyas_derived`. Epistemic state is independently recorded in `Claim.assessment_status=no_recorded_objection|contested|undetermined`; `no_recorded_objection` merely reports the graph's known objections, **not universal support or juristic soundness**. `Claim.modality=actual|counterfactual` is mandatory. A counterfactual claim must be inferred and must bind a `counterfactual_context` to a particular scholar, source evidence and historical-availability case, with an explicit assumption. A structural proof for a counterfactual remains hypothetical; it must never be projected onto a scholar as a historical fact.

Each inference must use at least one rule whose kind matches its kind. Ancillary `constraint` and `exception` rules may supplement the main rule but never substitute for it. A qiyas rule may **not** be hidden in deduction/tarjih to bypass mandatory asl/far/hukm/illah claims. `answered` objections require an explicit evidence-bound answer. `structurally_checked` proofs are forbidden for `contested` or `undetermined` conclusions, open/sustained objections, or unresolved/triggered/unchecked rule exceptions.

Nonempty source/evidence/method/rule/claim/inference/proof collections are required for a valid inference bundle. P0 limits validation to **5000 entities** and at most **128 claim-dependency levels**; this is a small-bundle structural validator, not a replacement for P1 corpus infrastructure. Identifier checks reject final-newline aliases.

## CLI and error contracts

```bash
python -m pip install -r core/requirements-test.txt
python -m core.inference --help
python -m core.inference /path/to/bundle.json
python -m unittest discover -s core/tests -v
```

The CLI accepts a UTF-8 JSON file no larger than **5 MiB**. Exit code **0** means only that structural checks passed; the output explicitly disclaims external source authenticity and scholarly correctness. Exit code **1** indicates schema/cross-reference/graph validation failure; exit code **2** indicates missing, malformed, unreadable, or oversized input. The CLI never issues a fatwa or independently asserts that quoted evidence appears in its claimed edition.

## P0 follow-on integrity guarantees

`counterfactual_context.assumed_evidence_id` must occur within the referenced counterfactual claim's actual dependency closure of claim citations or applied rule citations. Merely having the evidence in a scholar's historical-availability record or methodology profile is insufficient. This is still a **structural** dependency claim, not proof the cited passage supports the counterfactual.

`assessment_status=no_recorded_objection` cannot be used on the conclusion of an inference with an open/sustained objection, nor on an inferred descendant that relies on the objection-affected conclusion; `blocked` and `undetermined` proofs do not excuse mislabeling. A documented `answered` objection must retain its evidence-bound response, without claiming scientific agreement.

All claim-dependency paths have a maximum length of **128 claims** independent of record ordering. This depth does not count independent parallel siblings. Iterative proof-closure collection supports wide shallow graphs up to the separate 5000-entity bound.

### Exception evidence reference integrity

Every explicitly listed `exception_checks[*].evidence_ids` item must resolve to an existing evidence entity **for all outcome values**, including `unknown` and `triggered`. For unresolved/triggered outcomes, an empty evidence list or references to identified but unverified evidence are permitted because the state makes no claim of successful clearance. For `cleared`, a nonempty set of verified evidence references is required. Passing this structural check does not establish that a jurisprudential exception or material `mani'` was correctly evaluated; semantic verification remains future P4 scope.
