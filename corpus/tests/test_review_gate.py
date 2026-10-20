import unittest

from core.review_gate import evaluate_action


BASE = {
    "machine_checks_passed": True,
    "known_safety_blockers_absent": True,
}


class RiskBasedReviewGateTests(unittest.TestCase):
    def test_engineering_without_human_or_license(self):
        result = evaluate_action({"action": "engineering_change", **BASE})
        self.assertEqual(result["decision"], "ELIGIBLE")
        self.assertFalse(result["qualified_human_review_is_action_gate"])
        self.assertFalse(result["scholarly_verified"])

    def test_technical_report_with_source_provenance(self):
        request = {"action": "document_source_anomaly", **BASE,
                   "provenance_verified": True, "source_untouched": True,
                   "rights": "unknown"}
        self.assertEqual(evaluate_action(request)["decision"], "ELIGIBLE")
        request["source_untouched"] = False
        self.assertEqual(evaluate_action(request)["decision"], "BLOCKED")

    def test_internal_diagnostics_does_not_infer_public_rights(self):
        result = evaluate_action({
            "action": "internal_text_diagnostics",
            "provenance_verified": True,
            "access_restricted": True,
            "rights": "restricted",
        })
        self.assertEqual(result["decision"], "ELIGIBLE")
        self.assertFalse(result["rights_granted_by_this_check"])

    def test_verbatim_tafsir_needs_rights_but_not_generic_scholar_gate(self):
        q = {"action": "publish_verbatim_source", **BASE,
             "source_kind": "tafsir", "provenance_verified": True,
             "source_untouched": True, "rights": "unknown"}
        self.assertEqual(evaluate_action(q)["decision"], "BLOCKED")
        q["rights"] = "redistribution_permitted"
        self.assertEqual(evaluate_action(q)["decision"], "ELIGIBLE")
        self.assertFalse(evaluate_action(q)["qualified_human_review_is_action_gate"])

    def test_scripture_publication_still_needs_pinned_witness(self):
        q = {"action": "publish_verbatim_source", **BASE,
             "source_kind": "quran", "provenance_verified": True,
             "source_untouched": True, "rights": "redistribution_permitted"}
        result = evaluate_action(q)
        self.assertIn("REQUIRES_QURAN_WITNESS_VERIFIED", result["blockers"])
        q["quran_witness_verified"] = True
        self.assertEqual(evaluate_action(q)["decision"], "ELIGIBLE")

    def test_no_automatic_editorial_reconstruction(self):
        q = {"action": "publish_editorial_reconstruction", **BASE,
             "source_kind": "tafsir", "provenance_verified": True,
             "rights": "redistribution_permitted"}
        self.assertEqual(evaluate_action(q)["decision"], "BLOCKED")
        q["editorial_approved"] = True
        self.assertEqual(evaluate_action(q)["decision"], "ELIGIBLE")
        q["source_kind"] = "quran"
        self.assertEqual(evaluate_action(q)["decision"], "BLOCKED")

    def test_scholarly_conclusion_requires_qualified_review(self):
        q = {"action": "publish_scholarly_conclusion", **BASE,
             "provenance_verified": True}
        self.assertEqual(evaluate_action(q)["decision"], "BLOCKED")
        q["qualified_scholarly_review"] = True
        self.assertEqual(evaluate_action(q)["decision"], "ELIGIBLE")
        self.assertFalse(evaluate_action(q)["scholarly_verified"])

    def test_h392_gold_never_bypasses_frozen_independent_protocol(self):
        q = {"action": "promote_h392_gold", **BASE,
             "h392_protocol_passed": True}
        self.assertEqual(evaluate_action(q)["decision"], "BLOCKED")
        q["independent_human_protocol_verified"] = True
        self.assertEqual(evaluate_action(q)["decision"], "ELIGIBLE")
        q["h392_protocol_passed"] = False
        self.assertEqual(evaluate_action(q)["decision"], "BLOCKED")

    def test_system_release_separate_from_engineering(self):
        q = {"action": "system_release", **BASE}
        self.assertEqual(evaluate_action(q)["decision"], "BLOCKED")
        q["integration_evaluation_passed"] = True
        self.assertEqual(evaluate_action(q)["decision"], "ELIGIBLE")
        q["includes_scholarly_conclusions"] = True
        self.assertEqual(evaluate_action(q)["decision"], "BLOCKED")

    def test_unknown_requests_and_string_booleans_fail_closed(self):
        for request in [
            {"action": "approve_everything", **BASE},
            {"action": "engineering_change", **BASE, "scholarly_verified": True},
            {"action": "engineering_change", "machine_checks_passed": "true"},
            {"action": "publish_verbatim_source", "rights": "free_online"},
            {"action": [], "machine_checks_passed": True},
            {"action": "publish_verbatim_source", "rights": []},
            {"action": "publish_verbatim_source", "source_kind": []},
        ]:
            with self.subTest(request=request):
                with self.assertRaises(ValueError):
                    evaluate_action(request)

    def test_default_unknown_rights_never_assumes_permission(self):
        result = evaluate_action({"action": "publish_verbatim_source", **BASE,
                                  "source_kind": "hadith",
                                  "provenance_verified": True,
                                  "source_untouched": True})
        self.assertIn("REDISTRIBUTION_RIGHTS_NOT_VERIFIED", result["blockers"])

    def test_cli_exit_codes_are_not_scholarly_certificates(self):
        import json
        import subprocess
        import sys
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "decision.json"
            def run(payload):
                file.write_text(json.dumps(payload), encoding="utf-8")
                return subprocess.run(
                    [sys.executable, "-m", "core.review_gate", str(file)],
                    capture_output=True, text=True, check=False)
            good = run({"action": "engineering_change", **BASE})
            self.assertEqual(good.returncode, 0)
            self.assertEqual(json.loads(good.stdout)["decision"], "ELIGIBLE")
            self.assertFalse(json.loads(good.stdout)["scholarly_verified"])

            restricted = run({"action": "publish_verbatim_source", **BASE,
                              "source_kind": "tafsir", "provenance_verified": True,
                              "source_untouched": True, "rights": "unknown"})
            self.assertEqual(restricted.returncode, 1)
            self.assertEqual(json.loads(restricted.stdout)["decision"], "BLOCKED")

            invalid = run({"action": "system_release",
                           "machine_checks_passed": "true"})
            self.assertEqual(invalid.returncode, 2)
            self.assertEqual(json.loads(invalid.stdout)["decision"], "INVALID")



if __name__ == "__main__":
    unittest.main()
