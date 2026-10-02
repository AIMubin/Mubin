# H3.9.2 Benchmark Factory

The Benchmark Factory operationalizes the 1,280-case campaign without turning AI opinion into benchmark truth.

```text
Pinned source corpus
        ↓
Git-blob verified source cache
        ↓
Deterministic source index
        ↓
Frozen 1,280 quota slots
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

`non_holdout` is the only default acquisition/index/task partition. Any operation containing final-holdout sources requires `--custodian-holdout`, and its cache/task/review/ledger output must be outside the campaign checkout.

This does not make public source books secret. It prevents H4 development artifacts and tuning workflows from accidentally consuming the preregistered final-holdout source partition.

## Factory policy

| Benchmark | Risk | Auto promotion |
|---|---:|---|
| external-critical-commentary | 1 | source-attributed dual-AI agreement |
| transmission-language | 1 | source-attributed dual-AI agreement |
| biographical-scope | 2 | source-attributed dual-AI agreement |
| cross-witness-identity | 3 | no; adjudication required |
| report-family-identity | 3 | no; adjudication required |

Auto-promotion still requires literal source support and all H3.9.2 provenance checks. AI agreement alone never qualifies a case.

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

All subsequent holdout commands use `--custodian-holdout` and `/custodian/...` paths. Only after the full reviewed population is complete does the existing split/seal flow produce public holdout records without plaintext gold.

## File-based AI interface

The factory intentionally uses JSONL contracts instead of embedding one model-provider SDK. Curator and Verifier can be local or remote as long as each records a stable `model_family` and `model_ref` and obeys the contracts.

## Curation ledger

`CURATION_LEDGER.jsonl` contains task identity, outcome, response hashes, model families, and promoted case ID. It does not contain gold answers. For holdout it remains inside the external custodian boundary.

## Failure behavior

A case goes to adjudication when Curator and Verifier disagree, model families are not independent, source support is invalid or crosses partitions, benchmark/anchor identity differs from the frozen slot, policy forbids auto-promotion, or the candidate fails the source-attributed qualification contract.

No disagreement is silently discarded or rewritten into agreement.
