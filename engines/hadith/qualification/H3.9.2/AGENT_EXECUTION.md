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
    "command": ["python", "adapters/chat_completions.py", "--input", "{input}", "--output", "{output}", "--index", "{index_dir}", "--contract", "{contract}", "--base-url", "https://endpoint.example/v1", "--timeout", "600"],
    "env_allowlist": ["MUBIN_MODEL_API_KEY"],
    "artifacts": ["adapters/chat_completions.py"]
  },
  "batch_size": 1,
  "timeout_seconds": 660,
  "max_attempts": 1,
  "task_failure_policy": "record_rejection"
}
```

Do not put an API key, bearer token, password, or request header value in this JSON.

## Collection versus qualification execution

The executor separates **obtaining model output** from **admitting output into the benchmark**.

`task_failure_policy=fail_fast` is the default strict execution mode. Any adapter/model failure aborts the run.

`task_failure_policy=record_rejection` is the collection mode used by the non-holdout pilot. It requires `batch_size=1`, so one malformed model answer cannot invalidate unrelated tasks. Bounded `adapter:model_output_*` and `adapter:contract_*` failures are recorded as task-local rejections in the execution manifest and execution continues. Authentication failures, connection/provider failures, endpoint-shape failures, adapter protocol errors, source/index integrity failures, and executor failures remain fatal. Holdout execution is always `fail_fast`; collection-mode rejection recording is prohibited there.

The manifest distinguishes `attempted_task_count`, `completed_task_count` (valid adapter responses, including `no_candidate`), `rejected_task_count`, `pending_task_count`, and aggregate `rejection_counts`. Rejected tasks never become Curator/Verifier responses and therefore cannot enter reconciliation or promotion as valid candidates.

On the non-holdout collection surface, a second task-local filter exists between Curator collection and Verifier execution: verifier-task preparation checks that `candidate.payload.input` is structurally blind to the Curator's selected answer. A blindness violation suppresses only that Verifier task, increments the redacted verifier-preparation rejection count, and leaves the Curator candidate available for reconciliation/adjudication. Holdout preparation remains fail-closed. The full preregistered `allowed_labels` list is not treated as selected-answer leakage when it exactly matches the task contract, because Verifier AI-B receives the same label vocabulary independently.

## Inference policy

The reference adapter defaults to ordinary provider-native inference behavior:

- `--completion-budget auto` is the default and omits both `max_tokens` and `max_completion_tokens`;
- `--reasoning-effort provider_default` is the default and sends no reasoning-control field;
- the default HTTP request timeout is 600 seconds.

The pilot deliberately does not expose completion-budget or reasoning-effort controls. Provider-native behavior is used unless a separate, reviewed execution config has a reproducibility reason to set them explicitly. Unsupported provider capabilities must fail at the endpoint boundary rather than being silently translated or retried with a different request shape.

All explicit inference values remain part of the command/config binding and therefore of execution provenance.

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

The reference adapter emits bounded diagnostic categories such as `http_<status>`, `connection_failed`, `endpoint_timeout`, `endpoint_invalid_json`, `response_shape_invalid`, `model_output_empty`, `model_output_reasoning_only`, `model_output_no_json_object`, `model_output_unbalanced_json`, `model_output_truncated`, `model_output_invalid_json`, and `model_output_ambiguous_json`. Read-stage disconnects such as incomplete HTTP bodies, remote disconnects, TLS/socket resets, and similar transport exceptions are reduced to the same content-safe `connection_failed` class instead of surfacing as `adapter_internal_error`. Contract failures are likewise reduced to fixed structural categories such as `contract_status_invalid`, `contract_gold_not_object`, `contract_gold_labels_missing`, `contract_gold_label_type_invalid`, `contract_gold_labels_duplicate`, `contract_gold_label_outside_contract`, `contract_family_id_missing`, `contract_support_not_verbatim`, `contract_mode_invalid`, and `contract_verbatim_not_supported`. These codes disclose only failure classes; they never expose model text, evidence text, identifiers supplied by the model, or reasoning. In collection mode only the `model_output_*` and `contract_*` classes are task-local; infrastructure and protocol failures remain fail-closed. The non-holdout pilot may retry a `connection_failed` transport failure once. Contract/model-output failures, HTTP status failures, endpoint timeouts, protocol failures, missing output, invalid adapter output, and executor timeouts are not retried. Holdout execution is strictly one-shot and requires `max_attempts=1`.

Multiple literal support spans may cite the same retrieved evidence/source. This is not a provenance duplication: the benchmark record still carries one canonical `source_ref` per source while `answer_provenance.supports` may contain multiple independently hash-bound literal spans from that source. The adapter must not reject such evidence multiplicity merely because the `source_id` repeats.


The execution implementation and this protocol document are part of the H3.9.2 freeze surface. Changing either after benchmark freeze changes the qualification protocol and requires a new freeze/version rather than silent mutation.


### Strict JSON recovery

The reference adapter never repairs malformed JSON or infers missing fields. It accepts model content only through one of three deterministic paths:

1. the entire trimmed content is one JSON object;
2. the entire trimmed content is one `json`/unlabelled code fence containing one JSON object;
3. the content contains exactly one balanced top-level JSON object, with no second object, array payload, or code fence outside it.

Nested objects inside that single payload are allowed and do not count as multiple candidates. More than one top-level object is `model_output_ambiguous_json`. Missing objects, unbalanced objects, empty content, reasoning-only content, and output truncated by the provider token limit are distinguished with content-safe diagnostic codes. Model JSON is decoded strictly: non-standard constants such as `NaN`, `Infinity`, and `-Infinity` are rejected. After extraction, the same Curator/Verifier contract validation remains mandatory. No field repair, quote repair, trailing-comma repair, type coercion, or semantic correction is performed.
