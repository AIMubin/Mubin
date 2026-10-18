# U0.3 research question cards — primary maintainer and quota-fallback audit

**Date:** 2026-10-18. **Base dependency:** unmerged U0.2 PR #67,
`69f4fd95e9880de7de953b1768f558642eaa23e7`.
**Implementation HEAD before adding this audit document:**
`db7d6fe6c36030c987add901f7aeb7c7de6c2b13`.
U0.3 PR #68 is a draft stacked on PR #67, which is stacked on U0.1 PR #66.

## Provenance of implementation — no false byte-for-byte claim

The prior local U0.3 research documentation and primary-audit description were
read from the Mubin Library. The historical U0.3 ZIP exists in that Library,
but its original ZIP bytes could not be exported into this session (materialization
reported no authorized raw-byte path). The U0.3 files submitted here were
**reimplemented against the recorded research contract**, not copied or asserted
byte-identical to the earlier ZIP. Their quality is established only by the
review and GitHub HEAD CI described below. The unmodified U0.2 parent data
reports metadata fingerprint:
`bf298ea01dc0f121c279b090acecbf229234d22387b0f82f7b13afb1112514f8`.

## Exact PR scope and preserved boundaries

Seven changed paths before this document:
`.github/workflows/mubin-usul-synthetic.yml`,
`core/tests/test_usul_u03.py`,
`core/usul/claims.py`,
`core/usul/claims_cli.py`,
`docs/research/USUL-U03-RESEARCH-QUESTION-CARDS.md`,
`research/usul/u03-risala-hypothesis-cards.json`,
`schemas/usul-u03-research-cards.schema.json`.

All U0.1 rulebook and 40-case test bytes, U0.2 original docket and validator,
H3.9.2 corpus/heldouts, governance or publisher-rights records, and the global
`0.1.0-alpha` version remain untouched.

## Primary engineering inspection on HEAD

1. **State model:** four cards are researcher-origin questions, not quotations,
   authenticated descriptions of al-Shafi'i's doctrine, fiqh rulings, qiyas
   AST rules or certification. No function calls the U0.1 executor or accesses
   Quran/Hadith corpus. The CLI performs no network fetch.
2. **Schema vs runtime:** JSON Schema Draft 2020-12 closes every new object
   with `additionalProperties:false`, fixed `automatic_promotion=false`,
   `text_storage=none`, `review_status=not_started`,
   `rule_status=not_formalized`, and all six axes marked
   `not_completed`. Runtime checks the exact axis order; mere enum
   membership is insufficient. The four `u03_hNNN` IDs must bind to
   corresponding `u02_cNNN` IDs, topic, web route and title provenance.
3. **Parent authority boundary:** the submitted U0.2 dossier must itself
   validate. The card's declared `source_docket_sha256` must equal the
   canonical *metadata* fingerprint of that supplied dossier. This is not
   an edition digest, immutable trusted source, license or external attestation;
   supplying a new valid parent and matching hash is possible.
4. **Programmatic boundary:** exact builtin-only JSON tree check rejects
   dict/list subclasses, aliased containers, cycles and unexpected custom
   scalars; bounded preflight rejects deep/large objects and unsafe Unicode.
   Unknown fields are rejected early before exploring deeply nested objects.
   JSON Schema error enumeration is capped.
5. **CLI boundary:** the shared U0.1 safe file reader accepts only bounded
   local regular files, rejecting symbolic links, FIFO/device, duplicate
   members, invalid UTF-8, lone surrogates and nonstandard numeric values.
   Return code 0 = syntactically consistent metadata, 1 = invalid metadata
   or parent binding, 2 = invalid/unsafe file read.
6. **Report semantics:** `valid_metadata` and `source_docket_match`
   are separate. The latter remains true for an invalid question if the
   same valid parent metadata fingerprint matches. Every report keeps
   `eligible_for_engine=false`, `reviewed_rule_count=0`,
   `human_review_performed=false`, `rights_verified=false`,
   `edition_authenticated=false`, `scholarly_authority_verified=false`.
   The SHA-256 digest of cards is order-stable and unauthenticated.
7. **CI paths:** workflow triggers on U0.3 implementation under `core/usul/**`,
   U0.3 test, schema, research fixture, documentation and review audit on
   both PRs and `main` pushes. The workflow runs 110 unit tests
   and invokes all three stages' offline CLI checks. The general P0
   workflow is also triggered by `core/**`.

## Test-first falsification: observed live GitHub runners

- Initial RED-only commit `c20d2ac1469bfb3af92797d55da42eb7c3243311`,
  [P0 run 39093161737](https://github.com/AIMubin/Mubin/actions/runs/39093161737):
  expected `ModuleNotFoundError: No module named 'core.usul.claims'`,
  **92 test methods, 1 import error**.
- Initial implementation `0ab56eed12fb7b3ab242e5528701303898f90778`,
  [Usul run 39093316426](https://github.com/AIMubin/Mubin/actions/runs/39093316426)
  and [P0 run 39093316413](https://github.com/AIMubin/Mubin/actions/runs/39093316413):
  **109/109 passed** plus CLI checks.
- Primary reviewer spotted incorrect conflation of question validity and
  source digest consistency in `assess_cards`. RED test-only commit
  `ebfdbccbb5a40b6477ea421bba8394f23d3a151a` asserted that an
  invalid question with unchanged valid parent must still report
  `source_docket_match=true`.
  [Usul 39093414608](https://github.com/AIMubin/Mubin/actions/runs/39093414608)
  and [P0 39093414605](https://github.com/AIMubin/Mubin/actions/runs/39093414605)
  both failed as expected: **110 methods, 1 failure**.
- Repair commit `3bb21eb421d0b2a674e4047c55098f0c0ac908e3`
  separates bounded parent-fingerprint matching from overall question validation;
  genuine lone-surrogate test corrected in `51eb1503` and workflow title
  corrected in `db7d6fe6`.
  [Usul run 39093470727](https://github.com/AIMubin/Mubin/actions/runs/39093470727)
  and [P0 run 39093470705](https://github.com/AIMubin/Mubin/actions/runs/39093470705)
  both succeeded at the exact `db7d6fe6` HEAD: **110/110 passing**,
  including frozen U0.1 and U0.2 smoke checks.

## Supplemental maintainer-only adversarial review and limitations

`codex_review=unavailable` for this review cycle: Codex explicitly reported
**code-review quota exhaustion** in the predecessor PR #67. No Codex
code-review result for the U0.3 HEAD was obtained, and this maintainer-only
security review must never be represented as independent or scholarly signoff.

Manually checked falsifying swaps of candidate identity, topic, route and
authorship provenance; modified/reordered/omitted six evidence axes; forged
`rule_ast`, `author_quote`, `reviewers` or `p1_receipt`;
forged source hash; mutated parent; malformed JSON, pathological containers,
custom dict comparisons, invalid UTF-8 and lone surrogates; missing question
mark, out-of-budget text and CLI exit codes. Automated tests cover each
structural class and run successfully on GitHub, but **they do not establish
source authenticity or interpretive correctness**.

Residual risks:
- Arabic question-mark checks cannot prove a real interrogative, doctrinal
  neutrality or absence of hidden assertions/third-party verbatim phrases.
  Even allowed generic string fields could be misused to put protected text
  into the JSON. Human source/rights review remains indispensable.
- Only *supplied* metadata identity is checked. No independent print-edition
  collation or external hash registry exists. U0.2 printed page labels are
  not verified by U0.3.
- Schema/formal tests do not attest two human reviews, academic qualifications,
  identity independence, legal permission, historic scholarly agreement,
  hadith authenticity or valid fiqh rulings. The four cards still have
  **24 pending evidence tasks and zero approved Usul rules**.
- The offline input reader's no-follow guarantee is implementation/OS-specific;
  Linux GitHub CI does not establish equivalent behavior on every platform.

**Disposition:** no known structural correctness blocker within the defined,
bounded U0.3 metadata pilot at the reviewed implementation HEAD.
**Do not merge** without checking this audit commit's own exact-HEAD CI,
resolving review comments, and dealing with dependencies #66/#67.
Nothing here authorizes use of copyrighted texts, rule promotion or a
Mubin release. This is not independent validation.
