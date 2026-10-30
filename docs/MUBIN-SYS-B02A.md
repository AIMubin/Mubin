# MUBIN-SYS-B02-A — P0 Evidence Projection Bridge

**Architectural ownership:** ChatGPT / Integration Engineering. **Implementation status:** B02-A first increment.

## Zero duplicate Evidence Graph

The only source of P0 structural validity remains
[`core/inference/validator.py`](../core/inference/validator.py) operating
on the original private [P0 inference contract](../schemas/inference-foundation.schema.json).
`core/orchestration/evidence_projection.py` is a **derived read-only materialized
graph view**, not a competing truth store, validator, new inference semantics or
scholarly approval engine.

A full P0 bundle requires excerpt text, SHA256 digests and nonempty
sources/evidence/methodologies/claims/rules/inferences/proofs. A metadata-only
GitHub handoff cannot satisfy that contract on its own. DO NOT fabricate an
`inference`, `rule`, `proof` or source excerpt to make a candidate discovery
look P0-valid.

### Private vs public lanes

| Vault-only (operator) | GitHub-safe proposal |
|---|---|
| Original complete P0 bundle with excerpt/locators | Versioned `mubin-b02a-p0-projection/1.0` |
| `validate_bundle(full_bundle)` | `verify_redacted_projection(view)` |
| Ingest/independent source checksum checks | Opaque SHA256 handles, entity counts, link topology and commitments |
| Explicit engine receipt ref -> P0 evidence mapping | Hashed `MATCHED_SUBMITTED_RECEIPT_ONLY` links |
| Local replay vs immutable source corpus | Diagnostic counts and structural status **only** |

The exported `private_bundle_sha256` and `graph_sha256` are unkeyed
commitments, **not signatures**, custody proofs, source authenticity
determinations or proof of the existence of a private source. Anyone can
recompute a forged projection hash. A trusted operator can independently
replay the full P0 check and compare hashes in the private environment.
The `verify_private_projection(full_bundle, public_view)` helper performs that
trusted local replay and exact comparison. Even a successful in-process replay
does not independently establish source authenticity.

No source text, original work title, path, locator, quote, interpretation,
scholarly verdict, or raw entity ID is included in this projection.
Opaque graph structure may itself be sensitive. The operator decides whether
the graph topology is releasable; a metadata-only export is not automatically
safe for publication in an unrestricted repository.

### Failure semantics

- P0 invalid: `P0_REJECTED`, no graph or digest; error count and fixed code
  only. No raw validator error may cross the local boundary.
- P0 structurally valid: `P0_STRUCTURALLY_VALID`, **never**
  `scholarly_verified=true` or `external_source_authenticated=true`.
- P0 omitted or not yet available: **no P0 receipt at all**. It is not
  legal to invent P0 fixtures or claim a validation succeeded.
- An explicit engine-to-evidence binding must resolve in both a supplied
  runtime receipt's `evidence_refs` and the private P0 evidence collection.
  The bridge refuses mismatched, duplicate or missing links.
- The public verifier validates shape, topology and graph digest only; it
  cannot reconstruct or authenticate private content.

### B02-B interoperation

The local execution lead owns the five-file `research/b02b/` handoff
format and source-specific scans. Do not stall its work waiting on a new
central schema or the B02-A PR. The local lead may emit a **P0-compatible
private bundle** whenever enough actual source-grounded inference exists.
For a pure retrieval/no-evidence/Fiqh-gap finding, preserve its true
`UNDETERMINED` / `NO_MATCH` / `UNAVAILABLE` status in a separate
metadata receipt, rather than manufacturing P0 entities.

**Important B01 limit:** `detect_tafsir_mentions` calls the
H-Search mention detector, not the four-source witness search in
`run_hsearch`. Real-world source search receipts must come from the
actual local H-Search-01 pipeline. A source-unavailable state is not NO_MATCH.
The B01 Fiqh F0.1 scaffold assembles attributed references; it does not
perform actual fiqh deductions.

### Run

```bash
python -m pip install -r core/requirements-test.txt
python -m unittest discover -s evaluation/integration -v
```

The tests cover P0 integration, redaction, forged links, graph tampering,
invalid source witness, and absence of inferred public authority.
