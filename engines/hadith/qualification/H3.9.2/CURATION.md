# H3.9.2 Curation Guide — R3

## Trust boundary

Curation is performed by a source-review custodian. The developer/tuning surface must never receive plaintext final-holdout gold. Pre-seal reviewed inputs can contain gold, but they should live outside the repository (for example `/custodian-private/...`). After `build-splits`, the repository staging file is sanitized and final-holdout gold exists only in the AES-256-GCM sealed store.

The external holdout key is a release secret. Do not commit it, copy it into artifacts, attach it to the package, or expose it to the model/tuning process.

## Human-reviewed input

The input to `curate-reviewed` is JSONL. Do not provide split, hashes, or derived `source_ids`; the tool derives them. Minimal single-source record:

```json
{
  "case_id": "stable-case-id",
  "family_id": "globally-canonical-semantic-family-id",
  "gold_status": "reference_pilot",
  "synthetic": false,
  "source_refs": [
    {
      "source_id": "openiti:0742Mizzi.TahdhibKamal",
      "locator": "exact OpenITI/CTS/page/entry locator",
      "excerpt": "exact verbatim source text"
    }
  ],
  "annotation": {
    "reviewers": ["reviewer:pseudonym"],
    "source_verified": true,
    "adjudicated": false,
    "adjudicator": null
  },
  "payload": {
    "input": {},
    "gold": {"label": "..."}
  }
}
```

For H3.8/H3.9, include every work used by the comparison as a separate `source_ref`. Do not hide a second source in `payload.input` without adding it to `source_refs`.

## Qualification levels

`reference_pilot` requires source verification and at least one reviewer. `expert_gold` requires two distinct reviewers plus an independent adjudicator. Synthetic records and automatically inferred labels are never qualification-eligible.

## Family IDs

`family_id` is semantic, not a phrase-template identifier. It must remain stable across records representing the same underlying question/family. Where H3.8 and H3.9 reuse the same report family, reuse the same canonical family ID so campaign-global leakage checks detect contamination.

## Curation quotas

Use `config/curation-quotas.json`. Each case is counted once against an operational `anchor_source_id`, while `source_ids` still enumerates every canonical source used. The anchor quota is a sampling-control mechanism only; it does not change the provenance contract.

The quota plan is frozen before case selection. Do not rebalance it after seeing model performance or final-holdout labels. If source feasibility makes a quota impossible, invalidate the campaign version and issue a new preregistered plan rather than silently editing the current one.

## Holdout sealing

Generate the key outside the repository:

```bash
python -m benchmark_campaign generate-holdout-key --out /secure/off-repo/mubin-m392.key
```

After all five reviewed pools reach their exact target counts:

```bash
python -m benchmark_campaign build-splits \
  --holdout-key-file /secure/off-repo/mubin-m392.key
```

For each holdout row the command removes `payload.gold`, writes `payload.gold_sealed=true`, encrypts the secret gold record, and sanitizes the staging copy. The encrypted secret is bound to `case_id`, input fingerprint, full source set, semantic family, and gold status.

Keep at least two securely controlled backups of the key. Losing it makes the frozen final holdout unevaluable; replacing it requires a new seal/freeze version.

## No automatic gold

Candidate discovery, regex mining, embedding similarity, Itqan links, LLM suggestions, or heuristic parsers may propose cases. They do not create qualification labels. A label enters the reviewed pool only through the declared human/source-grounded review contract.
