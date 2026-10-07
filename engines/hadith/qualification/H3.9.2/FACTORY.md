# H3.9.2 Benchmark Factory

The Benchmark Factory operationalizes the 1,280-case campaign without turning AI opinion into benchmark truth.

```text
Pinned source corpus
        ↓
Git-blob verified source cache
        ↓
Deterministic source index
        ↓
Frozen exact record quotas
(1,280 primary slots)
        ↓
Preregistered candidate plan
(+1 reserve per primary)
        ↓
Curator AI-A
        ↓
Blind task for Verifier AI-B
        ↓
Independent evidence verification
        ↓
Exact gold agreement?
       / \
     no   yes
     ↓     ↓
adjudication  policy gate
                 / \
              human  source-attributed auto-promotion
                 \ /
              reviewed pool
```

## Partition isolation

`non_holdout` is the only default acquisition/index/task partition. Any operation containing final-holdout sources requires `--custodian-holdout`. Every source-bearing input and output for that operation — source cache, source index, Curator tasks/responses, Verifier tasks/responses, reviewed staging, adjudication queue, and curation ledger — must be outside the campaign checkout.

This does not make public source books secret. It prevents H4 development artifacts and tuning workflows from accidentally consuming the preregistered final-holdout source partition.

## Factory policy

| Benchmark | Risk | Auto promotion |
|---|---:|---|
| external-critical-commentary | 1 | source-attributed dual-AI agreement |
| transmission-language | 1 | source-attributed dual-AI agreement |
| biographical-scope | 2 | source-attributed dual-AI agreement |
| cross-witness-identity | 3 | no; adjudication required |
| report-family-identity | 3 | no; adjudication required |

Auto-promotion still requires literal source support, an exact `gitblob:<sha>#char=start:end` locator that resolves to the excerpt, a record-to-frozen-slot binding hash, and all H3.9.2 provenance checks. AI agreement alone never qualifies a case. The promoted record embeds Curator/Verifier model identities, response SHA-256 hashes, task fingerprint, risk tier, and independently verified support hashes; the validator rejects unreviewed AI `source_attributed` records that bypass this contract.

Freeze schema 24 separates **record quota** from **candidate-discovery capacity**. The original 1,280 primary slots remain the exact record-quota surface and retain their IDs/order/task fingerprints. One reserve candidate slot is preregistered for each primary, giving 2,560 candidate slots total while leaving the record target at 1,280. Reserve tasks are linked by `replacement_for_slot_id` and must use a source window distinct from their linked primary.

Freeze schema 24 preregistered reserve capacity but left it disabled. Schema 25 established cumulative replacement eligibility. Schema 26 adds a second binding layer: reserve reconciliation requires a reviewed `RESERVE_ACTIVATION.json`, and final validation separately requires that the record's activation hash match the repository-approved activation in `H3.9.2-STATUS.json`. Unresolved adjudication is never replacement eligibility.

## Non-holdout workflow

From `engines/hadith/qualification/H3.9.2`:

```bash
python -m benchmark_campaign acquire-sources --partition non_holdout --cache-dir source-cache
python -m benchmark_campaign factory-index-sources --partition non_holdout --cache-dir source-cache --out-dir factory-work/non-holdout-index
python -m benchmark_campaign factory-plan --out factory-work/plan.json
python -m benchmark_campaign factory-build-tasks --partition non_holdout --plan factory-work/plan.json --index-dir factory-work/non-holdout-index --out factory-work/curator-tasks.jsonl
```

Run Curator AI-A using `agents/CURATOR_CONTRACT.md`, producing `curator-responses.jsonl`, then:

```bash
python -m benchmark_campaign factory-prepare-verifier --tasks factory-work/curator-tasks.jsonl --curator-responses factory-work/curator-responses.jsonl --out factory-work/verifier-tasks.jsonl
```

Run a different model family as Verifier AI-B, then reconcile:

```bash
python -m benchmark_campaign factory-reconcile --tasks factory-work/curator-tasks.jsonl --curator-responses factory-work/curator-responses.jsonl --verifier-responses factory-work/verifier-responses.jsonl --source-cache-dir source-cache --reviewed-dir staging --adjudication-out factory-work/adjudication.jsonl --ledger-out factory-work/CURATION_LEDGER.jsonl
```

## Holdout workflow

Run the same flow under the benchmark custodian boundary. Acquisition, source index, tasks, responses, reviewed staging, adjudication queue, and ledger must use paths outside the repository.

Example:

```bash
python -m benchmark_campaign acquire-sources --partition holdout --custodian-holdout --cache-dir /custodian/h392/source-cache
```

All subsequent holdout commands use `--custodian-holdout` and `/custodian/...` paths for both inputs and outputs. Only after the full reviewed population is complete does the existing split/seal flow produce public holdout records without plaintext gold.

## File-based AI interface

The factory intentionally uses JSONL contracts instead of embedding one model-provider SDK. Each task includes a hash-bound `retrieval_scope` for the complete allowed partition index; the anchor segment is only the starting point, so multi-source H3.8/H3.9 cases can retrieve corroborating material without crossing the frozen source boundary. The exact 1,280-record quota plan and its preregistered reserve candidate suffix are re-derived from frozen quotas/spec/policy whenever tasks are built, each task fingerprint is recomputed before use, and the source-index manifest hashes `segments.jsonl`; tampering with any of these surfaces fails closed. Curator and Verifier can be local or remote as long as each records a stable `model_family` and `model_ref` and obeys the contracts.

## Curation ledger

`CURATION_LEDGER.jsonl` contains task identity, outcome, response hashes, model families, and promoted case ID. It does not contain gold answers. For holdout it remains inside the external custodian boundary.

## Failure behavior

A case goes to adjudication when Curator and Verifier disagree, model families are not independent, source support is invalid or crosses partitions, benchmark/anchor identity differs from the frozen slot, policy forbids auto-promotion, or the candidate fails the source-attributed qualification contract.

On the non-holdout collection surface, a Curator candidate whose `payload.input` would leak a selected answer to Verifier AI-B is not allowed into the verifier task set. That candidate is counted as a verifier-preparation rejection and later reaches reconciliation without a verifier response, which routes it to adjudication rather than aborting unrelated tasks. Holdout preparation remains fail-closed.

The full preregistered `allowed_labels` vocabulary is public task metadata, not a selected answer. An exact duplicate inside `payload.input` is therefore permitted; a subset or modified list is rejected.

No disagreement is silently discarded or rewritten into agreement. Reserve tasks are fail-closed unless `factory-reconcile` receives a schema-26 activation manifest that authorizes each exact reserve slot.

## Orchestration trust boundary

`model_family` and `model_ref` are **orchestration metadata**, not scholarly evidence and not a model's self-asserted authority. The runner/custodian is responsible for wrapping model output with the actual model family/ref used for that run. The factory enforces structural separation, rejects ordinary answer-bearing fields/label values from the Verifier input, normalizes model-family strings for independence checks, and hashes both response envelopes. It does not claim cryptographic proof of a provider identity or immunity to deliberate steganographic leakage.


## Cumulative primary evidence gate

Canonical encrypted primary runs are consolidated before reserve activation. The implementation is documented in `CONSOLIDATION.md` and exposed by:

```bash
python -m benchmark_campaign consolidate-primary \
  --evidence-root /path/to/provenance-bound/decrypted-runs \
  --out-dir /path/to/protected/cumulative-output \
  --expected-task-count 210
```

The consolidator rejects duplicate primary tasks, reserve tasks, task/fingerprint drift, incomplete Curator/Verifier manifests, reviewed/adjudication mismatches, and unbound terminal failures. It emits a cumulative ledger, cumulative adjudication queue, merged reviewed records, and a replacement-eligibility manifest whose entries are bound to the cumulative ledger SHA-256.

A primary is replacement eligible only when the cumulative evidence proves a terminal Curator `no_candidate` or a task-local Curator contract/model-output rejection. Promoted primaries and every unresolved adjudication remain ineligible. The resulting manifest is evidence only: freeze schema 25 still keeps reserve reconciliation disabled.


### Freeze schema 25: cumulative evidence binding

Freeze schema 25 adds `benchmark_campaign/consolidation.py` to the frozen protocol surface and introduces provenance-bound cumulative primary accounting. It does not alter the schema-24 primary/reserve candidate plan. The cumulative artifact binds the exact zero-based primary prefix, source workflow/artifact digests, reviewed/adjudication outcomes, the current Factory-plan hash, and replacement-eligible primary/reserve slot bindings. Reserve reconciliation remains disabled.


## Freeze schema 26: reserve activation binding

The authoritative schema-25 cumulative result for the first completed non-holdout benchmark surface proves 41 terminal replacement-eligible primaries. Schema 26 does not treat that count as execution authority.

Use `benchmark_campaign post-consolidation` via the `build-reserve-activation` CLI to derive a redacted activation manifest from the decrypted cumulative bundle:

```bash
python -m benchmark_campaign build-reserve-activation \
  --cumulative-dir /protected/cumulative \
  --out /protected/RESERVE_ACTIVATION.json \
  --expected-cumulative-ledger-sha256 <reviewed-ledger-sha256> \
  --expected-replacement-eligibility-sha256 <reviewed-eligibility-sha256>
```

The builder re-derives the Factory plan, validates the schema-25 eligibility rules, requires each eligible primary to be a terminal skipped row in the cumulative ledger, and rechecks every primary/reserve slot-binding hash. The emitted manifest contains only identifiers, bounded reason classes, and hashes.

After an activation artifact is independently reviewed and frozen, reserve reconciliation uses:

```bash
python -m benchmark_campaign factory-reconcile \
  ... \
  --reserve-activation /protected/RESERVE_ACTIVATION.json
```

Primary-only reconciliation must not receive this flag. A reserve task absent from the activation manifest fails closed. See `POST_CONSOLIDATION.md` for the full adjudication and activation sequence.

## Freeze schema 27: selective capacity-extension proposal

Schema 26 completed the first reserve cycle and proved a structural shortfall: 10 non-holdout primary slots remain exhausted after their exact approved `reserve:01` opportunity. The base Factory plan remains the schema-26 1,280-primary + 1,280-reserve plan and is not rewritten after observing those outcomes.

Schema 27 introduces `benchmark_campaign/capacity_extension.py` and `.github/workflows/h392-capacity-extension.yml`. The builder consumes only the canonical schema-26 reserve ledger and exhausted-slot evidence and deterministically proposes one `:reserve:02` slot for each of the 10 exhausted primaries. The new slot is an append-only overlay definition; historical primary and `reserve:01` slot objects, hashes, offsets, task fingerprints, activation evidence, and execution provenance remain untouched.

The generated `CAPACITY_EXTENSION.json` is redacted and explicitly carries `execution_authorized=false` and `requires_repository_approval=true`. No Factory task generation or reconciliation path accepts `reserve:02` under this schema until a later reviewed enablement change consumes the frozen proposal. Pending adjudications are excluded from this extension surface. See `CAPACITY_EXTENSION.md`.

