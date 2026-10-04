# H3.9.2 Curator/Verifier Pilot Runbook

This runbook covers the **first real non-holdout AI curation pilot** for the H3.9.2 benchmark campaign. It does not authorize holdout access, does not change qualification policy, and does not convert model agreement into scholarly authority.

## Objective

Prove that the production execution path can turn frozen non-holdout Factory tasks into evidence-bound Curator and independent Verifier outputs without:

- exposing the final-holdout partition;
- fabricating source evidence;
- losing model/adapter provenance;
- leaking plaintext source-bearing artifacts;
- bypassing Factory reconciliation or adjudication.

The first run should be deliberately small. Do **not** start by processing all 896 non-holdout tasks.

## Required repository configuration

The manual workflow is:

`.github/workflows/h392-curation-pilot.yml`

Configure all runtime identity and endpoint data as GitHub **Secrets** so no service or model identity appears in repository files or workflow-dispatch metadata:

- `H392_CURATOR_ENDPOINT`
- `H392_VERIFIER_ENDPOINT`
- `H392_CURATOR_MODEL_FAMILY`
- `H392_CURATOR_MODEL_REF`
- `H392_VERIFIER_MODEL_FAMILY`
- `H392_VERIFIER_MODEL_REF`
- `H392_CURATOR_API_KEY`
- `H392_VERIFIER_API_KEY`
- `H392_CURATION_ARTIFACT_KEY`

The artifact passphrase must contain at least 20 characters. Do not place API keys, bearer tokens, passwords, request headers, or the artifact passphrase in committed JSON/YAML configuration.

The GitHub connector used during development cannot read or create repository Secrets, so secret presence must be configured and confirmed through repository administration before the first dispatch. Do not retain endpoint values in repository Variables once the protected Secret-based workflow is in use.

## Model independence

Curator AI-A and Verifier AI-B must have different normalized `model_family` values. Prefer genuinely different model families, and preferably different providers or independently operated endpoints, to reduce correlated failure.

The Verifier does not receive the Curator's proposed gold or supporting citations. It receives the answer-free candidate input plus independently retrieved evidence.

Do not use Mubin outputs to create benchmark gold.

## First pilot parameters

Start with:

- `task_offset = 0`
- `task_limit = 8`

The pilot intentionally exposes no completion-budget or reasoning-effort controls. The reference adapter uses its provider-native defaults: it sends no `max_tokens`/`max_completion_tokens` field and no `reasoning_effort` field. Each task is sent as one independent model request with a 600-second HTTP timeout.

Endpoint and model identity remain loaded from protected Secrets and are not workflow inputs. The workflow validates internally that the two protected model-family identifiers differ before either model is invoked.

## Comprehensive readiness gate

A manual dispatch is now a **single gated operation**. Do not run a separate sequence of speculative pilot reruns to discover basic protocol or transport defects. The workflow also refuses non-`main` or stale reruns whose checked-out SHA is no longer the current `main`, preventing validation of superseded protocol code.

Before the real non-holdout chunk is touched, the same workflow automatically runs:

1. the complete compile + unit/integration suite with **no provider secrets in scope**;
2. live Curator canaries using the production adapter, streaming transport, selected auth/JSON mode, twelve bounded synthetic evidence sources, and both classification and multilabel contracts;
3. live Verifier canaries in parallel using the same production transport surface and both classification and multilabel contracts.

The four live role-by-task-type canaries use synthetic readiness evidence only. They do not read holdout data, do not become benchmark records, and do not assert scholarly authority. Their only purpose is to prove that the current code, contracts, endpoint capabilities, streaming parser, JSON handling, and model response discipline can complete a simple evidence-bound request before expensive real curation begins.

The readiness report contains only redacted status, task type, duration, and bounded diagnostic codes. It contains no endpoint, model identity, API key, source-bearing benchmark text, or model reasoning. A `no_candidate` canary is a readiness failure because the synthetic evidence is intentionally sufficient and the gate must exercise the candidate path.

Only when `ready=true` does the workflow continue automatically into pinned source acquisition, the frozen 896-task reconstruction, the selected real chunk, independent verification, reconciliation, encryption, and artifact upload. Thus one workflow dispatch covers readiness **and** the real pilot end to end.

## What the workflow does

For every dispatch, the runner:

1. checks out Mubin and validates required protected runtime configuration;
2. runs the complete offline compile/unit/integration suite without provider secrets;
3. runs the four live role-by-task-type readiness canaries;
4. acquires only the pinned `non_holdout` source partition after readiness passes;
5. re-verifies every source against its Git blob SHA;
6. rebuilds the source index;
7. rebuilds the frozen 1,280-slot Factory plan;
8. regenerates the 896 non-holdout Curator tasks;
9. selects the requested deterministic task chunk;
10. runs Curator AI-A as one task per request;
11. records malformed/model-contract outputs as task-local rejections instead of aborting the remaining chunk;
12. prepares structurally blind Verifier tasks only from valid Curator candidates;
13. runs Verifier AI-B with the same one-task collection policy;
14. routes valid responses through the real Factory reconciliation path;
15. records promoted/adjudication/skipped outcomes in the curation ledger;
16. emits the redacted readiness, attempted/completed/rejected, and reconciliation summary;
17. encrypts all source-bearing run material with authenticated AES-256-GCM;
18. uploads only the encrypted source-bearing bundle plus redacted metadata.

The workflow never requests the holdout partition.

## Expected artifact

The workflow artifact contains redacted reports plus:

`h392-curation-source-bearing.tar.gz.aesgcm`

The encrypted bundle contains the task chunk, execution configs, Curator/Verifier responses, manifests, reconciliation outputs, reviewed records, adjudication queue, and curation ledger.

The artifact directory must not contain plaintext Curator tasks, Verifier tasks, model responses, source segments, or source text payloads.

## Decrypting the protected bundle

Run from:

`engines/hadith/qualification/H3.9.2`

Set the same external passphrase used by the workflow:

```bash
export ARTIFACT_KEY='...'
python -m benchmark_campaign.artifact_crypto decrypt \
  --input h392-curation-source-bearing.tar.gz.aesgcm \
  --output h392-curation-source-bearing.tar.gz \
  --passphrase-env ARTIFACT_KEY
mkdir h392-curation-source-bearing
tar -xzf h392-curation-source-bearing.tar.gz -C h392-curation-source-bearing
```

Treat the decrypted directory as sensitive benchmark evidence. Do not commit it.

## Pilot acceptance criteria

An 8-task pilot is operationally acceptable only when all of the following are true:

- pinned source acquisition and re-verification succeed;
- the source index rebuild succeeds;
- exactly 8 requested tasks are selected and attempted;
- no holdout source enters task scope;
- Curator responses are execution-bound to model/config/adapter hashes;
- task-local model/contract failures are recorded as bounded rejection categories and do not masquerade as valid responses;
- Verifier execution is bound to the Curator manifest but remains answer-blind;
- every cited support string in an accepted response is verbatim in retrieved evidence;
- reconciliation completes without integrity exceptions;
- every selected task is accounted for by an accepted response or a recorded task-local rejection, and reconciliation classifies all accepted Curator paths as promoted, adjudication-required, or skipped;
- no source-bearing plaintext file appears in the uploaded artifact;
- AES-GCM decryption succeeds with the correct passphrase and fails if the ciphertext is tampered;
- no qualification or H4 gate changes as a side effect of the pilot.

A high adjudication rate is not itself a pilot failure. It is evidence about task difficulty, retrieval quality, or model suitability. Likewise, multiple literal support spans from one canonical source are valid evidence; they must not be rejected merely because they share a source ID, provided each span is verbatim and the final record retains one canonical source reference per source.

Model-output and contract failures such as `model_output_invalid_json`, `model_output_reasoning_only`, `contract_gold_labels_missing`, `contract_gold_label_outside_contract`, `contract_support_not_verbatim`, or `contract_verbatim_not_supported` are task-local collection outcomes. Verifier-preparation blindness violations are also task-local: the unsafe candidate input is not sent to Verifier AI-B, the preparation report increments `rejected_candidates`, and reconciliation routes that Curator candidate to adjudication because no verifier response exists. The pilot continues with other tasks. Do not copy private reasoning into the answer, repair malformed JSON, coerce labels, or loosen source-verbatim/evidence/provenance constraints merely to improve the pass rate.

Infrastructure and execution-integrity failures remain fatal: authentication errors, persistent connection/provider failures, endpoint response-shape failures, source/index binding failures, partition violations, adapter protocol failures, and executor failures stop the workflow. The manual pilot uses streamed chat-completions transport so long-running responses can emit SSE chunks during generation; the adapter retains only final answer text and a presence marker for reasoning, never the reasoning text itself. Stream accounting limits retained final answer/event size, not the cumulative bytes of discarded reasoning chunks, so a reasoning-heavy compatible endpoint is not rejected merely for streaming more internal reasoning data. The non-holdout pilot retries one content-safe `connection_failed` transport failure once, because a dropped HTTP body or socket reset is not evidence about benchmark quality. No model-output/contract failure is retried. A request exceeding the adapter's 600-second timeout remains fatal and is not retried. Final holdout execution remains strictly one-shot with `max_attempts=1`.

## Expansion sequence

Only after reviewing the 8-task pilot:

1. run a 32-task chunk;
2. review retrieval quality, no-candidate rate, agreement rate, adjudication reasons, and source coverage;
3. run one or more 64-task chunks;
4. scale across the remaining non-holdout tasks only after the execution path is stable.

Never tune prompts or model behavior against the sealed final holdout.

If the Curator/Verifier process exposes a systematic defect, fix the protocol or adapter, record the change, rerun non-holdout work, and treat the changed protocol as a new freeze surface when applicable.

## Human and scholarly authority boundary

AI extraction from human-authored hadith and rijal sources is part of the curation workflow, but the **authority comes from the cited human-authored evidence**, not from the model.

- literal source-derived cases may qualify through deterministic verification and independent agreement under the Factory policy;
- interpretive or uncertain cases must enter adjudication;
- risk-tier 3 judgment-heavy cases are not automatically promoted merely because two models agree.

This preserves the distinction between AI-assisted collection and human/source authority.

## Repository governance prerequisite

At the time this runbook was added, GitHub reported `main` as **not protected**.

Before treating H3.9.2 artifacts as qualification-critical infrastructure, configure repository rules/branch protection so that direct destructive changes to `main` are constrained. At minimum:

- require pull-request based changes for protected paths or `main`;
- block force-pushes and branch deletion;
- require the appropriate H3.9.2 integrity checks for qualification-protocol changes;
- keep secret-management permissions limited to trusted repository administrators.

Status-check rules must match workflow trigger coverage; do not require a path-filtered check on unrelated changes unless the workflow is guaranteed to run.

Repository protection is an administrative control and is separate from the H3.9.2 benchmark gate.

## Qualification state

Running a pilot does not by itself change qualification:

```ini
benchmark_gate_passed = false
architecture_gate_passed = false
h4_development_allowed = true
h4_qualification_allowed = false
h4_release_allowed = false
```

The real 1,280-case population, benchmark freeze, system/model lock, one-shot holdout evaluation, and architecture gate remain required before H4 qualification or release.
