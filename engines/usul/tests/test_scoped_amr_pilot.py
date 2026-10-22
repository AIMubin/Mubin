"""Source-backed (but not authoritative) al-Waraqat synthetic scope pilot."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

from engines.usul.pilots.scoped_amr_pilot import run
from engines.usul.pilots.amr_default import SOURCE_EXCERPT


class ScopedPilotTests(unittest.TestCase):
    def test_truth_table_with_scoped_exception_checks(self):
        first, second = run(), run()
        self.assertEqual(first, second)
        statuses = {k: v["rule_status"] for k, v in first["cases"].items()}
        self.assertEqual(statuses, {
            "declared_scope_inspected_no_indicator": "CONDITIONALLY_SUPPORTED",
            "indicator_observed": "BLOCKED_BY_EXCEPTION",
            "inspection_not_performed": "UNDETERMINED",
            "premise_missing_despite_scope_check": "UNDETERMINED",
        })
        self.assertFalse(first["scholarly_verified"])
        self.assertFalse(first["external_source_authentication_verified"])
        self.assertFalse(first["valid_juristic_ruling"])

    def test_negative_finding_only_claims_declared_scope(self):
        results = run()
        checked = results["cases"]["declared_scope_inspected_no_indicator"]
        self.assertEqual(checked["assessment"]["finding"], "ABSENT_IN_DECLARED_SCOPE")
        self.assertTrue(checked["assessment"]["declared_scope_coverage_complete"])
        self.assertFalse(checked["assessment"]["real_world_absence_verified"])
        self.assertFalse(checked["real_world_absence_verified"])
        self.assertEqual(results["scope_type"], "DECLARED_SYNTHETIC_CASES_ONLY")
        self.assertTrue(results["scope_completeness_does_not_prove_universal_absence"])

    def test_source_citations_do_not_reproduce_original_passage(self):
        data = run()
        case = data["cases"]["declared_scope_inspected_no_indicator"]
        sources = {item["source_id"]: item for item in case["cited_evidence"]}
        self.assertIn("pilot:waraqat-digital", sources)
        self.assertIn("pilot:synthetic-fixture", sources)
        self.assertIn("الورقات", sources["pilot:waraqat-digital"]["work_title"])
        self.assertTrue(all(not c["source_excerpt_reproduced"]
                            for c in case["cited_evidence"]))

    def test_cli_output_is_portable_to_windows_and_contains_no_passage(self):
        repo = Path(__file__).resolve().parents[3]
        proc = subprocess.run([sys.executable, "-m", "engines.usul.pilots.scoped_amr_pilot"],
                              cwd=repo, capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertIn("cases", data)
        self.assertNotIn(SOURCE_EXCERPT, proc.stdout)


if __name__ == "__main__":
    unittest.main()
