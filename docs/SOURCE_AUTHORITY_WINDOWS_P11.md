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

`check_linked_p1_receipt(binding, p1_result)` checks that the **direct P1 validator result** has the expected local scope, operator-only rights assurance, exactly one matching receipt and an exact match of window ID, window SHA-256, quote SHA-256, relative start/end and receipt type. It also validates binding schema, deterministic window identity, canonical binding fingerprint and quote locator-to-char/byte consistency. A detached fabricated P1 result or forged operator-supplied registry remains outside these guarantees.

The synthetic `rights.status=operator_cleared` in the P1 test applies **only to locally generated test bytes**. Production rights are NOT inferred from `source_blob_sha` or from this derived binding. The implementation does not generate a rights declaration.

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
