# Mubin source use and attribution — implementation policy

Effective 2026-10-20. Applies to Quran, Hadith, Tafsir, Usul and future Fiqh workstreams.

## Decision

**Use identified sources to develop, search, cite, test and reason. Do not require a blanket human-reviewed corpus before building an engine.** Every source-grounded result must identify the underlying source, not merely claim that it has sources. Preserve the exact provenance and differentiate a cited historical opinion from Mubin's own inference.

**Attribution is not a copyright licence, a source authentication protocol or scientific endorsement.** A text may be usable for internal testing or remote citation while still being ineligible for public bulk redistribution. Historical authorship/public-domain status of the underlying work must not be conflated with modern publishers' editorial text, translations, annotations, or scanned page images. Applicable law and source terms still control each use.

## Required trace metadata

For each evidence item that contributes to a result, retain:

- Stable `source_id` and `evidence_id`.
- `work_title` and `edition` (record "unknown" explicitly when missing; do not invent it).
- Precise source locator, plus excerpt-specific locator (volume/page, chapter/section, hadith ID, sura:ayah, or other source-appropriate unit).
- Source file/content SHA-256 and excerpt SHA-256 *as declarations to check*, not guarantees of scholarly accuracy.
- Verification status, method and the **scope of that verification** (P0 metadata, independently matched source bytes, or qualified scholarly review).
- Whether the output is direct `SOURCE_ATTRIBUTED`, mechanically transformed `FORMAL_EXECUTION`, or `AI_INFERENCE_UNVERIFIED`.
- Rights state for any planned text publication, separate from permission to include a bibliographic citation.

A missing work/edition/locator or unresolvable evidence reference must not be silently replaced by a fabricated reference. A rule without explicit cited provenance remains research-only and should not become an authoritative jurisprudential output.

## Source-first implementation workflow

1. Prefer already available, edition-identified reference corpora and official primary sources. Where the work's text is in the public domain, still check the specific edition's terms; avoid re-digitizing existing materials needlessly.
2. Pin the original bytes and keep indexes, normalization and model-ready representations as **separate derived artifacts**, with a trace back to exact source positions.
3. Allow internal/test-time source use and bibliography metadata without a human signoff for every item, subject to access restrictions and applicable terms.
4. Present a citation trail with every sourced/derived answer. Use the shortest clear locator and explicitly distinguish conflicting sources and uncertain passage boundaries.
5. Publish source text or a modern editorial reconstruction only after its *specific* applicable permission and integrity checks; public metadata-only provenance may remain usable even when text redistribution is restricted.
6. Any independent scholarly attestation is an action-specific gate for authoritative claims, not a general condition on software development. Historical H3.9.2 protocol remains unchanged.

## U0.1 bridge, current executable scope

The [P0 semantic binding implementation](../engines/usul/semantic_binding.py) adds a versioned binding for each of a P0 Rule's labels, cited source-anchored premise claims, exception evidence and inferred conclusion claim. The binding is pinned to the exact complete P0 rule with SHA-256. The [bridge](../engines/usul/p0_bridge.py) emits `source_citations` containing work, edition, source and evidence locator, and both digests **without copying source excerpts**.

A binding result of `STRUCTURALLY_BOUND` certifies only one-to-one record mapping and a digest match. It **does not** establish that the machine predicate means the same thing as the source passage or that the passage appears in a real printed edition. Legacy rules without a binding continue to run only as explicitly labelled `LEGACY_UNBOUND` experimental examples. Invalid supplied bindings are rejected rather than silently downgraded.

Only `deduction` + `machine_checkable` + bounded explicit logical specs can execute in U0.1. `qiyas` and `tarjih` are still refused. `scholarly_verified`, `valid_juristic_ruling`, `public_fatwa_authorized`, and `semantic_equivalence_verified` remain false for this prototype.

## Gate distinction

- **Internal cited reference or controlled technical experiment:** source metadata/provenance + appropriate access and use terms; no blanket human approval.
- **Metadata-only source citation in public-facing research:** evidence-specific bibliographic trace with scope/uncertainty; no automatic permission to include long protected excerpts.
- **Public verbatim corpus publication:** provenance, verified text integrity, and sufficient redistribution rights for the actual edition.
- **Authoritative new fiqh ruling:** source trace, methodology, examination of objections and qualified decision process; mere citation does not make it authoritative.
- **Quran canonical display:** independently verified, pinned exact witness/riwayah and numbering plus appropriate redistribution conditions; no use of malformed derived verse reconstruction.

Use [risk-proportionate review](RISK_BASED_ASSURANCE.md) for each action, not a globally blocking review committee.

## Development-first source admission (2026-10-22)

A source with independently pinned original bytes and lawfully obtained
access may enter a controlled, purpose-limited private AI development
vault **without waiting for public redistribution clearance** where a
genuinely applicable legal basis permits this use. This is a **source-level
development decision**, not a general licence to obtain any digital copy
or publish its contents. Check acquisition and access/database terms;
record work type, source, purpose and use date as required by the Saudi
2026 Implementing Regulations Article 30.

See [internal source development policy](INTERNAL_SOURCE_DEVELOPMENT_POLICY.md)
for the Art. 26(2)/(4), Art. 37 and regulation Art. 29–30 distinctions, and
the fail-closed engineering-only operator declaration contract.
**Public publishing** of any edition/annotations/text still requires
specific rights and fidelity gates. Valid metadata and copied-text
hashes do not authenticate scholarly attribution or content correctness.
