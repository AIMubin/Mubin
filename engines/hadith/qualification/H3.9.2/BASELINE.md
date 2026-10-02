# Baseline compatibility

This delivery is an additive **H3.9.2 R3 benchmark-campaign overlay** for the Hadith H3.9.1 foundation tree. It deliberately does not alter H3.5–H3.9 architecture behavior or introduce H4 code.

The Project Library contains `Mubin-foundation-v3.9.1.zip`, but that archive cannot be byte-materialized in the current execution environment. Accordingly this package is not represented as a merged foundation build.

R3 preserves the R2 corrections (complete multi-source disjointness, campaign-global leakage checks, and a performance-backed benchmark gate) and closes the remaining holdout-visibility gap: final-holdout gold is AES-256-GCM sealed with an external key, removed from public records and in-repository staging, and only decrypted by the one-shot evaluator after model lock. R3 also freezes deterministic source-anchor curation quotas for all 1,280 target cases before case selection.
