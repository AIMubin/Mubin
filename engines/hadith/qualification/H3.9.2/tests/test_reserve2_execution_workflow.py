from __future__ import annotations

import json
import unittest
from pathlib import Path


class Reserve2ExecutionWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        project = Path(__file__).resolve().parents[1]
        repo_root = project.parents[3]
        cls.campaign = (
            repo_root / ".github" / "workflows" / "h392-reserve2-campaign.yml"
        ).read_text(encoding="utf-8")
        cls.pilot = (
            repo_root / ".github" / "workflows" / "h392-curation-pilot.yml"
        ).read_text(encoding="utf-8")
        cls.integrity = (
            repo_root / ".github" / "workflows" / "hadith-h392.yml"
        ).read_text(encoding="utf-8")
        cls.status = json.loads(
            (project / "artifacts" / "H3.9.2-STATUS.json").read_text(encoding="utf-8")
        )

    def test_repository_target_is_exactly_ten_executed_reserve2_slots(self):
        self.assertEqual(self.status["freeze_schema_version"], 31)
        self.assertTrue(self.status["capacity_extension_enabled"])
        target = self.status["reserve2_execution_target"]
        self.assertFalse(target["ready"])
        self.assertTrue(target["completed"])
        self.assertTrue(target["execution_succeeded"])
        self.assertFalse(target["consolidation_pending"])
        self.assertEqual(target["successful_run_id"], 37613354755)
        self.assertEqual(target["successful_run_attempt"], 1)
        self.assertEqual(
            target["runner_commit"],
            "d6e04fc061426d2248dba0e9e4f7e5e484b6ae1b",
        )
        self.assertEqual(
            target["canonical_evidence_path"],
            "artifacts/RESERVE2_CONSOLIDATION_EVIDENCE_10.json",
        )
        self.assertEqual(target["workflow"], ".github/workflows/h392-reserve2-campaign.yml")
        self.assertEqual(target["task_scope"], "approved_capacity_extension")
        self.assertEqual(target["expected_task_count"], 10)
        self.assertEqual(target["expected_shards"], 5)
        self.assertEqual(target["shard_size"], 2)
        self.assertFalse(target["adjudication_cases_eligible"])
        self.assertEqual(
            target["capacity_extension_manifest_sha256"],
            self.status["capacity_extension_proposal"]["manifest_sha256"],
        )
        self.assertEqual(
            target["capacity_extension_evidence_path"],
            self.status["capacity_extension_proposal"]["evidence_path"],
        )

    def test_campaign_has_no_task_identity_or_count_inputs(self):
        workflow_dispatch = self.campaign.split("workflow_dispatch:", 1)[1].split(
            "permissions:", 1
        )[0]
        for forbidden in (
            "task_offset:",
            "task_limit:",
            "task_scope:",
            "slot_id:",
            "expected_task_count:",
            "reserve_attempt:",
        ):
            self.assertNotIn(forbidden, workflow_dispatch)

    def test_campaign_is_main_only_exact_manifest_bound_and_pinned(self):
        self.assertIn('test "${GITHUB_REF_NAME:-}" = "main"', self.campaign)
        self.assertIn('status.get("freeze_schema_version", 0)) != 28', self.campaign)
        self.assertIn('status.get("capacity_extension_enabled") is not True', self.campaign)
        self.assertIn("validate_frozen_capacity_extension", self.campaign)
        self.assertIn("require_execution_enabled=True", self.campaign)
        self.assertIn('target.get("expected_task_count", -1)', self.campaign)
        self.assertIn("expected != 10", self.campaign)
        self.assertIn("shard_size = 2", self.campaign)
        self.assertIn("task_scope: approved_capacity_extension", self.campaign)
        for action in (
            "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
            "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
            "actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093",
            "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
        ):
            self.assertIn(action, self.campaign)

    def test_pilot_manual_dispatch_remains_primary_only(self):
        direct = self.pilot.split("workflow_dispatch:", 1)[1].split(
            "workflow_call:", 1
        )[0]
        self.assertNotIn("task_scope:", direct)
        reusable = self.pilot.split("workflow_call:", 1)[1].split(
            "permissions:", 1
        )[0]
        self.assertIn("task_scope:", reusable)
        self.assertIn('default: "primary"', reusable)

    def test_pilot_threads_capacity_overlay_through_every_factory_boundary(self):
        self.assertIn('scope == "approved_capacity_extension"', self.pilot)
        self.assertIn("validate_frozen_capacity_extension", self.pilot)
        self.assertIn("capacity_extension_sha256", self.pilot)
        self.assertIn('--capacity-extension "$extension_path"', self.pilot)
        self.assertGreaterEqual(self.pilot.count("--capacity-extension"), 4)
        self.assertIn('row.get("reserve_attempt") != 2', self.pilot)
        self.assertIn("approved reserve:02 tasks missing from Factory overlay output", self.pilot)

    def test_aggregate_requires_exact_five_shards_and_capacity_hash(self):
        self.assertIn('"kind": "approved_non_holdout_reserve2_campaign_summary"', self.campaign)
        self.assertIn('"capacity_extension_manifest_sha256": expected_capacity', self.campaign)
        self.assertIn('row.get("task_scope") != "approved_capacity_extension"', self.campaign)
        self.assertIn('row.get("capacity_extension_sha256") != expected_capacity', self.campaign)
        self.assertIn('row.get("reserve_activation_sha256") is not None', self.campaign)
        self.assertIn('"coverage_complete": not coverage_errors', self.campaign)
        self.assertIn("h392-approved-reserve2-campaign-summary", self.campaign)

    def test_integrity_ci_covers_reserve2_workflow(self):
        self.assertIn('".github/workflows/h392-reserve2-campaign.yml"', self.integrity)


if __name__ == "__main__":
    unittest.main()
