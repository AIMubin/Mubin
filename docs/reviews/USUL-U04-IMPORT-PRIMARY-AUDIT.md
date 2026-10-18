# U0.4 — primary maintainer and security fallback audit

**Review date:** 2026-10-18. **Stacked base:** U0.3 PR #68 HEAD
`726de1441832aeb9f993df09a3daff3ab0266e63`.
**Reviewed implementation HEAD:** `cb45ea8330bad6bb43ac6daaef37683187c9368a`.
**PR:** #69, draft. Dependencies: U0.3 #68 → U0.2 #67 → U0.1 #66.
**Global Mubin version:** unchanged `0.1.0-alpha`.

## Source-vs-engineering provenance

Reviewed prior U0.4 *local research documentation* and maintainer notes in the
Mubin Library; the old cumulative ZIP was not exported into this GitHub
workspace. This PR is a **new implementation of the bounded research
contract**, not a byte-for-byte reproduction of the historical local ZIP.

Independently examined public-display pages:
- https://shamela.ws/book/8180/146 (site page label 53)
- https://shamela.ws/book/8180/149 (site page label 56)
- https://shamela.ws/book/8180/157 (site page label 64)
- https://shamela.ws/book/8180/556 (site page label 471)

**Attribution-sensitive observations:** the /146 editor notes additional
`قال الشافعي` in some witnesses; /149 notes
`الخاص` vs `الخصوص` variation; /157 notes `دلت` vs
`فدلت` variation; /556 starts with a question of an interlocutor,
and the footnote says the `باب الإجماع` heading was added from
printed variants and not recorded in the original. None of this
establishes an independently collated, authenticated printed edition.
The web tool's rendered public-display pages, not local book bytes,
were the evidentiary basis for the eight short fixture excerpts.
**No publisher byte digest, source-book acquisition, lawful
redistribution grant or scholarly approval was obtained.**

## Exact files changed (implementation candidate)

Seven paths before this audit:
1. `core/usul/observations.py`
2. `core/usul/observations_cli.py`
3. `core/tests/test_usul_u04.py`
4. `schemas/usul-u04-text-observations.schema.json`
5. `research/usul/u04-risala-text-observations.json`
6. `docs/research/USUL-U04-TEXT-OBSERVATIONS-AND-REVIEW-PROTOCOL.md`
7. `.github/workflows/mubin-usul-synthetic.yml`

No modifications to frozen U0.1 synthetic truth tables/hashes,
U0.2 dossier, U0.3 questions, H3.9.2 heldout manifests/corpora,
external-source rights registry, P0 data, or Mubin release metadata.

## Primary code, schema, CLI and threat-boundary review

1. **Parent validation:** `validate_observations` fully checks the
   U0.3 question registry against its U0.2 parent before comparing
   the ledger's `source_docket_sha256` and
   `question_cards_sha256`. These pins bind **local metadata**
   only. A modified parent and matching new hash do not
   independently prove a publisher text or permission.
2. **Stable identity:** four exact `u04_t00N` IDs bind to four
   `u03_h00N` and `u02_c00N` parents, fixed route IDs
   `146,149,157,556`, site-reported print-page labels
   `53,56,64,471`, URL and parent heading provenance.
   The route number is not a printed-page number.
3. **Speaker separation:** every one of the eight excerpt IDs
   `u04_t00N_e0X` is bound to its exact declared voice role and
   local SHA-256 of UTF-8 exact text. An editor footnote cannot
   be relabeled author; the Ijma question is not treated as the
   author's verdict, nor its editorial heading as authorial.
   In the bounded v1 pilot, exact snippet changes fail closed
   pending explicit review. The hashes are part of this repository,
   not an externally witnessed source-identity record.
4. **Finite source display:** two bounded snippets per site route,
   <=25 whitespace-delimited words per route across both
   snippets. This is a conservative **engineering length cap**,
   **not** a legal finding that this amount is freely
   reproducible. No large texts or complete pages stored.
   The display fragments require rights review before public use
   beyond the research context.
5. **Schema/hostile inputs:** Draft 2020-12 schema with
   `additionalProperties:false` at root, observation and excerpt
   levels; fields for authority/rights/edition review are absent
   or locked to explicit non-verified states. Early unknown-field
   screening precedes bounded exact-builtin-JSON-tree and
   canonical input preflight. Dict equality spoofing, nested
   subclassed containers, aliases, cycles, unpaired surrogates,
   bad Unicode and size/depth bombs fail before hashing.
   Diagnostics are bounded.
6. **CLI/error semantics:** source and both parents are read by
   the shared safe offline reader (256KiB input cap, regular
   files only, reject symlink/FIFO/device, duplicate JSON keys,
   NaN/Infinity, invalid UTF-8 and lone surrogates).
   Return 0 = structural observation success only;
   1 = metadata invalid; 2 = unsafe/unreadable file.
   Report does **not echo excerpts or analytic notes**.
7. **No inference bypass:** results hardcode
   `approved_rule_count=0`, `eligible_for_engine=false`,
   `edition_authenticated=false`,
   `legal_rights_verified=false`,
   `source_bytes_pinned=false`,
   `human_review_performed=false` and
   `author_attribution_verified=false`.
   The validator never invokes a juristic AST or downloads
   source materials; its internal output is not a fatwa.
8. **CI coverage:** U0.4 source under `core/usul/**`,
   tests, schema, research fixture/docs/review docs and workflow
   all trigger the scoped workflow on PR/main push.
   The workflow executes compileall, entire core unittest
   discovery and explicit offline CLI checks for U0.1-U0.4,
   while the P0 workflow independently runs for `core/**`.

## RED-first findings and live GitHub proof

- Test-only commit `7dd3cee750ffb33117ed618fa414cd4ad98e2865`
  defined U0.4 adversarial contract before new modules existed;
  [P0 run 39099814780](https://github.com/AIMubin/Mubin/actions/runs/39099814780)
  failed as expected due to absent `core.usul.observations`.
- Initial implementation commit
  `58caa156e3b0d6c10d2c4a5cbbfb626fb483197e`,
  [U0.4 run 39100006061](https://github.com/AIMubin/Mubin/actions/runs/39100006061)
  and [P0 run 39100006072](https://github.com/AIMubin/Mubin/actions/runs/39100006072)
  **RED** with 127 methods and two failures: over-escaped
  `site_page_url` regular expression rejected all four
  canonical site URLs. Fixed schema regex in `da7afbc6`;
  [U0.4 run 39100077211](https://github.com/AIMubin/Mubin/actions/runs/39100077211)
  and [P0 39100077209](https://github.com/AIMubin/Mubin/actions/runs/39100077209)
  then passed.
- During maintainer adversarial review, observed that
  `parent_bindings_match` was conflated with any source excerpt
  validation failure. Regression test-only commit
  `40e1c0860b482cae3e10e9ac4849b1944dc0f193`
  reproduced wrong `false` on mutated excerpt with unchanged
  correct U0.2/U0.3 parents.
  [U0.4 RED 39100129915](https://github.com/AIMubin/Mubin/actions/runs/39100129915):
  **128 tests, one expected failure**.
  Fixed in `cb45ea8330bad6bb43ac6daaef37683187c9368a`;
  [U0.4 CI 39100178227](https://github.com/AIMubin/Mubin/actions/runs/39100178227)
  and [P0 CI 39100178314](https://github.com/AIMubin/Mubin/actions/runs/39100178314)
  passed **128/128**. Real CLI output: 4 observations, 8
  excerpts, local observation digest
  `729b9aa8036c5e71fc255dccbb31c101f6c6f34a852d5bda86137a934e69e164`,
  all authority flags false and no body quote values leaked.
- Following this audit-file commit, final HEAD must again show
  **both** CI checks green. No historic green result may be
  silently substituted for changed-HEAD evidence.

## Codex quota fallback — not independent review

`codex_review=unavailable`: #67 recorded explicit Codex
code-review quota exhaustion. We did **not** perform a new
Codex pass for this HEAD or claim that agent review happened.
This additional test-first adversarial analysis is
**maintainer-only**; tests and AI assessment are not qualified
human certification.

## Scientific and rights blockers

The site could change; snapshots here are not the source's
authenticated bytes, a critical-edition collation, publisher
authorization or an approved reuse license. The two per-route
excerpts and researcher descriptions can still be misinterpreted
and cannot validate a whole book's historical textual tradition.
No independent reviewers, complete Usul conditions, legal rights
adjudications, methodology-specific competing authorities,
Hadith grades or fiqh rulings are supplied. Neither source
headline nor interlocutor text may be automatically promoted
to an authorial doctrine.

**Decision:** software research observation pilot is structurally
acceptable on implementation HEAD (subject to **final audit
commit** CI confirmation). Scholarly/rights/operational admission
stays NO-GO. Keep draft PR #69 stacked on #68, no premature
merge, no production release and no `main` mutation.
