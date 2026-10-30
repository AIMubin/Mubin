# MUBIN-SYS-B02-C.6 — Hadith Witness Identity Qualification (Research Contract)

**Engineering contract:** `mubin-hadith-witness-identity/1.0`  
**System:** Mubin `0.1.0-alpha` (unchanged)  
**Frozen benchmarks:** H3.9.2 is **not** modified, sampled, imported or evaluated.

## Reason for this increment

The preserved 6:145 B02-C.3 chain contains one `LEXICAL_WITNESS_CANDIDATE`,
not an identified or graded Hadith. B02-C.4 assesses a proposed Hadith→Usul
semantic relation but explicitly cannot prove narration identity. B02-C.5
establishes declared execution-plan/result consistency, not source truth.

This increment assesses **source-bound textual witness hypotheses**, not
narration authentication or opinion attribution. The local assistant collects
actual source anchors and variants; the architecture implements the conservative
verification gate in `core/orchestration/hadith_witness_identity.py`.

## Private input interface

`assess_hadith_witness_identity(request, *, source_registry, read_span,
read_bridge)` requires:

- `source_registry[source_id]`: exact operator-pinned
  `{source_sha256, work_id, version_ref, access_scope: "non_holdout"}`.
  Source pins are trusted operator input; the full file is **not rehashed**
  by this adapter.
- `read_span(source_id, start_byte, end_byte)`: local, independent,
  source-pinned UTF-8 **raw-byte** reader; the caller must not allow
  model-proposed file paths, symlinks, URLs, or arbitrary sources.
- `read_bridge(link_id)`: returns original raw bytes of a frozen, local
  normalized `mubin-hsearch-witness-bridge/1.0` receipt, matching the
  H-Search candidate's link/source/fragment SHA, with
  `narration_identity_verified=false` and `grade_assigned=false`.
  A bridge's internal coverage declaration is not independent proof that
  the full four-book H-Search ran.
- A JSON request (schema
  `schemas/hadith-witness-identity-v1.schema.json`) with exactly one
  `role=candidate`, up to five `role=comparison` records, one
  `candidate_fragment`, reported `segment_type`, independently
  pinned `segment`, `context`, optional `isnad`, and all
  `open_objection_ids`.

Each `span` is `{start_byte, end_byte, sha256}`, with `[start,end)`
and a SHA256 of the **exact bytes**. The context is limited to 8192
bytes and must include at least 16 additional bytes outside the cited
segment. The isnad and matn-candidate span must not overlap. A whole
source file's Git blob SHA or UTF-8 text hash is **not** interchangeable
with the SHA of its slice.

**Critical source-offset boundary:** H-Search `raw_source_span` uses
Unicode **codepoint indices** in parsed text. B02-C.4 and B02-C.6 use
UTF-8 **byte offsets**. The local assistant must independently derive
the byte offsets from the unchanged source bytes, check boundaries
against the original source encoding, and never directly copy codepoint
indices into `start_byte`.

## Result semantics

| Outcome | Exact meaning |
| --- | --- |
| `EXACT_MATN_CROSS_SOURCE_RESEARCH_ONLY` | The reported matn bytes match exactly across two separately pinned source IDs and distinct declared work IDs, and local constraints are satisfied. Textual co-occurrence only. |
| `UNDETERMINED` | No exact cross-work match or segment is unclassified; variants may exist and require investigation. |
| `REPORTED_NON_NARRATION_SEGMENT` | Operator-supplied segmentation labels the candidate Quran quote/commentary; the contract does not itself authenticate the label. |
| `CONTESTED` | An open objection vetoes positive textual research status. |
| `INCOMPLETE_HSEARCH_COVERAGE` | The normalized H-Search bridge declares fewer than four pinned sources or unavailable sources. |

Even the first outcome does **not** establish independent source
families, narration identity, isnad continuity, Hadith grade,
scholarly source edition or correct legal usage. The published outcome
always has `narration_identity_verified=false`,
`source_authenticity_verified=false`,
`scholarly_verified=false`,
`scientific_chain_established=false`,
`juristic_inference_allowed=false` and `text_included=false`.

Work IDs, book labels and segment classifications originate in a
trusted *operator registry* or submitted claims: the code checks their
consistency but does not certify scholarly independence or correct
exegesis. No private source excerpts or filesystem paths are returned.

## Local handoff and scientific gate

1. Collect private candidate matn/isnad/context for 6:145, and its
   cross-source comparisons. Explicitly classify Quran quotation and
   commentary alternatives. Preserve raw source hashes and source spans.
2. Supply the frozen H-Search candidate bridge and registered source
   read callbacks. Record variants and objections; include at least one
   known false-positive control.
3. Run bounded research assessment, archive full private receipts
   append-only, and publish **metadata-only** redacted summaries if
   checked for identifiers/paths.
4. Request a **separate qualified scholarly assessment** of narration
   identity and of any claimed criticism/grade; no AI vote is an
   independent scholarly certification.
5. Only after these scientific gates may an independent Usul attribution
   and rule-application study begin. Never modify strict-case selection
   or the H3.9.2 frozen evaluation for this diagnostic.

```bash
python -m unittest evaluation.integration.test_hadith_witness_identity_v1 -v
python -m unittest discover -s evaluation/integration -v
```

**Explicitly excluded:** private-vault source downloads, network fetching,
Hadith grade inference, semantic-link promotion, fatwa or product release.
