# Q0.1e-b primary engineering review — extracted direct reader

**Previous state:** The original #76 53-commit stack combines multiple capabilities and a direct reader that predates Q0.1f. This PR extracts only the Q0.1e-b direct reader and its minimum required Q0.1c/Q0.1f integration onto current main. The prior #76 review record is historical and is not approval of this extracted HEAD.

## Mandatory review gates

- **Fixed source:** the Q0.1e entrypoint calls merged Q0.1e-a's pinned HTTPS fetcher; original bytes are held in memory only. A changed byte SHA, invalid UTF-8, missing copyright notice, invalid row count/coordinate causes a fail-closed error **before** opening 127.0.0.1.
- **Startup reconstruction:** Q0.1c's previous generic manifest reparsing cannot authenticate the new source kind. The dedicated branch uses `load_official_candidate(raw)` with a fixed digest and topology, then compares both verse tuples and exact manifest against the passed index. Caller-created forged indices cannot self-authorize.
- **Same-origin privacy:** the existing loopback server retains 127.0.0.1-only bind, strict Host and Origin guards, GET-only endpoints, CSP, Cache-Control no-store and no-referrer. No source bytes in logs, artifacts or Git.
- **Tafsir boundaries:** Q0.1f accepts the direct-source kind only after the server has reconstructed that candidate from pinned bytes. `catalog_for_ref` remains metadata-only with six unreviewed titles and all privilege flags false. Synthetic fixtures cannot receive tafsir catalog endpoint.
- **Display:** external navigation remains user-triggered, fixed host, no-referrer and DOM textContent only; independently observed domain bytes never become authenticated or a license to publish scripture or tafsir.
- **Testing:** full 6,236-row synthetic test, forged manifest/candidate, wrong bytes, manual Host restrictions, JSON status and bibliography. Both Windows and Ubuntu must pass. Full core regression on Ubuntu, and the external real-domain advisory must be separately checked.
- **Approval:** maintainer-first exact-head code review and independent Codex review must be completed before merge; no shortcuts from earlier #76 or PR #92 review. Publication/scholarly authorization remains separate.

**Status:** awaiting exact-head CI and review. This document is a review checklist, not a signed-off result.
