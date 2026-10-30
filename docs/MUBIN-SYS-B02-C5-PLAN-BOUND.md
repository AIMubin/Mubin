# MUBIN-SYS-B02-C.5 — Plan-Bound Execution Provenance

**Internal engineering increment:** Does not change Mubin version, frozen
Hadith benchmarks, P0 schema or existing `run_case` receipts.

## Motivation

B02-C.2 and B02-C.3 source-bound results can show that evidence identifiers
are present in two different engine outcomes. The existing
`run_case` receipt **does not contain the original CasePlan operation,
node inputs or direct `depends_on`**. Therefore a shared evidence
identifier alone cannot prove the actual DAG dependency relationship.

## Implementation

`core/orchestration/plan_bound_provenance.py` exposes:

```python
run_case_plan_bound(plan, registry, *, audit_key, store=None)
verify_plan_bound_replay(plan, receipt, public_audit, *, audit_key)
```

`run_case_plan_bound` calls the *actual* `run_case` within the same
process, then derives a plan/result audit from that same plan object
and the returned receipt. It does not attempt to reconstruct a
historical CasePlan out of B02-C.2 metadata.

The audit includes node ID, engine, operation, direct dependencies,
result status, evidence reference count, and **HMAC-SHA256 commitments**
for private node inputs and engine-result payloads. It records direct
DAG edges from the validated plan, not guessed from source labels.

The operator supplies a **private, high-entropy 32-byte or longer
`audit_key`**. Do not check keys into GitHub, reuse demonstration keys,
send them to review bots or disclose plaintext private inputs.
HMAC avoids publishing ordinary SHA digests of low-entropy private
source inputs. Verification requires the same trusted operator key.

`verify_plan_bound_replay` recomputes the commitments for the exact
submitted plan and engine receipt; changing the operation, inputs,
direct dependencies, result payload or key fails. The audit never
includes the private `node.inputs` object or source text.

## Scientific and security limitations

- The result asserts **operator-local plan/receipt consistency**, not
  identity or authenticity of an external computing environment.
  A malicious operator can generate a self-consistent audit with their
  own plan, data, and key; HMAC is not an externally trusted signature.
- The wrapper cannot prove that a particular engine's underlying
  source corpus, H-Search candidates, Tafsir interpretations or
  juristic attributions are correct.
- The old `run_case` receipt *by itself* cannot be retroactively
  plan-bound; an actual local rerun is needed.
- A declared direct dependency is part of the supplied plan; evidence
  provenance and **actual semantic correctness** are separate checks.
- `scientific_chain_established=false`, `scholarly_verified=false`
  and `juristic_inference_allowed=false` unconditionally.

## Local Lead handoff

The local AI may rerun the preserved 6:145 diagnostic with its
pinned Waraqat/H-Search/Tafsir sources using the wrapper and a secret
operator key, retaining the complete plan/receipt in the private vault.
Export only the plan-bound audit after inspecting operation/ID metadata
for sensitive information. The result of original strict selection
remains `REJECTED_ALL_CANDIDATES_UNDER_FULL_BAR`; the closed research
case does not acquire scientific acceptance.

Tests: `python -m unittest discover -s evaluation/integration -v`.
