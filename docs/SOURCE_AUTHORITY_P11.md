# P1.1 Phase A — Offline Hadith Source Pin Bridge

**Status:** proposed integration component, NOT completed P1.1 source authority.  
**Depends on:** P1.0 PR #49 (offline byte-exact snapshot verification).  
**No change** to frozen H3.9.2 campaign source registry, qualification protocols, 1,280 case quotas, human decisions, holdout, or H4 gates.

## Problem and narrow solution

The Hadith H3.9.2 `sources/source-registry.json` uses version-pinned source descriptors and Git blob SHA-1 digests. P1.0 uses SHA-256 over operator-provided UTF-8 snapshots, 8 MiB per source and 32 MiB per batch. The two representations are not interchangeable.

`core.source_authority` reads the **existing** H3.9.2 registry and independently supplied local source cache. It streams files in 1 MiB chunks, checks Git's blob-encoding SHA-1 (`"blob " + decimal byte length + NUL + exact raw bytes`) against the registry's expected `source_blob_sha`, and calculates a raw-byte SHA-256.

Each result preserves source identity, work ID, version ID, title, provider, repository, pinned commit, source path, format, qualification eligibility and deterministic cache filename. All source material remains on disk; only digests and metadata enter the report.

## Demonstrated assurances

| Output | Precisely what it means | What it **does not** mean |
| --- | --- | --- |
| `status=registry_blob_matched` | Cached bytes match the SHA-1 Git blob pin in the **supplied** registry | GitHub/provider authenticated, edition attribution correct or licensed |
| `local_sha256` | SHA-256 of the exact cached bytes read in this process | Independent truth of the registry or the contents |
| `registry_sha256` | SHA-256 of canonical JSON of the supplied registry | Signed/trusted publisher statement |
| `authority.edition=not_authenticated` | No independently authenticated source edition | An approved scholarly edition |
| `authority.rights=not_reviewed` | No license permission is asserted | Legal permission to read, transform or distribute |
| `authority.entailment=not_checked` | No evidence-to-claim semantics have been evaluated | An authenticated hadith grade or fiqh ruling |

Git SHA-1 is retained **only for comparability with existing frozen registry pins**; SHA-256 is freshly computed and must be the digest used in future independently defined P1.1 provenance contracts. This bridge does not create an authenticated mapping between a provider and its declared SHA-1 pins.

## Usage

```bash
python -m core.source_authority \
  engines/hadith/qualification/H3.9.2/sources/source-registry.json \
  /private/hadith-source-cache \
  --json
```

**Selection of the available source subset is explicit.** The H3.9.2 registry contains a discovery-only entry; the frozen cache acquisition skips ineligible entries by default. Therefore use `--eligible-only` if the local cache contains all 18 qualification-eligible registry sources, or repeat `--source-id` for the exact subset actually present. Verification of all 19 sources is the default. Unknown IDs or selections resolving to zero sources fail closed; the report includes both the complete registry hash and the selected scope.

```bash
# Verify only qualified registry entries (does not imply non-holdout):
python -m core.source_authority \
  engines/hadith/qualification/H3.9.2/sources/source-registry.json \
  /private/hadith-source-cache --eligible-only --json

# Verify one explicitly named source in a separate prepared cache:
python -m core.source_authority \
  engines/hadith/qualification/H3.9.2/sources/source-registry.json \
  /private/hadith-source-cache \
  --source-id openiti:0279Tirmidhi.Sunan --json
```

**Qualification-eligible does not mean non-holdout.** This standalone verifier does not know or authorize H3.9.2 source partitions; operators must preserve the campaign's strict source-cache and final-holdout custodian separation. Never run it against restricted holdout cache material as part of model development or ordinary CI. No actual source files are included in tests.

No network access or source acquisition is attempted. Source paths are looked up using exactly the existing H3.9.2 cache filename convention (`: -> __`). The command never modifies source files, registry files or cache directories.

**Exit status:** 0 iff all files match pins, 1 for unverifiable/missing/mismatched source data, 2 for invalid CLI JSON input or filesystem read failures while loading the registry. Invalid registry metadata is a verification failure (exit 1), not a source authenticity claim.

**Runtime constraints:** 256 registry entries maximum, 5 MiB registry JSON, 512 MiB per source and 2 GiB per invocation by default, streamed in 1 MiB chunks. Cache path must be a non-symlink directory and opened cache files must be regular. On POSIX, file opens use `O_NOFOLLOW` and descriptor-level metadata checks against concurrent size/timestamp modification.

## Next required work — not implemented by this phase

1. Authenticated source-authority records: publisher/release identity, signed commits or independent content attestation, edition provenance and evidence-backed licensing rights.
2. Independent concordance from pinned source bytes to **UTF-8 byte spans** and H3.9.2 `gitblob:<sha>#char=start:end` locators; handle character vs byte offsets explicitly.
3. Integration with P1.0’s manifest/receipts on bounded source windows or chunks, not entire >8 MiB documents. Reject changed normalization, encoding or edition aliases.
4. Concurrency-safe immutable snapshot custody, auditable acquisition attestations and reproducible external corpus evaluation.
5. Qualified scholarly assurance for source attribution, hadith analysis and usul reasoning, never inferred from hash matching.

System stays `0.1.0-alpha`; this PR must not be described as a new working Hadith/Usul/Fiqh engine.
