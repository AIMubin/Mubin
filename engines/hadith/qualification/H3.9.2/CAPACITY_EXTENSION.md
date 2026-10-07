# H3.9.2 Schema-27 Selective Capacity Extension

Schema 27 begins only after the canonical schema-26 reserve consolidation is frozen.

The authoritative completed non-holdout state for `external-critical-commentary` is:

```text
40 promoted primaries
129 pending primary adjudications
7 promoted reserve:01 replacements
24 pending reserve adjudications
10 exhausted reserve:01 slots
= 210 required primary slots
```

This yields:

- **47** validated promoted records;
- **153** pending adjudications;
- **10** exhausted slots;
- a maximum of **200/210** fillable slots under the current one-reserve-per-primary candidate capacity, even if all 153 pending adjudications are eventually accepted.

Therefore the minimum capacity shortfall is exactly **10**.

Schema 27 does not reinterpret adjudication as failure and does not alter the 210-record quota. It introduces a narrowly scoped mechanism to propose one additional candidate opportunity for each of the 10 already-exhausted slots.

## Why this is a protocol change

The schema-26 Factory plan preregistered exactly one reserve opportunity per primary. It intentionally contains no `:reserve:02` slots.

A second reserve attempt cannot be created by:

- editing a task ID;
- increasing an offset;
- rerunning `reserve:01`;
- treating a pending adjudication as rejected;
- changing `reserve_slots_per_primary` globally;
- silently rebuilding the historical Factory plan.

Any of those would destroy the evidence chain or change candidate capacity after observing outcomes.

Schema 27 instead defines an **append-only overlay proposal** derived from the canonical exhausted-slot evidence. The schema-26 base Factory plan remains byte-for-semantic unchanged.

## Canonical source boundary

The capacity-extension proposal is derived only from canonical reserve consolidation run `37578659973`:

- runner commit: `b3888b24b20571884465b349c9764c669b0e66f9`;
- artifact ID: `11464000900`;
- artifact digest: `sha256:00385663166059b3701c0581bd460ba2f2d39a796d3cca1c1b015fb96170b64e`;
- redacted summary SHA-256: `13ccc3f3ae985fb2f577fb05e2f5e9b5bbddcbf87d41d1263e1a4fa07a87bd67`;
- encrypted consolidated bundle SHA-256: `f73a1e1dc170af9a8fa4dde6c47348e85690fe4df712bda573b001c66b39dc19`;
- reserve ledger SHA-256: `f1fbd43fd68806c64a3d63d7eae0226c4f66e6e5f5ec12ab07e74d1d6ff63012`;
- exhausted-slots SHA-256: `7140e7b110d4be44d3685b20649bcd4df04b69d1cd561eb4afa69c3ba1c75490`.

The schema-26 reserve activation remains part of the chain:

- activation manifest SHA-256: `ca53b0403a1a9b9b3f9dba8bd18494966dc5df407f75932e94076c0088e2da3c`;
- base Factory plan SHA-256: `8f7824f26c7db3124d6fc8b521195fe1189bf2897d28687153821d44d6ea4f6f`.

## Proposal builder

`benchmark_campaign.capacity_extension.build_capacity_extension_manifest` consumes the decrypted schema-26 reserve consolidation bundle and fails closed unless:

1. repository status is schema 27 and the capacity-extension target is open;
2. the canonical reserve consolidation repository evidence matches the expected reserve-ledger and exhausted-slot hashes;
3. the decrypted `RESERVE_LEDGER.jsonl`, `EXHAUSTED_SLOTS.json`, and `RESERVE_MANIFEST.json` match those canonical hashes;
4. the source reserve consolidation manifest is schema 26 and is bound to the same base Factory plan and activation manifest;
5. exactly **10** exhausted rows are present;
6. every exhausted row maps to a schema-26 `reserve:01` task whose ledger state is `exhausted`, outcome is `skipped`, and terminal-failure flag is true;
7. every `reserve:01` predecessor was part of the reviewed activation manifest;
8. the linked primary is a non-holdout primary slot;
9. the base Factory plan contains no `reserve:02` for that primary;
10. no primary, predecessor reserve, or proposed reserve ID is duplicated.

For each validated exhausted primary, the builder deterministically constructs one slot:

```text
<primary-slot-id>:reserve:02
```

The slot inherits the frozen primary benchmark, partition, anchor source, task type, labels, policy, risk tier, and visibility, then adds:

```json
{
  "candidate_slot_kind": "reserve",
  "replacement_for_slot_id": "<primary-slot-id>",
  "reserve_attempt": 2
}
```

The proposed slot and its SHA-256 binding are written into `CAPACITY_EXTENSION.json`.

## Proposal is not execution authority

The generated manifest explicitly carries:

```json
{
  "capacity_extension_proposed": true,
  "execution_authorized": false,
  "requires_repository_approval": true
}
```

The proposal must be independently reviewed and committed before any task builder, reconciliation path, or execution workflow may accept `reserve:02`.

Schema 27 therefore has the same two-boundary pattern used by schema 26:

```text
canonical exhausted evidence
        ↓
capacity-extension proposal
        ↓
repository review/freeze
        ↓
later execution-enablement protocol
```

The current PR implements only the first two stages. It does not implement or authorize reserve-attempt-2 execution.

## Proposal workflow

Use:

`.github/workflows/h392-capacity-extension.yml`

The workflow is manual, main-only, stale-dispatch resistant, and has no editable run ID, artifact ID, slot count, slot IDs, or reserve-attempt inputs.

It:

1. verifies the repository is on schema 27 and capacity extension is still disabled;
2. verifies the exact canonical reserve consolidation target;
3. downloads only artifact `11464000900`;
4. verifies GitHub run provenance, artifact digest, redacted-summary hash, encrypted-bundle hash, and bundle hash declaration;
5. decrypts the source-bearing bundle only in the ephemeral runner;
6. invokes the schema-27 proposal builder using the repository-reviewed reserve-ledger and exhausted-slot hashes;
7. proves the proposal contains exactly 10 unique `:reserve:02` slots;
8. proves `execution_authorized=false` and `requires_repository_approval=true`;
9. rejects source text, gold payload, model identity, task payloads, excerpts, and support text from the proposal;
10. deletes decrypted evidence;
11. reconfirms `main` before publication;
12. uploads only `CAPACITY_EXTENSION.json`.

The artifact name is:

`h392-capacity-extension-proposal`

## Adjudication remains separate

The **153 pending adjudications** are not part of the capacity-extension set.

They remain a separate source-review surface:

- 129 primary adjudications;
- 24 reserve adjudications.

AI may prepare evidence packets, verify source locations, compare Curator/Verifier claims, and organize the cases. AI cannot self-authorize acceptance. The final decision must satisfy the human/authority review policy in `CURATION.md`.

A future terminal adjudication rejection also does not automatically create further reserve capacity. Any new candidate opportunity arising from adjudication outcomes requires its own evidence-bound reviewed update.

## Frozen schema-27 proposal

Capacity extension proposal run `37588897387` completed successfully on main commit `174da564ff8158c86898575e3097d15394a2ffae`.

The reviewed GitHub artifact is:

- artifact ID: `11467766861`;
- artifact digest: `sha256:2b36aef77dfa885a01f271377d4f6164698c9d6cd56adb1c59aaba906c045115`;
- proposal manifest SHA-256: `9bd2468737d0cd1b89227b3b625814dfc1a3cab25512fece98ae377ef1ac4fce`.

The artifact contained exactly one file, `CAPACITY_EXTENSION.json`, and exactly ten extension rows. Independent maintainer review rechecked all ten row bindings, including the primary-slot binding, prior `reserve:01` binding, and proposed `reserve:02` binding. The exact canonical exhausted offsets are:

```text
0, 1, 2, 3, 4, 5, 13, 20, 21, 32
```

All ten exhausted predecessors terminate with the canonical reason `curator_rejection:adapter:contract_support_not_verbatim`. No source text, gold payload, model identity, Curator/Verifier payload, excerpt, or support text is present in the proposal.

The exact reviewed proposal is committed as:

`artifacts/CAPACITY_EXTENSION_9bd2468737d0cd1b89227b3b625814dfc1a3cab25512fece98ae377ef1ac4fce.json`

The committed file must remain byte-identical to the reviewed artifact payload.

## Schema-28 execution enablement

Schema 28 supplies the separate execution authority that schema 27 deliberately withheld. The authority is repository state, not a mutation of the schema-27 proposal artifact: `CAPACITY_EXTENSION.json` continues to record `execution_authorized=false`.

The executable set is exactly the ten committed rows in:

`artifacts/CAPACITY_EXTENSION_9bd2468737d0cd1b89227b3b625814dfc1a3cab25512fece98ae377ef1ac4fce.json`

The reusable pilot accepts the internal task scope `approved_capacity_extension` only through `workflow_call`; direct manual pilot dispatch remains primary-only. For this scope, Factory task construction appends the frozen `reserve:02` slots in memory after the complete schema-26 base plan. This preserves every historical primary and `reserve:01` slot, offset, task fingerprint, and Factory-plan hash. Because the overlay is appended after the base plan, the deterministic source-window allocator sees each primary and `reserve:01` predecessor first and requires a distinct segment for `reserve:02`.

Curator execution, verifier-task preparation, and reconciliation all require the exact committed capacity-extension path. Reconciliation rejects mixed reserve attempts and stores a dedicated `factory_verification.capacity_extension` binding rather than pretending that `reserve:02` was part of the schema-26 activation.

Execution uses:

`.github/workflows/h392-reserve2-campaign.yml`

The workflow has no task-count, task-ID, task-scope, offset, or reserve-attempt inputs. It validates schema 28, the exact manifest SHA-256, and the exact ten-slot execution target; performs one centralized readiness gate; and delegates five deterministic two-task shards to the reusable pilot. Source-bearing outputs remain AES-GCM encrypted. Only redacted shard summaries and a redacted aggregate are public artifacts.

The current gate is:

```ini
freeze_schema_version               = 28
capacity_extension_proposal_frozen  = true
capacity_extension_enabled          = true
reserve2_execution_target.ready     = true
reserve2_execution_target.completed = false
reserve2_expected_tasks             = 10
reserve2_expected_shards            = 5
benchmark_population_complete       = false
benchmark_gate_passed               = false
h4_qualification_allowed            = false
```

The 153 pending adjudications are not eligible for this execution. A successful reserve2 campaign is still execution evidence, not an automatic benchmark-population mutation; it must be consolidated and frozen before canonical population state changes.
