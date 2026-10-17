# U0.1 Synthetic Usul AST — primary maintainer import audit

**Review date:** 2026-10-17. **Account:** Alajmah. **Review sequence:** personally audited local code and source transfer **before** any Codex request. **Scope:** synthetic logic only; no real Islamic legal inference or religious approval.

## Exact baseline and submitted candidate

- Base main `567e55858a9911a23430ef81f1e41b7a5f26480e`.
- First implementation commit `5e6d215facc82f7cb12c5b5ac71a185f4b80cba9`.
- Complete diff: **11 added text files**, with no modifications to existing main or H3.9.2 frozen assets: `core/usul/{__init__.py,engine.py,benchmark.py,__main__.py}`; `core/tests/test_usul_u01.py`; two Draft 2020-12 schemas; two frozen JSON fixtures; one dedicated workflow; research documentation.
- The eleven files were transferred from a reviewed local snapshot through GitHub's tree/commit/ref interface, and **each individual GitHub file was fetched afterward and verified to match the supplied text exactly**. No stage U0.2–U0.6 file or source-corpus text was transferred.
- The shared main test dependency `jsonschema==4.25.1` is already present; no dependency or global version changes.

## Independently verified fixture identities

- Frozen synthetic rulebook SHA-256: `a551b35678d6dc182f2e4cbab5e25cea8eb4b6392ee66eabc7a5cdc5611a02ea`.
- Frozen synthetic test cases SHA-256: `658e8278d7b7addf6dc56d81a6703bc55c95d19d7550e456bd3094016c368de9`.
- Suite: **15 synthetic positive examples and 25 synthetic adversarial examples**, no Quran/Hadith source material or H3.9.2 holdout data.
- Hashes check source identity, **not independent experimental preregistration or cryptographic signing by a qualified reviewer**.

## Primary inspection of algorithms, invariants and schema

1. **Schema**: Strict `additionalProperties:false` objects, unique declared synthetic symbols, restricted methodology/rule/fact names, finite operators `fact|not|all|any`, closed conclusion vocabulary (`track_north`/`track_south`), max numbers/depth of rules and AST nodes. No executable code field or qiyas shortcut.
2. **Preflight**: Programmatic input is bounded in UTF-8 serialized bytes, nested depth, node count and string cardinality, rejecting cyclic/repeated container aliases, non-JSON and invalid Unicode before JSON Schema error traversal. Diagnostic count is capped; the contract reports validation **status**, not raw model evaluation of protected texts.
3. **Three-valued logic**: Unknown facts remain `unknown`, with explicit `not`, `all`, `any` semantics. Established exceptions defeat a rule; unresolved premise/exception holds it pending. Contradictory active conclusions return `conflict`; a pending rule prevents unsafe single-conclusion promotion. Methodologies are evaluated separately without silent fallback.
4. **Frozen suite**: The runner checks BOTH raw byte SHA-256 pins, independently verifies exact expected outcomes for all 15 positives, requires negative cases to have no conclusion, and accepts only listed test-rulebook mutations. Deliberate fixtures remain untouched.
5. **CLI security**: Offline only. Maximum input size 256 KiB per file; regular files only; reject symlink/FIFO/device on Linux through `lstat`, `fstat` and `O_NOFOLLOW`; strict UTF-8, reject duplicate JSON members, NaN/nonstandard constants and lone surrogate strings. Output is JSON/human text with exit codes 0 pass, 1 suite mismatch, 2 malformed/unreadable input. On platforms lacking `O_NOFOLLOW`, file race hardening still requires platform-specific review; the supported Linux CI behaviour is tested.
6. **Assurance**: Reports always identify `synthetic_logic_only` or `synthetic_benchmark_only`, `scholarly_authority_verified=false`, `external_corpus_access=none`. No Quran, Hadith, Shamela corpus, publisher database, fiqh claim or reviewer identity is accessed or adjudicated.
7. **CI scope**: The new `mubin-usul-synthetic.yml` triggers on changes to the new source, tests, schemas, research/usul fixtures, relevant research/review docs, and workflow file for pull requests and main pushes. The existing P0 workflow also runs because `core/**` changes.

## Material flaw reproduced **before GitHub transfer** and repaired

**Problem:** Original `run_frozen_suite(rulebook, suite, raw_rulebook, raw_suite)` checked only the raw byte hashes, then executed the supplied programmatic `rulebook` and `suite` objects. A caller could reorder or otherwise alter the rulebook in memory while passing the original frozen bytes and still get `PASS`: a reproducible false association between executed content and pinned source.

- A new negative test `test_frozen_runner_binds_executed_objects_to_original_bytes` passed a reordered rulebook object and unchanged original bytes. It failed on the original code (`UNRECOGNIZED_RULEBOOK` expected, `PASS` returned).
- Fixed in `core/usul/benchmark.py`: after checking pinned SHA-256, bounded preflight checks the objects and compares them to re-parsed pinned raw bytes. A changed rulebook/case set now returns `UNRECOGNIZED_RULEBOOK` or `UNRECOGNIZED_FIXTURES`; cyclic substituted inputs fail closed.
- Ran the focused local test suite after the fix: **22/22 passing**. Frozen JSON bytes and their SHA-256 values were unchanged.

## Exact-head GitHub CI before this audit-document commit

- [U0.1 workflow run 39057423237](https://github.com/AIMubin/Mubin/actions/runs/39057423237): **72/72 tests passed**, plus frozen CLI.
- [P0 contract run 39057423151](https://github.com/AIMubin/Mubin/actions/runs/39057423151): **72/72 tests passed**.
- No independent Codex report was present when this primary review was prepared. Check the **new final HEAD** and rerun status after the audit documentation commit before requesting Codex.

## Known limitations and merge gate

- Passing tests does not establish actual Usul doctrines, appropriate legal rules, real evidence provenance, scholarly consensus or a valid fatwa.
- The formal outcomes are **artificial tracks**, not normative jurisprudential rulings; `established` fact states are user-supplied synthetic variables.
- The file hash pins are included in this same codebase, not independently witnessed immutable source records.
- No benchmark score is valid for untested input domains. All H3.9.2 source/family holdouts and human adjudication gates remain separately frozen.
- Pending **latest-HEAD CI and Codex second pass** (if available). Do not merge without resolving material findings and an explicit maintainer decision. The global Mubin release stays `0.1.0-alpha`.

**Disposition:** Ready for a secondary engineering review **only once the audit-document HEAD's CI is green**. No claim of scientific authenticity or human qualification.
