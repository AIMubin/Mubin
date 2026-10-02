# Final Holdout Seal

## Threat model

The final benchmark must remain useful as an unseen qualification set even while developers tune on development/validation data. A split flag alone is insufficient if the gold label remains readable in the repository.

R3 therefore separates **public holdout inputs** from **secret holdout gold**.

## Format

Each benchmark has a frozen wrapper at:

```text
sealed-holdout/<benchmark-id>.gold.aesgcm.json
```

The wrapper contains only algorithm/version metadata, a random nonce, ciphertext, a non-secret key identifier, count, and a hash binding the ciphertext to the public holdout index. Gold values are encrypted with AES-256-GCM.

The encryption key is a random 256-bit external secret encoded as URL-safe base64. It is never stored in the repository, manifests, freeze, logs, or delivery archive.

## Associated data and binding

AES-GCM associated data binds campaign ID and benchmark ID. Inside the encrypted payload each gold value is tied to a hash of:

- `case_id`;
- normalized input fingerprint;
- complete sorted `source_ids`;
- semantic `family_id`; and
- `gold_status`.

Changing any of those public properties makes decryption/evaluation fail the binding check even if the ciphertext itself is unchanged.

## Operational rule

The custodian generates and retains the key. Developers receive the frozen public benchmark and, after freeze, the development/validation tuning pack. The final candidate is locked before the custodian/evaluator supplies the key to the scoring process.

The first successful final evaluation creates `HOLDOUT_ACCESSED.json`. Only byte-identical prediction replay is allowed afterward under that freeze.
