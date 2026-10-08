# Mubin System Architecture — P0 Inference Foundation

Mubin is an **evidence-grounded research and inference system**, not just retrieval, and not a substitute for qualified scholarly judgment. It may propose new deductions, qiyas and critical analyses; each must expose cited premises, methodology, exceptions, objections and unresolved uncertainty.

## Integrated topology

```text
Pinned sources: Quran | Hadith | Usul | Fiqh | scholarly precedents
                         |
           Evidence & Provenance Core (P1)
                         |
     Quran Q0.1  Hadith operational foundation  Usul U0.1
                         |
             Reasoning Kernel (P4)
     rule application | ta'lil | qiyas | objection checks
                         |
       Scholar–Evidence Historical Graph (P5)
        attested / refuted / unknown reachability
                         |
                Fiqh Engine (P6)
                         |
       Proof & Falsification Evaluation (P7)
                         |
      Cited research inference / contested / undetermined
```

Hadith H3.9.2 is a **separate frozen qualification campaign**. Its Schema-31 human decision protocol, evidence artifacts, 158 pending decisions and closed benchmark/H4-qualification gates are untouched. H4 development may continue independently; qualification is still gated.

## P0 contracts and implementation boundary

`schemas/inference-foundation.schema.json` is a JSON Schema 2020-12 **structural** contract. `core/inference/validator.py` checks reference integrity, methodology consistency, evidence anchoring, graph cycles, qiyas slots, unresolved objections and historical non-reachability claims. Neither performs scholarly authentication or fully operational rule execution.

Entities: Source (pinned text/edition), Evidence (quoted excerpt and checksum), Methodology (sourced school/profile), Claim (source-attributed vs AI-inferred), Rule (versioned, cited rule), Inference (premises/rules/result), Objection (potential defeater), Proof (structural trace), HistoricalAvailability (evidence that a scholar did/did not receive a specific source, or unknown).

### Non-negotiable boundaries

1. Every inferred claim must recursively depend on source-anchored verified evidence and sourced rules; validity of citations in the real world requires separate P1 verification.
2. No silent mixing of methodological profiles. P0 rejects cross-profile inferences; future explicit bridging requires a new audited contract.
3. Rule descriptions are not executable semantics yet. `structurally_checked` is **not** a proof that the juristic ruling or hadith is correct.
4. Source quotation vs machine-derived reasoning, human review vs machine review, and scholarly opinion vs counterfactual hypothesis must remain distinguishable.
5. Missing evidence, ambiguous identity, unresolved 'illah, open objections, or unproven historical non-reachability produce `undetermined`/blocked states, not fabricated certainty.
6. Published scholarly rulings are source evidence and possible evaluation precedents, not replacement attestations for Schema 31.
7. P0 must not update `VERSION.yaml`; system is still `0.1.0-alpha`.

## Evaluation

Measure independently: quotation fidelity, faithful rule encoding, correct execution of those encoded rules, and correspondence to historical precedents. Do not conflate them. Freeze source/family-disjoint holdouts before tuning; add counterexamples, abstentions and model leakage checks. Review P0 contract details in `docs/INFERENCE_CONTRACTS.md`.

## Claim origin versus confidence and hypothesis

Every Claim now distinguishes `conclusion_kind` (source/rule/qiyas derivation), `assessment_status` (no recorded objection/contested/undetermined) and `modality` (actual/counterfactual). A bound counterfactual assumes access to evidence and models possible reasoning **without asserting what an historical scholar certainly thought**. Independent historical provenance is required before an actual assertion that a source reached—or did not reach—an historical figure.
