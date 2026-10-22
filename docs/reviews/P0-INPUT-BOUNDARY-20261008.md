# P0 input-boundary maintainer audit — 2026-10-08

**Branch:** `fix/p0-input-boundary-20261008` (draft PR #50)  
**Reviewed base:** `567e55858a9911a23430ef81f1e41b7a5f26480e`  
**Fix candidate:** `4e981dac50998e222080cd1887cca8ae0ac66af0`  
**Scope:** `core/inference/validator.py`, `core/inference/__main__.py`, and `core/tests/test_inference_foundation.py` only (plus this audit). No Hadith H3.9.2 or system-version changes.

## Maintainer-first threat and invariant review

The original P0 CLI caught JSON syntax and Unicode decoding errors but omitted `RecursionError` from `json.loads`. The library hashed evidence excerpts by calling `.encode("utf-8")` without guarding JSON-escaped lone surrogates. Its 5,000-entity cap ran *after* full JSON Schema traversal; programmatic input received no library-bound 5 MiB guard.

| Test-first finding | Original failure | Fix |
| --- | --- | --- |
| Deep JSON CLI input | `test_cli_rejects_deeply_nested_json_without_traceback` errored due to decoder recursion | Catch `RecursionError` and return documented exit 2 / `INPUT_ERROR` |
| Non-UTF8 JSON strings | `test_lone_surrogate_rejected_at_p0_library_and_cli_boundary` errored on source excerpt encoding | Validate UTF-8 serializability at library boundary; return structural issue and CLI exit 1 |
| Oversized invalid collection | `test_oversized_invalid_entity_collection_fails_before_schema` returned thousands of schema diagnostics instead of early cap failure | Type-safe entity preflight before schema validation |
| Deep programmatic values | `test_deep_programmatic_bundle_fails_closed` returned only a schema error without rejecting deeply recursive input itself | Catch `RecursionError` from serialized representation preflight |

**Controlled failing run:** commit `68e2f9095ae995ae73525bef235883a9457c01d1`, workflow run `37832985739`: **54 tests — 3 failures, 1 error**. Failures confined to the four new negative tests.

**Corrective commits:** `8109006c1fe41fe6ccf90b5147d5941733560b72` and `4e981dac50998e222080cd1887cca8ae0ac66af0`.

**Passing fix run:** `37833096277`, **54/54** tests; new negative cases passed. The CI run above belongs to the fix commit before this audit-documentation commit. A new latest-HEAD CI run is required before merge.

## Residual limits

- Structural validity is not source fidelity, legal-semantic entailment, or a sound religious conclusion.
- UTF-8 serialization preflight places a 5 MiB bound on ordinary Python JSON inputs, not an absolute memory bound on arbitrary Python object graphs or custom object implementations.
- File size and entity caps protect individual small-bundle validations; they are not a substitute for streaming hostile-input processing.
- The fix does not relax Hadith qualification, Schema-31 human signoff, holdout seals, or any H4 gate.

## Review gate

Primary maintainer audit completed before secondary review. Before merging: verify latest-HEAD CI, review complete diff and exceptions, obtain secondary review when available, resolve all findings, then verify postmerge main. Self-review is not independent approval.
