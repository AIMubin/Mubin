# U0.1–U0.6 local archive → repository import: maintainer-first readiness audit

**Date:** 2026-10-17. **Current system release:** `0.1.0-alpha`. **Status:** source import NOT YET PERFORMED; this document is a scoped pre-import audit, not approval.

## Baseline and user-selected account

- Selected GitHub connection: **Alajmah**. The second linked account is not used for mutations.
- Confirmed `main` SHA at the start: `567e55858a9911a23430ef81f1e41b7a5f26480e`; branch protection was disabled. No direct write to `main`.
- Open independently: P1 work #49, #50, #53, #55, #57; Shamela bibliographic #59; Shamela research #62. Do not treat any as merged dependencies.
- Local unmerged artifact: `Mubin-U06-Unverified-Reviewer-Intake-Cumulative-2026-10-17.zip`. Its 110 ZIP members were inspected for unsafe paths/symlinks and extracted locally. This artifact is not in this PR.
- Original maintainer instruction: `docs/REVIEW_POLICY.md`; complete primary review and exact-HEAD CI before requesting any Codex review.

## Readiness audit of local code

The local archive includes heritage/source-use decision routing and offline Usul stages:

| Stage | Local scope | Current assurance boundary |
| --- | --- | --- |
| Heritage-first | Source-layer/purpose routing, intake triage, private AI-use log | Operator declarations are not licensed permissions; legal review separate |
| U0.1 | Synthetic typed rulebook, all-positions/test-case replay, 15 positive + 25 counterexample fixture program | No proof of real Usul correctness |
| U0.2 | Four book/page metadata locators | No publisher/edition/byte attestation |
| U0.3 | Four research question cards | Questions are not authorial rulings or executable rules |
| U0.4 | Short attributed observations, including editorial-heading/speaker distinction | No independently collated printed edition |
| U0.5 | Four review items and 24 pending evidence tasks | No independent human scholarly decisions |
| U0.6 | Structurally validated, **unverified** reviewer envelopes | No trusted identity, independence attestation or rule admission |

**Important invariant:** U0.2–U0.6 must never increase an admitted-religious-rule count as a result of well-formed metadata or two agreement claims. The frozen H3.9.2 benchmark/holdout partition and all open P1 provenance work are separate.

## Local evidence checked in the current review

- 110 archive members / 30 historical local evidence entries. Do not transfer old run logs, temporary evidence and duplicate local application instructions into versioned production source by default.
- U0.6 focused `python -m unittest discover -s core/tests -p test_usul_u06.py -q` succeeded with **21 tests**, and U0.5 focused suite succeeded with **20 tests** on extracted archive.
- A new `python -m unittest discover -s core/tests -q` attempt did **not** complete within the available tool timeout. Accordingly, the archive's historical `175/175` statement is not independently re-certified for the GitHub tree; no CI claims are made for U0.1–U0.6 imported code.
- Main currently pins `jsonschema==4.25.1`, compatible with the archive's use of Draft 2020-12 validation. The current main workflow only covers its existing `core/**` contract; Usul-specific CLI smoke tests require an additional scoped workflow included in the code stage, not merely this audit.
- The archive contains public-web-only, brief textual observations attributed to al-Risala. They are not a licensed/collated full corpus and may not be promoted to normative rules.
- The prototype may contain residual correctness and security flaws that only a full latest-branch diff review, negative tests and CI can rule out. Earlier local reports cannot substitute for that review.

## Import procedure / gates

1. **Source policy PR:** import `core/source_policy` and its focused tests, rights notice, complainant workflow and only stable governance docs. Check TOCTOU/private ledger path, malicious JSON, review-status gating and per-source hold semantics. Include tests that actually exercise the path filters.
2. **U0.1 PR:** import the exact rules/cases, AST engine and frozen tests, schemas and CLI. Test immutability/digests of the original synthetic fixture. All output remains `synthetic_benchmark_only`.
3. **U0.2 and U0.3 PRs:** metadata and question cards only, preserving source identifiers and explicit `not_verified` states. Do not merge Shamela P1 identities or use H3.9.2 holdouts to tune prompts.
4. **U0.4 PR:** short attributed observations and independent edition-trace requirements, no bulk text or implicit author/editor conflation.
5. **U0.5 and U0.6 PRs:** queue and unverified-intake data model, binding checks, negative tests for duplicate reviewer/slot/unstated evidence, and strict nonpromotion invariants.
6. **Each new head:** inspect exact diff, code, schemas, test logic and CI filters; first reproduce material bugs, then correct and run CI. Request Codex only when latest-HEAD primary review and green CI are already established. Resolve every real review finding. Report any quota fallback as maintainer-only.
7. **Release:** no merge or general system version change without integration and rights/source credibility gates. Existing open PRs remain independent; obtain explicit review decision for each.

## Next implementation step

Code has **not** been copied by this documentation change. Track the staged imports under [Issue #63](https://github.com/AIMubin/Mubin/issues/63). The local ZIP remains a proposed source artifact awaiting a per-stage verified transfer, not a GitHub artifact or published app.

**Decision:** PASS for documenting integration scope, BLOCKED for declaring runtime code integrated, independently verified scholarly review, new license rights, or permission to merge Usul logic into `main`.
