# Mubin — development-first verified-source admission

**Policy proposal:** 2026-10-22. **Mubin system:** 0.1.0-alpha.
**Scope:** private research, indexing, retrieval and AI algorithm/product R&D.
This document is not legal advice or public text redistribution authorization.

## Decision

An independently byte-pinned source, lawfully published and acquired,
may enter a private, purpose-bounded development vault without a separate
**public redistribution** licence where the applicable legal basis permits
that use. Missing conditions hold **that source only**, never the other
engines or synthetic tests. Neither website availability nor a self-declared
hash establishes legitimate access, authenticated authorship or copyright
status. Do not scrape unlawfully, bypass access controls, or publish source
bytes merely because the internal admission gate passes.

## Applicable Saudi law (official references)

- [Saudi Copyright Law (2026)](https://www.uqn.gov.sa/details?p=28845),
  published 13 February 2026; in force 12 August 2026. Art. 26(4)
  addresses copying an original to develop AI products/algorithms where
  publication/acquisition are lawful and copying is limited to purpose.
  Art. 26(2) separately covers proportionate NONPROFIT research/education
  with attribution. Art. 37 protects normal exploitation and legitimate
  interests; Art. 61 defines commencement 180 days after publication.
- [Implementing Regulations](https://www.uqn.gov.sa/decisions-and-regulations/4001498),
  published 31 July 2026. Art. 29 addresses software/application/database
  licence terms. Art. 30(1–6) limits copying to development need, restricts
  purely commercial uses, requires a retained register of **work type,
  source, purpose and date**, protects legitimate interests and normal
  exploitation, limits publication/unnecessary final-product inclusion,
  and recognizes separately protected elements.

The operator must assess whether these or other rules genuinely apply
to the particular source, activity, contract and jurisdiction. A Boolean
assertion in software does NOT prove lawful use. For ambiguous commercial
use, third-party rights or other jurisdictions, seek appropriate review.

## Independent gates

| Stage | Basis | Effect |
| --- | --- | --- |
| Private development | Verified original-byte pin, independently evaluated lawful acquisition/purpose, restricted vault, use register | Internal research ONLY |
| Scientific verification | Edition, locator, textual variant and qualified claim review | Separate from CI |
| Public text release | Exact edition rights, content fidelity and exposure controls | Separate publication approval |

Never infer public redistribution rights, Hadith-grade qualification,
Quran authenticity, scholarly verification, juristic inference or public
fatwa authorization from an admission result. Existing conservative
corpus.registry.can_publish() and release gates remain unchanged.

## Engineering contract

Module: core/internal_source_use.py
Function: assess_internal_source_use(source, attestation,
independently_pinned_sha256=..., use_record=...)

- Source includes ID/kind/work/edition, SHA-256, declared byte-match
  scope and independent publication-rights status.
- Independent expected SHA must come from a trusted source outside the
  submitted metadata. The function compares declarations; it DOES NOT
  hash a live file or authenticate scholarly source attribution.
- Use record contains work_type, source_reference, purpose_code, use_date.
  The operator must retain real underlying source evidence and this
  register locally; the function does not persist or attest either.
- Operator attestations cover lawful publication/acquisition, bounded
  purpose, private storage, applicable basis, software/database access
  terms, limits on public use and final-product inclusion, rights-holder
  harm, commercial context, separate protected rights and record retention.
- Allowed declared bases: SA_2026_ART26_4_AI_DEVELOPMENT and
  SA_2026_ART26_2_NONPROFIT_RESEARCH. Nonprofit research additionally
  requires genuine nonprofit scope and source/author attribution.
  Unassessed commercial contexts are rejected; limited commercial
  exceptions need specific review by the operator.

Output is a fixed non-disclosing status, at most
INTERNAL_DEVELOPMENT_RESEARCH_ELIGIBLE; it NEVER sets
public_redistribution_authorized, scholarly_verified,
source_authenticity_attested_by_this_gate,
operator_attestations_independently_verified,
automated_hadith_grade_authorized, juristic_inference_allowed or
public_fatwa_authorized to true.

## Engine execution fast lanes

Quran keeps frozen raw witness bytes/riwayah/numbering and never
promotes malformed derived records to scripture. Hadith source-local
experiments keep H3.9.2 Schema-31 benchmarks and its pending human
adjudications frozen. Tafsir indexing of legitimately obtained materials
may proceed privately with correct edition/locator metadata. Usul W1/W2
research files and HMAC keys remain outside GitHub; no automatic semantic
claims. Fiqh remains research-only without normative public judgments.

## Testing and integration limit

Run: python -m unittest discover -s core/tests -p test_internal_source_use.py -v

GitHub CI uses synthetic metadata only. Existing local source adapters
must independently verify source bytes, retain usage logs and call this
admission API before a private intake. The new module is not a downloader
or a universal source-import integration. This policy does not change
system version or authorize public source-text exposure.
