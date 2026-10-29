# MUBIN-SYS-A01 — AI-native integration kernel (Wave A)

Scope: shared contract v1, bounded DAG execution, per-case concurrency, explicit partial
failures, per-case in-memory receipt, synthetic adapters for ALL FIVE engines, and typed
research-only Fiqh models. This is an **engineering skeleton**, NOT a working MVE and NOT
an end-to-end scholarly/juristic integration.

## Verify

```bash
python -m pip install -r core/requirements-test.txt
python -m unittest discover -s evaluation/integration -v
```

### Contracts

`core/contracts/types.py` defines strict wire request invariants; the corresponding
JSON schemas are in `schemas/engine-request-v1.schema.json` and `engine-result-v1.schema.json`.
No runtime dependency on an LLM or any external service. Registry operations are
explicitly allowlisted; unknown operations and unavailable engines are not guessed.

### Kernel

`core/orchestration/plan.py` rejects missing dependencies, cycles, duplicate nodes,
invalid limits, non-versioned state and malformed IDs. `runner.py` uses a bounded
**per-case semaphore**, not a global lock. Dependency failures yield `UNDETERMINED`.
Timeouts yield `UNAVAILABLE` and are distinct from the engine's `NO_MATCH`.
Source snapshot IDs are verified exactly on each response.

The `InMemoryCaseStore` is for Wave-A tests only; it does **not** provide crash-safe
or restart-safe persistence. It does not store private source text; any future
durable store must separately establish redaction, integrity and concurrency behavior.
No cross-node evidence propagation or real source-backed adapters are claimed.

### Fiqh boundary

`engines/fiqh/models.py` creates typed cases and attributed opinion references.
`prepare_research` never returns a juristic verdict; until a real Usul application
exists it reports `PARTIAL` or `UNDETERMINED`, authority `RESEARCH_ONLY`.

### Wave B / remaining deliverables

- Replace each synthetic adapter with separately tested real-source engine adapters.
- Add actual evidence graph propagation, dependency data flow and pinned replay.
- Add crash-safe case persistence and idempotent resumes.
- Integrate existing P0 structural validator, without converting its
  `structurally_checked` label into scholarly certification.
- Implement an actual narrow Fiqh workflow and genuine five-engine research case.
- Keep H3.9.2 frozen human-labelled campaign intact.
- Publication/rights/official-approval checks remain in independent release lane.
