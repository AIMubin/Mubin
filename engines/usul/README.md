# Usul Engine — U0.1 executable prototype

**Milestone:** `U0.1` **in progress / not qualified**, not an operational jurisprudential reasoning engine. **Mubin system remains `0.1.0-alpha`.**

## What is implemented now

- [One-step conditional simulator](executor.py) with deterministic evaluation of typed, explicit propositions.
- The three relevant semantic distinctions: an asserted **false** fact is distinct from a **missing** fact; unknown exceptions **cannot** be silently considered cleared; opposing supported conclusions become `CONTESTED`.
- Explicit single `methodology_id` per scenario; rejection of cross-methodology rules. Source evidence is carried as **identifiers**, not fetched or authenticated.
- Blocked outcomes for triggered exceptions and open/sustained objections, and `UNDETERMINED` for missing prerequisites.
- Synthetic tests and [cross-OS CI](../../.github/workflows/usul-checks.yml).

This is **not** a representation of real legal maxims, `qiyas`, `tarjih`, or fatwa. The accepted rule kind is deliberately `propositional_demo`; normative rule kinds fail closed. Rule outputs are NOT chained into premises. A successful simulation means only that the supplied propositional contract was executed deterministically.

## Example

Run from the repository root:

```bash
python -m engines.usul.executor engines/usul/examples/synthetic-demo.json
python -m unittest discover -s engines/usul/tests -v
```

Expected result: `demo:output` has status `CONDITIONALLY_SUPPORTED`. The output explicitly sets `rules_scholarly_authenticated=false`, `input_evidence_ids_externally_verified=false`, `scholarly_verified=false`, `valid_juristic_ruling=false`, `public_fatwa_authorized=false`. The CLI returns code 0 for a valid *simulation*, code 2 for malformed input; code 0 **never** means a sound religious conclusion.

## Contract summary

- Required top-level fields: `schema_version`, `methodology_id`, `facts`, `rules`, `objections`.
- Each input fact requires atom, explicit truth `true|false` and at least one claimed source evidence identifier.
- Every rule requires rule ID, identical methodology, `rule_kind=propositional_demo`, nonempty `if_all`, optional `unless_any`, `then`, and source-evidence identifiers.
- Every objection requires known `rule_id`, source evidence IDs, and `open|sustained|answered`.
- Input bounded to 128 KiB / 256 facts / 128 rules / 16 clauses per condition list. Unrecognized keys, duplicate facts, unsupported rule kinds, malformed IDs and methodology mismatches are invalid.
- A rule is `CONDITIONALLY_SUPPORTED` only if *all* `if_all` predicates are explicitly supported, *all* `unless_any` exception triggers are explicitly false, and no open/sustained objection exists.
- Unknown information results in `UNDETERMINED`, not an inferred negative. No default negation, silent rule chaining, remote source retrieval or LLM interpretation.

## Required before a genuine U0.1 engineering qualification

1. Define a versioned **typed usul rule language** with traceability to the existing P0 `Methodology`, `Rule`, `Evidence`, `Inference` and `Objection` contracts. No source verification is implied by matching identifier spelling.
2. Build source-attested, methodologically versioned example rules from documented scholarly source texts; initially research-only, with disputed semantics marked.
3. Implement formal rule-precondition and exception matching, explicit qiyas `asl/far/hukm/illah`, contradictions, objections and proof trace with **negative/adversarial** tests.
4. Evaluate on published precedents and bounded counterexamples without turning structural validity into scholarly correctness.
5. Keep [risk-based assurance](../../docs/RISK_BASED_ASSURANCE.md): routine execution and evaluation do not require blanket human signoff, but authoritative scholarly conclusions require accountable review.

The next work item is **P0 → U0.1 typed rule semantics bridge**, not releasing this prototype as an usul opinion engine.
