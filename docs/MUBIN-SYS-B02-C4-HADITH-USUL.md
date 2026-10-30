# MUBIN-SYS-B02-C.4 — Hadith → Usul research mediation

**Version:** `mubin-hadith-usul-mediation/1.0`.
**Scientific status:** Never automatically qualified; no system release change.

The B02-C.3 preserved chain identifies Hadith→Usul as
`SEMANTIC_LINK_UNASSESSED_AT_THIS_HOP`. Existing
`mubin-semantic-link-research/1.0` evaluates Quran/Tafsir/Usul,
**not Hadith/Usul**. This new contract makes a bounded *research*
assessment possible without pretending that a Hadith cue is authenticated
narration or a juristic principle.

## Trusted local inputs and behavior

Call `assess_hadith_usul_hop(request, source_pins=..., read_span=...,
read_witness=..., read_assessment=...)`. Source bytes, local paths,
model rationale and H-Search details remain **in the local vault**.

The JSON schema in `schemas/hadith-usul-mediation-v1.schema.json`
accepts a bounded Hadith candidate anchor and a separate Usul rule
anchor, raw byte offsets and SHA256 of both an excerpt and its context.
Both are compared against operator-pinned source SHA registry and
trusted `read_span(source_id,start,end)`, not caller-supplied files.

The local AI must supply a **normalized, immutable H-Search witness
bridge** from the actual previously executed four-source search. Its
contract is `mubin-hsearch-witness-bridge/1.0` with:

```json
{
  "contract": "mubin-hsearch-witness-bridge/1.0",
  "link_id": "hl.example.001",
  "classification": "NARRATION_FRAGMENT_CANDIDATE",
  "witness_source_sha256": "<64-hex>",
  "witness_span_sha256": "<64-hex>",
  "pinned_source_count": 4,
  "source_unavailable": [],
  "candidate_only": true,
  "narration_identity_verified": false,
  "grade_assigned": false
}
```

The complete raw bytes of that private bridge receipt must hash to
`witness.hsearch_receipt_sha256` in the request. **Even that is a
locally submitted statement**, not independently audited H-Search
authenticity or identification of a specific Hadith narrator/isnad.

Similarly, every AI review requires a stored
`mubin-hadith-usul-review/1.0` receipt with the exact submitted
`run_id`, `model_id`, role/verdict, `anchor_roles=["hadith","usul"]`,
`input_sha256` of the canonical frozen request core, and at least 50
characters of recorded rationale. No private text/rationale is returned.

## Outcomes

- `INCOMPLETE_SOURCE_COVERAGE`: fewer than four declared pinned books
  or any reported unavailable source.
- `LEXICAL_CANDIDATE_ONLY`: merely shared text; never semantic support.
- `CONTESTED`: declared unresolved objection, rejection or open
  defeater.
- `UNDETERMINED`: not enough independent-review *run receipts*.
- `MACHINE_RESEARCH_CANDIDATE_ONLY`: at least two different declared
  supporting model IDs and a critic reporting no open defeater, complete
  reported four-book coverage, and two source-anchored contexts.

A research candidate status does **not** prove independent model
families, narration identity or a Hadith grade, a rule sourced to the
narration, correct legal reasoning, or an Islamic legal judgment.
`scientifically_established_hop=false` in all cases. Source text
is not returned.

## Local lead acceptance interface

Run on the privately pinned 6:145 H-Search candidate and two Waraqat
source excerpts, with actual private context windows and recorded
objections. Include the 49:6 and 2:8 adversarial cases and negative
source/receipt mutation checks. Do not change the original
`REJECTED_ALL_CANDIDATES_UNDER_FULL_BAR` selection gate.

**Important:** Do not rewrite the frozen B02-B and B02-C.3 receipts.
Generate new B02-C.4 receipts and label private vs GitHub-safe
outputs separately. Do not update `VERSION.yaml` or H3.9.2 datasets.

```bash
python -m pip install -r core/requirements-test.txt
python -m unittest discover -s evaluation/integration -v
```
