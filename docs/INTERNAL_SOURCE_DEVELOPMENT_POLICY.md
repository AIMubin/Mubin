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

## Local importer bridge, integrity limitations, and release isolation

The local operator added the research-only wrapper at
`corpus/internal_research_ingest.py`; it records one metadata-only
admission manifest and a private usage-register entry. A manifest
marked `internal_only` is **not** an export entitlement.

The follow-up hardening enforces fail-closed **usage-chain verification
before append and again before admission**, validates sequence and digest
fields, checks the content-addressed object still matches the pinned
digest, and rejects both the corpus vault and the register file when
placed under the Git working tree. Use records stay outside Git.

**Scope limitation:** This is a SHA-256 linked register, **not** a
tamper-proof audit log against an adversary able to edit and recompute
all earlier entries. Preserve its final head hash independently in a
trusted, restricted ledger, or add an authenticated signature/append-only
storage backend before making adversarial non-repudiation claims.

A local pilot W1/W2 admission receipt is evidence of two local source
files meeting this *operator-declared* ingestion contract, not proof
of edition authenticity, scholarly equivalence, sublicensing rights,
or public distribution entitlement. The unresolved W2
`EVIDENCE_RECONCILIATION_FAILED` erratum is a separate historical
integrity matter: **do not rewrite frozen evidence or silently replace
the legacy field** based solely on a reported byte count.

**Concurrency limit:** The initial register uses a read-and-atomic-
replace pattern intended for one trusted operator at a time. Concurrent
writers require an explicit inter-process lock and integrity review.
No version of this private importer is an authorization to run
unreviewed automatic training or public text exposure.

## Transactional private intake hardening (PR #83)

The private bridge now performs **resolved-path and ancestor symlink checks**
for the original source, content-addressed object, manifest and usage-register
before the legacy importer is invoked. It rejects destinations inside any
Git working tree, including a linked objects/manifest subdirectory.

The legacy importer runs inside a **private temporary staging root**.
New final manifests are made visible only after source-byte digest and
object checks; they are not **admitted** until a corresponding valid
usage-register entry exists. An uncommitted new manifest is removed on a
failed register append. An unadmitted content-addressed object may remain
after failure; garbage-collect only if no other record references it.

For repeat imports with the same source ID and bytes, the bridge reuses the
already-admitted manifest **byte-for-byte** and appends a new usage event
without rewriting the manifest. If append fails, previous admission survives.
Existing unadmitted manifests are rejected for operator investigation.

Filesystem and legacy-importer exceptions at the public bridge boundary map
to a stable non-disclosing refusal; raw exception messages may include private
paths and must not reach callers or logs.

**Limit:** pre-write path checks alone do not prevent another process from
replacing directory entries concurrently (TOCTOU). One trusted writer and a
restricted vault are required; platform-specific no-follow handle-relative
writes and exclusive locking are a separate gate before untrusted concurrent
writers. SHA-linked journal chains also need an independent head anchor for
tamper evidence against an attacker who can rewrite historical entries.

The private W1/W2 pilot is operator-reported and separate from the historical
W2 EVIDENCE_RECONCILIATION_FAILED receipt. No source authenticity, rights,
scholarly or religious-use authority is granted.

