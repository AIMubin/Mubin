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

### Structural-only CLI

```bash
python -m core.inference --help
python -m core.inference /path/to/bundle.json
```

Exit 0 = valid **structure only**; 1 = invalid schema/provenance graph; 2 = malformed, missing or oversized input (5 MiB). Programmatic validator caps bundles at 5000 entities and dependency depth at 128. No human review, hadith authentication, scholarly citation verification, or executable usul is implied.

### P1.0 offline provenance pilot

- `provenance/validator.py`: match P0 evidence excerpts against pinned UTF-8 local source snapshots with exact byte spans and full SHA-256.
- `../schemas/source-snapshot-manifest.schema.json`: source paths, editions, locators, operator-declared rights and byte spans.
- `tests/test_provenance.py`: synthetic positive/negative tests (no bundled real religious corpora).
- `python -m core.provenance --help` for CLI; see `docs/P1-PROVENANCE.md` for scopes and limits.

This proves **local bytes only** and does not verify authoritativeness, copyright compliance or scholarly correctness.
