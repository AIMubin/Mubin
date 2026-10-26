# E2E-01.4b.3 — Real local-model dispatch (operator-run, AI-only)

**Status: executable runner; independent model experiment NOT executed on a real local model in GitHub CI.** No human-review gate, no new servers built into Mubin, no authority promotion.

## Purpose

E2E-01.4b.1 shipped 24 source-referenced research cases. E2E-01.4b.2 shipped a hash-checked local witness + evaluator/critic report contract. This increment makes **two actual model API calls possible**, rather than fabricating the evaluator and critic outputs in the same Python process or accepting only handwritten reports.

The runner `engines/e2e/local_model_trial.py` takes the operator's legally permitted, local UTF-8 witness packet as input. It sends identical witness data to **two separately configured, already running OpenAI-compatible chat-completion servers**. One model is instructed to assess supporting evidence; the other independently attempts falsification and contextual/qarīnah objections. Each session sees the same packet, **not the other model's answer**.

**Only literal** `http://127.0.0.1:<port>/v1/chat/completions` or `http://[::1]:<port>/v1/chat/completions` **are allowed.** The two endpoints and model IDs must differ. No DNS resolution, redirects, custom URL path or direct remote TLS/provider endpoints. **The localhost listener may be a proxy that forwards elsewhere; the CLI cannot attest otherwise.** The HTTP transport uses only the Python standard library, sends POST JSON, sets `temperature=0` and `stream=false`, and has a 30-second socket timeout and bounded request/response lengths.

The model endpoint must produce a single Chat Completions-style object with `model` matching the configured model ID, a bounded `id`, and `choices[0].message.content` containing **only** JSON:

```json
{"decision":"UNDETERMINED","evidence_ids":["v","t","u"]}
```

`SUPPORTED`, `REFUTED` and `UNDETERMINED` remain **model hypotheses**, not certified scientific facts, rights decisions, or fatwas. Unknown `evidence_ids`, replayed/duplicate response IDs, missing/forged model identity and malformed/extra fields fail closed.

> **E2E-01.4b.4 revision:** The production launcher now requires the
> operator packet to match the exact frozen receipt in
> `evaluation/evidence/amr_2_43_local_excerpt_digests_v01.json`
> **before dispatch**. First run
> `python -m engines.e2e.local_model_trial --case AMR-01-P --packet /private/operator/2-43-witness.json --preflight-only`
> without any model servers. An arbitrary new self-hashed local excerpt
> no longer qualifies for model dispatch. See
> [E2E-01.4b.4](E2E-014B4-PINNED-PREFLIGHT.md). These checks still
> cannot authenticate original publisher bytes.
>
## Run locally with two independently operated models

Start **two separate already installed model servers**, for example on ports 8181 and 8282 with explicitly different model weights and appropriate ownership/permission controls. The exact invocation depends on your local inference stack; **no model is installed or started by this repository**.

Provide a local `AMR-01-P` witness packet as described in [E2E-01.4b.2](E2E-014B2-WITNESS-TRIAL.md). The three source excerpts are limited to the narrow verse, tafsir and Usul propositions you have a right to process, never a full protected database. Compute `sha256` over the exact UTF-8 `text` of each excerpt. Example run:

```sh
python -m engines.e2e.local_model_trial \
  --case AMR-01-P \
  --packet /local/private/2-43-witness.json \
  --evaluator-url http://127.0.0.1:8181/v1/chat/completions \
  --evaluator-model <model-A-id> \
  --critic-url http://127.0.0.1:8282/v1/chat/completions \
  --critic-model <model-B-id>
```

The response is a **single metadata-only JSON object**. Its runtime metadata guarantees only an immediate loopback socket destination, not that a model server or local proxy never forwarded text to another machine. It records that two valid local HTTP responses were received, their distinct requested model IDs and response IDs, source URLs, packet hash and source-local UTF-8 hashes. It **does not record full witness text, prompts, HTTP tokens or free-text agent responses**. Save the JSON along with the git SHA and casebook SHA for reproducibility; do not put sensitive witness packets, source database material or signing keys in the repo.

## First real-source excerpt digest record

`evaluation/evidence/amr_2_43_local_excerpt_digests_v01.json`
stores only citations, family labels and **SHA256 of three short local
UTF-8 excerpts**, one each from the public Quran.com 2:43 reading,
al-Qurtubi's explanation of the verse on King Saud University's Quran
site, and the digital `الورقات` under `الأمر`. The exact canonical
JSON packet hash is
`bc2f326e119052b415ca78077d2d21d2ee924b082e2e22bfdbc50f19183c15bc`.

The snippet bytes were manually assembled from publicly **rendered**
online source readings during AI source research, not obtained as
authenticated original publisher bytes. They may be checked locally
against the three canonical URLs but they do **not** prove a protected
Quran-vault match, scholarly edition attribution, permissions, or a
valid fatwa. No source body is checked into Git. The local sample
packet remains outside the repository; all six authority flags in the
manifest are false. The manifest is tested for structure, no leaked
`text` field, accurate number of roles and explicit absence of
independent model results.

**Real AI execution has NOT taken place for this sample.** The runner
and local sample packet make the next actual two-server experiment
reproducible without a mandatory human reviewer, but the outcome
remains `UNDETERMINED` until those model calls and their evidence
checks occur.

## Required scientific limitations

1. Local SHA recomputation verifies packet *self-consistency*, not that the excerpt bytes actually match the upstream web source, a canonical Tanzil/KFGQPC edition, a private vault entry or publisher custody. Upstream source identity is still `UNVERIFIED`.
2. Different localhost ports, declared model IDs and response IDs prove only **API-level operational separation**. A proxy can serve the same weights on both endpoints; distinct training data, providers, weights or model implementation are **not independently attested**.
3. The literal `أَقِيمُوا` substring check is orthography-dependent. A failed exact-byte check is `UNDETERMINED`/refusal, never a claim that the Arabic morphological form is absent.
4. Citation-ID validation proves only that the model cited an ID in the supplied packet, **not** that the citation truly supports its argument. Independent source interpretation and qarinah analysis remain an open scientific task.
5. A narrow 2:43 verse excerpt, Qurtubi's statement about the imperative, and al-Waraqat's default-rule excerpt are a stronger source-grounded candidate than mere verse co-location. But they do **not** settle all other command meanings, contextual qarinah or downstream legal implications.
6. A fabricated or rejected packet must never lead to any `SUPPORTED` published verdict. Even matching model opinions yield `AI_AGREEMENT_UNCERTIFIED`; disagreements yield `AI_DISAGREEMENT`; insufficient source types / lexical match cause `LOCAL_EVIDENCE_INSUFFICIENT` **before any HTTP call**.
7. Model endpoints may store or **forward prompt content** outside Mubin's control even when listening on loopback. The report therefore sets `immediate_network_destination_loopback_only=true` but `local_server_forwarding_independently_excluded=false`. Run only locally administered endpoints with independently checked forwarding/log policies, isolate machines and logs, and obtain appropriate rights before processing third-party source text.

## Test evidence versus real scientific run

```sh
python -m unittest core.tests.test_e2e_local_model_trial -v
```

CI uses a **mock local Chat Completions transport** and synthetic, explicitly invented Arabic fixture text, never canonical Quran/Tafsir or an external model invocation. It exercises real request formatting and response parsing with no network access. An actual two-model test requires a local operator runtime with two independently served models. Do not label passing CI `real two-model scientific accuracy`.

**Acceptance beyond this increment**: use real, permitted, pinned excerpt bytes; operate two distinguishable local models; retain metadata-only results, check contradictory source interpretations, measure model disagreement and refusal across cases, and report coverage with uncertainty. No mandatory human review. No additional rights, `scholarly_verified`, `source_authenticated`, publication, juristic inference, P1 or fatwa authority is granted. Mubin global version stays `0.1.0-alpha`.
