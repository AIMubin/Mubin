# P1.0 Independent Maintainer Engineering Review

**Stage:** offline source snapshot provenance pilot, not complete P1 corpus qualification.  
**Primary reviewed candidate:** branch `p1-evidence-provenance-core` after initial contract/validator/test commits; source baseline `567e55858a9911a23430ef81f1e41b7a5f26480e`.  
**Audit author:** primary maintainer engineering review **before any P1 Codex request**.

## Source-based findings and responses

| Area | Finding and consequence | Correction / test |
| --- | --- | --- |
| Source digest | P0 permits a self-asserted `verified` field that does not prove the original file matches | Recompute full local file SHA-256, compare with both P0 `Source.content_sha256` and manifest; independently bind quote to exact byte span. Tamper+fake-quote tests |
| Locator integrity | Global substring search could satisfy a quote from the wrong location | Use versioned, unique half-open byte spans; reject bad interval, duplicate locator, overlap and UTF-8 split; positive Arabic multibyte test |
| Input traversal | User-supplied relative paths could access files outside corpus | Reject absolute/traversal/backslash/unusual path segments and existing symlinked ancestors; negative tests for parent/final symlinks |
| Rights | Initial validator flagged restricted rights but still opened local source; even reading was inappropriate | Fail before source file open if `rights.status != operator_cleared`. Regression with restricted source deliberately deleted |
| Resource limits | Initial design bounded file bytes but not number of per-source locator spans | Cap 16 sources, 1,024 spans each, 4,096 total spans, 8 MiB/source, 32 MiB total, 5 MiB each CLI JSON input; cap regressions |
| False assurance | A self-consistent malicious fake book+manifest can pass a local hash check | Return only `local_byte_exact_match_only` receipts, `rights_assurance=operator_assertion_only`. Never call this verified external origin, legal clearance, a valid hadith or fiqh conclusion |
| CLI | Should not expose receipts for partly failing bundles or overwrite pinned source snapshots | Read-only CLI and library; failure returns `receipts=[]`; 0 structural+local match, 1 validation rejection, 2 malformed/missing/oversize input |
| Compatibility | Source manifests must not mutate P0, rewrite scholar-derived statements or relax H3.9.2 | Reuse P0 validator before P1 and leave system `VERSION.yaml`, all H3.9.2 campaign artifacts and their qualification gates unchanged |

## Reproducibility

```bash
python -m pip install -r core/requirements-test.txt
python -m compileall -q core/inference core/provenance core/tests
python -m core.provenance --help
python -m unittest discover -s core/tests -v
```

Initial P1 implementation CI `37817922739` passed **80** combined P0/P1 tests. Following the primary review, further tests cover hardening and resource limits; only the CI run associated with **final reviewed HEAD** can authorize a PR review request. Any subsequent commit requires re-evaluation of HEAD-specific CI.

**Scientific caveat:** Unit fixtures are synthetic, not actual Quran/Hadith/fiqh editions. This P1.0 pilot demonstrates local byte correspondence and explicit uncertainty but **does not** provide an independently authenticated Islamic corpus or historical facts. A signed/verified external source trust anchor, license audit, and immutable corpus acquisition (P1.1) are still required.

## Known operational limits, separate future work

- Concurrent malicious changes to the local filesystem between path checks and reading are outside the trusted, stable-snapshot model. Do not deploy P1.0 as a hostile-multi-tenant file ingestion service without an audited descriptor-safe open implementation.
- Rights information is operator-supplied metadata, not legal authentication.
- P0 proof checking remains structural; source match does not establish that a quotation entails a proposition or validates a scholarly conclusion.
- No real corpus content or redistribution license is bundled. P1.1 ingestion requires explicit source evidence and licensing review.

## Review order

This written independent maintainer audit and green HEAD CI must precede the first P1 Codex invocation. Resolve any Codex finding by independently reproducing it, adding a regression test, correcting the code, and rerunning HEAD CI. If Codex is unavailable or quota-limited, disclose the absence of independent review and perform an explicitly **non-independent** extra maintainer adversarial pass.

## Second-pass review findings and falsification (post PR #49)

Codex's review of primary-audited HEAD `322228fca470856b629f5fb903f156e50567756b` raised two P2 concerns. **Maintainer independently inspected the code and wrote failing tests before altering the validator.**

| Finding | Original failure proof | Fixed invariant |
| --- | --- | --- |
| MR-P1-09: escaped lone surrogate (`\\ud800`) crashes verifier / CLI | Pre-fix CI `37828101212`: `test_lone_surrogate_in_bundle_fails_closed_in_library` errored with `UnicodeEncodeError`, `test_lone_surrogate_in_bundle_cli_uses_documented_exit` failed on raw traceback | Reject non-UTF-8-encodable JSON values with `valid=false`, empty receipts, diagnostics and CLI exit 1 before calling P0, in both programmatic and CLI paths |
| MR-P1-10: oversized, malformed manifest traversed by JSON Schema before P1 caps | Same pre-fix run failed two tests: `test_malformed_oversized_spans_short_circuit_before_schema` and `test_oversized_source_count_short_circuits_before_schema` | Preflight source/span counts before expensive schema traversal, guarded against malformed nested entry types; enforce 5 MiB JSON bytes per programmatic argument as for CLI |

**Controlled failing stage:** commit `a8d2323e5663e142aaf2f44b68b453021fd2a53e`, run `37828101212`, **87 tests: 3 failures and 1 error**, confined to the four newly added regressions. No preexisting passing test was loosened.

**Code correction:** commit `3979c9f154a3e66ff02d2d349bd5c15b7cba84cd`. Both post-fix PR workflows passed: P1 `37828257950`, P0 `37828258051` — each **87/87**, as did P1 branch run `37828250963`. The later documentation-only commit requires its own latest-HEAD CI before another Codex review request.

**Maintainer risk analysis:** early cardinality checks are intentionally type-guarded; invalid scalar/nested manifest structures are still rejected by the JSON Schema. Pure-Python library input beyond 5 MiB of compact UTF-8 JSON is now rejected; rejecting this early is not a proof of memory-safe processing of an adversarial Python object with highly complex custom types. No source trust, external rights verification, source authenticity, source-to-claim entailment, or qualified religious review is asserted.


## MR-P1-11 — nested JSON decoder recursion (8 October 2026)

**Secondary-review discovery:** Codex on `3039ef32650624a6a467ce41f886862ca981d426` identified that `_load_json` could raise an uncaught `RecursionError` on deeply nested JSON well below the 5 MiB input limit. This violates the documented CLI input-error contract. The associated PR #49 thread remained unresolved when reproduction began.

**Independent maintainer reproduction FIRST:** test-only commit `86954e2d437e0975bd38daef1c4b49042e6b61d7` added two targeted negative tests, one for the bundle and one for the manifest. Workflow `37832965816` recorded **89 tests, 2 failures**; both tests showed an uncaught `RecursionError` and exit 1 rather than documented exit 2.

**Correction:** `ce988b831992539ca864e30e74d9779b9cc4c5a2` includes `RecursionError` in the guarded JSON input exceptions, preserving `INPUT_ERROR` and exit 2. Workflow `37833093496` completed **89/89** tests successfully, including both newly failing regressions.

**Scope:** only `core/provenance/__main__.py` and `core/tests/test_provenance.py` changed in this correction. P0 contracts, prior P1 trust boundaries, and all H3.9.2 frozen assets remained untouched. P0 input-boundary hardening is separately tracked in draft PR #50.

**Review policy:** this document commit requires fresh latest-HEAD CI before any merge. Recheck the complete new diff, Codex finding/thread resolution, and the repository's main-branch protection state. No source authenticity, operator rights, scholarly review or fiqh correctness is claimed.
