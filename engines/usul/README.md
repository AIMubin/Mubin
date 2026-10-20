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

## P0 bridge implemented (2026-10-20)

The [typed P0 bridge](p0_bridge.py) now validates inference bundles using `core.inference.validator`, checks that cited evidence identifiers exist and carry the bundle's `verified` labels, and executes only independently specified, `machine_checkable` **deduction** rules. It neither authenticates those P0 evidence labels against external editions nor interprets free-text `Rule.expression`. Rules labeled `qiyas` and `tarjih` are explicitly rejected, and cross-methodology combinations cannot execute.

A [synthetic integration fixture](examples/p0-bridge-demo-bundle.json) exercises `Source → Evidence → Methodology → Rule → Execution → Trace` reproducibly and offline. Run:

```bash
python -m pip install -r core/requirements-test.txt
python -m engines.usul.p0_bridge engines/usul/examples/p0-bridge-demo-bundle.json engines/usul/examples/p0-bridge-demo-specs.json engines/usul/examples/p0-bridge-demo-facts.json
python -m unittest discover -s engines/usul/tests -v
```

CLI exit **0** means a valid bridge execution with no refused input, **1** reports a rejected derivation or source assertion, and **2** denotes malformed input. The output and any positive rule result never constitute a scholarly verdict.

**Known semantic gap:** A `machine_checkable` P0 rule and its supplemental propositional spec have not been proven mathematically or philologically equivalent to its free-text `preconditions`, `exceptions`, or `expression`. The P0 evidence label `verified` confirms an internal metadata claim and excerpt hash check, not external source authentication. This remains a **research-only technical bridge**, not an engine capable of issuing or validating fiqh.

The next priority is a versioned and independently testable **semantic binding** between the typed P0 rule and the executable spec, then bounded rules with verified provenance and negative tests. Specialized `qiyas/tarjih` semantics should be developed separately and remain rejected until demonstrated; do not make their absence a blocker to testing the limited deduction bridge.

## Source-use policy and structurally bound demo

Mubin now uses source-attributed evidence without requiring blanket manual scholarly review for engineering. Source **work title, edition, exact locator, evidence ID and digests** are carried in `source_citations`; cited provenance does not by itself authorize redistribution or validate an inference. See [source attribution policy](../../docs/SOURCE_ATTRIBUTION_POLICY.md).

The [semantic binding contract](semantic_binding.py) is optional for compatibility with old synthetic tests. New executable specifications should include `binding.version=0.1.0`, `binding.rule_sha256`, one P0 label/claim per premise, one P0 label/evidence record per exception, and the actual P0 inference conclusion claim ID. It rejects stale/missing/renamed clauses and bound evidence errors. **It does not assert equivalence of a P0 prose statement and a machine predicate**; `semantic_equivalence_verified=false` is mandatory.

Run the bound-source example:

```bash
python -m pip install -r core/requirements-test.txt
python -m engines.usul.p0_bridge engines/usul/examples/p0-bridge-demo-bundle.json engines/usul/examples/p0-bridge-demo-bound-specs.json engines/usul/examples/p0-bridge-demo-facts.json
```

The result reports `STRUCTURALLY_BOUND` and an explicit bibliography. The printed/source edition in this example is **synthetic**. For actual classical source use, supply real titles, identified editions and precise locators, verify the applicable conditions, then preserve the difference between internal citation and textual publication.
