from __future__ import annotations

import json
import unittest
from pathlib import Path


class Schema31DecisionTemplateWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        project = Path(__file__).resolve().parents[1]
        repo_root = project.parents[3]
        cls.workflow = (
            repo_root / ".github" / "workflows" / "h392-schema31-decision-template.yml"
        ).read_text(encoding="utf-8")
        cls.integrity = (
            repo_root / ".github" / "workflows" / "hadith-h392.yml"
        ).read_text(encoding="utf-8")
        cls.status = json.loads(
            (project / "artifacts" / "H3.9.2-STATUS.json").read_text(encoding="utf-8")
        )

    def test_manual_main_only_without_editable_inputs(self):
        self.assertIn("workflow_dispatch:", self.workflow)
        dispatch = self.workflow.split("workflow_dispatch:", 1)[1].split(
            "permissions:", 1
        )[0]
        self.assertNotIn("inputs:", dispatch)
        self.assertIn('test "${GITHUB_REF_NAME:-}" = "main"', self.workflow)
        self.assertGreaterEqual(
            self.workflow.count("git ls-remote origin refs/heads/main"), 3
        )

    def test_exact_schema30_packet_is_hash_and_metadata_bound(self):
        for value in (
            "11526263194",
            "h392-adjudication-packet",
            "sha256:0333a36089ece40573d67cce106879dbc638892d00fed98890f91f2699ff6947",
            "5f154c631b6a0fd6494b329c62e863e26512a0aa17211daa13c56435dd8637fd",
            "44df7e629adb56a8a822a08de95f1025f439db40cd7a3501028be114b2c5eb27",
            "e4c4d89429d445502b128a3cd32dfb15d27628684b627202dd0081e2dd51abf2",
        ):
            self.assertIn(value, self.workflow)
        self.assertIn("Schema-30 decrypted packet surface mismatch", self.workflow)
        self.assertIn("legacy Schema-30 decision-template SHA mismatch", self.workflow)

    def test_migration_is_fail_closed_until_template_freeze(self):
        self.assertIn('surface.get("human_review_authorized") is not False', self.workflow)
        self.assertIn('surface.get("decision_ingestion_authorized") is not False', self.workflow)
        self.assertIn('get("automatic_reserve3_authorized") is not False', self.workflow)

    def test_new_template_forbids_legacy_unattested_decision(self):
        self.assertIn("build-schema31-decision-template", self.workflow)
        self.assertIn('if "decision" in row:', self.workflow)
        self.assertIn('row.get("reviews")!=[]', self.workflow)
        self.assertIn('row.get("terminal_signoff") is not None', self.workflow)
        self.assertIn(
            'row.get("reviewer_registry_snapshot_sha256") is not None',
            self.workflow,
        )

    def test_secret_bearing_outputs_are_encrypted_and_redacted(self):
        self.assertIn("H392_CURATION_ARTIFACT_KEY", self.workflow)
        self.assertIn("h392-schema31-decision-template.tar.gz.aesgcm", self.workflow)
        self.assertIn("ENCRYPTED_SCHEMA31_DECISION_TEMPLATE_SHA256.txt", self.workflow)
        self.assertIn("SCHEMA31_DECISION_TEMPLATE_SUMMARY.json", self.workflow)
        self.assertIn("h392-schema31-decision-template", self.workflow)

    def test_repository_target_is_open_and_review_remains_closed(self):
        target = self.status["adjudication_decision_template_target"]
        self.assertTrue(target["ready"])
        self.assertFalse(target["completed"])
        self.assertEqual(target["protocol_freeze_schema"], 31)
        self.assertEqual(target["expected_case_count"], 158)
        self.assertEqual(target["source_packet_artifact_id"], 11526263194)
        self.assertFalse(
            self.status["adjudication_review_surface"]["human_review_authorized"]
        )

    def test_integrity_ci_covers_template_workflow(self):
        self.assertIn(
            '".github/workflows/h392-schema31-decision-template.yml"',
            self.integrity,
        )


if __name__ == "__main__":
    unittest.main()
