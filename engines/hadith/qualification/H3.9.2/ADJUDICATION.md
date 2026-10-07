# H3.9.2 Schema-30 Human/Authority Adjudication Packet

Schema 30 begins after the canonical schema-29 reserve:02 consolidation is frozen.

The authoritative non-holdout state is:

```text
50 validated promoted records
158 pending adjudications
2 exhausted slots
= 210 required slots
```

The 158 pending cases are provenance-distinct:

- **129 primary adjudications** from the canonical schema-25 cumulative primary evidence;
- **24 reserve:01 adjudications** from the canonical schema-26 reserve consolidation;
- **5 reserve:02 adjudications** from the canonical schema-29 reserve2 consolidation.

Schema 30 prepares the exact review packet for those 158 cases. It does **not** decide them.

## Authority boundary

Every case requires a human or recognized authority decision consistent with `CURATION.md`.

AI may:

- reconstruct the exact canonical evidence packet;
- verify source pins, locators, task identity, response hashes, and provenance;
- organize Curator and Verifier evidence;
- identify the deterministic reason the case entered adjudication;
- help a reviewer compare the evidence.

AI may not:

- self-authorize `accepted`;
- convert model agreement into human review;
- silently reject a case;
- treat `deferred` as rejected;
- activate replacement capacity from a rejection;
- create `reserve:03`.

The allowed review states are:

```text
accepted
rejected
deferred
```

An accepted case must later be source-verified and resealed as a reviewed record. A rejected case produces no reviewed record and does not itself authorize another reserve. A deferred case remains pending and nonreplaceable.

## Canonical evidence sources

The packet is derived only from the three canonical encrypted consolidation artifacts already frozen in repository status:

1. schema-25 cumulative primary consolidation;
2. schema-26 reserve:01 consolidation;
3. schema-29 reserve:02 consolidation.

The workflow first verifies each canonical workflow run, exact artifact ID, artifact ZIP SHA-256, redacted summary SHA-256, encrypted-bundle SHA-256, and canonical ledger SHA-256. It then decrypts those consolidated bundles only in the ephemeral runner.

The exact originating curation artifacts are **not configured by hand**. They are derived from the canonical adjudication rows and ledger bindings:

```text
source_run_id
source_run_attempt
source_sha
source_artifact_id
source_artifact_sha256
source_encrypted_bundle_sha256
```

Only those referenced artifacts are downloaded.

## Packet preparation workflow

Use:

`.github/workflows/h392-adjudication-packet.yml`

The workflow is manual, main-only, stale-dispatch resistant, and has no editable run IDs, artifact IDs, task IDs, counts, layer selectors, or decision inputs.

It must:

1. verify schema 30 and the exact 158-case repository target;
2. verify that human/authority review is required and AI self-authorization is disabled;
3. reacquire and verify the pinned non-holdout source cache;
4. fetch and decrypt the exact three canonical consolidation artifacts;
5. derive the exact 158 adjudication task IDs and their originating artifact provenance from the canonical ledgers;
6. fetch only those originating curation artifacts and verify their ZIP and encrypted-bundle SHA-256 values;
7. re-run the appropriate primary, reserve:01, or reserve:02 evidence validator against every source artifact;
8. verify that every packet task is still deterministically classified as adjudication with the same canonical reason and task fingerprint;
9. build one source-bearing packet row per canonical pending case;
10. emit a blank human decision template with no preselected decision;
11. encrypt the complete packet and decision template;
12. delete plaintext canonical bundles, source artifacts, source cache, and packet files before publication;
13. upload only a redacted summary, encrypted packet bundle, and encrypted-bundle digest declaration.

## Source-bearing packet

The encrypted bundle contains:

- `ADJUDICATION_SOURCE_TARGET.json`;
- `ADJUDICATION_PACKET.jsonl`;
- `ADJUDICATION_DECISION_TEMPLATE.jsonl`;
- `ADJUDICATION_PACKET_MANIFEST.json`.

Each packet row preserves:

- canonical layer: `primary`, `reserve01`, or `reserve02`;
- task ID, slot ID, task fingerprint, benchmark, and anchor source;
- canonical and reconciliation reasons;
- exact source run/artifact provenance;
- the original Factory task;
- Curator response;
- blinded Verifier task when one existed;
- Verifier response when one existed;
- canonical adjudication record;
- the human/authority decision policy.

Because these rows can contain source excerpts, gold payloads, and model identity, the packet is source-bearing and must remain encrypted or custodian-private.

## Decision template

The generated template contains one row per packet ID with empty fields for:

- `decision`;
- `reviewer`;
- `reviewer_role`;
- `reviewed_at`;
- `source_verified`;
- `accepted_candidate`;
- `rationale`.

Schema 30 does not ingest or apply those decisions. A later reviewed protocol must validate completed human decisions, source-verify accepted candidates, reseal accepted records, preserve rejected/deferred provenance, recompute the exact unresolved/shortfall state, and only then determine whether further candidate capacity is required.

## Capacity sequencing

The current minimum shortfall is already two slots, but adjudication can increase the final deficit if cases are rejected or remain deferred.

Therefore schema 30 deliberately **does not** create `reserve:03` before the adjudication result is known. After decisions are frozen, the campaign can calculate one exact evidence-bound remaining capacity requirement rather than repeatedly extending capacity after every observed failure.

Current gates remain:

```ini
validated_promoted_record_count   = 50
pending_adjudication_count        = 158
remaining_exhausted_slots         = 2
benchmark_population_complete     = false
benchmark_gate_passed             = false
h4_qualification_allowed          = false
automatic_reserve3_authorized     = false
```
