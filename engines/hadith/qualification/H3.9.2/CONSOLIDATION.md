# H3.9.2 Cumulative Primary Evidence Consolidation

This stage consolidates canonical encrypted **non-holdout primary** campaign artifacts before any reserve candidate is allowed to participate in benchmark population.

It does not change record quotas, source partitions, label vocabularies, model prompts, inference settings, holdout policy, or final benchmark cardinality. Freeze schema 24 preregistered reserve capacity and explicitly deferred activation until cumulative replacement eligibility existed. Freeze schema 25 adds that cumulative evidence protocol without changing quotas, partitions, labels, thresholds, prompts, or holdout isolation.

## Current canonical input boundary

The first cumulative consolidation is bound to these successful campaign runs:

- `37280971913` — primary offsets `0..39`
- `37295517184` — primary offsets `40..103`
- `37326459365` — primary offsets `104..167`

Together they represent exactly **168 primary tasks** for `external-critical-commentary`.

The workflow does not trust editable dispatch inputs as the canonicality decision. `run_ids` and `expected_task_count` must exactly match the repository-reviewed values in `artifacts/H3.9.2-STATUS.json`; otherwise it fails before artifact acquisition. Future campaign runs must therefore be explicitly admitted into the reviewed repository history before cumulative consolidation can consume them.

Observed encrypted-shard outcomes are:

- promoted: **34**
- pending adjudication: **103**
- skipped/rejected primary opportunities: **31**

The workflow must reproduce these counts from the decrypted, provenance-bound evidence. They are not accepted merely because they appear in documentation.

## First canonical consolidation result

Workflow run `37409931064` executed on main commit `696b0e1c30fda5cdb4ea011840b562d63f151701` and completed successfully. It reproduced the exact 168-task prefix and the `34 promoted / 103 adjudication / 31 skipped` accounting.

The published redacted/encrypted artifact is permanently referenced in `artifacts/CUMULATIVE_PRIMARY_EVIDENCE_168.json`. The compact repository evidence binds:

- GitHub artifact digest `sha256:abdc98472114378c0d2bb4b680d9d9549dbc624698bd3ab822c2970ef6ad301d`;
- redacted-summary SHA-256 `fef1a9aba21ade7c4f04deee51095124ef7b0297758dbad3bc4b3107ed023e46`;
- encrypted cumulative bundle SHA-256 `1497788cd01c03102cccac126ac7234f9cbdfff3284ebe53d78b8c911b1b5a7d`;
- cumulative-ledger SHA-256 `473ccc5fc8f6f545208c2868d28e40aafc88b9dcda397921f80d4a037528bea9`;
- replacement-eligibility SHA-256 `1233bead33e534325b6f88f952ed28ebb3764bdc3d739cd2f77d42a43d6dac12`.

The result proves **31 replacement-eligible terminal primaries**. The **103 pending adjudications remain replacement-ineligible**, and reserve reconciliation remains disabled.

## Workflow

Use:

`.github/workflows/h392-cumulative-consolidation.yml`

The workflow is manual, main-only, and stale-dispatch resistant. It accepts a comma-separated list of canonical campaign run IDs and an exact expected cumulative task count.

For every source run it:

1. verifies the GitHub Actions run completed successfully on `main`;
2. verifies it is the reviewed H3.9.2 campaign workflow and was manually dispatched;
3. discovers only `h392-curation-chunk-*` artifacts;
4. requires the GitHub artifact SHA-256 digest and verifies the downloaded ZIP bytes;
5. verifies the encrypted source-bearing bundle against its recorded SHA-256;
6. safely extracts the artifact ZIP and AES-GCM decrypts the protected bundle only in the ephemeral runner;
7. safely extracts the decrypted tar archive with path/link/device rejection;
8. validates every task against the current frozen primary plan;
9. rejects reserve tasks, duplicate tasks, incomplete execution manifests, summary/decrypted-evidence mismatches, and inconsistent reviewed/adjudication sets;
10. reacquires and verifies the current pinned non-holdout source bytes, then revalidates every promoted row against those bytes, the bound Curator/Verifier response hashes and model families, exact gold agreement, source provenance, reviewed-record field/content-fingerprint/support bindings, and the current frozen primary-slot binding;
11. creates one cumulative ledger and cumulative reviewed/adjudication material;
12. derives a replacement-eligibility manifest bound to the cumulative ledger SHA-256;
13. re-encrypts all source-bearing cumulative material and removes plaintext before upload.

Only a redacted cumulative summary and the AES-GCM encrypted cumulative bundle are uploaded.

## Canonical cumulative ledger

`CUMULATIVE_LEDGER.jsonl` contains one row per selected primary task and binds:

- primary task and slot IDs;
- task fingerprint;
- benchmark and anchor source;
- canonical primary offset;
- original reconciliation outcome/reason;
- normalized cumulative reason;
- promoted case ID when applicable;
- source workflow run SHA and artifact identity/digest;
- replacement eligibility.

Duplicate primary task IDs across source artifacts fail closed rather than being silently deduplicated.

## Adjudication semantics

A primary task in adjudication remains **pending**, including:

- `curator_requested_adjudication`;
- `gold_disagreement`;
- `verifier_no_candidate`;
- support/provenance disagreements;
- verifier contract/model-output failures;
- missing verifier responses.

When the original reconciliation reason is `missing_verifier_response`, consolidation reconstructs whether the Curator candidate was omitted from the verifier task set. In that case the cumulative reason is `candidate_input_blindness`; the original reconciliation reason is preserved separately.

No pending adjudication is replacement eligible.

## Replacement eligibility

`REPLACEMENT_ELIGIBILITY.json` is hash-bound to `CUMULATIVE_LEDGER.jsonl`.

Schema-25 eligibility rules are:

```text
primary promoted
    -> reserve NOT eligible

primary pending adjudication
    -> reserve NOT eligible

primary terminal Curator no_candidate
    -> linked reserve eligible

primary terminal task-local Curator contract/model-output rejection
    -> linked reserve eligible

missing/unbound/infrastructure evidence
    -> fail closed; reserve NOT eligible
```

Eligibility does **not** activate reserve reconciliation. The manifest explicitly carries:

```json
"reserve_reconciliation_enabled": false
```

The normal campaign workflow and `factory-reconcile` therefore remain primary-only until a later reviewed protocol change consumes the eligibility binding.

## Why consolidation precedes offsets 168..209

After 168 primary opportunities, 31 are already terminally unusable. Even under the optimistic assumption that all 103 pending adjudications are eventually accepted and all remaining 42 primaries succeed:

```text
34 promoted
+ 103 adjudication
+ 42 remaining primary opportunities
= 179 maximum primary-derived reviewed records
```

The exact `external-critical-commentary` non-holdout quota is 210, so at least 31 reserve replacements are unavoidable.

The first cumulative consolidation is now verified. The next live collection step is therefore exactly the remaining primary surface `168..209` (**42 tasks**), executed with the existing primary-only campaign workflow.

After that batch succeeds, its run ID must first be admitted into the repository-reviewed canonical history and the expected cumulative prefix advanced from 168 to 210. A second cumulative consolidation over the exact `0..209` prefix must succeed before any reserve activation protocol is designed or enabled. Reserve execution remains a separate later step.

## Security boundary

The decrypted source-bearing evidence and cumulative outputs are ephemeral and must never be committed or uploaded as plaintext.

The artifact encryption key remains a protected GitHub Secret and is step-scoped. The cumulative workflow uploads only:

- `CUMULATIVE_SUMMARY.json` — redacted;
- `h392-cumulative-source-bearing.tar.gz.aesgcm`;
- the encrypted bundle SHA-256 text file.

The redacted summary contains no source text, gold payloads, or model identity.


## Freeze binding

This implementation is part of **freeze schema 25**. Historical canonical primary artifacts from schemas 23 and 24 are admissible only because the primary task prefix and fingerprints were preserved. Every decrypted task is revalidated against the current frozen plan, and an expected cumulative count requires an exact zero-based primary prefix with no gaps or overlaps.
