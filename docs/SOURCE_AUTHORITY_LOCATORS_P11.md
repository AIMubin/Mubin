# P1.1 Phase B — H3.9.2 character locator to UTF-8 byte-span bridge

**Status:** bounded proof-of-concept, not full provenance P1.1 qualification, not P1.0 receipt integration.  
**Parent:** PR #53 (Hadith registry pin bridge), itself stacked on P1.0 PR #49.  
**Frozen material:** No H3.9.2 source registry, Factory implementation, benchmark quotas, adjudication, holdout or H4 gate may be changed to make this work.

## Exact Factory semantics

The H3.9.2 Factory \`benchmark_campaign/factory.py\` uses \`Path.read_text(encoding="utf-8", errors="strict")\` in \`build_source_index\` (line ~224) and then \`text[start:end]\`, with locator \`gitblob:<40-hex>#char=start:end\`. These are **Python Unicode codepoint** indices, not UTF-8 byte positions, grapheme indices or tokenizer indices.

Python text-mode reads use universal-newline handling; an input containing CRLF or CR is normalized to LF. Thus \`text[start:end]\` **does not always identify the same raw byte interval**. A naive \`len(text[:start].encode("utf-8"))\` mapping is unsound for raw CRLF/CR sources. The Phase-B bridge rejects **any CR byte/codepoint anywhere in the cached source**, even before the requested span. LF-only UTF-8 sources can be mapped without rewriting bytes.

## API

\`\`\`python
from core.source_authority import verify_hadith_locator

result = verify_hadith_locator(
    registry,                 # frozen declared registry JSON (schema 2)
    source_cache_directory,   # offline cache in the correct access partition
    "openiti:0279Tirmidhi.Sunan",
    "gitblob:<pinned-blob-sha>#char=<start>:<end>",
    exact_excerpt,            # supplied excerpt, never returned
)
\`\`\`

The complete source is SHA-1 Git-blob verified (including exact "blob <size>\\0" header) against the **untrusted registry declaration** and hashed with raw SHA-256. A strict streaming UTF-8 incremental decoder scans the same opened file descriptor in 1 MiB chunks and derives raw byte offsets at the two Unicode-codepoint boundaries. The exact raw byte slice is read back and compared with the provided excerpt encoded in strict UTF-8; no normalization, transliteration or whitespace repair is applied.

This is a **bounded metadata-only locator receipt**; its fields include \`start_char\`, \`end_char\`, \`start_byte\`, \`end_byte\`, \`source_git_blob_sha1\`, \`source_sha256\`, \`excerpt_sha256\`, the pinned source version/path/commit, and \`verification_kind=registry_pinned_bytes_and_exact_quote\`. The actual text and excerpt are never included in the result.

## Assurance boundaries

| Result element | Demonstrates | Does NOT demonstrate |
| --- | --- | --- |
| \`scope=pinned_bytes_and_exact_excerpt_only\` | Local exact match to a declared registry-pinned raw file | Source origin or signed edition |
| \`start_byte:end_byte\` | Conversion from original Python-codepoint range on an LF-only UTF-8 file | Validity on CRLF/CR sources, or corrected text |
| \`excerpt_sha256\` | Digest of the exact excerpt verified against the raw byte slice | Entailment of a proposition |
| \`source_sha256\` | Digest of cached file bytes read in this invocation | Independently authenticated publisher |
| \`authority.edition=not_authenticated\` | No independent edition attestation | Validated scholarly source |
| \`authority.rights=not_reviewed\` | No legal rights attestation | License clearance |
| \`authority.entailment=not_checked\` | No semantic inference check | Hadith grade, usul validity, fiqh verdict |

**No P1.0 receipt equivalence:** P1.0's \`core.provenance.verify_bundle\` verifies entire operator-supplied UTF-8 snapshots against independent P0+manifest SHA-256 and byte ranges, with a maximum 8 MiB per snapshot. This Phase-B result independently creates a byte-span mapping and a pin-bound hash; it does not bypass P1.0 validation, certify source rights, manufacture a P0 inference graph, or assert a P1 \`local_byte_exact_match\` receipt.

## Trust, resource and custody constraints

- The registry must pass Phase-A metadata validation; the source must be a regular cached file, without a direct symlink, opened by descriptor and with \`O_NOFOLLOW\` where supported.
- Only positive integer byte budgets are accepted; defaults are 512 MiB per source and 1 MiB per excerpt. Source bytes are scanned incrementally, not loaded in full into memory.
- Locators use canonical, bounded decimal offsets without leading zeros and exactly the registry's 40-character lowercase Git blob SHA-1 pin. Unknown sources or inconsistent references fail closed.
- A whole-file registry Git SHA-1 pin is compared, and an independent raw SHA-256 is calculated. A same-descriptor stat check detects common concurrent mutation. This is **not** a proof that the operator-supplied registry or host filesystem is trustworthy.
- The Phase-B code has **no access-partition authorization**: \`qualification_eligible\` does not mean non-holdout. Do not use this mapper on hidden/held-out final qualification data in normal research or CI; the Hadith custodian must enforce partition isolation independently.
- It returns only structured metadata, never the quote text, but callers are responsible for securely handling the \`exact_excerpt\` argument before invocation.

## Future integration test (NOT implemented in Phase B)

Given an independently authorized source snapshot or an immutable quote window, construct a versioned P1.0-compatible P0 evidence bundle and P1 manifest; validate via \`core.provenance.verify_bundle\` against actual bytes. For larger sources, specify a new contract for parent-source SHA-256 + window SHA-256 + unambiguous absolute offset, and retain the full pinned parent hash. Do not pretend an extracted window is identical to the entire pinned book.

Successful tests on synthetic LF-only Arabic/emoji, BOM, UTF-8 chunk boundaries, exact same-length quote substitutions, invalid UTF-8, tampering, huge locators and newline mismatches are necessary but do not demonstrate correctness on the real corpus. No version bump is authorized by this phase.
