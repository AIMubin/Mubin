# P1.1 Phase-A Maintainer Audit

**Branch:** `feat/p11-hadith-pin-bridge`; stacked against PR #49 at `f5397ef1aa28af62e5e72eb4fc4e6f6f2e6e0dce`.

## Primary review and threats

- **Source authority:** matching the SHA-1 Git blob hash in an operator-supplied registry cannot authenticate provenance, a publisher, edition, scholarly meaning or rights; explicit report states keep these unverified.
- **Existing H3.9.2 cache:** deterministic filename parity, sorted deterministic outputs, metadata passthrough, and duplicate-ID/filename-collision rejection. Never rewrite qualification sources or protocol.
- **Raw byte identity:** Git blob header includes exact byte length and a NUL; calculate Git SHA-1 and independent raw SHA-256 in a streaming 1 MiB loop.
- **Filesystem:** reject symlinked cache roots and individual symlinked source files, open through a no-follow descriptor where supported, reject nonregular files; fstat before/after to detect changes during read. A malicious administrator able to alter both frozen registry and cache is outside the trust assertion.
- **Resource caps:** registry bounds, input recursion/Unicode rejection, source count bound, per-source and global byte budget. Never load corpus-sized source bodies into one JSON object.
- **Fail closed:** missing cached file, digest mismatch, source ID/path malformed, duplicate source, cache filename collision and oversize must set `valid=false`; all source reports keep `authority` explicitly unauthenticated.
- **Scope:** no external network; no licensing attestation; no content analysis; no operational inference or human adjudication claims.

## Test-first evidence

- **Deliberately failing test-only HEAD:** `5b652d6a6b774dba52794d0e61defcbb9ff2ffc2`; workflow `38902401939`, 90 tests with one ImportError (`core.source_authority` absent), demonstrating the new test suite is exercised by CI.
- **First implementation HEAD:** `4fadb833777cc60ceadab4a5ef65da4ab13ff915`; workflow `38902681041`, 102/102 passed. All 13 new source-bridge test methods passed, including the real frozen-registry **metadata-only** fixture, missing/tampered cached data, collision, symlink, byte limit, CLI recursion.
- The 19 frozen registry entries are read for metadata validation only; 18 are marked qualification eligible in their **existing declared registry**. No real corpus cache was available to the CI suite, thus no real source content was verified.

## Residual limitations and gate

- Git SHA-1 matching is **registry consistency**, not independent provider authenticity. Chosen-prefix risks of SHA-1, lack of signed authoritative edition records, and unknown rights explicitly remain out of scope.
- This implementation does not yet reconcile H3.9.2 character ranges with P1 UTF-8 byte ranges. It cannot claim correct quotation spans.
- Snapshot custody and multi-user hostile-filesystem ingestion require additional security review; path checks on POSIX use `O_NOFOLLOW` and fstat but do not attest to external origin.
- Final code, documentation and tests must run successfully on the exact latest HEAD. Secondary Codex review is requested only **after** maintainer review and clean CI; quota/unavailability fallback is a non-independent maintainer-only second pass and must be labeled as such.
- PR #49 prerequisite, PR #50 input hardening, and branch protection remain open governance dependencies.
