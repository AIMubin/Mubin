# H3.9.2 Provider-neutral Agent Execution Layer

The execution layer runs Curator AI-A and Verifier AI-B through an external command adapter without embedding a provider SDK or API key in Mubin.

## Security and provenance boundary

- Adapter commands are executed as an argument vector; no shell interpolation is used. Every execution config must declare one or more `adapter.artifacts`; their SHA-256 digests and sizes are bound into the execution config/manifest and every stamped response.
- The supported secret path is `env_allowlist`: the config stores variable **names** only, values are inherited at runtime, and values are never written to manifests. Common secret-bearing command flags are rejected. Arbitrary opaque command arguments cannot be proven non-secret, so operators must not embed credentials in command tokens.
- The adapter is not allowed to set `model_family`, `model_ref`, task fingerprints, or execution bindings. The executor stamps those fields centrally from the reviewed config.
- Every Curator task is revalidated against the frozen Factory plan before execution.
- Every Verifier task has its own self-fingerprint in addition to the original task fingerprint.
- The source-index manifest and `segments.jsonl` hashes must match every task's retrieval scope before a model is invoked.
- Verifier execution requires a valid Curator execution manifest for the same partition and identical source-index hashes, rejects the same normalized model family, and records the Curator-manifest SHA-256 plus Curator config/model/task bindings in the Verifier execution manifest.
- Holdout execution inherits the existing external custodian-path rule.
- Resume is allowed only when the task/index/config/contract/model identity bindings are unchanged; existing response payloads are rehashed before reuse.

## Adapter protocol

The adapter receives a JSONL batch at the path substituted into `{input}` and must write exactly one JSON object per task to `{output}`.

Curator raw response:

```json
{"task_id":"...","status":"candidate","candidate":{...}}
```

Verifier raw response:

```json
{"task_id":"...","status":"candidate","answer":{...}}
```

Unsupported evidence:

```json
{"task_id":"...","status":"no_candidate","reason":"source evidence is insufficient"}
```

The executor exposes controlled runtime metadata through `MUBIN_AGENT_ROLE`, `MUBIN_MODEL_FAMILY`, `MUBIN_MODEL_REF`, `MUBIN_SOURCE_INDEX_DIR`, `MUBIN_AGENT_CONTRACT`, `MUBIN_AGENT_INPUT`, and `MUBIN_AGENT_OUTPUT`.

## Example execution config

```json
{
  "schema_version": 1,
  "role": "curator",
  "model_family": "provider-model-family-a",
  "model_ref": "provider/model-a@immutable-or-recorded-revision",
  "adapter": {
    "command": ["python", "adapters/openai_compatible.py", "--input", "{input}", "--output", "{output}", "--index", "{index_dir}", "--contract", "{contract}", "--base-url", "https://provider.example/v1"],
    "env_allowlist": ["MUBIN_OPENAI_API_KEY"],
    "artifacts": ["adapters/openai_compatible.py"]
  },
  "batch_size": 8,
  "timeout_seconds": 900,
  "max_attempts": 2
}
```

Do not put an API key, bearer token, password, or request header value in this JSON.

## Flow

```text
factory-build-tasks
  -> factory-run-agent --role curator
  -> factory-prepare-verifier
  -> factory-run-agent --role verifier --independent-from-manifest <curator-run.json>
  -> factory-reconcile
```

The execution layer validates transport/provenance integrity. It does not elevate AI output into authority; promotion remains governed by Factory source verification, risk policy, and adjudication.


Adapter stdout and stderr are discarded by the executor rather than persisted, reducing accidental leakage of source excerpts or credentials through provider logs. Batch failure reports expose only sanitized error classes/return codes, not command arguments.


The execution implementation and this protocol document are part of the H3.9.2 freeze surface. Changing either after benchmark freeze changes the qualification protocol and requires a new freeze/version rather than silent mutation.
