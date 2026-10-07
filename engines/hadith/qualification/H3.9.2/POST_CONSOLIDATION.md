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

## Approved reserve execution

The reviewed execution surface is now `.github/workflows/h392-reserve-campaign.yml`. It is manual, main-only, stale-dispatch resistant, and bound to the committed activation manifest rather than to a copied count.

The execution target is exactly **41 non-holdout reserve slots**. Before any model task runs, the workflow revalidates repository status, the activation manifest SHA-256, the Factory-plan binding, and the exact activated slot count. It then performs one centralized Curator/Verifier readiness gate and dispatches the activated set in deterministic shards of at most eight tasks through the reusable curation runner.

The reusable runner keeps ordinary manual pilot dispatch primary-only. Reserve mode is available only to a `workflow_call` caller using `task_scope=approved_reserve`. In that mode, task selection is by exact activated reserve slot ID, not by the unrestricted candidate suffix, and `factory-reconcile` receives the repository-approved `--reserve-activation` manifest. Any unlisted reserve fails closed.

Every shard persists source-bearing tasks, model responses, reviewed records, adjudication rows, and the curation ledger only inside the existing authenticated encrypted bundle. The campaign aggregate reads only redacted shard summaries and requires exact 0..40 coverage, one outcome per activated slot, a single Git commit, and the approved activation hash.

A successful execution run is still evidence, not a mutation of the canonical benchmark population. Its run/artifact provenance and source-bearing outcomes must be consolidated and frozen before repository status marks the execution target complete or any later eligibility expansion is considered.

### Completed reserve execution observation

Reserve execution run `37532437191` was dispatched from main commit `5fdeb0d8a7446a319c0bf21477d1ac916e2d7fc7`.

Attempt 1 failed only in shard `0..7` when Verifier AI-B hit an executor timeout. The workflow correctly failed closed. GitHub's failed-job rerun was then used rather than replaying all 41 stochastic tasks. Final run attempt 2 completed successfully, preserving the five successful attempt-1 shard artifacts and generating a new `0..7` artifact.

The successful redacted aggregate artifact is:

- artifact ID: `11460611920`;
- artifact ZIP digest: `sha256:f00b363321838289034388af9953cb11fde6709acf4780c210acd931bb3003a9`;
- `RESERVE_CAMPAIGN_SUMMARY.json` SHA-256: `8638a50d177ea716fa429fe0f5cc356203a2ff081072212c3edaf47e05b394d0`;
- exact activated coverage: **41/41**, ranges `0..7`, `8..15`, `16..23`, `24..31`, `32..39`, `40`;
- redacted outcome accounting: **7 promoted, 24 adjudication, 10 skipped**.

Those counts are an execution observation only. They become canonical evidence only if reserve consolidation decrypts and independently revalidates every source-bearing shard.

The source artifact lineage is intentionally mixed-attempt and must be preserved exactly:

- `0..7`: run attempt 2, job `112616768431`, artifact `11459534901`;
- `8..15`: run attempt 1, job `112505599674`, artifact `11447747202`;
- `16..23`: run attempt 1, job `112505599470`, artifact `11447791580`;
- `24..31`: run attempt 1, job `112505599580`, artifact `11447431400`;
- `32..39`: run attempt 1, job `112521204424`, artifact `11449199919`;
- `40`: run attempt 1, job `112525032628`, artifact `11447543077`.

Treating every artifact as "attempt 2" would erase the provenance of the five preserved successful shards and is prohibited by the repository-reviewed consolidation target.

## Reserve execution consolidation

Use:

`.github/workflows/h392-reserve-consolidation.yml`

The workflow has no editable run-ID, artifact-ID, count, or outcome inputs. The complete acquisition target is frozen in `artifacts/H3.9.2-STATUS.json`.

It must:

1. verify the final reserve run is successful on the exact reviewed main commit and final attempt;
2. verify the successful redacted aggregate artifact by exact artifact ID, GitHub digest, summary hash, activation hash, coverage, and outcome accounting;
3. fetch only the six repository-reviewed shard artifact IDs;
4. bind every shard artifact to its exact source job ID and actual run attempt, including the mixed attempt-1/attempt-2 history;
5. verify artifact ZIP, redacted-summary, and encrypted-bundle SHA-256 values before decryption;
6. reacquire and verify the current pinned non-holdout source bytes;
7. decrypt source-bearing evidence only in the ephemeral runner;
8. revalidate every reserve task against the frozen Factory plan and the exact repository-approved activation manifest;
9. reconstruct Curator/Verifier response bindings, deterministic reconciliation, promoted records, adjudication rows, and exact source grounding;
10. emit one 41-row reserve ledger in activation order;
11. mark a skipped reserve as **exhausted** only when the frozen plan proves that linked primary has no unconsumed preregistered reserve capacity;
12. re-encrypt all source-bearing consolidated material and delete plaintext before publication;
13. upload only a redacted consolidation summary and the authenticated encrypted consolidated bundle.

The source-bearing consolidated bundle contains:

- `RESERVE_LEDGER.jsonl`;
- `RESERVE_ADJUDICATION.jsonl`;
- promoted reviewed records grouped by benchmark;
- `EXHAUSTED_SLOTS.json`;
- `RESERVE_MANIFEST.json`.

The redacted summary may expose counts, identifiers, hashes, and bounded reason classes, but never source text, gold payloads, model identity, or hidden reasoning.

If decrypted validation reproduces the observed **7 promoted / 24 adjudication / 10 skipped** result, the 210-slot primary surface will have:

```text
40 promoted primaries
129 pending primary adjudications
7 promoted reserve replacements
24 pending reserve adjudications
10 exhausted slots
= 210 original required slots
```

Under the current one-reserve-per-primary freeze, the maximum fillable population before any new capacity is therefore `47 + 153 = 200`. The **minimum capacity shortfall is 10** even if every pending adjudication is eventually accepted. That shortfall must be reported; a second reserve attempt requires a later reviewed protocol/capacity extension and cannot be created implicitly by consolidation.

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

## Canonical reserve consolidation result

Reserve consolidation workflow run `37578659973` completed successfully on main commit `b3888b24b20571884465b349c9764c669b0e66f9`.

The published artifact is:

- artifact ID: `11464000900`;
- artifact ZIP digest: `sha256:00385663166059b3701c0581bd460ba2f2d39a796d3cca1c1b015fb96170b64e`;
- redacted summary SHA-256: `13ccc3f3ae985fb2f577fb05e2f5e9b5bbddcbf87d41d1263e1a4fa07a87bd67`;
- encrypted consolidated bundle SHA-256: `f73a1e1dc170af9a8fa4dde6c47348e85690fe4df712bda573b001c66b39dc19`;
- reserve-ledger SHA-256: `f1fbd43fd68806c64a3d63d7eae0226c4f66e6e5f5ec12ab07e74d1d6ff63012`;
- exhausted-slots SHA-256: `7140e7b110d4be44d3685b20649bcd4df04b69d1cd561eb4afa69c3ba1c75490`.

The workflow revalidated the exact six mixed-attempt source artifacts, decrypted them only in the ephemeral runner, reacquired and verified pinned source bytes, reconstructed all 41 reserve outcomes, and reproduced the execution aggregate exactly:

```text
7 promoted reserve replacements
24 pending reserve adjudications
10 exhausted slots
= 41 activated reserves
```

The canonical 210-slot surface is therefore:

```text
40 promoted primaries
129 pending primary adjudications
7 promoted reserve replacements
24 pending reserve adjudications
10 exhausted slots
= 210 required slots
```

This yields **47 validated promoted records**, **153 pending adjudications**, and **10 exhausted slots**. Under the frozen one-reserve-per-primary capacity, even accepting every pending adjudication can fill at most **200/210** slots, so the minimum capacity shortfall is now canonically **10**.

The compact repository evidence is `artifacts/RESERVE_CONSOLIDATION_EVIDENCE_41.json`. No second reserve attempt is authorized by schema 26.

## Current state

```ini
cumulative_primary_evidence_complete       = true
primary_pending_adjudication_count         = 129
reserve_consolidation_complete             = true
canonical_reserve_promoted                 = 7
canonical_reserve_pending_adjudication      = 24
canonical_exhausted_slots                  = 10
validated_promoted_record_count            = 47
combined_pending_adjudication_count        = 153
maximum_fillable_under_current_capacity    = 200
minimum_capacity_shortfall                 = 10
automatic_second_reserve_authorized        = false
benchmark_population_complete              = false
benchmark_gate_passed                      = false
```

The next work must remain split into two reviewed surfaces: adjudicate the 153 pending cases under the human/authority policy, and separately define any capacity extension needed for the 10 exhausted slots. A capacity extension is a new protocol decision; consolidation itself does not create reserve attempt 2.

## Schema-27 handoff

Schema 26 is now closed as an evidence-producing stage. Its canonical outputs are the 47 validated promoted records, 153 pending adjudications, and 10 exhausted slots recorded in `artifacts/RESERVE_CONSOLIDATION_EVIDENCE_41.json`.

Because the 10 exhausted slots prove a minimum shortfall even under the best possible adjudication outcome, the next machine-generated artifact is a **capacity-extension proposal**, not another reserve execution. Schema 27 is specified in `CAPACITY_EXTENSION.md` and implemented by `.github/workflows/h392-capacity-extension.yml`.

The proposal is limited to the exact 10 canonical exhausted slots and defines one deterministic `:reserve:02` slot for each. It is not executable authority. A separate repository-review boundary must freeze the generated manifest before task generation or reconciliation can be extended to those slots.

The 153 adjudications remain orthogonal. Their future packet/review protocol must preserve the primary-vs-reserve provenance of each case and require human/authority decisions; schema 27 does not convert them into replacement eligibility.

## Schema-28 reserve2 execution handoff

Schema 27 is now closed as the proposal/freeze stage. Capacity proposal run `37588897387` produced and repository review froze exactly ten `:reserve:02` overlay slots in `artifacts/CAPACITY_EXTENSION_9bd2468737d0cd1b89227b3b625814dfc1a3cab25512fece98ae377ef1ac4fce.json`.

Schema 28 authorizes execution of only those ten slots through `.github/workflows/h392-reserve2-campaign.yml`. The schema-27 manifest itself remains `execution_authorized=false`; execution authority comes from the schema-28 repository status and workflow binding. The historical schema-26 Factory plan is not rewritten.

The reusable pilot receives the explicit internal scope `approved_capacity_extension`, and every Factory boundary that can admit Curator output receives the exact capacity manifest: task construction, Curator task validation, verifier-task preparation, and reconciliation. A promoted `reserve:02` record carries a dedicated `factory_verification.capacity_extension` provenance object; it is never represented as a schema-26 `reserve_activation` record.

The campaign is fixed at ten tasks in five two-task shards. This reduces the replay surface if a workflow-level fatal infrastructure failure requires a failed-job rerun while preserving the existing task-local collection semantics.

A successful reserve2 campaign remains execution evidence only. Its encrypted source-bearing shards and redacted aggregate must be consolidated and frozen before the canonical 210-slot population is updated. The existing 153 pending adjudications remain outside the reserve2 execution set.

## Schema-29 reserve2 evidence consolidation

Reserve2 execution run `37613354755` completed successfully on attempt 1 from main commit `d6e04fc061426d2248dba0e9e4f7e5e484b6ae1b`. Its redacted aggregate artifact is `11478509807` with ZIP digest `sha256:dc02b20177f70f86d6f404f30d4733ccd204e309acef817b9c3d665d265754a1` and summary SHA-256 `22aa91a82d7b35eda0480806c89a417b222282edcd6aff86b7ff851210a75b73`.

The execution observation is exactly:

```text
3 promoted
5 adjudication
2 skipped
= 10 reserve:02 tasks
```

Schema 29 deliberately does not make those counts canonical from the redacted aggregate alone. It closes `reserve2_execution_target.ready` against redispatch and freezes the exact five shard artifact IDs, source job IDs, artifact ZIP digests, redacted-summary hashes, encrypted-bundle hashes, offsets, and run attempt in repository status.

Use `.github/workflows/h392-reserve2-consolidation.yml`. The workflow has no editable evidence inputs. It verifies the successful source run and aggregate, fetches only the five reviewed shard artifacts, binds every artifact to its exact successful job, reacquires and verifies pinned non-holdout source bytes, decrypts source-bearing evidence only in the ephemeral runner, and invokes `consolidate-reserve2` against the exact committed schema-27 capacity manifest.

The consolidator re-runs the same Curator/Verifier identity, blindness, source-grounding, deterministic reconciliation, reviewed-record resealing, and provenance checks used for schema-26 reserve evidence, but requires `reserve_attempt=2` and `factory_verification.capacity_extension`. Before counting any new promotion, the workflow also reacquires the exact canonical schema-25 primary-consolidation artifact and schema-26 reserve-consolidation artifact, verifies their run/artifact/encrypted-bundle/ledger bindings, decrypts them only ephemerally, and reconstructs the exact 47 already-promoted `case_id` values. Any reserve:02 promotion colliding with that canonical set fails consolidation. The derived ID set is not published; only its count and SHA-256 binding may appear in redacted consolidation evidence. The consolidator emits `RESERVE2_LEDGER.jsonl`, `RESERVE2_ADJUDICATION.jsonl`, promoted reviewed records, `RESERVE2_EXHAUSTED_SLOTS.json`, and `RESERVE2_MANIFEST.json` only inside the encrypted consolidated bundle.

If source-bearing validation reproduces the observed 3/5/2 outcome, the resulting evidence-level state will be 50 validated promoted records, 158 pending adjudications, and 2 remaining exhausted slots, with a maximum fillable population of 208/210 and a minimum capacity shortfall of 2. Those figures remain non-canonical until the consolidation artifact itself is independently reviewed and frozen. No `reserve:03` capacity is authorized by schema 29.

