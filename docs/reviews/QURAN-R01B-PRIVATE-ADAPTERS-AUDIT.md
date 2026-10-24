# R0.1b maintainer security review checklist — not a scholarly approval

Derived from **merged** R0.1a HEAD `f87e43bb01baa34ac023759fd82304a6232bca8a`. This PR introduces no new ingestion or source files. Test checks are not evidence of access to actual operator-only private files.

## Before merge verify

- No public HTTP or UI entry point; module imports never open the vault, never download and never create SQLite files
- `verify_evidence` validates the R0.1a chain/HMAC/head, corpus DB digest and TafsirCenter pinned SHA on **every** metadata/text call; selected corpus DB path must match the anchored path
- Only five corpus IDs and six TafsirCenter source table identifiers; fixed SQL text columns; all verse coordinates parametrized and validated against canonical topology
- `mode=ro&immutable=1` and `query_only`, no side effects; documentation explains immutable snapshot assumption and file substitution risk between evidence read and SQLite open
- No text/footnotes in default metadata output; private text denied until externally signed source-specific, head-pinned, time-bounded local approval; signing is out-of-band and not implemented here
- Local permit authorizer must be an independent governance process; a signed local token **does not** prove publisher, rights or lawful use. Never claim the source-use metadata validator independently verifies legal attestations
- Cross-OS synthetic tests and R0.1a/ingest/sidecar regression all green on exact head; Codex independent review clean at the same head; retain false scholarly/rights/inference/fatwa flags

**Status:** awaiting exact-head CI and review. No permission or scholarship is conferred by this checklist.
