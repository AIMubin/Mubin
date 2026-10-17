# U0.2 source-anchored Usul docket — primary maintainer audit

**Date:** 2026-10-17. **Reviewer:** primary maintainer code review (not independent scholarly adjudication). **Base:** unmerged U0.1 PR #66 at `8f961ac47e6b758b51cd88fad3c5a0ff3353581c`. **Implementation HEAD before this audit:** `b75a1a56ef93e6f9ad6819ce83fffca4552ff9ba`.

## Verified diff and dependency

Exactly seven changed files before this audit: `core/usul/docket.py`, `core/usul/docket_cli.py`, `core/tests/test_usul_u02.py`, `schemas/usul-u02-source-docket.schema.json`, `research/usul/u02-risala-source-candidates.json`, `docs/research/USUL-U02-SOURCE-ANCHORED-CANDIDATES.md` and `.github/workflows/mubin-usul-synthetic.yml`. This is **stacked** on PR #66. Do **not** merge U0.2 directly into `main` before its dependency is approved and merged; update target after any rebase and re-audit.

The source snapshot uses Shamela book 8180 only. Its four recorded web route IDs are `146`, `149`, `157`, `556`; associated site-reported print page values are 53, 56, 64, 471. The latter numbers are **not independently authenticated printed-edition page evidence**. Original-book text, publisher DB, source bytes, rights and independent authenticity are not part of this PR.

## Contract invariants personally inspected

- No text fetching, database import, training or external HTTP call. CLI reads an offline bounded local file through the existing U0.1 `_read` safe JSON loader, which rejects ambiguous duplicate members, NaN/Infinity, special files, symlinks and excessive input.
- JSON schema 2020-12 is a fixed four-slot pilot. An exact `source_id`, `book_id` and canonical provider book URL are required. Each `candidate_id` is bound to the fixed **topic_id and route_id** and cannot be swapped or silently removed. The URL must exactly match the identified book/route; duplicate candidate IDs and route IDs fail.
- Unknown nested fields are rejected before schema traversal. An iterative bounded exact-type JSON tree check rejects hostile dict/list/scalar subclasses and cycles before schema, then U0.1 bounded canonical preflight prevents large diagnostics and malformed UTF-8 output.
- `heading_authorship=not_verified_authorial` on all records; the ijma entry notes the editor-added chapter title. No editorial heading or question is promoted into the attributed doctrine of al-Shafi'i.
- Hardcoded `automatic_promotion=false`, `review_status=unreviewed`, `rule_status=not_formalized`, `source_bytes_status=not_acquired`, `text_rights_status=not_assessed_for_use`. The returned report always has `verified_rule_count=0`, `eligible_for_engine=false`, `rights_verified=false`, `edition_authenticated=false`, `source_bytes_available=false`, `scholarly_authority_verified=false`, even when syntactically valid.
- `docket_sha256` is a canonical fingerprint of our **metadata record**, not an edition/source text hash or authority signature. `research/usul/**`, new schema/test/doc paths and the CLI smoke command appear in both PR and push CI path filters.
- No H3.9.2 disjointness manifests, holdout texts or source registry altered. Frozen U0.1 truth table and SHA-256 fixture constants stay unchanged.

## Test-first adversarial evidence

1. **Missing implementation:** PR #67 began with test-only commit `1119c3a7773354b90f90ca77244e4f3a5666dce8`. The new module was intentionally absent at first CI (red-first), then schema, four-site metadata records, validator and CLI were implemented. Main workflow and scoped synthetic workflow ran green **88 tests** on `e6bb016d166794dff9fa54d2ab4ced44ae93675f`: [39064453280](https://github.com/AIMubin/Mubin/actions/runs/39064453280) and [39064453270](https://github.com/AIMubin/Mubin/actions/runs/39064453270).
2. **Identity laundering found during primary review:** the original docket allowed exchanging two candidate IDs, duplicate topic assignments, or dropping one chapter while still returning valid metadata. Red-first test commit `65632a7b8fe3c5de6eeb98877ac0b9b461b3f418` reproduced two failing test methods across [39064553858](https://github.com/AIMubin/Mubin/actions/runs/39064553858) and [39064553836](https://github.com/AIMubin/Mubin/actions/runs/39064553836), **90 tests / 2 failures**. Strict four-slot schema and ID→topic→route binding repairs followed in `2c5a502af93ea9b5103056891d9b2520edc8cf17` and `a805c9581bc643837002652d97972f7bd358118d`.
3. **Result after repairs/doc:** both exact implementation HEAD `b75a1a56ef93e6f9ad6819ce83fffca4552ff9ba` CI [39064676990](https://github.com/AIMubin/Mubin/actions/runs/39064676990) (P0) and [39064676946](https://github.com/AIMubin/Mubin/actions/runs/39064676946) (U0.2) passed **90/90**. A future audit-document commit is another HEAD and must have its own verified green CI.

## Additional latest-HEAD primary finding: editorial warning laundering (2026-10-17)

**Observed flaw on HEAD `c53f57328c5984d8d6a589a84abaeafeb5120031`:**
`validate_docket` pinned candidate ID, topic and route but only *enumerated*
`heading_provenance` and permitted unconstrained replacement of
`editorial_warning`. A caller could relabel the recorded editor-added
`u02_c004` Ijma heading as a printed variant and replace its caution with
a denial, while `valid_metadata=true`. This is metadata integrity
laundering, not evidence of real source falsity.

- RED test-first commit `05d96e38e1ddda740d5001bbcb24c2491603d64e`:
  new `test_source_editorial_interventions_cannot_be_reclassified` exercises
  the four changed classifications and a replaced Ijma caveat.
- RED CI: [P0 #39065501920](https://github.com/AIMubin/Mubin/actions/runs/39065501920)
  and [U0.2 #39065501922](https://github.com/AIMubin/Mubin/actions/runs/39065501922)
  both failed as expected; U0.2 job recorded **91 tests, 5 failed subcases**,
  while all previously covered tests passed.
- Repair commit `b26bbcc99d983b7d30821913be9b2f7f99746715` pins each
  candidate ID to its topic, route and exact declared `heading_provenance`,
  and binds the critical Ijma editorial caveat to the four-slot v1 contract.
  Other unrestricted research descriptions are still **site metadata only**.
- After this documentation commit, verify **the final HEAD's** syntax, unit
  tests, both CI workflows and offline CLI before requesting Codex. Do not
  treat historic green runs as proof for the updated HEAD.

## Remaining boundaries and review decision

- The website route may change. The site description could be wrong; no independent editor/printed-edition collation, content rights or publisher authentication occurred. All statements in the docket are site-observation **claims**, not scholarly gold.
- No human reviewer approved any usul rule. U0.2's fixed al-Risala docket is intentionally a pilot, **not** a general Quran/Hadith/Fiqh or multi-book source ingestion engine.
- CI asserts formal invariants, not philological truth, legal permissions, or sound deduction. The project-wide release stays `0.1.0-alpha`.
- Codex second pass may begin **only after** this primary audit and latest-HEAD CI are green, with full dispositions to actionable comments. If review quota is unavailable, report maintainer-only fallback, never second-party approval.
- **Merge hold:** U0.2 remains unmerged and dependent on PR #66; no release or main-branch mutation authorized by tests.
