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

Reserve promotion is intentionally **disabled** in schema 24. The standard reviewed workflows remain bounded to the 896 non-holdout primary tasks, and reconciliation fails closed if a reserve task is supplied. A later protocol revision must bind reserve use to cumulative evidence that the linked primary is terminally replaceable; unresolved adjudication is not replacement eligibility.

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

No disagreement is silently discarded or rewritten into agreement. Reserve tasks are also fail-closed at reconciliation until an explicit cumulative replacement-eligibility binding is implemented.

## Orchestration trust boundary

`model_family` and `model_ref` are **orchestration metadata**, not scholarly evidence and not a model's self-asserted authority. The runner/custodian is responsible for wrapping model output with the actual model family/ref used for that run. The factory enforces structural separation, rejects ordinary answer-bearing fields/label values from the Verifier input, normalizes model-family strings for independence checks, and hashes both response envelopes. It does not claim cryptographic proof of a provider identity or immunity to deliberate steganographic leakage.
