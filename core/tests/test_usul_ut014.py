"""UT-01.4 presentation acceptance tests (synthetic CI data only)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from engines.usul.ut014 import (
    load_usul_evidence, usul_research_section, UsulPresentationError,
)

BUNDLE_META = {
    "usul_rule_candidate_id": "candidate:amr-structural-hypothesis",
    "usul_research_pointer_id": "pilot:amr-rule-research-pointer",
    "catalog_sha256": "ab77f297b0b6e4518bd7c8f0b00e13cf38df4c6372d642d76d494a7df1b75ca5",
    "graph_sha256": "72ca6bd80c4e70378dd9d2f1cfc75841024b292d2335479d167add1a8ca6fdb2",
    "usul_source_id": "pilot:waraqat-primary",
    "usul_work_id": "0276Juwayni.Waraqat",
    "usul_section_path": "PLACEHOLDER",
    "usul_section_sha256": "20879bade7a4a831a0020e1bae51806ca015d7803be42fdb44e580a9055581ab",
    "query_terms": ["الأمر"],
    "waraqat_primary_html": "PLACEHOLDER",
    "waraqat_primary_export": "PLACEHOLDER",
    "waraqat_primary_manifest": "PLACEHOLDER",
    "waraqat_primary_section": "PLACEHOLDER",
    "waraqat_secondary_html": "PLACEHOLDER",
    "waraqat_secondary_section": "PLACEHOLDER",
}


class BundleValidationTests(unittest.TestCase):
    def test_forbidden_text_fields_refused(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "b.json"
            bad = dict(BUNDLE_META, text="protected matn")
            p.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(UsulPresentationError):
                load_usul_evidence(p)

    def test_missing_field_refused(self):
        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "b.json"
            bad = {k: v for k, v in BUNDLE_META.items()
                   if k != "catalog_sha256"}
            p.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(UsulPresentationError):
                load_usul_evidence(p)


class PresentationContractTests(unittest.TestCase):
    def test_five_levels_preserved(self):
        from engines.usul.ut014 import EVIDENCE_LEVELS, USUL_LINK_MAX_LEVEL
        self.assertEqual(len(EVIDENCE_LEVELS), 5)
        self.assertEqual(EVIDENCE_LEVELS[-2], "TEXTUALLY_ATTRIBUTED")
        self.assertEqual(EVIDENCE_LEVELS[-1], "SCHOLARLY_VERIFIED")
        self.assertEqual(USUL_LINK_MAX_LEVEL, "AUTOMATED_CANDIDATE")

    def test_contract_id(self):
        from engines.usul.ut014 import CONTRACT
        self.assertEqual(CONTRACT, "mubin-usul-tafsir-presentation-v1")


if __name__ == "__main__":
    unittest.main()
