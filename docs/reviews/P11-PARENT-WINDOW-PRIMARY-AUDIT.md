# P1.1 Phase C — Primary maintainer audit

**Scope:** only the new `core/source_authority/windows.py`, `schemas/parent-window-binding.schema.json`, `core/tests/test_parent_window.py`, one `__init__.py` export change and documentation. Branch `feat/p11-parent-window-phase-c` is **stacked on #55**. No H3.9.2 files, source registries, human-gold adjudication, benchmark quotas, holdout seals, H4 gates or Mubin system version changed.

## Source-inspection invariants

1. **Dual identity:** P1 snapshot source ID must equal derived window ID, never parent source ID. P1 receipt source SHA-256 is the window SHA-256 and must differ from parent SHA-256 for typical proper subsets; the parent retains pinned Git blob SHA-1, SHA-256 and absolute quote byte offsets in a separate binding.
2. **Trusted source read:** actual parent bytes are re-opened and rehashed after Phase B's character-to-byte mapping; the same file descriptor is used for the second complete digest and window extraction. Mismatched digest, size, file identity or timestamps rejects any bytes/receipt. Source symlinks and nonregular files are rejected. Operator-controlled registry and file custody remain untrusted authority.
3. **UTF-8 correctness:** phase B's LF-only restriction carries through unchanged, as do strict no-normalization, correct codepoint offsets and exact excerpt matching. Derived windows must decode as strict UTF-8; context that slices multibyte characters fails rather than being repaired.
4. **Bounds:** max 4 MiB derived window (default 1 MiB), source size cap inherited from Phase B. One window/one quote/one P1 receipt per binding. No automatic staging, ingestion or assertions about third-party legal rights.
5. **Binding checks:** deterministic `win.<hash>` identity and binding hash, schema rejects extra authority states, parent/quote/window offset relationship checked, and direct P1 output must match window and quote digests/offsets. Canonical hashes are consistency checks, **not trusted origin signatures**.
6. **Claim boundaries:** passing P0/P1 demonstrates structural and local-byte-exact consistency, not the veracity of a hadith, a work's scholarly source identity, legal clearance or correct reasoning.

## Test-first and targeted reviews

- Initial test-only `5c741a3b9e4fb14433baf0bc3b092cc1f1e77e1e`, CI `38916688226`: import error for non-existent `core.source_authority.windows` (128 tests, one error).
- Initial schema and implementation through `fa48b30c705db90c069f1c863cd17052aa71c5d9`, CI `38917097149`: **139/139** including synthetic parent >8 MiB, two identity SHA-256 values and direct P1 local receipt.
- Test-only `df8acc73b493ec9a2dc8b7a082904239f37d0b6e`, CI `38917325560`: missing explicit P1-link-check import (expected failure). Fixed in `b271fb026b491426efed6cd473395f32b59e772f` and export `962b6efbd8e828af43734de375c9fdd723bb0dd7`, CI `38917484171`: **141/141**.
- Further maintainer adversarial test `90b82f636824de3ec6db1c62e314083089907547`, CI `38917636202`: **141 tests / 1 failure**, proving that a detached P1 receipt was incorrectly accepted after editing parent `version_id` in the binding. Fix `4caa61a3b20f7ce009513bd3e0d0c4d6ce4d71bb` now verifies the binding and window identity hashes plus the immutable quote locator-to-char/byte connection when linking any P1 receipt.
- Latest exact HEAD CI must be verified **after this documentation commit**. No merge until that result and independent secondary review are accounted for.

## Residual limitations

- `validate_parent_window_binding` is **metadata and derived-window content self-consistency only**. `check_linked_p1_receipt` checks an input P1 result's consistency; it cannot independently prove it was executed by trusted P1 code. Only `derive_parent_window` actually reads/rechecks the pinned parent file, and operator custody remains a trust assumption.
- Full parent is hashed twice per window: correct but inefficient for many quotes, requiring later safely batched immutable parent snapshots, coalesced spans and source-scale benchmarking.
- Real corpus source and authority/edition rights verification, CRLF handling, and protocol-specific holdout custody are separate gates. The current integration uses explicitly cleared **synthetic** P1 bytes exclusively.
- This record represents **primary maintainer inspection**, not independent Codex/research/scholarly review. Any Codex quota fallback must be identified as maintainer-only and cannot authorize an independent-approval claim.

## 2026-10-16: mandatory maintainer revisit after PR review findings

Reviewed exact code and contract (validator, receipt linker, schema, CLI/test workflow and documentation), **before authorizing any further outside review**. On PR #57, Codex had identified two unclosed findings against previous HEAD `a4d9731b9b3cca72115587723b18acb2ce6e8c5f`:

1. **P1 (linker accepts rehashed inconsistent windows):** two-argument `check_linked_p1_receipt(binding, p1_result)` checked metadata hashes but never validated actual window byte length, window size/span consistency or 4 MiB cap. A fabricated declared length could be canonically rehashed and accepted as linked.
2. **P2 (standalone validator trusts hashed but illegal contents):** self-consistent `binding_sha256` and `window.id` could hide invalid UTF-8 or a CR byte in the claimed window. Both violate the Phase-B strict-UTF-8 and LF-only contract.

**Additional independent maintainer finding:** even a window with valid UTF-8 bytes could claim a locator with a different Unicode codepoint count while recomputing metadata hashes. This is not a defensible H3.9.2 char locator mapping.

**Test-first negative evidence:** test-only `0e2dc4bef22aa664b8bdfd3e151419a9ed499823` and fixture-fix `5578ef77cabd66d40f413f5940851485f95b1a1d`: [CI 38920523338](https://github.com/AIMubin/Mubin/actions/runs/38920523338) **143 tests; 3 failures (one for quote character count, two UTF-8/CR subtests) and 1 error**. Failures were missing raw-window linker argument and unsupported integrity invariants. A separate earlier run `38920446804` also exposed an accidentally double-escaped *test fixture*; its fixture was corrected before the proper red run.

**Fix:** `887f64e9fd8e3d91df25110e55cbf9be756769fc` makes actual immutable `window_bytes: bytes` mandatory in P1 linkage, calls the full `validate_parent_window_binding` before comparing P1 receipt fields, decodes window and quote in strict UTF-8, validates UTF-8 quote codepoint count, and checks declared-size limits. A literal `CR` byte probe was corrected in `f2da73d5ecbeaba6d7504019051acd5275282e8f`. **CI [38920708657](https://github.com/AIMubin/Mubin/actions/runs/38920708657) passed 143/143**, including all new regression cases.

**API compatibility:** This is an intentional breaking change *inside unmerged PR #57*; all known new call sites in `core/tests/test_parent_window.py` are updated. No released or merged public API is being broken.

**Residual red-team boundaries:** binding SHA-256 is not a signature; a detached window cannot independently establish the exact parent-book character positions without parent access; a caller-supplied `p1_result` cannot prove trustworthy execution of the actual P1 validator. Registry/edition/rights/holdout restrictions remain separate. Last CI evidence for this updated audit/doc commit must be checked on its exact HEAD before resolving findings or merging.
