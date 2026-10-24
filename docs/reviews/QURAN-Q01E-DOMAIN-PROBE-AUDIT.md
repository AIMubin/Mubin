# Q0.1e-a transport probe extraction — primary audit

Historical PR #76 combined an HTTPS fetcher, pinned direct reader, Chrome tests, Tafsir registry, private sidecar and corpus ingestion. This new branch deliberately extracts **only** a domain transport attempt and comparison. It relies on already merged Q0.1b manifest verification and Q0.1d byte/verse comparator; it does not bind a public source edition or expose a new server.

## Review invariants

- The only external probe URL is a literal `https://tanzil.net/pub/download/index.php`, the query is a fixed preset; no host injection/URL input/redirect following.
- Limit upstream response to 4 MiB, require status 200 and exact URL, and guard against HTML/binary/CRLF/BOM in the comparison path.
- Keep the pinned mirror input bounded and no-follow/regular-file protected using Q0.1b reader. No source text output; only SHA-256 and bounded differing verse coordinates.
- Do not permit a mocked comparator to launder nonhex digests, unbounded or non-coordinate differences, or reviewer/source/rights flags into the report.
- The transport-observed bit is not set by `run_probe` with an arbitrary injected fetcher. Even a successful fixed-host request is **not** publisher identity/permission attestation.
- All errors are classified without echoing the raw HTTP body, source text, secrets, or exception details. Network failures are reported as advisory non-success rather than green source evidence.
- No modifications to Q0.1c web reader, Q0.1f Tafsir metadata, Q0.3, Usul/Fiqh, Hadith holdouts, or versioning.

**Engineering status:** extracted-head CI and independent code review are required. This audit records design expectations, not a performed code review or downstream scholarly accreditation.
