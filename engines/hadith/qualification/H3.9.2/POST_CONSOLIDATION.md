# H3.9.2 Post-Consolidation Protocol

Freeze schema **26** begins after the authoritative schema-25 cumulative primary evidence has been frozen.

The current external-critical-commentary boundary is:

- cumulative primary prefix: `0..209` — **210 primary tasks**;
- promoted: **40**;
- pending adjudication: **129**;
- terminal skipped/rejected: **41**;
- currently replacement eligible: **41**;
- cumulative-ledger SHA-256: `36938de84bd9053433b9d890a9f25ce6c5613d9fa1e1b1996f28df69f6cc5f0d`;
- replacement-eligibility SHA-256: `21275d808dd369a362975a45f92ee6889cecac88b293f1287d0b0660bb72baee`.

Schema 26 does **not** change the 210-record non-holdout quota, candidate source partitions, task IDs, primary task fingerprints, label vocabulary, holdout policy, or the one-reserve-per-primary candidate plan.

## Two independent unresolved surfaces

Post-consolidation work must keep these surfaces separate.

### 1. Pending adjudication — 129 primaries

A pending adjudication is **not** a failed primary and is **not** replacement eligible.

The pending set includes source-grounded candidates that could not be automatically promoted because of disagreement, missing/invalid verifier evidence, Curator-requested adjudication, blindness routing, or another bounded reconciliation reason.

Adjudication may use AI to organize the evidence, locate passages, compare claims, and prepare a decision packet, but AI agreement is not the authority that resolves the case. A qualifying adjudication acceptance must satisfy the existing curation policy:

- the final answer remains attributable to pinned human-authored source evidence;
- cited excerpts/supports are reverified verbatim;
- the adjudication is explicitly human/authority reviewed;
- the final reviewed record is resealed against the current source cache and validation contract;
- the decision is bound to the cumulative task ID/fingerprint and the cumulative-ledger SHA-256.

A terminal adjudication rejection does **not** silently enable the linked reserve. It can become replacement eligibility only through a later evidence-bound eligibility update that records the adjudication decision and preserves the original cumulative history.

### 2. Replacement-eligible primaries — 41 slots

The schema-25 replacement-eligibility manifest already proves 41 primary slots are terminally unusable under the frozen rules. Those rows may authorize only their own preregistered linked reserve slots.

The activation chain is:

```text
schema-25 cumulative ledger
        |
        +-- exact cumulative-ledger SHA-256
        |
schema-25 replacement eligibility
        |
        +-- exact eligibility SHA-256
        |
schema-26 reserve activation manifest
        |
        +-- reviewed/frozen artifact SHA-256
        |
schema-26 reserve execution
```

No count copied into documentation, status text, or workflow input can authorize a reserve.

## Reserve activation manifest

`benchmark_campaign.post_consolidation.build_reserve_activation_manifest` consumes the decrypted schema-25 cumulative bundle and re-derives the current frozen Factory plan.

It fails closed unless:

1. the cumulative ledger file hash exactly matches the repository-reviewed binding;
2. the replacement-eligibility file hash exactly matches the repository-reviewed binding;
3. both bindings agree with `CUMULATIVE_MANIFEST.json`;
4. the eligibility object is schema-25 `primary_replacement_eligibility`;
5. promoted primaries remain non-replaceable;
6. pending adjudications remain non-replaceable;
7. each eligible primary exists in the cumulative ledger, has outcome `skipped`, and carries `replacement_eligible=true`;
8. every primary slot binding matches the current frozen Factory plan;
9. every linked reserve slot exists, is a reserve, points back to the eligible primary, and has the exact frozen slot-binding hash;
10. no primary or reserve slot is duplicated.

The emitted `RESERVE_ACTIVATION.json` contains identifiers and cryptographic bindings only. It contains no source text, gold payload, model output, or model identity.

## Activation evidence workflow

Use:

`.github/workflows/h392-reserve-activation.yml`

The workflow is manual, main-only, stale-dispatch resistant, and read-only with respect to repository contents.

It:

1. verifies freeze schema 26 and the repository-reviewed activation target;
2. fetches exactly the frozen cumulative artifact from run `37471731102`;
3. verifies the GitHub artifact digest and cumulative run provenance;
4. safely extracts the ZIP;
5. verifies the redacted summary and encrypted-bundle digest against repository state;
6. decrypts the cumulative bundle only in the ephemeral runner;
7. builds the hash-bound activation manifest;
8. deletes all decrypted cumulative material;
9. proves the upload surface contains only `RESERVE_ACTIVATION.json`;
10. reconfirms `main` before publishing.

For the currently frozen cumulative evidence, the expected activation is exactly **41 reserve slots**.

## Activation is not execution

A successful activation workflow is still not enough to execute reserves.

The activation artifact from workflow run `37524604933` has now passed the second evidence-freeze review boundary:

- workflow head: `69f288d515fd8b65747eba9cedabade9f3cc123a`;
- artifact ID: `11442200728`;
- artifact ZIP digest: `sha256:7c4001c1a90caae84b9eeb7944da2b1dab2e5dd534c4a8e2530241989fcdfd32`;
- manifest SHA-256: `ca53b0403a1a9b9b3f9dba8bd18494966dc5df407f75932e94076c0088e2da3c`;
- activated reserve slots: exactly **41**.

The byte-identical activation manifest is committed under `artifacts/` and repository status binds runtime authorization to that exact file and hash. This approval authorizes only those 41 listed reserve slots; it does not authorize any pending adjudication, promoted primary, unlisted reserve, or additional reserve attempt.

## Factory reconciliation after approval

Schema 26 adds an optional `--reserve-activation` input to `factory-reconcile`.

For primary-only task sets, supplying an activation manifest is an error.

For any reserve task set:

- an activation manifest is mandatory;
- every task must appear in the activated reserve-slot set;
- its frozen reserve-slot hash and `replacement_for_slot_id` must match;
- promoted reserve records carry `factory_verification.reserve_activation` with the activation-manifest SHA-256, cumulative-ledger SHA-256, replacement-eligibility SHA-256, linked primary slot, and reserve attempt.

Final benchmark validation separately requires that this activation binding match the **repository-approved** activation recorded in `H3.9.2-STATUS.json`. This prevents a locally fabricated activation manifest from producing qualification-eligible records.

## Adjudication sequencing

Reserve activation for the current 41 terminal failures may proceed independently of adjudication because those 41 primaries are already final.

The 129 pending adjudications should then be resolved in a source-review campaign. Each decision has three legitimate terminal states:

- **accepted** — produces a reviewed record after human/authority review and resealing;
- **rejected** — produces no reviewed record and may later create a new linked-reserve eligibility row through a reviewed evidence update;
- **deferred** — remains pending and cannot authorize a reserve.

This sequencing matters because the exact 210-record quota is not guaranteed by the present candidate capacity. If any adjudication is rejected or any activated reserve fails to yield a qualifying record, the benchmark remains short. The protocol must report that shortfall rather than manufacture acceptance or silently create additional candidate attempts.

## Security and disclosure boundary

Source-bearing cumulative evidence, adjudication packets, model responses, and reviewed records remain encrypted or custodian-private until they enter the normal reviewed dataset lifecycle.

Public/persisted post-consolidation evidence may contain:

- workflow/run/artifact identifiers;
- task/slot identifiers;
- counts;
- SHA-256 bindings;
- bounded reason classes;
- activation state.

It must not contain source excerpts, gold payloads, credentials, model identity, or hidden reasoning.

## Current state

After repository approval of activation run `37524604933`:

```ini
cumulative_primary_evidence_complete = true
pending_adjudication_count           = 129
replacement_eligible_primary_count   = 41
reserve_activation_evidence_frozen   = true
reserve_reconciliation_enabled       = true
benchmark_population_complete        = false
benchmark_gate_passed                = false
```

The immediate next operation is to execute only the 41 repository-approved non-holdout reserve slots bound by the frozen activation manifest. The 129 pending adjudications remain a separate human/authority review surface and cannot authorize reserves.
