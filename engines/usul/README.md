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
python -m engines.usul.p0_bridge engines/usul/examples/p0-bridge-demo-bundle.json engines/usul/examples/p0-bridge-demo-bound-specs.json engines/usul/examples/p0-bridge-demo-facts.json --require-semantic-binding
```

The result reports `STRUCTURALLY_BOUND` and an explicit bibliography. The printed/source edition in this example is **synthetic**. For actual classical source use, supply real titles, identified editions and precise locators, verify the applicable conditions, then preserve the difference between internal citation and textual publication.

For each accepted result, `conclusion_citations` now lists the evidence actually linked to supporting rule IDs, and `rule_citations` lists references for each executed rule. `source_citations` is only the combined diagnostic inventory and must **not** be interpreted as every source supporting every conclusion. Use `--require-semantic-binding` for source-driven runs; without it legacy synthetic examples remain labelled `LEGACY_UNBOUND`. CLI refusals are nonzero and cannot be interpreted as accepted derivations.

## Source-backed pilot 01 — al-Waraqat, Bab al-Amr (2026-10-20)

The first bounded **real-source-attributed research pilot** is [`engines/usul/pilots/amr_default.py`](pilots/amr_default.py) with [source and scope documentation](pilots/README.md). It reads a short, attributed digital-text excerpt of Imam al-Haramayn al-Juwayni's *al-Waraqat*, chapter **الأمر**, and applies a narrow propositional model to **synthetic** test cases only. The output cites the original digital witness URL, book/author/section, and exact **excerpt-scoped** SHA-256. A second public digital witness serves as a textual comparator, not a verified printed-edition claim.

Run `python -m engines.usul.pilots.amr_default` after installing `core/requirements-test.txt`. The four cases demonstrate a default conditional support, a blocking diverting indicator, an unknown diverting indicator and an absent command premise. Tests check the P0 structural bundle, strict semantic binding, citation separation between historical text and synthetic inputs, Unicode-safe Windows output, and the absence of fatwa/scholarly approval flags.

This is **not** independent authentication of the entire source edition or proof that the machine representation expresses all linguistic and jurisprudential restrictions in the original. A short excerpt checksum does not verify the digital site's full HTML, full work or publisher's rights. Continue to maintain `U0.1=experimental_prototype_not_qualified` until engineering acceptance is explicitly scoped and measured.

## U0.1 evidence-scoped exceptions (research-only)

The experimental [exception evidence contract](exception_evidence.py) rejects the false inference **"not found" ⇒ "does not exist"**. In strict execution mode, exception assertions are accepted only as documented inspection of an **enumerated synthetic test scope**, citing P0 evidence records; an uninspected exception remains `UNDETERMINED`. Claimed real-world exhaustiveness, partial inspection presented as total absence, missing evidence and direct Boolean overrides are rejected.

Use [the next-stage al-Waraqat scenario](pilots/scoped_amr_pilot.py):

```bash
python -m engines.usul.pilots.scoped_amr_pilot
```

Read [pilot source notes and truth table](pilots/README.md). A fully checked **declared synthetic scope** permits conditional support *for the simulation only*. It does not prove the nonexistence of a textual `qarīnah`, source validity or a juristic obligation. Existing one-step explicit facts remain accessible in `ALLOW_LEGACY_EXPLICIT_FACTS` compatibility mode but must not be described as evidence-backed exception investigations. The Mubin system version, Hadith frozen gold qualification and all scholarly/republication holds are unchanged.

## Stage 04 — private source snapshot and section coverage contract

[Source snapshot auditor](source_snapshot_coverage.py) and [separate draft manifest preparer](source_snapshot_prepare.py) now support exact byte-pinned **UTF-8 text exports** from private source captures, with unique chapter boundaries, complete source-line byte partitioning, digest per indexed source line and no source text in result reports. The preparer returns `DRAFT_NOT_ATTESTED`; only a subsequent verification using an **independently frozen manifest digest** may return `SNAPSHOT_COVERAGE_PASS`.

The first intended real witness is [al-Waraqat, heading الأمر through heading النهي](pilots/SOURCE_SNAPSHOT_COVERAGE.md). Exact raw HTML capture and original-to-UTF8 export mapping **have not been supplied** in this assistant environment; real-source replay is therefore **pending** rather than certified. The CI tests use only entirely synthetic Arabic UTF-8 fixtures, including tamper, overlapping sections and missing-manifest cases.

A source snapshot/section PASS establishes **bitwise conformity with a specified text export and declared extraction bounds**, not print-edition identity, semantic equivalence of legal rules, exhaustiveness of juristic exceptions or the right to republish a hosted edition. System version `0.1.0-alpha` and Usul prototype non-authoritative gates remain unchanged.
