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
