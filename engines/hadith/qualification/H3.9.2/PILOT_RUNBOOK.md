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

Configure these GitHub repository or organization **Variables**:

- `H392_CURATOR_BASE_URL`
- `H392_VERIFIER_BASE_URL`

Configure these GitHub **Secrets**:

- `H392_CURATOR_API_KEY`
- `H392_VERIFIER_API_KEY`
- `H392_CURATION_ARTIFACT_KEY`

The artifact passphrase must contain at least 20 characters. Do not place API keys, bearer tokens, passwords, request headers, or the artifact passphrase in committed JSON/YAML configuration.

The GitHub connector used during development cannot read or create repository Secrets, so secret presence must be configured and confirmed through repository administration before the first dispatch.

## Model independence

Curator AI-A and Verifier AI-B must have different normalized `model_family` values. Prefer genuinely different model families, and preferably different providers or independently operated endpoints, to reduce correlated failure.

The Verifier does not receive the Curator's proposed gold or supporting citations. It receives the answer-free candidate input plus independently retrieved evidence.

Do not use Mubin outputs to create benchmark gold.

## First pilot parameters

Start with:

- `task_offset = 0`
- `task_limit = 8`

Provide:

- exact Curator model-family identifier;
- exact Curator model/deployment reference;
- exact Verifier model-family identifier;
- exact Verifier model/deployment reference;
- authentication style for each endpoint;
- JSON response mode only when supported by that endpoint.

The workflow validates that the two model-family identifiers differ before either model is invoked.

## What the workflow does

For every dispatch, the runner:

1. checks out Mubin;
2. acquires only the pinned `non_holdout` source partition;
3. re-verifies every source against its Git blob SHA;
4. rebuilds the source index;
5. rebuilds the frozen 1,280-slot Factory plan;
6. regenerates the 896 non-holdout Curator tasks;
7. selects the requested deterministic task chunk;
8. runs Curator AI-A;
9. prepares structurally blind Verifier tasks;
10. runs Verifier AI-B when Curator candidates exist;
11. routes every task through the real Factory reconciliation path;
12. records promoted/adjudication/skipped outcomes in the curation ledger;
13. encrypts all source-bearing run material with authenticated AES-256-GCM;
14. uploads only the encrypted source-bearing bundle plus redacted metadata.

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
- exactly 8 requested tasks are selected;
- no holdout source enters task scope;
- Curator responses are execution-bound to model/config/adapter hashes;
- Verifier execution is bound to the Curator manifest but remains answer-blind;
- every cited support string is verbatim in retrieved evidence;
- reconciliation completes without integrity exceptions;
- every task ends as promoted, adjudication-required, or explicitly skipped;
- no source-bearing plaintext file appears in the uploaded artifact;
- AES-GCM decryption succeeds with the correct passphrase and fails if the ciphertext is tampered;
- no qualification or H4 gate changes as a side effect of the pilot.

A high adjudication rate is not itself a pilot failure. It is evidence about task difficulty, retrieval quality, or model suitability.

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
