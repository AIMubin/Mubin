# H3.9.2 Post-Consolidation Preparation

Freeze schema 26 begins **after** the authoritative schema-25 cumulative primary evidence has been frozen.

The source evidence is:

- cumulative workflow run: `37471731102`;
- cumulative main commit: `e1422b3262ee308084ce2212a2f2825fdc737032`;
- exact primary prefix: `0..209` / 210 tasks;
- promoted: 40;
- pending adjudication: 129;
- skipped: 41;
- replacement eligible: 41;
- cumulative ledger SHA-256: `36938de84bd9053433b9d890a9f25ce6c5613d9fa1e1b1996f28df69f6cc5f0d`;
- replacement eligibility SHA-256: `21275d808dd369a362975a45f92ee6889cecac88b293f1287d0b0660bb72baee`.

The permanent schema-25 evidence record remains
`artifacts/CUMULATIVE_PRIMARY_EVIDENCE_210.json`.

## Why a separate preparation stage exists

The schema-25 redacted summary intentionally does not publish task IDs or reserve-slot IDs. The exact eligible identities exist only inside the encrypted cumulative bundle.

Publishing a raw list of eligible slot IDs would unnecessarily disclose which deterministic Factory slots failed. Publishing ordinary unsalted hashes would not materially improve privacy because the Factory plan is deterministic and public enough for an observer to precompute candidate slot hashes.

Schema 26 therefore introduces a **secret-nonce commitment layer**.

The preparation stage converts:

- the 41 exact replacement-eligible reserve identities; and
- the 129 exact pending-adjudication identities

into opaque SHA-256 commitment leaves.

The nonces are deterministically derived with HMAC-SHA-256 from the protected campaign artifact secret and a domain-separated identity binding. The secret and nonces never appear in the public binding.

This yields two useful properties:

1. the repository can permanently freeze opaque authorization/adjudication sets without publishing task or slot IDs;
2. a later execution record can reveal only the nonce and identity needed for the specific case being acted on, allowing the validator to recompute that leaf and check membership in the frozen set.

## Protocol boundary

Schema 26 **does not**:

- enable reserve reconciliation;
- execute reserve tasks;
- resolve adjudications;
- promote a pending adjudication;
- change the Factory plan;
- add candidate capacity;
- change benchmark quotas, labels, source partitions, prompts, thresholds, or holdout policy.

Both execution flags remain false:

```json
{
  "reserve_reconciliation_enabled": false,
  "adjudication_execution_enabled": false
}
```

A later reviewed protocol revision is required before either private identity set may be consumed.

## Preparation command

The source-bearing cumulative bundle must first be decrypted in an ephemeral trusted workspace.

Then run:

```bash
python -m benchmark_campaign prepare-postconsolidation \
  --cumulative-dir /secure/ephemeral/cumulative \
  --control-evidence artifacts/CUMULATIVE_PRIMARY_EVIDENCE_210.json \
  --public-out-dir /tmp/h392-postconsolidation/public \
  --private-out-dir /tmp/h392-postconsolidation/private \
  --commitment-secret-env H392_CURATION_ARTIFACT_KEY
```

The command validates all of the following before producing output:

- the repository status points to the same completed 210-primary cumulative evidence;
- the cumulative target is closed;
- reserve reconciliation is still disabled;
- the materialized cumulative ledger hash exactly matches the frozen ledger hash;
- the materialized replacement-eligibility hash exactly matches the frozen eligibility hash;
- the cumulative adjudication file matches the encrypted cumulative manifest;
- the source cumulative manifest and eligibility artifact are schema 25;
- the current deterministic Factory plan has the same plan hash as the cumulative evidence;
- every eligible primary is a non-holdout primary in the frozen benchmark surface;
- every eligible primary is a terminal skipped ledger row;
- every linked reserve is the exact frozen reserve for that primary and has `reserve_attempt=1`;
- no pending adjudication is replacement eligible;
- the 41 reserve identities and 129 adjudication identities are disjoint;
- exact reason accounting agrees with the frozen cumulative summary.

Any mismatch fails closed.

## Public output

`POSTCONSOLIDATION_BINDING.json` contains only:

- frozen cumulative hashes;
- Factory-plan hash;
- protocol versions;
- counts;
- 41 opaque reserve commitment leaves;
- 129 opaque adjudication commitment leaves;
- the SHA-256 of each sorted commitment set;
- explicit redaction and disabled-execution flags.

It contains no task IDs, slot IDs, source text, gold payloads, or model identity.

`POSTCONSOLIDATION_SUMMARY.json` contains only counts, set hashes, the public-binding hash, protocol identifiers, and the same disabled-execution/redaction flags.

## Private output

The plaintext private output is temporary:

- `RESERVE_AUTHORIZATION_PRIVATE.json` maps the 41 eligible primary identities to their exact linked reserve slots, nonces, and commitment leaves.
- `ADJUDICATION_QUEUE_PRIVATE.jsonl` maps the 129 pending task identities to their cumulative reason, source run/artifact provenance, nonce, and commitment leaf.
- `PRIVATE_MANIFEST.json` binds both private maps to the public binding.

These private files contain identifiers but still do not contain source text, gold payloads, or model identity.

The workflow encrypts the entire private directory with AES-256-GCM and removes plaintext before upload.

## Workflow

Use:

`.github/workflows/h392-postconsolidation-prepare.yml`

The workflow is manual, main-only, and stale-dispatch resistant. It has no editable task/run inputs; it obtains the canonical cumulative run, artifact ID, artifact digest, and evidence path from repository-reviewed status.

It:

1. verifies freeze schema 26 and the ready/not-completed preparation state;
2. verifies the schema-25 cumulative control record;
3. downloads the exact frozen cumulative artifact without forwarding the GitHub token to the signed storage URL;
4. verifies the GitHub ZIP digest, redacted-summary digest, and encrypted cumulative-bundle digest;
5. safely decrypts/extracts the cumulative source-bearing bundle;
6. runs the schema-26 preparation command;
7. encrypts the private identity map;
8. deletes all cumulative and private plaintext;
9. proves the upload directory contains exactly two redacted JSON files, one encrypted private bundle, and its digest file;
10. reconfirms current `main` before publication.

The uploaded artifact is named:

`h392-postconsolidation-preparation`

## Next protocol revision

After a successful preparation artifact is independently verified and frozen into repository evidence, the next revision may define two independent consumers:

### Reserve activation

A reserve may be executed only if its later execution record reveals a nonce and reserve identity whose commitment leaf is a member of the frozen 41-leaf reserve set.

That revision must also modify Factory reconciliation and campaign validation so a reserve-derived record cannot qualify merely by carrying a reserve slot ID. It must carry and validate the frozen authorization commitment.

### Adjudication

A decision may act only on a task identity whose nonce/identity recomputes to a member of the frozen 129-leaf adjudication set.

The adjudication protocol must preserve the authority boundary in `CURATION.md`: AI may extract or structure explicit human-authored source statements, but unsupported AI judgment cannot become gold. Any case that cannot be resolved as source-attributed evidence must remain pending or pass through the required human/authority gate.

Adjudication rejection may create new replacement eligibility only through a later, separately hash-bound state transition. It must not silently reuse the original 41-slot authorization set.

## Security note

The HMAC-derived nonce construction is used only to hide deterministic Factory/task membership before selective execution disclosure. It is not a substitute for the AES-GCM confidentiality of the private map.

The public commitment leaves are not themselves authority. Their meaning comes from the reviewed schema-26 protocol and the frozen schema-25 cumulative ledger/eligibility hashes to which every leaf is bound.
