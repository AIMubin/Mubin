# S0.1 Shamela Bibliographic Pilot — Primary Maintainer Audit

**Audit date:** 2026-10-16. **Scope:** metadata inventory only, source integrity and adverse inputs, with exact diff against Mubin main `567e55858a9911a23430ef81f1e41b7a5f26480e`. No text acquisition, API scraping, rights certification, model training, H3.9.2 frozen source modifications, or release-version change.

## Primary source inspection and trust model

Before authorizing secondary review, the maintainer independently examined:
- Official category landing and per-book bibliographic descriptions for `1681`, `7798`, and `8180`, including links to three human-browsable passage pages.
- Official https://shamela.ws/page/download: desktop app distributions and transferable `database` folder are publicly described, but neither on-disk format nor source rights or API is established by the inspected page.
- Existing Mubin `main` test workflow `.github/workflows/mubin-inference-foundation.yml`: `core/**` and `schemas/**` PR changes trigger Linux/Python 3.12 `unittest discover`.
- Existing Mubin architecture and frozen Hadith H3.9.2 registry: avoid claiming `source_blob_sha` alignment, inheritance of partition privileges or approved Hadith authority from a public web catalog.

The longer textual description of the al-Tabari entry mentions an earlier electronic textual source whose pages were matched to another edition; the top publisher metadata says the edition was re-keyed on al-Turki's print. This is an edition reconciliation **open question**, not a corrected fact. The `1681/9`, `7798/1` and `8180/114` route suffixes are **not asserted to be printed page numbers**.

## Contract and implementation invariants

1. Entire public catalog is editorially *observed* metadata only. Book pages, sample routes, publisher/editor fields and site-reported print pagination are evidence pointers, not text snapshots or authenticated editions.
2. `schema.additionalProperties=false` on top-level, acquisition and entries; hard-constant `rights_status=unverified`, `edition_verification=bibliographic_claim_only`, `text_acquisition_status=not_acquired`, and all three top-level acquisition booleans false. No `text`, `excerpt`, `text_sha256`, `spans`, `content_sha256`, `qualification_eligible` or `download_url` accepted.
3. Canonical stable *local catalog key* uses `shamela:book:ID` plus exact official `https://shamela.ws/book/ID` URL. A sample page URL must be an exact matching `/book/ID/POSITIVE_ROUTE_ID`. Link existence observed today **does not guarantee longevity**, API permissions, independent edition authenticity or page-to-text byte offsets.
4. Structural limits before schema traversal: <=256 entries, <=1 MiB canonical UTF-8 JSON, per-field lexical bounds and early rejection of unexpected/nested metadata (including acquisition keys), invalid UTF-8 surrogates, invalid JSON trees, duplicate book/source/page keys. Boolean `book_id` is not treated as a valid integer. Schema error diagnostics are truncated to bounded length.
5. Only the entry-independent `catalog_sha256` is computed from deterministic operator-supplied metadata JSON; it is **not** a SHA-256 of any classical work or downloaded book. CLI emits only validity/count/fingerprint/errors, not book excerpts, text or edition/source attestations.
6. The public-validator contract is narrower than P1; it does NOT grant content access, resolve legal rights, assert publisher authentication, grade a hadith, reconcile editorial footnotes or certify fiqh derivations. H3.9.2 holdouts remain sealed.

## Test-first evidence (negative before repair)

- Initial test-only commit `49deaec8050c93f4d84114e3482aa956df20d175`; [CI 38931976510](https://github.com/AIMubin/Mubin/actions/runs/38931976510) red with missing `core.source_catalog` import.
- Initial schema/corpus-free catalog and offline CLI through `d37d311feb33fb3df8be401ec633ca1e7a276228`; [CI 38932311959](https://github.com/AIMubin/Mubin/actions/runs/38932311959) had 66 tests and **2 failures**: whitespace-only edition accepted and nested JSON field produced giant diagnostics. Both fixed in `43cb172a2040a0bfe246a820a1f80b1bfe3fd8f6`; [CI 38932486874](https://github.com/AIMubin/Mubin/actions/runs/38932486874) **66/66 passed**.
- New adversarial tests `6c08c67ccf7c6b326415888a357f7f4f9440c522`; [CI 38932660885](https://github.com/AIMubin/Mubin/actions/runs/38932660885) red (**68 tests, 2 failures**) on oversized text being stripped before cap and unknown deeply nested entry data not being rejected early. Corrected in `1df72acf33b3f70a9ec5881ed1269907fad61166`; [CI 38932796509](https://github.com/AIMubin/Mubin/actions/runs/38932796509) **68/68 passed**.
- Further independent primary review revealed another early-validation bypass in nested `acquisition` metadata. Test-only `3b10fcc1c7bb4a119a73a7bfaeb922bd0e4b0ee6` reproduced it in [CI 38933111372](https://github.com/AIMubin/Mubin/actions/runs/38933111372): **69 tests, 1 failure**; fail-closed root/acquisition preflight in `7e54cb701a212919558a71217012d1ae213c3108`. Green CI [38933232999](https://github.com/AIMubin/Mubin/actions/runs/38933232999) passed after the repair.

## Residual limits

- This is a **static, manually assembled candidate catalog**. No automated extraction, resilient deep-link persistence test, authorized local database inspection or source-level hash comparison has occurred.
- Text acquisition, rights, authoritative editions, footnote collation, and OpenITI/Shamela exact edition crosswalk are unverified.
- Strictly offline scope means the runtime never queries the site. Public page metadata may change after the manual observation; its recorded catalog hash only identifies our JSON snapshot.
- The schema and helper are not an authenticated source authority. A malicious actor can fabricate a well-formed offline catalog. Human provenance and source verification remain separate governance steps.
- Tests are unit and synthetic adversarial metadata tests, not legal verification or research evidence that source content is accurate.
- Do not merge until current-HEAD CI is green, the full latest diff is verified, and the independent secondary review process is accounted for. If secondary review quota fails, record maintainer-only fallback rather than representing it as independent approval.

**Gate decision:** S0.1 metadata-only catalog is eligible for maintainer review when tests pass. S0.2 real text ingestion remains BLOCKED without authorization and proof of edition-level rights/custody.

## Secondary review findings and independent maintainer reinspection

Codex submitted review against `a5c9f707c3182316fcf3bde1616ca4e91f384834`, identifying two material P2 weaknesses. The primary maintainer re-read the exact HEAD CLI, schema, source validator, test suite, CI path filters, catalog and documents, and independently confirmed both issues before changes:

1. **Ambiguous duplicate JSON members**: Python's permissive default `json.loads` is last-wins, which let JSON with two `rights_status`, `book_id`, `scope`, or `text_acquired` keys validate even if a first-wins consumer would see a forbidden status. An explicit `object_pairs_hook` now rejects all duplicate keys at any object nesting level before source validation. `parse_constant` also rejects `NaN`/`Infinity` (not standard JSON), and the CLI returns input error code 2 without echoing unsafe book content.
2. **CI excludes catalog-only changes**: The inference contract workflow filters omitted `research/shamela/**` for pull requests and main pushes. Both event filters now include the catalog path, along with research documentation. The test suite asserts both occurrences; catalog-only change detection remains to be demonstrated by an actual catalog-only commit.

**Red-first evidence:** Tests added in commit `1876816b84803630623eb581fb4c695bb3edf1fe`; GitHub [run 38938067669](https://github.com/AIMubin/Mubin/actions/runs/38938067669) failed as expected (**72 tests, 6 failures** across a CI-trigger test, four duplicate-key subtests and non-standard NaN). The CLI parser fix `1f7494fed9446599d5366114d58cfc7f1d52e1d3` correctly rejected duplicate keys and NaN but did not yet update error diagnostics and CI filters; run `38938193640` still failed (**5 failures**). Workflow fixed in `b7a4ba84b5766633cc5302732867c15c58e002fd`. Final CLI diagnostics fix `12fed754acccad8c015d8cb77906a2ef3a174801` returned the expected stable `INPUT_ERROR` contract. **Green [run 38938347602](https://github.com/AIMubin/Mubin/actions/runs/38938347602): 72/72.**

**No change in scholarly assurance:** Source provider site URLs and human-book-page metadata do not establish printed-edition authenticity, licensed reuse, source bytes, page span, P1 proof, or permission to train a model. Tests establish only the validator's bounded local input contract.

**Additional official-source observation:** The public [official Shamela Telegram feed](https://t.me/s/shamelaws) describes portable `app` and `database` directories, calls out externally hosted paid AI tools using Shamela books without coordination, and mentions development of a free Shamela AI effort. That warning does not itself constitute a binding general-use prohibition; it is a strong reason to seek independent written clarification before any ingestion. The official [download page](https://shamela.ws/page/download) describes portability and availability of a full data folder, **not** an API, storage format, or rights grant.

**Review disposition:** P2 technical fixes were reproduced in unit tests, then repaired and CI validated. Resolve review threads with evidence and request a secondary pass on the final change if necessary. No merge unless final HEAD CI and change-scope review pass.

## Catalog-only CI trigger proven empirically

A **catalog-only** metadata clarification was committed as `6475ecef3a4c167cd4f03bedb8b2fe16bc1f486e` after the workflow path-filter correction. [GitHub Actions 38938699339](https://github.com/AIMubin/Mubin/actions/runs/38938699339) triggered from that exact commit **without edits to source code, schema or workflow in the same commit**, and passed **72/72**. This provides direct evidence that a change to `research/shamela/pilot-catalog.json` now invokes the contract suite on a PR. Both the `pull_request` and `push` path filters include `research/shamela/**`; the push behavior was code-inspected, not demonstrated by an actual main push because PR #59 remains unmerged.

## Follow-up gate

Written rights and supported source-format clarification are tracked in [S0.2 Issue #60](https://github.com/AIMubin/Mubin/issues/60). The official project’s publicly stated disagreement with uncoordinated *paid* AI products is a coordination signal; it does not establish a blanket prohibition, nor does it grant any rights. Mubin must obtain explicit authorized, per-purpose source access before local corpus extraction, embedding/indexing, AI training or redistribution.

**Approval boundary:** This remains a maintainer source-code and metadata-validator audit; final PR must be checked at its exact HEAD, secondary comments disposed with negative tests, and it must not be represented as an edition or legal license audit.
