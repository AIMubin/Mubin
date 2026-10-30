# MUBIN-SYS-B02-C — Diagnostic integration and machine-research semantic-link contract

**Decision owners:** System/Integration Architecture. **Baseline:** Mubin `0.1.0-alpha`, `main@5306410`.

## Decision 1 — Run diagnostic integration now, independently from semantic qualification

B02-B strict-gate outcome is `REJECTED_ALL_CANDIDATES_UNDER_FULL_BAR`. Preserve
`6:145` as the **diagnostic focus candidate**, not as an accepted case.
Run real-source Quran, Tafsir T0.3, full Hadith `run_hsearch`, Usul
and Fiqh F0.1 in one reproducible *engineering* transaction. Keep:
- `functional_path_pass`: whether the actual five engine stages executed;
- `evidence_graph_linkage_pass`: only exact local source-bound links;
- `semantic_research_gate_pass`: separately versioned assessment;
- `fiqh_output`: `RESEARCH_ONLY`/`UNDETERMINED`, no fatwa.

A structurally valid **Usul-only** P0 projection with zero
`engine_bindings` is NOT evidence that Quran/Hadith/Tafsir were connected.
Never manufacture P0 rules, excerpts, proofs, or grade labels to satisfy
a schema. The original full P0 bundle is private; export only vetted
redacted receipts. Do not change frozen H3.9.2 qualification data.

## Decision 2 — Generic semantic link beyond the old amr-only pilot

Introduce `mubin-semantic-link-research/1.0`, separate from the legacy
`engines/e2e/semantic_linkage.build_linkage` which still enforces its
original 2:43/bab-al-amr scope. Do NOT relax or silently patch that pilot.

The local operator supplies a trusted source-pin registry and a bounded
`read_span(source_id, byte_start, byte_end)` callback. The request must
contain Quran, Tafsir, and Usul anchors, each pointing at the same verse
reference (Quran/Tafsir) or explicit Usul rule (Usul). Excerpt and
context-window SHA256 are checked against **locally retrieved bytes**,
and each source ID must match its trusted pinned source digest.
The callback must never use file paths from the AI candidate.

An AI proposes one relation class:
`LEXICAL_OVERLAP`, `EXPLICIT_SOURCE_APPLICATION`,
`TAFSIR_MEDIATED_APPLICATION`, or `CONTEXTUAL_HYPOTHESIS`.
At least two independent **run identifiers** supporting the relation
and one adversarial review reporting no open defeater are needed
for `MACHINE_SUPPORTED_RESEARCH_ONLY`. Reused run IDs, missing anchors,
unsupported context and open objections fail closed.

**Critical:** A run identifier is not proof of genuinely independent
reviewers or of an authentic source edition. The machine result is an
auditable *research-stage procedural assessment*, NOT a scientific
verification of semantic truth or a juristic conclusion. It does not
assert independent model families, human signoff, Hadith grading, or
`scholarly_verified=true`.

Lexical term overlap, such as `الاصل`/`اباحته` or `الخبر`,
**always** remains `LEXICAL_ONLY` even if several AI workers vote
otherwise. Explanations and complete private source context stay
inside local receipts. The GitHub projection may hold only source
digests, IDs vetted for disclosure and scope-limited statuses.

The local lead runs the new contract against pinned `6:145`, `49:6`,
and adversarial false positives. An `UNDETERMINED` result counts as
correct execution and is not silently promoted by AI model consensus.

### Source-integrity versus research semantics

`source_span_digests_matched=true` means the supplied window matched
the trusted operator-pinned byte record. It does NOT prove original
authenticity or correct tafsir/usul interpretation. Likewise
`MACHINE_SUPPORTED_RESEARCH_ONLY` records supplied model assessments;
without actual reviewed rationale and source context the operator must
not elevate it to accepted scholarly linkage.

## B02-B PR #129 boundary

The original PR head `51ca6a2` is behind a separate v3 branch
`feat/b02b-gate-v3@0d6d034`. The v3 research handoff must be
synchronized to a current PR head, with clear distinctions between the
original run base and post-integration gate. GitHub CI must check the
final PR head. Codex quota error is documented as lack of optional
secondary review; maintainer-first audit cannot be presented as independent.

## Acceptance

1. Python engine contracts and P0 tests continue to pass.
2. B02-C diagnostic replay has source-identity checks and no unbounded
   waiting for semantic classification.
3. Synthetic source-reading tests verify same reference/context on all
   engine anchors; false positives remain unaccepted.
4. No authoritative Fiqh claim or `VERSION.yaml` bump.
5. Local actual-source linkage qualification requires separately
   inspecting the machine review receipts and pinned source context,
   not merely the returned status flag.
