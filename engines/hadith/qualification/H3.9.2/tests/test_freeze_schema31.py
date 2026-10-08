from __future__ import annotations

import unittest
from pathlib import Path

from benchmark_campaign.freeze import FREEZE_SCHEMA_VERSION, _frozen_protocol_files


class Schema31FreezeSurfaceTests(unittest.TestCase):
    def test_freeze_schema_version_matches_repository_schema31_state(self):
        self.assertEqual(FREEZE_SCHEMA_VERSION, 31)

    def test_schema31_authority_and_template_files_are_frozen(self):
        root = Path("/campaign")
        rel = {
            str(path.relative_to(root))
            for path in _frozen_protocol_files(root)
        }
        required = {
            "config/adjudication-decision-contract.json",
            "schemas/adjudication-decision.schema.json",
            "schemas/adjudication-reviewer-registry.schema.json",
            "benchmark_campaign/decision_template.py",
            "CURATION.md",
            "ADJUDICATION.md",
            "ADJUDICATION_DECISIONS.md",
        }
        self.assertTrue(required.issubset(rel), required - rel)


if __name__ == "__main__":
    unittest.main()
