# H3.9.2 Schema-31 Human Decision Contract

Schema 31 defines the human decision contract for the **exact 158-case packet** frozen by Schema 30. It changes no benchmark answers, creates no reviewed records, and does not ingest decisions into the repository. Human review remains **blocked** until the Schema-31-compatible decision template is generated from that exact packet and its execution evidence is frozen.

## Scope binding

This contract is bound to:

- packet workflow run `37722153068`;
- packet artifact `11526263194`;
- encrypted packet SHA-256 `5f154c631b6a0fd6494b329c62e863e26512a0aa17211daa13c56435dd8637fd`;
- source-target SHA-256 `318913edd13ab6148926f7c414dab7ba6c1ff4a3846013a68db551793893a1ba`;
- exactly **158** cases: 129 primary, 24 reserve:01, 5 reserve:02;
- benchmark surface: **158 external-critical-commentary cases only**.

The machine-readable contract is `config/adjudication-decision-contract.json`. Final decision rows must conform to `schemas/adjudication-decision.schema.json`. The legacy Schema-30 blank template remains historical evidence only and is **not authorized for review** because its field layout predates this contract.

## Decision-template migration gate

The Schema-30 packet remains canonical evidence and is not rewritten. Its historical blank decision template is hash-bound as legacy input only. Before human review starts, `.github/workflows/h392-schema31-decision-template.yml` must decrypt the exact frozen packet artifact in an ephemeral runner, verify its artifact and plaintext hashes, preserve the exact 158 `packet_id`/`task_id` bindings, generate a blank Schema-31 field layout with no unattested top-level `decision`, encrypt that new template, and publish only redacted hashes/counts plus the encrypted bundle. Human review becomes authorized only after that execution evidence is independently frozen in repository state.

## Authority model

The canonical terminal outcome is `terminal_signoff.decision`, and `terminal_signoff` is always a human-attested action. There is no independent unattested top-level decision field. AI may reconstruct evidence, compare sources, or draft a rationale, but it may not occupy a reviewer identity, provide a human attestation, cast the terminal decision, or self-authorize acceptance.

A pinned statement written by a human scholar or other recognized authority may be **authority evidence**. It remains evidence: it does not replace the required human sign-off for this campaign. This is the operational boundary that permits AI-assisted extraction from books without converting model agreement into scholarly authority.

## Reviewer registry

Reviewer identities are custodian-private. Repository decision records use pseudonymous reviewer IDs; personal identity is not required in Git.

Before any decision bundle can be ingested, the custodian must freeze a reviewer-registry snapshot conforming to `schemas/adjudication-reviewer-registry.schema.json` and bind its SHA-256. Each human has exactly one registry entry and one pseudonymous `reviewer_id`; role eligibility is an array on that entry. The private registry also stores a stable `person_binding_sha256`, derived as HMAC-SHA-256 from the custodian's stable internal person identity using an external secret that is never committed or uploaded. Reviewer IDs and person bindings must both be unique. This lets Schema 32 prove distinct-human independence without publishing personal identity.

Allowed roles are:

- `qualified_reviewer`: human with attested competence in hadith/source-language evaluation and this benchmark decision surface;
- `source_verifier`: human able to verify pinned source identity, locator, excerpt/support fidelity, and actual source support;
- `adjudicator`: independent human with equal or stronger relevant competence than the case reviewer.

## Independence and conflicts

For any terminal accepted/rejected decision:

1. reviewer and source verifier are distinct people, proven using the private `person_binding_sha256`, not pseudonym inequality alone;
2. an adjudicator, when required, is distinct from every case reviewer and the source verifier on the same basis;
3. a human who curated a case cannot serve as its terminal reviewer;
4. every reviewer, source verifier, adjudicator, and terminal signer records a per-case conflict declaration and `recused=false` before the sign-off can count;
5. a recused participant does not count toward quorum;
6. an undisclosed material conflict invalidates the sign-off;
7. AI systems cannot occupy any human role.

## Decision rules

The current packet is classified as risk tier 2 because it contains only `external-critical-commentary`. This contract does **not** pre-authorize the later H3.8/H3.9 identity/family surfaces; those require an equal-or-stronger reviewed contract.

### Accepted

Requires one qualified human reviewer, an independent human source verifier, `source_verified=true`, a non-empty rationale, and a cryptographic binding to the accepted candidate. If there is material disagreement, an independent adjudicator is mandatory.

Acceptance does not directly insert a record into the benchmark. The accepted record must preserve packet/task provenance, be source-verified, and be resealed under a later ingestion/outcome-freeze protocol.

### Rejected

Requires one qualified human reviewer, an independent human source verifier, a non-empty rationale, and a rejection reason. Rejection creates no reviewed record and does not authorize replacement capacity.

### Deferred

Requires one qualified human reviewer and a non-empty defer reason. It remains pending and nonreplaceable. Source verification is not required merely to defer a case.

### Expert-gold escalation

Schema 31 does not weaken the stronger `CURATION.md` rule for `expert_gold`. If an accepted candidate is `expert_gold`, or the judgment is genuinely derived/adjudicative and therefore belongs on that track, the case requires **two distinct qualified reviewers plus an independent adjudicator**, with source verification. The case may not be relabeled `source_attributed` merely to avoid that stronger quorum.

## Disagreement

Each decision row explicitly records `material_disagreement`. Material disagreement requires an independent adjudicator, and the terminal signer role must be `adjudicator`. Simple majority voting without that adjudicator is insufficient. The adjudicator may resolve to accepted, rejected, or deferred and must supply a rationale. Schema 32 must verify that the declared disagreement state matches the human recommendations and that the terminal sign-off is coherent with the reviewer/adjudicator evidence.

## Decision custody

Completed decision files remain custodian-private and encrypted or equivalently access-controlled. The JSON schemas constrain record and registry **shape**, but cannot by themselves prove cross-record identity independence or quorum. A future Schema-32 ingestion/outcome-freeze validator must prove exact packet coverage, reject duplicate/unknown packet IDs, enforce unique reviewer IDs and unique stable person bindings, validate reviewer/source-verifier/adjudicator distinct-person independence, validate every per-case conflict/recusal declaration, enforce terminal quorum and expert-gold escalation, verify `material_disagreement`, verify that `terminal_signoff.decision` is coherent with the human recommendation/adjudication path, bind the reviewer-registry snapshot SHA-256, and bind the completed decision-bundle SHA-256.

Schema 31 currently authorizes the **decision contract and template migration only**. Human review is not yet authorized. No repository ingestion, automatic decision application, benchmark-population mutation, or `reserve:03` authorization is created here.

## Next protocol

First run and freeze the Schema-31-compatible decision-template migration. Only after that freeze may the 158-case human review begin. After a completed human decision bundle exists, Schema 32 may define the reviewed ingestion and outcome-freeze mechanism. Only that later evidence-bound step may compute accepted/rejected/deferred totals and the resulting exact capacity deficit.
