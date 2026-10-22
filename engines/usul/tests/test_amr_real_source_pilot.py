"""The first REAL textual witness pilot; only test inputs are synthetic.

Rule attribution from al-Waraqat is not the same as asserting a fatwa,
external original-edition attestation or general validity of this rule.
"""
import copy
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

from core.inference.validator import validate_bundle
from engines.usul.p0_bridge import build_and_run
from engines.usul.pilots.amr_default import (
    SOURCE_EXCERPT, SOURCE_URL, SYNTHETIC_VIGNETTE,
    example_bundle, example_spec, run_pilot, scenarios,
)


class AlWaraqatPilotTests(unittest.TestCase):
    def test_full_source_attributed_bundle_is_structurally_valid(self):
        bundle = example_bundle()
        self.assertEqual(validate_bundle(bundle), [])
        self.assertEqual(
            hashlib.sha256(SOURCE_EXCERPT.encode("utf-8")).hexdigest(),
            bundle["sources"][0]["content_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(SYNTHETIC_VIGNETTE.encode("utf-8")).hexdigest(),
            bundle["sources"][1]["content_sha256"],
        )
        self.assertNotIn("source_url", bundle["sources"][0])  # P0 schema disallows it
        self.assertEqual(SOURCE_URL, run_pilot()["source_reference"]["public_digital_witness_url"])

    def test_four_case_truth_table_and_determinism(self):
        output = run_pilot()
        self.assertEqual(output, run_pilot())
        self.assertEqual(
            {key: value["rule_status"] for key, value in output["cases"].items()},
            {
                "fully_declared_no_indicator": "CONDITIONALLY_SUPPORTED",
                "diverting_indicator_present": "BLOCKED_BY_EXCEPTION",
                "indicator_unknown": "UNDETERMINED",
                "command_missing": "UNDETERMINED",
            },
        )
        self.assertFalse(output["scholarly_verified"])
        self.assertFalse(output["valid_juristic_ruling"])
        self.assertFalse(output["public_fatwa_authorized"])
        self.assertFalse(output["semantic_equivalence_verified"])
        self.assertFalse(output["source_reference"]["witness_externally_revalidated_by_cli"])

    def test_trace_names_real_book_and_synthetic_fixture_separately(self):
        output = run_pilot()
        citations = output["cases"]["fully_declared_no_indicator"]["source_citations"]
        lookup = {citation["source_id"]: citation for citation in citations}
        self.assertEqual(set(lookup), {"pilot:waraqat-digital", "pilot:synthetic-fixture"})
        self.assertIn("الورقات", lookup["pilot:waraqat-digital"]["work_title"])
        self.assertEqual(lookup["pilot:waraqat-digital"]["evidence_locator"],
                         "باب الأمر، paragraph on صيغة افعل")
        self.assertEqual(lookup["pilot:waraqat-digital"]["source_content_sha256"],
                         output["source_reference"]["excerpt_utf8_sha256"])
        self.assertEqual(lookup["pilot:synthetic-fixture"]["verification_claim"], "verified")
        self.assertFalse(output["source_reference"]["redistribution_rights_inferred"])
        for value in citations:
            self.assertFalse(value["source_excerpt_reproduced"])
            self.assertFalse(value["redistribution_permission_inferred"])

    def test_source_text_mutation_breaks_p0_digest(self):
        original = example_bundle()
        original["evidence"][0]["excerpt"] += "تعديل بلا ضبط"
        out = build_and_run(original, example_spec(example_bundle()),
                            scenarios()["fully_declared_no_indicator"],
                            require_semantic_binding=True)
        self.assertEqual(out["derivation_refused"]["code"],
                         "STRUCTURAL_VALIDATION_FAILED")

    def test_source_reference_changes_break_rule_binding(self):
        bundle = example_bundle()
        spec = example_spec(bundle)
        bundle["rules"][0]["expression"] += " edited"
        out = build_and_run(bundle, spec,
                            scenarios()["fully_declared_no_indicator"],
                            require_semantic_binding=True)
        self.assertEqual(out["attribution"]["rules_rejected"][0]["reason"],
                         "REJECTED_INVALID_SEMANTIC_BINDING")

    def test_missing_synthetic_fact_evidence_never_infers_permission(self):
        b = example_bundle()
        s = example_spec(b)
        corrupted = copy.deepcopy(scenarios()["fully_declared_no_indicator"])
        corrupted[1]["source_evidence_ids"] = ["pilot:unknown"]
        out = build_and_run(b, s, corrupted, require_semantic_binding=True)
        self.assertEqual(out["attribution"]["facts_rejected"][0]["reason"],
                         "REJECTED_UNKNOWN_EVIDENCE")
        self.assertEqual(out["usul_result"]["conclusions"]["pilot:default-obligation-candidate"]["status"],
                         "UNDETERMINED")

    def test_pilot_cli_emits_metadata_not_source_excerpt(self):
        repo = Path(__file__).resolve().parents[3]
        cmd = [sys.executable, "-m", "engines.usul.pilots.amr_default"]
        result = subprocess.run(cmd, cwd=repo, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["pilot"], "waraqat-bab-al-amr")
        self.assertNotIn(SOURCE_EXCERPT, result.stdout)
        self.assertEqual(data["source_reference"]["source_sha256_scope"],
                         "EXCERPT_ONLY_UTF8_NOT_ENTIRE_BOOK_OR_WEBPAGE")


if __name__ == "__main__":
    unittest.main()
