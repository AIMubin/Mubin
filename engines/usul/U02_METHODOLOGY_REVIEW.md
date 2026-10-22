# U0.2 pilot 02 — versioned methodology candidates and unresolved alternatives

This is an **extension** of the U0.2.0 candidate catalog, not a new
jurisprudential executor. The internal overlay contract is `u0.2.1`;
the Mubin system version remains `0.1.0-alpha`.

## What is now represented

| Record | Mandatory contract | Status |
| --- | --- | --- |
| Methodology proposal | unique `id`, semantic `version`, bounded `research_pointer_ids` | `UNASSESSED` |
| Rule–methodology binding | one profile and exact version for every rule candidate; its Stage08 research pointer must belong to that profile | `UNASSESSED` |
| Ambiguity record | concept or rule candidate + an actually associated research pointer + explicit uncertainty kind | `UNRESOLVED` |
| Alternative/disagreement *candidate* | two distinct catalog candidates; distinct profiles or structurally different candidate clauses | `UNASSESSED` |

Available ambiguity kinds: `LEXICAL_SCOPE_UNRESOLVED`,
`EXCEPTION_SCOPE_UNRESOLVED`, `CONDITION_SCOPE_UNRESOLVED`,
`FORMALIZATION_UNRESOLVED`.

Available alternative kinds: `PROFILE_DIVERGENCE` and
`STRUCTURAL_ALTERNATIVE`. These labels mean proposed *comparison tasks*,
not evidence that a disagreement actually exists among scholars.

The input overlay is bound to a full `catalog_sha256`, and the catalog
is **recomputed**, not trusted as a free-standing supplied blob. Recomputing
also checks Stage08's independently pinned graph hash, research navigation
and source-section identifiers. Scope switching, reused rule bindings,
ambiguous reference IDs, stale versions, duplicate reversals and illicit
`VERIFIED`/`RESOLVED` labels are rejected.

No source text, prose formalization, semantic equivalence or jurisprudential
obligation is ever synthesized by this interface. A profile version is only
a version of a *research proposal*: it does not constitute a source-backed
methodology verified by qualified scholars. A candidate alternative does not
constitute a classical school disagreement. No P0 rule is created or run.

## API

```python
from engines.usul.concept_rule_catalog import build_catalog
from engines.usul.candidate_methodology_review import build_methodology_review

catalog = build_catalog(trusted_stage08_graph, independently_frozen_graph_sha,
                        candidate_manifest)
# The overlay's catalog_sha256 must equal catalog["catalog_sha256"]
report = build_methodology_review(trusted_stage08_graph,
                                  independently_frozen_graph_sha,
                                  candidate_manifest, methodology_overlay)
```

Operator CLI:

```bash
python -m engines.usul.candidate_methodology_review \
  --stage08-graph /private/attested/stage08.json \
  --trusted-stage08-sha256 YOUR_EXTERNALLY_FROZEN_64_HEX_SHA \
  --catalog-manifest /private/research/u02-catalog.json \
  --methodology-manifest /private/research/u02-methodology.json \
  --out /private/research/u02-methodology-review.json
```

Generate/freeze the full candidate catalog SHA before preparing the
methodology overlay; do **not** copy a digest from a mutable or unreviewed
input as a trusted source. Output contains only IDs, provenance hashes,
proposal labels and explicit negative authorization flags.

## Assurance and next steps

- Synthetic tests build a **real** Stage07→Stage08→U0.2.0→U0.2.1 chain,
  exercise profile version mismatches, pointer scope, forged source graph,
  stale catalog, false scholarly assertions, unresolved ambiguities and
  candidate disagreement duplicates.
- Validation results do **not** assert source authentication, semantic
  appropriateness of formalizations, presence of real scholarly controversy,
  approval of a school or valid usul/fiqh deduction.
- Before expanding to actual scholars or source-grounded definitions, document
  independent source edition/locator, licensed quotation policies, explicit
  scholarly attribution and methodology-version evidence. Maintain a
  separate adjudication track for the 16 W1/W2 text-difference chapters.
- U0.1 executor/P0 bridge and Quran/Hadith remain unchanged; no fatwa,
  `qiyas`, `tarjih` or normative inference is enabled.
