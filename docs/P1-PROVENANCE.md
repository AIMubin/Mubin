# P1 — Offline Evidence & Provenance Verification

**Status:** first working P1 slice; *not* a Quran/Hadith corpus, a live web fetcher, an authenticated textual edition, or a fiqh proof engine.

P0's `verification_status: verified` can be self-asserted. P1 introduces an **independent byte comparison** against an explicitly selected, immutable local UTF-8 source snapshot. P1 never changes P0 data or raises H3.9.2 human-gold statuses.

## Contracts

- `schemas/source-snapshot-manifest.schema.json`: versioned offline manifest. Every entry pins a P0 `Source` by ID, exact work/edition/scope locator, full-file SHA-256 and relative POSIX path under the explicitly supplied corpus root.
- Each `span` declares the exact **half-open UTF-8 byte range** `[start_byte,end_byte)` corresponding to a unique P0 `Evidence.locator`. An excerpt must match **all bytes in the span**, not a substring elsewhere in the document. No Unicode normalization, OCR, approximate matching, global text search, or silent locator repair is performed.
- Each source requires `rights.status`, `rights.basis`, and `rights.reference`. Only `operator_cleared` permits ingestion. This is an **operator assertion**; software does *not* legally validate the license, distribution entitlement or rights holder. `restricted`/`unknown` fail closed.
- `core.provenance.verify_bundle`: runs the existing P0 schema/graph validator first; validates the new manifest, checks paths, rejects symlinked source paths, checks snapshot bytes against SHA-256, checks all source/edition/locator metadata and all evidence matches, and emits **receipts only if all checks succeed**.
- Receipts prove **local byte correspondence to the supplied snapshot only** and are not a signature, external origin certificate, human scholarly review, evidence semantic entailment or accepted fatwa. A maliciously authored snapshot+manifest may be internally consistent: independent corpus curation and trusted edition pinning remain out of scope.
- Default caps: 5 MiB per JSON input, 8 MiB per UTF-8 snapshot file, 5,000 total P0 entities. Large-corpus ingestion requires a new audited streaming design.

## Usage

```bash
python -m pip install -r core/requirements-test.txt
python -m core.provenance --help
python -m core.provenance bundle.json source-manifest.json /path/to/corpus --json
python -m unittest discover -s core/tests -v
```

CLI prints JSON receipts **to stdout**, and never writes or modifies source files. Exit codes: `0` = locally matched and structurally valid; `1` = contract/path/digest/locator/rights/evidence inconsistency; `2` = file missing, malformed, unreadable or oversized input. Never interpret `0` as source authenticity or Islamic scholarly endorsement.

## Next boundaries

- **P1.1:** source connector registry, immutable external corpus identifier and trust anchor (signed manifest/digest provenance), citation edition verification, source licensing audit, and acquisition/legal process.
- **P2:** Quran canonical-text import separately from tafsir.
- **P3:** Hadith chain and matn evidence with distinct editions and source families.
- **P4/P5:** execution of Usul rules and historical scholar-evidence inference. Prior `H3.9.2` benchmark gates remain unchanged.
