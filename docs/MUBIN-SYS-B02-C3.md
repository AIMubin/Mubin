# MUBIN-SYS-B02-C.3 — Cross-engine evidence transport

Internal engineering contract `mubin-cross-engine-chain-audit/1.0`.
This is a read-only verification of identifier transfer between
engine-result receipts, **not** a second P0 Evidence Graph.

`audit_cross_engine_chain(receipt, links)` accepts explicit pairs of
`from_node`, `from_ref`, `to_node`, `to_ref`, `relation`, and
`assessment_sha256`.

- `EXACT_REF_RELAY`: identical reference occurs in both engine results;
  status `OBSERVED_REFERENCE_RELAY_ONLY`.
- `CONTEXT_PROPOSAL`: two existent but semantically unverified endpoints.
- `SEMANTIC_PROPOSAL`: two endpoints and declared private review SHA256;
  the SHA is **not independently verified by this contract**.

The latter two remain `UNVERIFIED_RESEARCH_PROPOSAL` even with AI votes.
All report handles are hashed and source text is excluded. Every audit
is `TRANSPORT_ONLY_INCOMPLETE` with zero qualified semantic links,
no scholarly approval, no verified Hadith identity or Fiqh authority.

Use `verify_redacted_chain_audit(view)` for untrusted metadata
self-consistency and `verify_private_chain_replay(receipt, links, view)`
to recompute against operator-held input metadata. Neither validates
private source authenticity. Because existing `run_case` receipts
omit the original operations and `depends_on`, a matching reference
does not establish that the original execution graph contained a
declared dependency.

Regression tests use the published B02-C.2 six-node case and confirm
4 Usul-to-Fiqh reference relays (of 33 collected references); no
juristic inference is asserted.

Local AI retains responsibility for source-pinned H-Search,
Tafsir/Usul source context and semantic counterexamples. Preserve
`REJECTED_ALL_CANDIDATES_UNDER_FULL_BAR`, frozen H3.9.2 and
`VERSION.yaml`.

Run `python -m unittest discover -s evaluation/integration -v`.
