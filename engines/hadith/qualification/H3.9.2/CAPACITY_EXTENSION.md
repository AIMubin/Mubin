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

## Current schema-27 gate

Until the generated proposal is reviewed and frozen:

```ini
capacity_extension_enabled          = false
capacity_extension_target.ready     = true
capacity_extension_target.completed = false
reserve_attempt_2_execution         = unauthorized
benchmark_population_complete       = false
benchmark_gate_passed               = false
h4_qualification_allowed            = false
```
