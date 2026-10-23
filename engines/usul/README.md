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

The initial real witness is [al-Waraqat, heading الأمر through heading النهي](pilots/SOURCE_SNAPSHOT_COVERAGE.md). The private Windows operator subsequently recorded a successful real HTML→UTF-8 snapshot replay and pinned chapter coverage in [the Stage04 source receipt](../../corpus/reviews/u01-stage04-waraqat-source-link.json). Those private bytes were **not supplied to public CI**; synthetic CI tests verify the implementation, not independent acquisition of the witness.

A source snapshot/section PASS establishes **bitwise conformity with a specified text export and declared extraction bounds**, not print-edition identity, semantic equivalence of legal rules, exhaustiveness of juristic exceptions or the right to republish a hosted edition. System version `0.1.0-alpha` and Usul prototype non-authoritative gates remain unchanged.


## U0.1 Stage 05 — byte-anchored source retrieval and literal search

[Stage05 lexical indexer](source_lexical_index.py) now regenerates a complete line/byte-offset index from a Stage04-pinned UTF-8 section **after rechecking the trusted source manifest and section coverage**. A test query uses `literal_exact_v1`, returning every UTF-8 byte span, section locator, source attribution and digest; results contain no original book text or query string. Zero hits are explicitly `NO_EXACT_LITERAL_MATCH_IN_PINNED_SECTION`, **not** evidence that no juridical `qarīnah` exists.

The [real al-Waraqat operator runner](pilots/waraqat_stage05.py) additionally requires the original HTML bytes and `waraqat-extract/1.0.0` replay, and compares raw HTML, snapshot, chapter and manifest digests with the published Stage04 receipt. [Operator guide](pilots/STAGE05_LEXICAL_REPLAY.md) and [metadata-only keyword query fixture](pilots/data/waraqat-stage05-queries.json) are available. **CI runs on synthetic sources; the private Stage05 replay was subsequently reported as PASS by the Windows operator in [its metadata-only closing receipt](../../corpus/reviews/u01-stage05-waraqat-lexical-replay.json).** Neither `U0.1` engineering qualification nor scholastic/rights clearance is implied.


## Stage 06 — dual-witness technical replay closed (research-only)

A new [byte-addressed comparator](witness_alignment.py) and [pinned digital-witness runner](pilots/waraqat_stage06.py) detect differences between private al-Waraqat Bab al-Amr text witnesses. [Runbook](pilots/STAGE06_COMPARATIVE_ALIGNMENT.md) explains the separate Stage04 primary-witness and Stage05 comparator source hashes, exact section byte boundaries, private input requirements and the non-semantic normalization profiles.

Every strict difference is traceable to source-relative original UTF-8 byte spans, line numbers and hashes; the output does not reproduce original source text. Case-sensitive/diacritic-preserving comparison is primary. Ignoring Arabic marks or editorial square-bracket delimiters, or changing whitespace, is a **diagnostic** comparison only. Meaning-changing vowels, negation and altered words remain reviewable; matching normalized strings do not certify lexical or scholarly identity.

CI validates this engineering behavior against synthetic Arabic fixtures. The two private raw HTML captures and W2's extracted section have **not been independently replayed by this assistant**. The Stage06 runner returns `STAGE06_TEXT_ALIGNMENT_PROVENANCE_PARTIAL` by default. A new [candidate W2 h2 extractor](pilots/waraqat_witness2_extract.py) permits an **opt-in strict two-capture replay** (`--require-secondary-extraction`), which returns `STAGE06_DUAL_SOURCE_EXTRACTION_REPLAY_PASS` only when both pinned HTML captures deterministically regenerate their supplied section files. This stronger outcome still does not verify manuscript/printed editions, interpretive equivalence or redistribution rights. On the locally frozen W2 source, the operator reported a successful strict replay and committed [a Stage06 metadata-only closing receipt](../../corpus/reviews/u01-stage06-waraqat-dual-witness-alignment.json): W2 section 1,702 bytes, SHA-256 `db181b1d9466389d2b5aeaf50362dd57e716cc1e36d041948777e3fe0c9c9358`, and 232 raw alignment events. The public [145-test Usul CI](https://github.com/AIMubin/Mubin/actions/runs/39533986573) passed on Windows and Ubuntu for code SHA `18db3cb`. **Private original bytes were not replayed independently in public CI.** The local supplementary claim of no residual lexical difference is not the same as the public machine contract certifying lexical content equivalence; `lexical_content_equivalence_certified=false` and `full_witness_comparison_qualified=false` remain. Arabic semantic retrieval and scholarly qualification are **not** granted.


## Stage 07 — Arabic evidence retrieval across frozen digital witnesses

[Arabic retrieval engine](arabic_evidence_retrieval.py) produces separate `literal_exact_v1` matches and `ORTHOGRAPHIC_CANDIDATE_ONLY` leads for user-selected, **versioned** folds: ignoring specified Arabic vowel marks (but **not** combining hamza/madda), ignoring square-bracket delimiters only (never content), and optionally joining whitespace for diagnostic word-boundary candidates. The exact raw UTF-8 source bytes are preserved, and every hit contains an auditable source-section byte span, line, SHA-256 and coordinate-basis label; no source text is returned.

The [two-witness Stage07 runner](pilots/waraqat_stage07.py) calls Stage06's **strict dual HTML→section replay** before querying, and requires each section's independently frozen digest. [Full operator guide](pilots/STAGE07_ARABIC_EVIDENCE_RETRIEVAL.md) and [keyword-only sample queries](pilots/data/waraqat-stage07-queries.json) are available. The new synthetic adversarial tests cover Unicode-safe Arabic search, overlapping matches, non-identity between exact and folded matches, paragraph/word boundaries, bracket content, hamza, negation, source tampering and private-file gate failures.

**Stage07 is locally attested as `STAGE07_DUAL_WITNESS_ARABIC_RETRIEVAL_PASS`** in the [metadata-only closing receipt](../../corpus/reviews/u01-stage07-waraqat-arabic-retrieval.json), with 12 literal occurrences over six queries and separately reported folded candidates for both pinned witnesses. [Usul CI 39548101731](https://github.com/AIMubin/Mubin/actions/runs/39548101731) passed **160/160 tests on Windows and Ubuntu**; this CI tested synthetic fixtures, not the private original HTML replay. The operator-reported real data replay was not rerun independently in public CI. A folded candidate is **not** a validated textual variant, absence finding or juristic inference, and repeated counts across profile layers are not independent occurrences. All scholarly/rights flags remain false; Usul remains a research prototype.

The next narrowly scoped milestone is **Stage08: Evidence Context & Citation Graph**: source-span anchored evidence references, links to P0 rules and objections, distinct origin and candidate classifications, and reproducible provenance without copying source text or promoting lexical matches to juristic authority.


## Stage 08 — source-anchored Evidence Context & Citation Graph

The [context graph builder](evidence_context_graph.py) generates a **metadata-only, byte-anchored, deterministic** network of the verified original-section query observations and their bounded neighboring-line context. It independently recomputes Stage07 search results against the pinned UTF-8 section bytes, rejects any stale/fabricated matches, and records original SHA-256s for context windows, hits and lines. Repeated profile matches are separate **query/profile edges** to one unique source occurrence; they are not separate textual evidence.

The [private al-Waraqat Stage08 runner](pilots/waraqat_stage08.py) first replays Stage07's strict **two-HTML-to-section source gate**; it cannot construct a trusted historical graph from an arbitrary supplied JSON report. [Stage08 operator instructions](pilots/STAGE08_CONTEXT_CITATION_GRAPH.md), [unassessed research-pointer fixture](pilots/data/waraqat-stage08-research-pointers.json), and [synthetic graph tests](tests/test_evidence_context_graph.py) are available.

**Rule and objection pointers are query-navigation metadata only, never evidence support edges.** An exact Arabic phrase match, folded candidate, zero-hit search, and context checksum are not semantic juristic interpretations. No `Evidence` labels or semantic `qarīnah` judgments are promoted to P0 verified input. Stage08 is **locally attested as `STAGE08_DUAL_SOURCE_CONTEXT_GRAPH_PASS`** in [its metadata-only closure receipt](../../corpus/reviews/u01-stage08-waraqat-context-graph.json): 53 nodes, 87 edges, 13 hashed context windows and 22 unique original text occurrences, with the two rule/objection navigation pointers still `UNASSESSED`. The historical private source replay is **operator-reported**, whereas [Usul CI 39553023684](https://github.com/AIMubin/Mubin/actions/runs/39553023684) independently passed **173/173 synthetic tests on Windows and Ubuntu**. The corpus-only closure record also passed [Corpus CI 39556898598](https://github.com/AIMubin/Mubin/actions/runs/39556898598), 62/62 on each OS. The tool establishes structural traceability, **not** scholarly interpretation, `qarīnah` verification, edition identity or authorized legal reasoning. The next narrowly scoped project stage is **Stage09 Typed Evidence Binding & Provenance Contracts**, without promoting lexical observations to jurisprudential `P0 Evidence` automatically. The Usul engine continues to be `experimental_prototype_not_qualified` under system version `0.1.0-alpha`.


## U0.1 Full-Waraqat Batch Coverage — multi-chapter infrastructure

The [whole-book W1 inventory/batch engine](waraqat_batch.py) and [one-command W1 operator runner](pilots/waraqat_full_book_batch.py) remove the Bab al-Amr-only coding bottleneck. They reproduce the original pinned W1 HTML→whole-work UTF-8 export, discover every literal h5 heading, partition the complete book into contiguous section slices (including the prelude), preserve exact original byte offsets/digests and the legacy Bab al-Amr golden, and reuse the existing Stage07 Arabic retrieval and Stage08 context graph **on each section** with automatically cleaned private temporary files.

One oversized or malformed chapter fails with a separate section code rather than blocking other structurally valid W1 chapters; root-source tampering fails closed. The [optional W2 title matcher](waraqat_w2_heading_map.py) matches h2 heading fingerprints as **unassessed and potentially incomplete title candidates**, independently of W1 coverage; no W2 section identity, scholarly agreement or matching editorial editions is implied.

See the [private source operator runbook](pilots/FULL_WARAQAT_BATCH_COVERAGE.md). The [synthetic all-chapter regression suite](tests/test_waraqat_batch.py) includes a 20-heading fake witness plus negative and per-section isolation tests; the [W2 heading diagnostics tests](tests/test_waraqat_w2_heading_map.py) exercise ambiguous titles, order and pinned source roots. No public CI has rerun all chapters of the real private historical W1/W2 HTML captures yet. Therefore the actual number of W1 chapters and full-book coverage outcome must come from the local operator, **not synthetic fixture counts**. These chapter-engineering outcomes do NOT qualify semantic rules, publication rights, P0 evidentiary status or juristic judgments. The separate public metadata preview remains deployable without waiting for whole-book research.

## U0.2 development pilot 01 — concept/rule candidates (research-only)

The [candidate concept/rule catalog](concept_rule_catalog.py) introduces a small
versioned `u0.2.0` **internal** metadata contract for symbolic concept nodes,
unassessed candidate rule structures, and typed proposed relationships. It
binds each rule candidate to a pinned Stage08 `RULE_RESEARCH_POINTER` via
research-navigation metadata, checks reference integrity, and produces a
deterministic digest without including source text.

It deliberately does **not** create a P0 Rule, authenticate an edition,
interpret linguistic meaning, execute a juristic condition, infer a ruling,
or update scholarly/rights/semantic authorization flags. A passing catalog
is a structurally consistent *research index*, not an approved Usul engine.

See [U0.2 pilot contract and limits](U02_CONCEPT_RULE_CATALOG.md),
[synthetic candidate manifest](examples/u02-candidate-catalog-demo.json),
and `test_concept_rule_catalog.py`. Mubin version remains `0.1.0-alpha`.

## U0.2 development pilot 02 — methodology, ambiguity and alternatives

The [methodology candidate review overlay](candidate_methodology_review.py)
extends the U0.2.0 metadata catalog with separately versioned, **unassessed**
methodology proposals. Every candidate rule must bind to one declared profile
and exact profile version whose research pointer remains in Stage08.
Unresolved ambiguities and candidate cross-profile/structural alternatives
are tracked explicitly without asserting any genuine scholarly disagreement.

This reuses [Stage08 pinned research navigation](evidence_context_graph.py)
and [the U0.2.0 catalog](concept_rule_catalog.py), *not* a new juristic
executor. Invalid/stale graph or catalog pins, unauthorized review statuses,
cross-profile pointer mismatches and fabricated normative outcomes fail
closed. Full [pilot 02 contract and limits](U02_METHODOLOGY_REVIEW.md)
and synthetic regression tests appear under
`tests/test_candidate_methodology_review.py`.

Success means only structurally linked research candidates. It does not
verify source interpretation, school affiliation, disputed rules, `qiyas`,
`tarjih` or any fatwa. Mubin remains `0.1.0-alpha`.

## U0.2 pilot 03 — private-source replay bridge (W1/W2)

A [strict local operator](pilots/waraqat_u02_real_bridge.py) now
re-executes Stage06→Stage07→Stage08 from the **private frozen HTML
witnesses**, verifies the historically pinned Stage08 SHA-256
(`72ca6bd8…a6fdb2`), and constructs a candidate-only U0.2 catalog
with source-scoped, byte-addressed **lexical** links. The three W1
queries for the candidate concepts are bound to the frozen exact
occurrence counts 6/1/1. No source text appears in its output.

This is **not** runnable against private witnesses on public CI; synthetic
end-to-end tests validate the integration contract. Follow the
[U0.2 private-source operator runbook](pilots/U02_REAL_WARAQAT_BRIDGE.md)
to run the actual frozen W1/W2 replay locally and archive a
metadata-only receipt. No semantic equivalence, rule-support,
scholarly authentication, rights clearance or fiqh inference is granted.

## Structured definition candidates (Draft PR #81, research-only)

A new [strict metadata-only definition model](concept_definitions.py) separates
a pinned W1 **lexical observation** from an unassessed *candidate scholarly
definition* and from an independently versioned *proposed interpretation*.
Each record is a keyed HMAC commitment and identifier for real private phrases (or a clearly synthetic test-vector hash), never source text, a trusted attribution
or an executable rule. The initial source-registry contract allows only
`NOT_CLEARED` or `RESTRICTED` rights, and treats all work/author/edition
identifiers as unassessed claims.

The validator verifies the historical U0.2.3 receipt under an **externally
pinned digest**, strictly associates all three candidate concept IDs to
their W1 query IDs, rejects unauthorized schema fields/status promotions and
supports hash-linked append-only changes with an explicitly supplied
predecessor manifest. A [synthetic example](examples/u02-concept-definitions-synthetic.json)
and [adversarial tests](tests/test_concept_definitions.py) exercise only
structural/provenance behavior; the example's hashes are synthetic placeholders,
not actual scholarly definitions from al-Waraqat.

See [implementation scope and scientific non-goals](U02_CONCEPT_DEFINITIONS_IMPLEMENTATION.md).
No fiqh inference, semantic qualification, permission to redistribute source
text, authenticated author attribution, or claim of scholarly disagreement
is enabled. Overall system stays `0.1.0-alpha`.

## Private W1 definition intake (Draft PR #81)

The [local-only candidate intake operator](pilots/waraqat_definition_private_intake.py)
and [operator instructions](pilots/U02_PRIVATE_DEFINITION_INTAKE.md)
prepare an **unassessed metadata-only** manifest from private text files
stored **outside Git**. The operator validates the frozen U0.2.3 receipt,
requires exact W1 concept/query IDs, computes private HMAC commitments,
and refuses source-text fields, path traversal, unsupported concept IDs,
cross-concept interpretations and unapproved scholarly statuses.

See the [safe structural intake example](pilots/data/u02-private-definition-intake.EXAMPLE.json).
The example filenames do **not** imply that real quotations or source
attributions have been verified. GitHub CI uses synthetic temporary files
only; the private real-source intake has **not** been run here. The tool
does not verify whether a candidate is actually authored by the person
claimed, and must never promote it into a scholarly rule.


## PR #83 private source admission → Stage05 read-only integration

The [private admission lexical adapter](private_admission_lexical.py) joins a
currently admitted `usul` source in the restricted corpus store to the existing
Stage04 pinned-coverage and Stage05 exact-literal search. Its output contains
only byte offsets, hashes and controlled IDs; original text, query literals,
private paths, and source URLs are not returned. There is **no new rule
execution**, publication permission or religious authority.

See the [operator runbook](pilots/PRIVATE_ADMISSION_LEXICAL.md) for exact
private inputs, CLI arguments, source-ID namespace differences, synthetic CI,
and the unresolved W2 and independent-anchoring limitations. No protected
source bytes are supplied to GitHub and historical source receipts are not
modified or promoted.
