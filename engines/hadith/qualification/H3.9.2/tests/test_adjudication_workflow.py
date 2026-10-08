from __future__ import annotations

import json
import unittest
from pathlib import Path


class AdjudicationPacketWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        project = Path(__file__).resolve().parents[1]
        repo_root = project.parents[3]
        cls.workflow = (
            repo_root / ".github" / "workflows" / "h392-adjudication-packet.yml"
        ).read_text(encoding="utf-8")
        cls.integrity = (
            repo_root / ".github" / "workflows" / "hadith-h392.yml"
        ).read_text(encoding="utf-8")
        cls.status = json.loads(
            (project / "artifacts" / "H3.9.2-STATUS.json").read_text(encoding="utf-8")
        )

    def test_manual_main_only_without_editable_evidence_inputs(self):
        self.assertIn("workflow_dispatch:", self.workflow)
        dispatch = self.workflow.split("workflow_dispatch:", 1)[1].split(
            "permissions:", 1
        )[0]
        self.assertNotIn("inputs:", dispatch)
        self.assertIn('test "${GITHUB_REF_NAME:-}" = "main"', self.workflow)
        self.assertGreaterEqual(
            self.workflow.count("git ls-remote origin refs/heads/main"), 3
        )

    def test_secret_bearing_actions_are_commit_pinned(self):
        for action in (
            "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
            "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
            "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
        ):
            self.assertIn(action, self.workflow)

    def test_schema30_human_authority_boundary_is_explicit(self):
        self.assertIn('status.get("freeze_schema_version") != 30', self.workflow)
        self.assertIn('"combined_pending_case_count") != 158', self.workflow)
        self.assertIn('"human_or_authority_decision_required") is not True', self.workflow)
        self.assertIn('"ai_may_self_authorize_acceptance") is not False', self.workflow)
        self.assertIn('"automatic_reserve3_authorized") is not False', self.workflow)

    def test_canonical_three_layer_evidence_is_fetched_exactly(self):
        for name in (
            "h392-cumulative-primary-evidence",
            "h392-reserve-consolidated-evidence",
            "h392-reserve2-consolidated-evidence",
        ):
            self.assertIn(name, self.workflow)
        for encrypted in (
            "h392-cumulative-source-bearing.tar.gz.aesgcm",
            "h392-reserve-consolidated-source-bearing.tar.gz.aesgcm",
            "h392-reserve2-consolidated-source-bearing.tar.gz.aesgcm",
        ):
            self.assertIn(encrypted, self.workflow)
        self.assertIn('meta.get("digest")!=bound["artifact_digest"]', self.workflow)
        self.assertIn('encsha!=bound["encrypted_bundle_sha256"]', self.workflow)

    def test_originating_artifacts_are_derived_from_canonical_ledgers(self):
        self.assertIn("derive-adjudication-target", self.workflow)
        self.assertIn('"source_artifacts"', self.workflow)
        self.assertIn('expected["artifact_sha256"]', self.workflow)
        self.assertIn('expected["encrypted_bundle_sha256"]', self.workflow)
        self.assertIn('workflow_by_layer', self.workflow)

    def test_sources_are_reacquired_and_packet_builder_is_capacity_aware(self):
        self.assertIn("acquire-sources", self.workflow)
        self.assertIn("verify-source-cache", self.workflow)
        self.assertIn("build-adjudication-packet", self.workflow)
        self.assertIn("--activation", self.workflow)
        self.assertIn("--capacity-extension", self.workflow)

    def test_public_upload_is_redacted_and_source_packet_is_encrypted(self):
        self.assertIn("ADJUDICATION_PACKET_SUMMARY.json", self.workflow)
        self.assertIn(
            "h392-adjudication-packet-source-bearing.tar.gz.aesgcm", self.workflow
        )
        self.assertIn("ENCRYPTED_ADJUDICATION_PACKET_SHA256.txt", self.workflow)
        self.assertIn("actual!=expected", self.workflow)
        self.assertIn("h392-adjudication-packet", self.workflow)

    def test_repository_target_matches_exact_158_case_surface(self):
        self.assertEqual(self.status["freeze_schema_version"], 31)
        target = self.status["adjudication_packet_target"]
        self.assertEqual(target["protocol_freeze_schema"], 30)
        self.assertFalse(target["ready"])
        self.assertTrue(target["completed"])
        self.assertEqual(target["expected_case_count"], 158)
        self.assertEqual(
            target["layer_counts"],
            {"primary": 129, "reserve01": 24, "reserve02": 5},
        )
        self.assertEqual(target["successful_run_id"], 37722153068)
        self.assertEqual(target["artifact_id"], 11526263194)
        self.assertEqual(
            target["encrypted_bundle_sha256"],
            "5f154c631b6a0fd6494b329c62e863e26512a0aa17211daa13c56435dd8637fd",
        )

    def test_integrity_ci_covers_adjudication_workflow(self):
        self.assertIn(
            '".github/workflows/h392-adjudication-packet.yml"',
            self.integrity,
        )


if __name__ == "__main__":
    unittest.main()
