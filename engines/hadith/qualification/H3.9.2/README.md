# Mubin H3.9.2 — Benchmark Expansion Campaign R4

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

## R4 benchmark factory

R4 adds an executable, provider-neutral Benchmark Factory for source-grounded AI curation. It expands the frozen quotas into exactly 1,280 slots, builds tasks from Git-blob-verified source segments, separates Curator AI-A from blind Verifier AI-B, and routes disagreements or risk-tier 3 judgments to adjudication.

The full operational contract is in [FACTORY.md](FACTORY.md). The first live Curator/Verifier execution is documented in [PILOT_RUNBOOK.md](PILOT_RUNBOOK.md). AI agreement is never authority by itself: automatic promotion is limited to source-attributed cases with literal human-authored support and independent evidence verification.

The default acquisition/index/task path is `non_holdout`. Any holdout-bearing operation requires explicit custodian mode and output outside the repository checkout, so H4 development can proceed without consuming the preregistered final-holdout source partition.

## Provenance and holdout integrity

Final-holdout labels are not permitted in public benchmark records. During `build-splits`, holdout gold is encrypted with AES-256-GCM; the 256-bit key remains external. The public holdout retains inputs, provenance, family identity, fingerprints, and `gold_sealed=true`.

A case may depend on more than one source. `source_ids` contains every canonical work used and `source_refs` contains one pinned, verbatim reference per source. Source/family/fingerprint disjointness is enforced per benchmark and campaign-wide.

`source_attributed` AI extraction is valid only when the answer is bound to literal human-authored source support. Composite/judgment-heavy cases retain stronger review/adjudication requirements.

## Source acquisition

The registry pins 18 qualification-eligible OpenITI source versions. The default developer-safe command acquires only the non-holdout partition:

```bash
python -m benchmark_campaign acquire-sources --partition non_holdout --cache-dir source-cache
python -m benchmark_campaign verify-source-cache --partition non_holdout --cache-dir source-cache
```

A benchmark custodian may acquire the holdout partition only to an external path:

```bash
python -m benchmark_campaign acquire-sources --partition holdout --custodian-holdout --cache-dir /custodian/h392/source-cache
```

Downloaded bytes are checked using the Git blob algorithm against pinned blob SHA values. A mismatch is fail-closed.

## Qualification lifecycle

```text
partition-scoped source acquisition
→ Benchmark Factory source index
→ 1,280 frozen quota slots
→ Curator AI-A
→ blind independent Verifier AI-B
→ auto-promotion or adjudication
→ reviewed population complete
→ external holdout key
→ build source/family-disjoint splits + seal holdout gold
→ prepare manifests
→ validate
→ FREEZE
→ commit frozen manifest + protocol to Git
→ detached freeze anchor
→ tuning pack (development + validation only)
→ optional tuning
→ MODEL LOCK
→ one-shot final holdout evaluation
→ pre-h4-audit
```

The freeze hashes the factory implementation, factory policy, Curator/Verifier contracts, response schemas, benchmark records, source registry, validation protocol, and sealed holdout artifacts.

## Gate semantics

`benchmark_gate_passed` remains false until the real 1,280-case population qualifies, the freeze verifies, the locked candidate passes the one-shot final holdout, every preregistered metric threshold passes, and label/safety denominator coverage requirements are met.

```ini
h4_development_allowed = true
h4_qualification_allowed = false
h4_release_allowed = false
```

H4 development may continue in parallel. H4 qualification requires the H3.9.2 benchmark and architecture gates; H4 release requires a later H4-specific release audit.

## Tests

```bash
python -m compileall -q benchmark_campaign tests
python -m unittest discover -s tests -v
```
