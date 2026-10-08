from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


class Schema31DecisionTemplateEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.evidence_path = (
            cls.root / "artifacts" / "SCHEMA31_DECISION_TEMPLATE_EVIDENCE_158.json"
        )
        cls.status_path = cls.root / "artifacts" / "H3.9.2-STATUS.json"
        cls.contract_path = cls.root / "config" / "adjudication-decision-contract.json"
        cls.evidence = json.loads(cls.evidence_path.read_text(encoding="utf-8"))
        cls.status = json.loads(cls.status_path.read_text(encoding="utf-8"))
        cls.contract = json.loads(cls.contract_path.read_text(encoding="utf-8"))

    def test_exact_successful_migration_run_is_frozen(self):
        self.assertEqual(self.evidence["protocol_freeze_schema"], 31)
        self.assertEqual(self.evidence["runner_commit"], "4ca54bf0d98d4709774e04d80d18b74c13679abc")
        workflow = self.evidence["workflow"]
        self.assertEqual(workflow["run_id"], 37781676566)
        self.assertEqual(workflow["run_attempt"], 1)
        self.assertEqual(workflow["job_id"], 113326049266)
        self.assertEqual(workflow["event"], "workflow_dispatch")
        self.assertEqual(workflow["head_branch"], "main")
        self.assertEqual(workflow["conclusion"], "success")

    def test_public_artifact_hashes_are_exact(self):
        artifact = self.evidence["artifact"]
        self.assertEqual(artifact["id"], 11552726258)
        self.assertEqual(
            artifact["digest"],
            "sha256:7c7095a0a76b14479d37351bbf58f60307bcc6456e8ebd0e1b0a5aafc95da00d",
        )
        self.assertEqual(artifact["size_bytes"], 9958)
        self.assertEqual(artifact["published_file_count"], 3)
        self.assertEqual(
            artifact["redacted_summary_sha256"],
            "674c05e5e72afe58d2e62bacf4049c67dee43914e6aeee072963794eacd3291c",
        )
        self.assertEqual(
            artifact["digest_declaration_sha256"],
            "90aee8a9ff0aea0e13125be93da091d809f7a422bd70f5310d034f65265e0e20",
        )
        self.assertEqual(
            artifact["encrypted_bundle_sha256"],
            "631630ee20af8c50c43dedcf6b0e8bf6613cd5b4ed993d3bd0529216e584be05",
        )

    def test_result_is_blank_and_bound_to_schema31(self):
        result = self.evidence["result"]
        self.assertEqual(result["case_count"], 158)
        self.assertEqual(
            result["benchmark_counts"],
            {"external-critical-commentary": 158},
        )
        self.assertEqual(
            result["packet_task_binding_sha256"],
            "ce8d63b6d186bcfe715c56ba140d0b475ab1b53f1ef0577341189e98e78840fa",
        )
        self.assertEqual(
            result["decision_template_sha256"],
            "a72d1ba9993d2b5e1d156701c8a12684c7b3703426d99ba85c25b66479200558",
        )
        self.assertTrue(result["blank_template"])
        self.assertFalse(result["contains_terminal_decisions"])
        self.assertFalse(result["contains_source_text"])
        self.assertFalse(result["contains_gold_payloads"])
        self.assertFalse(result["contains_model_identity"])
        self.assertFalse(result["legacy_top_level_decision_field_present"])
        self.assertEqual(
            result["canonical_terminal_decision_path"],
            "terminal_signoff.decision",
        )

    def test_repository_state_authorizes_review_not_ingestion(self):
        surface = self.status["adjudication_review_surface"]
        self.assertEqual(surface["protocol_state"], "human_review_authorized")
        self.assertTrue(surface["human_review_authorized"])
        self.assertFalse(surface["human_adjudication_started"])
        self.assertTrue(surface["decision_bundle_may_be_prepared_off_repo"])
        self.assertFalse(surface["decision_ingestion_authorized"])
        self.assertFalse(surface["automatic_decision_application_authorized"])
        self.assertFalse(
            self.status["post_consolidation_protocol"]["automatic_reserve3_authorized"]
        )

    def test_contract_bytes_and_execution_gate_are_bound(self):
        status_contract = self.status["adjudication_decision_contract"]
        self.assertEqual(
            status_contract["contract_sha256"],
            hashlib.sha256(self.contract_path.read_bytes()).hexdigest(),
        )
        self.assertTrue(
            self.contract["execution_gates"]["human_review_may_begin_under_this_contract"]
        )
        self.assertFalse(
            self.contract["execution_gates"]["repository_decision_ingestion_authorized"]
        )
        self.assertEqual(
            self.contract["scope"]["schema31_decision_template"]["workflow_run_id"],
            37781676566,
        )
        self.assertEqual(
            self.contract["scope"]["schema31_decision_template"]["evidence_path"],
            "artifacts/SCHEMA31_DECISION_TEMPLATE_EVIDENCE_158.json",
        )

    def test_qualification_gates_remain_closed(self):
        effect = self.evidence["qualification_effect"]
        self.assertFalse(effect["benchmark_population_complete"])
        self.assertFalse(effect["benchmark_gate_passed"])
        self.assertFalse(effect["architecture_gate_passed"])
        self.assertTrue(effect["h4_development_allowed"])
        self.assertFalse(effect["h4_qualification_allowed"])
        self.assertFalse(effect["h4_release_allowed"])
        self.assertFalse(effect["automatic_reserve3_authorized"])


if __name__ == "__main__":
    unittest.main()
