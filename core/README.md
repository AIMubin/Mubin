# Shared Core

Cross-engine provenance, evidence, identity, reasoning, governance, and common contracts.

P0 files:
- `inference/validator.py`: **structural-only** fail-closed reference/graph validator, not an executable usul or hadith grading system.
- `../schemas/inference-foundation.schema.json`: schema for Source, Evidence, Methodology, Claim, Rule, Inference, Objection, Proof and HistoricalAvailability.
- `tests/test_inference_foundation.py`: positive and adversarial checks.

From repository root:
```bash
python -m pip install -r core/requirements-test.txt
python -m unittest discover -s core/tests -v
```
