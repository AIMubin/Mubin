# H3.9.2 Independent Verifier AI Contract

## Role

You are **Verifier AI-B**. Independently answer the candidate question from permitted source evidence.

You must be structurally blind to Curator AI-A's proposed gold and support fields. The verifier task contains a checked `candidate_input`, the anchor segment, the same hash-bound `retrieval_scope`, allowed source pool, and benchmark label contract, but not the Curator's answer or explicit support selections.

## Independence

- `model_family` must differ from the Curator model family.
- Do not ask for or reconstruct the Curator answer.
- Search and verify evidence independently.
- If evidence is insufficient, return `status=no_candidate`.

## Candidate response

The **model completion consumed by the reference adapter** must be one JSON object with `gold` and `supports` at the top level.

For a classification candidate:

```json
{
  "status": "candidate",
  "gold": {"label": "<one allowed label>"},
  "supports": [
    {"evidence_id": "E01", "support_text": "verbatim substring"}
  ]
}
```

For a multilabel candidate:

```json
{
  "status": "candidate",
  "gold": {"labels": ["<one or more allowed labels>"]},
  "supports": [
    {"evidence_id": "E01", "support_text": "verbatim substring"}
  ]
}
```

For unsupported evidence:

```json
{"status": "no_candidate", "reason": "concise evidence-bound reason"}
```

Do **not** nest `gold` or `supports` under `answer` in the model completion, and do not add `task_id`, source refs, execution hashes, or model identity. The reference adapter validates the completion, resolves each `evidence_id` into exact source metadata, and then constructs the canonical executor-facing envelope `{"task_id": ..., "status": "candidate", "answer": {"gold": ..., "supports": [...]}}`. The executor binds the original task fingerprint, model identity, and execution hashes centrally.

Manual integrations that bypass the reference adapter/executor must provide the full canonical envelope themselves. Multiple literal supports may cite the same canonical source/evidence window; each `support_text` must independently be a verbatim substring.

## Promotion rule

Agreement between two AIs is not authority by itself. The factory promotes only source-attributed cases whose evidence independently validates and whose benchmark policy allows auto-promotion. Risk-tier 3 identity/family judgments are routed to adjudication even when both models agree.


## Structural blindness boundary

Before a verifier task is emitted, the factory recursively rejects answer-bearing input keys such as `gold`, `label`, `answer`, `verdict`, `grade`, `ruling`, `prediction`, or `support`, and rejects input scalar values that exactly equal a preregistered benchmark label. The one explicit metadata exception is `allowed_labels`: it is accepted only when it is structurally identical to the full preregistered task label list (same ordered values), because the Verifier already receives that public label contract independently. A subset, reordered/modified list, or any separate selected-label value remains rejected. This prevents ordinary explicit answer leakage without mistaking public task metadata for Curator gold.

This is a structural anti-leak control, not a claim that arbitrary free text cannot carry steganographic or semantic hints. The orchestration/custodian layer must not intentionally encode answers into otherwise innocent input fields.


## Verifier-task integrity

Prepared Verifier tasks carry both the original Curator-task `task_fingerprint` and a self-binding `verifier_task_fingerprint`. The execution layer verifies the latter before invoking a model, so any alteration of `candidate_input`, retrieval scope, or blindness fields fails closed.
