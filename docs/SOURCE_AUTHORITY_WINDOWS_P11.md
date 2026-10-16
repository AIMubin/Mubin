# P1.1 Phase C — Parent-pinned byte windows and P1 local receipts

**Status:** synthetic, test-demonstrated end-to-end window proof only. Not a qualified corpus integration, authenticated classical edition, redistribution license, hadith grade, or scholarly inference. **Prerequisites:** P1.0 PR #49, Phase A PR #53, Phase B PR #55. This PR is a stacked change and must not be merged out of order.

## Distinct immutable identities

The actual source cache file is read in full **on two separate verifier passes**. The Phase-B locator verifier checks strict UTF-8, LF-only bytes, exact quotation, Git blob SHA-1 and source SHA-256. Phase C then opens the parent again with no-follow safeguards, streams its full bytes to validate the same pinned Git blob and SHA-256, and extracts a selected bounded raw-byte interval. The resulting byte window is **not** the parent book.

`derive_parent_window(registry, cache_root, source_id, locator, excerpt, left_context_bytes=0, right_context_bytes=0)` returns `(report, window_bytes)`. The `report` is metadata only; `window_bytes` are returned separately in memory, and **never written by the API**. The caller must secure these bytes and cannot assume permission to publish them.

The versioned binding schema is `schemas/parent-window-binding.schema.json`, with:

- `parent`: source/work/version, pinned repository commit/path, parent Git blob SHA-1 and **full-file SHA-256**, parent byte size, absolute quote start/end.
- `window`: distinct deterministic `win.<sha256>` ID, parent-absolute start/end, **window SHA-256**, exact size, explicit `derived_byte_window_not_parent_book` label.
- `quote`: original H3.9.2 character locator, character positions, quote's byte offsets **relative to the new window**, and quote SHA-256.
- `authority`: hard-coded `edition=not_authenticated`, `rights=not_reviewed`, `entailment=not_checked`. A canonical `binding_sha256` is a content fingerprint, **not a signature**.

A window can be up to 4 MiB with an explicitly chosen cap (default 1 MiB) and is strictly UTF-8. Its context cannot split a Unicode codepoint. The original source may be larger than P1.0's 8 MiB single-snapshot limit, subject to bounded full-parent verification. The source is not modified or copied automatically.

## What is tested against P1.0

The synthetic integration fixture explicitly writes an in-memory window to a private temporary directory. It represents the **derived window as its own P0 `Source`**, using the window's SHA-256—not the parent's. A P1 manifest references only that window and a relative quote byte span. `core.provenance.verify_bundle` returns a P1 local-byte-exact receipt for the **window**. A corrupted staged window correctly invalidates that receipt.

`check_linked_p1_receipt(binding, p1_result, window_bytes)` checks that the **direct P1 validator result** has the expected local scope, operator-only rights assurance, exactly one matching receipt and an exact match of window ID, window SHA-256, quote SHA-256, relative start/end and receipt type. It requires the **original immutable window bytes** to revalidate the maximum 4 MiB size, declared size versus byte span, strict UTF-8, rejection of CR, the quote's exact UTF-8 byte span and codepoint count, and the window/content digests, in addition to binding schema, deterministic window identity, canonical binding fingerprint and quote locator-to-char/byte consistency. This signature is intentionally stricter than the earlier two-argument draft. A detached fabricated P1 result or forged operator-supplied registry remains outside these guarantees.

The synthetic `rights.status=operator_cleared` in the P1 test applies **only to locally generated test bytes**. Production rights are NOT inferred from `source_blob_sha` or from this derived binding. The implementation does not generate a rights declaration.


## In-process P1 execution path

`verify_staged_parent_window(binding, window_bytes, bundle, manifest, corpus_root)` is the preferred **local integration** entry point when the caller already has the verified parent-window binding, the same immutable window bytes, a separately created/staged snapshot, and appropriately reviewed rights metadata. Unlike the passive `check_linked_p1_receipt`, this function invokes the actual `core.provenance.verify_bundle` on the staged window, requires a passing P1 response, and only then revalidates the quote and derived-window identifiers. It returns no excerpt or source text; the result includes the P1 bundle/manifest local fingerprints and one bounded receipt, with `scope=derived_window_local_p1_only`, `rights_assurance=operator_assertion_only`, and the unchanged three explicit non-authority statuses.

If rights are unknown or restricted, P1 itself rejects the manifest. If staging bytes are altered, P1 rejects the file; if metadata/bytes are inconsistent, the parent-window validator rejects before source ingestion. The code **does not** create or authorize any source file, rights declaration, or temporary directory: all staging remains the caller's explicit responsibility. It is an in-process implementation guarantee, **not remote execution attestation or independent publisher authentication**. A malicious operator with control of source registry, code runtime, and filesystem can still forge a self-consistent local dataset and run.

## Non-negotiable boundaries

- H3.9.2 source partitions and its source-disjoint final holdout are governed by external custodian rules. The window API does NOT grant access to holdout sources; normal research must use only permitted non-holdout files.
- Actual corpus source bytes have NOT been run through this test suite. CI uses synthetic UTF-8 Arabic/emoji examples, including a >8 MiB parent.
- Phase B still **rejects CR/CRLF** anywhere in a source; Phase C inherits this limitation. Never normalize silently.
- The entire pin check depends on a user-supplied registry and trusted local file custody; Git SHA-1 does not authenticate a publisher or license. A `binding_sha256` fingerprint can be recomputed by a malicious author.
- A safe production workflow requires independent source edition authentication and rights review, strong secure custody, source-partition attestation, a trusted pipeline for direct P1 result generation, multiple-window batching and adversarial corpus-scale evaluation.
- No H3.9.2 frozen target, qualification, human-review decision or H4 gate is changed. System remains `0.1.0-alpha`.

## Reproduction

```bash
python -m pip install -r core/requirements-test.txt
python -m unittest discover -s core/tests -v
```

Refer to `docs/reviews/P11-PARENT-WINDOW-PRIMARY-AUDIT.md` for commit-pinned red/green CI evidence and independent-review status.

## Verification vs attestation

`check_linked_p1_receipt` is a deterministic consistency checker over caller-supplied binding, window bytes, and a **claimed** P1 result. It does **not** execute `verify_bundle` itself. A malicious caller could forge every field and recompute the local hash; production provenance must invoke the actual P1 verifier in a controlled pipeline and retain its input identities. A quote's original source-character coordinates can only be confirmed by reopening the pinned parent with `derive_parent_window`; the binding validator alone cannot rederive original book positions from a detached window.

**Security and correctness gates:** PR #57 was held after review found a missing 4 MiB/size-span check in the two-argument receipt linker and missing UTF-8/CR checks in the standalone binding validator. Both are now guarded by mandatory window-byte revalidation; quote decoded codepoint count is also matched to the H3.9.2 locator. See the red/green audit. This is a code-hardening result, not an additional level of scholarly or licensing assurance.
