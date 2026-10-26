# E2E-01.4b.4 — Frozen-local-excerpt preflight for the two-model trial

**Status: engineering protection, not a completed dual-LLM scientific experiment.**

## Why this step exists

E2E-01.4b.3 verifies the SHA-256 of the text supplied **inside** an
operator packet. That protects local self-consistency but permits the
operator to substitute another self-hashed excerpt without matching the
published digest receipt. A three-role/three-family packet is not, by
itself, a frozen scientific input. Before sending any source bytes to
a local model, the launcher now compares the exact canonical packet
SHA-256 and every witness's `id`, `role`, `url`, `family` and
`local_excerpt_sha256` with the tracked
`evaluation/evidence/amr_2_43_local_excerpt_digests_v01.json`.

This check accepts **only AMR-01-P, Quran 2:43** and the specified
three frozen short excerpts, on the production CLI. Altered excerpts
with freshly recomputed self-hashes, reordered witnesses, edited
locators or fake source families fail closed *before* either model
is contacted. The operator CLI does not accept an alternate manifest
path or a `--skip-pin` bypass.

The tracked digest manifest itself is **not a signed upstream publisher
receipt**. SHA matches do not prove Quran edition custody, primary
source authenticity, textual entailment, lawful redistribution or
independence of AI model weights. The source snapshot's scientific
gold label remains `null`.

## Offline preflight: no servers necessary

Store permitted short excerpts in a private local packet (not in Git).

```sh
python -m engines.e2e.local_model_trial \
  --case AMR-01-P \
  --packet /private/operator/2-43-witness.json \
  --preflight-only
```

Expected successful status is
`LOCAL_FROZEN_EXCERPT_BYTE_PIN_MATCH`; the JSON result contains
the packet hash and explicit `false` authority states, **no source
text, prompts, model outputs or calls**. It is not a science verdict.
A mismatch returns nonzero exit and a limited refusal code.

After an offline preflight succeeds, the existing local two-model CLI
can be invoked with the two explicitly different loopback sockets,
model IDs and legally permitted operator packet. Each evaluator sees
the same immutable packet, never the other's answer.

The new runtime field
`frozen_repository_excerpt_manifest_matched_before_dispatch=true`
proves only the exact match to **this repository's** metadata manifest,
not the authenticity of its publisher/source bytes.

## Reproducible engineering tests

```sh
python -m unittest core.tests.test_e2e_local_model_trial -v
```

Fixture packets and fabricated model HTTP responses in CI are explicitly
**synthetic** and the frozen manifest loader is swapped only inside
the test process. Tests cover exact pin, tampered-and-rehashed text,
relabelled family, altered canonical packet SHA, manifest metadata
leak/authority promotion, isolation and existing localhost refusal.

## Pending real scientific step

1. Reconstruct locally the three **exact** SHA-pinned snippets from
   permitted source data; do not silently normalize diacritics or
   characters to force a match.
2. Record local preflight receipt and git commit in a private experiment
   ledger. A mismatch is an investigation, not grounds to rewrite the
   frozen manifest based on preference.
3. Execute two genuinely separate local models and retain
   metadata-only reports, while separately assessing model weight and
   forwarding/logging policies.
4. Test whether citations truly support the narrow proposed relation,
   search for counterexamples and qarā'in, and retain
   `UNDETERMINED` where the evidence does not justify a conclusion.

No mandatory human scholarly review for this AI-only research step.
This work does not authorize Quran/Tafsir text publication, hadith
qualification, certified juristic inference, public fatwas, or a Mubin
system version bump. Project version stays `0.1.0-alpha`.
