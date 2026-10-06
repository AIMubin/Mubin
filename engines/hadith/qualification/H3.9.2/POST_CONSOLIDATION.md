# H3.9.2 Post-Consolidation Planning Gate

Freeze schema 26 introduces a **planning-only** control plane between the authoritative 210-primary cumulative evidence and any later adjudication or reserve execution.

It does not change benchmark quotas, labels, source partitions, task fingerprints, holdout policy, model prompts, or the schema-25 replacement-eligibility rules.

## Frozen source boundary

The planner consumes only the authoritative cumulative evidence produced by workflow run `37471731102` and frozen in:

`artifacts/CUMULATIVE_PRIMARY_EVIDENCE_210.json`

The source boundary is:

- primary coverage: `0..209`;
- total primary tasks: **210**;
- promoted: **40**;
- pending adjudication: **129**;
- skipped: **41**;
- replacement-eligible primaries: **41**;
- cumulative-ledger SHA-256:
  `36938de84bd9053433b9d890a9f25ce6c5613d9fa1e1b1996f28df69f6cc5f0d`;
- replacement-eligibility SHA-256:
  `21275d808dd369a362975a45f92ee6889cecac88b293f1287d0b0660bb72baee`.

The 129 pending adjudications are not replacement eligible.

## Planner

The command is:

```bash
python -m benchmark_campaign plan-post-consolidation \
  --cumulative-dir /path/to/decrypted/cumulative-evidence \
  --out-dir /path/to/post-consolidation-plan \
  --evidence artifacts/CUMULATIVE_PRIMARY_EVIDENCE_210.json
```

The planner revalidates:

- the cumulative manifest, ledger, adjudication queue, and replacement-eligibility hashes;
- exact zero-based coverage of the frozen primary prefix;
- outcome counts against the repository-frozen evidence;
- current frozen Factory-plan SHA-256;
- every primary-slot binding;
- every linked reserve-slot binding;
- the primary-to-reserve replacement relation;
- exact agreement between cumulative-ledger replacement flags and the eligibility manifest;
- disjointness between pending adjudication and replacement eligibility.

Any mismatch fails closed.

## Outputs

The planner emits only a redacted control plane:

- `ADJUDICATION_PLAN.json`
- `RESERVE_ACTIVATION_PLAN.json`
- `POST_CONSOLIDATION_MANIFEST.json`
- a redacted summary on stdout.

The adjudication plan contains only task/slot identifiers, primary offsets, benchmark/anchor identifiers, canonical reasons, source-run bindings, and the already-public cumulative-ledger binding. It deliberately publishes **no hash of the full adjudication evidence row**, because those encrypted rows may contain low-entropy model-family metadata that must not become guessable through an unkeyed commitment. It contains no source text, gold payloads, or model identity.

The reserve activation plan contains only the 41 primary slots already proven terminally replaceable and their linked frozen reserve slots. Each row binds:

- primary slot;
- primary task fingerprint;
- primary slot SHA-256 binding;
- reserve slot;
- reserve slot SHA-256 binding;
- cumulative-ledger SHA-256;
- replacement-eligibility SHA-256.

## Execution remains disabled

Freeze schema 26 deliberately keeps:

```ini
adjudication_execution_enabled = false
reserve_execution_enabled      = false
reserve_reconciliation_enabled = false
```

The planning artifact is **not** permission to execute reserve tasks and is **not** an adjudication result.

A later reviewed revision must consume the frozen planning artifact before it may:

1. define how the 129 pending adjudications are resolved;
2. execute only the reserve slots enumerated in the frozen reserve plan;
3. reconcile reserve outcomes against their linked eligible primaries;
4. assemble reviewed benchmark records under the exact frozen quotas.

## Workflow

Use:

`.github/workflows/h392-post-consolidation-plan.yml`

The workflow is manual, main-only, and stale-dispatch resistant. It is hard-bound to cumulative run `37471731102` and artifact `11416657955`, verifies their repository-frozen metadata, downloads the exact artifact with a pinned GitHub action, verifies the redacted summary and encrypted cumulative-bundle hashes, decrypts only in the ephemeral runner, runs the planner, removes decrypted cumulative evidence, and uploads only the four redacted planning files.

The artifact encryption secret is not job-scoped and is used only in the validation/decryption steps.
