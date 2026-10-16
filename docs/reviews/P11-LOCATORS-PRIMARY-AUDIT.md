# P1.1 Phase-B Primary Maintainer Audit — 2026-10-16

**PR:** stacked Phase-B #55, base Phase-A PR #53 HEAD \`37636b67afb977be3e3edb93b1a8c07c3c1bedfb\`.  
**Scoped files:** \`core/source_authority/locators.py\`, \`core/source_authority/__init__.py\`, \`core/tests/test_hadith_locator_bridge.py\`, \`docs/SOURCE_AUTHORITY_LOCATORS_P11.md\`, this audit. No frozen H3.9.2 mutation.

## Source and invariants examined before requesting secondary review

1. **True locator unit:** \`benchmark_campaign/factory.py\` constructs \`#char=\` locators using Python string slicing of \`Path.read_text(..., encoding="utf-8")\`; never interpret them as original byte indices or grapheme offsets.
2. **Universal-newline drift:** standard text-mode decoding translates CRLF/CR into LF. Reject any source containing CR, even outside the requested span. Do not silently transform, strip, or normalize source material.
3. **Pin binding:** strict regex binds the complete exact 40-char lowercase SHA-1 Git blob pin and canonical nonnegative half-open char indices. Hash raw Git blob header+bytes and compute independent SHA-256 on the same opened descriptor.
4. **Bounded processing:** 1 MiB source streaming chunks and incremental strict UTF-8 decoder; no full corpus materialization. Reject huge decimal offsets before int conversion, source-size cap, and overlong excerpt before scanning.
5. **Quote binding:** ensure \`end_char-start_char == len(excerpt)\`; map byte boundaries using the exact UTF-8 lengths of decoded prefixes; compare raw file bytes to the supplied exact quote. Output hash and offsets, not the supplied text.
6. **Resource and file safety:** type-check byte budgets; open a regular file with \`O_NOFOLLOW\` where available and compare file descriptor identity, size and timestamps before/after. The trusted cache root/ancestor and supply of registry are **outside** the authenticated boundary; this is a declared local operator-controlled cache.
7. **Human/religious validity:** the bridge cannot authenticate a publisher, rights, hadith grade, textual entailment or source-disjoint split. It cannot produce P1 \`local_byte_exact_match\` receipts until actual P0/P1 bundle+manifest verification is implemented.

## Test-first red and green evidence

- Test-only \`02de0fd0452a18353345c760c5030e8959a4a48a\`, CI \`38911431242\`: expected missing \`verify_hadith_locator\` import, 109 tests with one import error.
- First implementation: \`988c8d0383f730c4543b3110eabdee857a0bffa5\`, export \`a0eb9b421befcbea934671fe39a442adca9e228e\`.
- CI \`38911704538\`: 121 tests, 1 failure caused by overbroad test-only privacy assertion (it accidentally rejected the field name \`excerpt_sha256\`, not an actual quotation). The assertion was corrected to reject the literal quote in the serialized result.
- New adversarial oversized decimal test in \`f2af6f2e63fa5a46ada96fadef48369fdbf0db6f\`, CI \`38911879042\`: 123 tests, one uncaught Python 3.12 \`ValueError\` due to a 5,000-digit offset. This was a genuine implementation bug.
- Corrected locator integer syntax and impossible-span short-circuit in \`d21afd9f0b863cd9db0d15ec124647752be741bd\`. CI \`38911979028\`: **123/123 passed**.
- Added further same-length quote-substitution, multi-byte-prefix, and out-of-bounds regression tests in \`d2b8cbbebc3cdb126ab03ed912c198d75aa67319\`. Verify latest-HEAD run and evidence before merge or secondary review.

## Residual limitations / no-merge condition

- CR/CRLF sources are **unsupported**, not repaired; enabling them would require rigorously translating Factory's normalized char intervals back to raw byte spans with a new reviewed mapping contract.
- Git SHA-1 second-preimage/collision considerations, authentic publisher/edition source, source rights and trust of registry require separate P1.1 design; SHA-256 here covers only local bytes.
- The bridge presently verifies one locator per invocation and rereads the whole source; it is not efficient for production multi-quote batch verification. No permission is given to access holdout material.
- No claim of matching or verifying real OpenITI book bytes: tests create synthetic LF-only caches and read the real registry only in Phase A metadata tests.
- Secondary reviewer must examine latest exact HEAD and complete diff **after** independent primary maintainer audit and successful latest-HEAD CI; record an honest maintainer-only fallback if Codex is quota-limited. All PRs #49, #50 and #53 remain separate unmerged prerequisites.

This audit is primary maintainer inspection, not independent approval, and it does not certify religious inference.

## Additional resource-boundary discovery and fix

After the first 126-test green run on \`8d7052d0bae408193e6a6f4dc4d4518bd4d678f0\` (run \`38912403688\`), the primary maintainer identified that encoding an attacker-provided string **before** enforcing the 1 MiB quote cap can itself allocate large memory. Test-only commit \`1f98e2e2ed210897a2c7a37f840be3e83ecc0eb8\` supplied a synthetic oversized \`str\` subclass whose \`.encode()\` must never be called; CI \`38912609453\` reproduced the error (127 tests; one failure). Fix \`e2f53b44a82e0e43767ca1eebdceae88a252e419\` preflights Unicode codepoint count before UTF-8 encoding; actual UTF-8 byte size is still checked afterward. A new latest-HEAD test run is necessary after this audit is committed. No new corpus content or independent scholarly review was introduced.
