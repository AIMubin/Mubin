# H3.9.2 reference model adapter

`chat_completions.py` implements the standard H3.9.2 HTTP adapter for endpoints exposing an chat-completions-compatible `/chat/completions` API.

The adapter is intentionally narrower than a general agent. It has no tools and no authority to create source facts. It retrieves bounded evidence from the hash-bound H3.9.2 source index, presents those excerpts to the model as untrusted data, and accepts citations only through generated evidence IDs. Every support string must occur verbatim in the retrieved excerpt before the adapter emits a response. A response may cite more than one literal support span from the same evidence/source; the adapter preserves those supports while constructing a single canonical source reference for that source.

The Factory task carries preregistered `retrieval_terms` from `factory-policy.json`. These terms receive higher retrieval weight than generic lexical overlap, while the anchor source is always included.

Credentials are supplied only through the environment variable named by `--api-key-env`. The base URL and model/deployment identifier are non-secret execution configuration and are hash-bound by the execution layer. The adapter file itself is SHA-256 bound through `adapter.artifacts` and belongs to the H3.9.2 freeze surface.

Supported authentication headers are Bearer and `api-key`. JSON response mode is optional because not every compatible provider implements it.

The model-facing output is deliberately smaller than a complete benchmark record. The adapter constructs deterministic fields such as benchmark ID, case ID, anchor source, `synthetic=false`, and annotation state. The model proposes only answer-bearing content and evidence selection; Factory reconciliation independently verifies locators, source bytes, model-family independence, policy gates, and exact gold agreement.

The reference adapter follows provider-native inference behavior by default: it omits completion-token caps and reasoning controls unless an execution config explicitly supplies them. Its default HTTP request timeout is 600 seconds.

For the manual non-holdout pilot, the executor uses one task per request and `task_failure_policy=record_rejection`. Model-output and role-contract failures are recorded as task-local collection outcomes, while authentication, provider/connection, source-integrity, adapter-protocol, and executor failures still stop the run. This keeps candidate acquisition simple without weakening the benchmark admission gate.

The manual `H3.9.2 curation pilot` workflow runs only the non-holdout partition. Source-bearing outputs are stored only inside an authenticated AES-256-GCM encrypted artifact; the upload directory otherwise contains redacted hashes and counts.
