# H3.9.2 Provider-neutral Agent Execution Layer

The execution layer runs Curator AI-A and Verifier AI-B through an external command adapter without embedding a provider SDK or API key in Mubin.

## Security and provenance boundary

- Adapter commands are executed as an argument vector; no shell interpolation is used.
- Secrets are never stored in the execution config. The config contains an `env_allowlist` of variable **names** only; values are inherited at runtime and are not written to manifests.
- The adapter is not allowed to set `model_family`, `model_ref`, task fingerprints, or execution bindings. The executor stamps those fields centrally from the reviewed config.
- Every Curator task is revalidated against the frozen Factory plan before execution.
- Every Verifier task has its own self-fingerprint in addition to the original task fingerprint.
- The source-index manifest and `segments.jsonl` hashes must match every task's retrieval scope before a model is invoked.
- Verifier execution requires a Curator execution manifest and rejects the same normalized model family.
- Holdout execution inherits the existing external custodian-path rule.
- Resume is allowed only when the task/index/config/contract/model identity bindings are unchanged.

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
    "command": ["python", "/opt/mubin-adapters/model_a.py", "--input", "{input}", "--output", "{output}", "--index", "{index_dir}", "--contract", "{contract}"],
    "env_allowlist": ["MODEL_A_API_KEY"]
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
