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
  "model_family": "model-family-a",
  "model_ref": "model-a@immutable-or-recorded-revision",
  "adapter": {
    "command": ["python", "adapters/chat_completions.py", "--input", "{input}", "--output", "{output}", "--index", "{index_dir}", "--contract", "{contract}", "--base-url", "https://endpoint.example/v1", "--completion-budget", "auto", "--completion-budget-field", "max_tokens", "--reasoning-effort", "provider_default"],
    "env_allowlist": ["MUBIN_MODEL_API_KEY"],
    "artifacts": ["adapters/chat_completions.py"]
  },
  "batch_size": 8,
  "timeout_seconds": 900,
  "max_attempts": 2
}
```

Do not put an API key, bearer token, password, or request header value in this JSON.

## Inference policy

The reference adapter separates the benchmark output contract from provider inference controls:

- `--completion-budget auto` omits both `max_tokens` and `max_completion_tokens`, allowing the endpoint/model to use its configured completion policy without an artificial Mubin cap.
- An explicit positive integer may be supplied when a qualification run requires a fixed budget. There is no Mubin-defined upper bound; the endpoint remains authoritative for its supported limit.
- `--completion-budget-field` selects `max_tokens` or `max_completion_tokens` only when an explicit budget is used.
- `--reasoning-effort provider_default` sends no reasoning-control field. `low`, `medium`, or `high` opt in to the common `reasoning_effort` chat-completions capability.
- Unsupported provider capabilities must fail at the endpoint boundary rather than being silently translated or retried with a different request shape.

These values are command/config inputs and therefore remain bound by the existing execution-config hash and manifest provenance. `auto` is useful for capability discovery and pilot runs; qualification-critical runs should record the exact provider/model revision and use an explicit budget/field when reproducibility requires it.

## Flow

```text
factory-build-tasks
  -> factory-run-agent --role curator
  -> factory-prepare-verifier
  -> factory-run-agent --role verifier --independent-from-manifest <curator-run.json>
  -> factory-reconcile
```

The execution layer validates transport/provenance integrity. It does not elevate AI output into authority; promotion remains governed by Factory source verification, risk policy, and adjudication.


Adapter stdout is discarded. Stderr is written only to an ephemeral per-attempt file and deleted with the temporary execution directory. The executor ignores arbitrary stderr content and recognizes only a strict `MUBIN_DIAGNOSTIC:<code>` marker matching `[a-z0-9_:-]{1,80}`; everything else is discarded. Batch failure reports therefore expose only sanitized diagnostic codes or return codes, never command arguments, endpoint values, model identity, source text, response bodies, or credentials.

The reference adapter emits bounded diagnostic categories such as `http_<status>`, `connection_failed`, `endpoint_timeout`, `endpoint_invalid_json`, `response_shape_invalid`, `model_output_empty`, `model_output_reasoning_only`, `model_output_no_json_object`, `model_output_unbalanced_json`, `model_output_truncated`, `model_output_invalid_json`, `model_output_not_object`, `model_output_ambiguous_json`, and `contract_validation_error`. These codes disclose only structural failure classes; they never expose model text or reasoning.


The execution implementation and this protocol document are part of the H3.9.2 freeze surface. Changing either after benchmark freeze changes the qualification protocol and requires a new freeze/version rather than silent mutation.


### Strict JSON recovery

The reference adapter never repairs malformed JSON or infers missing fields. It accepts model content only through one of three deterministic paths:

1. the entire trimmed content is one JSON object;
2. the entire trimmed content is one `json`/unlabelled code fence containing one JSON object;
3. the content contains exactly one balanced top-level JSON object, with no second object, array payload, or code fence outside it.

Nested objects inside that single payload are allowed and do not count as multiple candidates. More than one top-level object is `model_output_ambiguous_json`. Missing objects, unbalanced objects, empty content, reasoning-only content, and output truncated by the provider token limit are distinguished with content-safe diagnostic codes. Model JSON is decoded strictly: non-standard constants such as `NaN`, `Infinity`, and `-Infinity` are rejected. After extraction, the same Curator/Verifier contract validation remains mandatory. No field repair, quote repair, trailing-comma repair, type coercion, or semantic correction is performed.
