# Mubin H3.9.2 — Benchmark Expansion Campaign R3

This package implements **only H3.9.2**, the qualification campaign between H3.9.1 and H4.0. It does not add H4 features or change the H3.5–H3.9 reasoning architecture.

## Frozen target

| Milestone | Benchmark | Total | Development | Validation | Final holdout |
|---|---|---:|---:|---:|---:|
| H3.5 | `external-critical-commentary` | 300 | 150 | 60 | 90 |
| H3.6 | `transmission-language` | 240 | 120 | 48 | 72 |
| H3.7 | `biographical-scope` | 200 | 100 | 40 | 60 |
| H3.8 | `cross-witness-identity` | 240 | 120 | 48 | 72 |
| H3.9 | `report-family-identity` | 300 | 150 | 60 | 90 |

Total reviewed qualification target: **1,280 cases**.

## R3 integrity model

R3 closes the remaining holdout-visibility gap. Final-holdout labels are not permitted in public benchmark records. During `build-splits`, holdout gold is encrypted with **AES-256-GCM** into `sealed-holdout/<benchmark>.gold.aesgcm.json`; the 256-bit key is external and must never be committed or packaged with the campaign. The public holdout retains only inputs, provenance, family identity, fingerprints, and `gold_sealed=true`.

The encrypted payload is cryptographically bound to the public case identity, normalized input fingerprint, complete source set, semantic family, and gold status. The freeze hashes the ciphertext and protocol. Final evaluation requires the external key **after** `MODEL_LOCK.json` exists. A wrong key, modified ciphertext, changed public holdout, or changed predictions after first access fails closed.

The in-repository `staging/reviewed.jsonl` surface is also sanitized after sealing so it does not retain plaintext holdout labels. Any pre-seal curator source file containing holdout gold must be kept on a custodian-private surface outside the developer/tuning workspace.

## Provenance and disjointness

A case may depend on more than one source. `source_ids` contains **every** canonical work used by the case and `source_refs` contains one pinned, verbatim reference per source. Source isolation therefore applies to the complete evidence set, not merely a primary source.

Each source reference carries a canonical source ID, pinned repository/path/commit, Git blob SHA, exact locator, verbatim UTF-8 excerpt, and recomputed excerpt SHA-256. `content_fingerprint` is recomputed from normalized `payload.input`.

Disjointness is enforced both per benchmark and campaign-wide. A source, semantic `family_id`, or input fingerprint appearing in any final holdout may not appear in development/validation of another benchmark. `config/curation-plan.json` freezes the global source partition before curation; cross-partition multi-source cases are rejected.

## Pre-registered curation quotas

`config/curation-quotas.json` is deterministically derived from the benchmark targets and frozen source partition. It allocates all **1,280** pending cases across source pools before case selection begins. The quotas are operational anchors only: they do not infer or create gold labels. Validation rejects a quota file that no longer matches the frozen spec/source partition.

Generate/verify the plan with:

```bash
python -m benchmark_campaign curation-queue-plan
```

## Source acquisition and curation

The registry pins 18 qualification-eligible OpenITI source versions. `discovery:itqan:199d870` is candidate-only and can assist discovery, but can never serve as qualification provenance by itself.

In a network-enabled environment:

```bash
python -m benchmark_campaign acquire-sources
python -m benchmark_campaign verify-source-cache
```

Downloaded bytes are checked using the Git blob algorithm against the pinned blob SHA. A mismatch is fail-closed.

Reviewed records are then sealed from human-curated JSONL:

```bash
python -m benchmark_campaign curate-reviewed \
  --benchmark-id transmission-language \
  --input /custodian-private/reviewed-input.jsonl
```

Curation verifies every quoted excerpt verbatim against the pinned local source cache and derives source IDs, excerpt hashes, and the input fingerprint. It does **not** create labels automatically.

## Qualification lifecycle

The required order is:

```text
source acquisition
→ human/source-grounded curation
→ generate external holdout key
→ build source/family-disjoint splits + seal holdout gold
→ prepare manifests
→ validate
→ FREEZE
→ commit the frozen manifest + frozen file set to Git
→ create detached freeze anchor bound to that immutable Git commit
→ export tuning pack (development + validation only)
→ optional tuning
→ MODEL LOCK
→ one-shot final holdout predictions
→ decrypt/evaluate sealed holdout
→ pre-h4-audit
```

Typical commands:

```bash
python -m benchmark_campaign generate-holdout-key --out /secure/off-repo/mubin-m392.key
python -m benchmark_campaign build-splits --holdout-key-file /secure/off-repo/mubin-m392.key
python -m benchmark_campaign prepare-manifests
python -m benchmark_campaign validate
python -m benchmark_campaign freeze
git add artifacts/FREEZE_MANIFEST.json artifacts/HOLDOUT_MANIFEST.json artifacts/PROVENANCE_MANIFEST.json artifacts/DISJOINTNESS_REPORT.json benchmarks sealed-holdout config sources schemas benchmark_campaign requirements.txt
git commit -m "freeze: H3.9.2 qualification set"
python -m benchmark_campaign anchor-freeze --source-commit $(git rev-parse HEAD)\npython -m benchmark_campaign verify-freeze --freeze-anchor-file /secure/off-repo/mubin-h392-freeze-anchor.json
python -m benchmark_campaign export-tuning-pack --freeze-anchor-file /secure/off-repo/mubin-h392-freeze-anchor.json
python -m benchmark_campaign mark-tuning-started --model-ref <ref>
python -m benchmark_campaign lock-model --model-ref <immutable-ref> --system-commit <40-hex-commit> --model-artifact <artifact-file> --model-config <file> --generation-config <file> --freeze-anchor-file /secure/off-repo/mubin-h392-freeze-anchor.json
python -m benchmark_campaign evaluate-holdout \
  --predictions-dir <dir> \
  --holdout-key-file /secure/off-repo/mubin-m392.key \
  --freeze-anchor-file /secure/off-repo/mubin-h392-freeze-anchor.json
python -m benchmark_campaign pre-h4-audit --architecture-audit <architecture-audit.json> --holdout-key-file /secure/off-repo/mubin-m392.key --freeze-anchor-file /secure/off-repo/mubin-h392-freeze-anchor.json
python -m unittest discover -s tests -v
```

The final holdout is one-shot under one freeze. Byte-identical prediction replay is allowed for reproducibility; different predictions after first access require a new benchmark version/freeze.

## Gate semantics

`benchmark_gate_passed` requires all expanded datasets to qualify, campaign/local disjointness to pass, the freeze to verify, the candidate model to be locked, evaluator-produced one-shot holdout evidence to match the same freeze/model/ciphertext/predictions, and every preregistered threshold to pass.

H4 lifecycle state is reported as:

```ini
[pre-h4-audit]
benchmark_gate_passed = true
architecture_gate_passed = true
h4_development_allowed = true
h4_qualification_allowed = true
h4_release_allowed = false
```

with:

```text
h4_qualification_allowed = benchmark_gate_passed AND architecture_gate_passed
```

## Current state

The five canonical benchmark files remain intentionally empty. Population is **0 / 1,280**, so the campaign is correctly red and cannot freeze. Source pins, source partitions, enforced curation quotas, evaluator thresholds/denominator minima, detached-freeze protocol, sealed-holdout protocol, and qualification invariants are fixed; real reviewed cases still have to be curated. No synthetic records are used to make the gate green.
