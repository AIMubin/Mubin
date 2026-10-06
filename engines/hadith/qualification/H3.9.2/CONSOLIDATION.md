# H3.9.2 Cumulative Primary Evidence Consolidation

This stage consolidates canonical encrypted **non-holdout primary** campaign artifacts before any reserve candidate is allowed to participate in benchmark population.

It does not change record quotas, source partitions, label vocabularies, model prompts, inference settings, holdout policy, or final benchmark cardinality. Freeze schema 24 preregistered reserve capacity and explicitly deferred activation until cumulative replacement eligibility existed. Freeze schema 25 adds that cumulative evidence protocol without changing quotas, partitions, labels, thresholds, prompts, or holdout isolation.

## Current canonical input boundary

The repository-reviewed cumulative target is now bound to these successful campaign runs:

- `37280971913` — primary offsets `0..39`
- `37295517184` — primary offsets `40..103`
- `37326459365` — primary offsets `104..167`
- `37426135905` — primary offsets `168..209`

Together they represent exactly **210 primary tasks** for `external-critical-commentary`, with a zero-based contiguous prefix `0..209`.

Campaign run `37412193331` is explicitly excluded: it concluded failure after a Verifier timeout in shard `176..183`, so its partial artifacts are diagnostic only and are not part of canonical history.

The workflow does not trust editable dispatch inputs as the canonicality decision. `run_ids` and `expected_task_count` must exactly match the repository-reviewed target in `artifacts/H3.9.2-STATUS.json`; otherwise it fails before artifact acquisition.

Raw successful-shard accounting across the four admitted campaign runs is:

- promoted: **40**
- adjudication: **129**
- skipped/rejected primary opportunities: **41**

These are **pre-consolidation counts only**. The workflow must reconstruct the authoritative cumulative ledger, normalize adjudication reasons, and derive replacement eligibility from decrypted provenance-bound evidence. No cumulative count is accepted merely because it appears in documentation or campaign summaries.

## First canonical consolidation result

Workflow run `37409931064` executed on main commit `696b0e1c30fda5cdb4ea011840b562d63f151701` and completed successfully. It reproduced the exact 168-task prefix and the `34 promoted / 103 adjudication / 31 skipped` accounting.

The published redacted/encrypted artifact is permanently referenced in `artifacts/CUMULATIVE_PRIMARY_EVIDENCE_168.json`. The compact repository evidence binds:

- GitHub artifact digest `sha256:abdc98472114378c0d2bb4b680d9d9549dbc624698bd3ab822c2970ef6ad301d`;
- redacted-summary SHA-256 `fef1a9aba21ade7c4f04deee51095124ef7b0297758dbad3bc4b3107ed023e46`;
- encrypted cumulative bundle SHA-256 `1497788cd01c03102cccac126ac7234f9cbdfff3284ebe53d78b8c911b1b5a7d`;
- cumulative-ledger SHA-256 `473ccc5fc8f6f545208c2868d28e40aafc88b9dcda397921f80d4a037528bea9`;
- replacement-eligibility SHA-256 `1233bead33e534325b6f88f952ed28ebb3764bdc3d739cd2f77d42a43d6dac12`.

The result proves **31 replacement-eligible terminal primaries**. The **103 pending adjudications remain replacement-ineligible**, and reserve reconciliation remains disabled.

## Second canonical consolidation result

Workflow run `37471731102` executed on main commit `e1422b3262ee308084ce2212a2f2825fdc737032` and completed successfully. It reconstructed the exact zero-based primary prefix `0..209` from the four repository-admitted campaign runs and reproduced the full 210-task accounting:

- promoted: **40**;
- pending adjudication: **129**;
- skipped: **41**;
- replacement eligible: **41**;
- reviewed records: **40**.

The redacted/encrypted result is permanently referenced in `artifacts/CUMULATIVE_PRIMARY_EVIDENCE_210.json`. The compact evidence binds:

- GitHub artifact digest `sha256:b8fea5f254790fc7cd51e740349a169b470e18e3ee2730b8aba7bbfcd7073ced`;
- redacted-summary SHA-256 `2131f6358cf773b37a7abffa13aefe1dc7be5ebfb8111279fe13e458693bce69`;
- encrypted cumulative bundle SHA-256 `c6b5afa771a2aeba2f5017264d2fb98af56882baee0c6fe0109104678651c9f4`;
- cumulative-ledger SHA-256 `36938de84bd9053433b9d890a9f25ce6c5613d9fa1e1b1996f28df69f6cc5f0d`;
- replacement-eligibility SHA-256 `21275d808dd369a362975a45f92ee6889cecac88b293f1287d0b0660bb72baee`.

The 41 replacement-eligible rows are exactly the terminal skipped primaries under the current schema-25 eligibility rules. The 129 pending adjudications remain ineligible. This result establishes evidence; it does **not** activate reserves, resolve adjudications, or commit source-bearing reviewed records as plaintext.

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

## Post-consolidation gate

The second cumulative consolidation is complete and now supersedes the raw campaign summaries as the authoritative primary-evidence boundary for `external-critical-commentary`.

The next protocol revision must consume the exact cumulative-ledger and replacement-eligibility bindings above. It must explicitly address both unresolved surfaces:

- **129 pending adjudications**, none of which is currently replacement eligible;
- **41 replacement-eligible terminal primary slots**, whose linked reserves remain disabled until a separate reviewed activation mechanism binds to the schema-25 evidence.

No reserve task should be executed merely because the count 41 appears in documentation. Any activation must be hash-bound to the frozen 210-primary evidence and remain limited to the eligible linked reserve slots. Final benchmark assembly remains blocked until adjudication and replacement handling produce enough qualified reviewed records under the frozen 210-record non-holdout quota.

## Security boundary

The decrypted source-bearing evidence and cumulative outputs are ephemeral and must never be committed or uploaded as plaintext.

The artifact encryption key remains a protected GitHub Secret and is step-scoped. The cumulative workflow uploads only:

- `CUMULATIVE_SUMMARY.json` — redacted;
- `h392-cumulative-source-bearing.tar.gz.aesgcm`;
- the encrypted bundle SHA-256 text file.

The redacted summary contains no source text, gold payloads, or model identity.


## Freeze binding

This implementation is part of **freeze schema 25**. Historical canonical primary artifacts from schemas 23 and 24 are admissible only because the primary task prefix and fingerprints were preserved. Every decrypted task is revalidated against the current frozen plan, and an expected cumulative count requires an exact zero-based primary prefix with no gaps or overlaps.
