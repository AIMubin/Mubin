from __future__ import annotations

import json
import unittest
from pathlib import Path


class ReserveExecutionWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        project = Path(__file__).resolve().parents[1]
        repo_root = project.parents[3]
        cls.workflow = (repo_root / ".github" / "workflows" / "h392-reserve-campaign.yml").read_text(encoding="utf-8")
        cls.pilot = (repo_root / ".github" / "workflows" / "h392-curation-pilot.yml").read_text(encoding="utf-8")
        cls.integrity = (repo_root / ".github" / "workflows" / "hadith-h392.yml").read_text(encoding="utf-8")
        cls.status = json.loads((project / "artifacts" / "H3.9.2-STATUS.json").read_text(encoding="utf-8"))

    def test_reserve_campaign_is_manual_main_only_and_stale_resistant(self):
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertIn('test "${GITHUB_REF_NAME:-}" = "main"', self.workflow)
        self.assertGreaterEqual(self.workflow.count("git ls-remote origin refs/heads/main"), 2)
        self.assertIn("Refusing stale reserve execution", self.workflow)
        self.assertIn("Main advanced during reserve readiness", self.workflow)

    def test_secret_bearing_actions_are_commit_pinned(self):
        for action in (
            "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
            "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
            "actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093",
            "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
        ):
            self.assertIn(action, self.workflow)
        self.assertNotIn("actions/checkout@v", self.workflow)
        self.assertNotIn("actions/setup-python@v", self.workflow)
        self.assertNotIn("actions/download-artifact@v", self.workflow)
        self.assertNotIn("actions/upload-artifact@v", self.workflow)

    def test_execution_target_is_repository_reviewed_and_exactly_41(self):
        target = self.status["reserve_execution_target"]
        self.assertTrue(target["ready"])
        self.assertFalse(target["completed"])
        self.assertEqual(target["workflow"], ".github/workflows/h392-reserve-campaign.yml")
        self.assertEqual(target["task_scope"], "approved_reserve")
        self.assertEqual(target["expected_task_count"], 41)
        self.assertEqual(target["activation_manifest_sha256"], self.status["reserve_activation"]["manifest_sha256"])
        self.assertEqual(target["cumulative_ledger_sha256"], self.status["reserve_activation"]["cumulative_ledger_sha256"])
        self.assertEqual(target["replacement_eligibility_sha256"], self.status["reserve_activation"]["replacement_eligibility_sha256"])

    def test_campaign_revalidates_activation_and_target(self):
        section = self.workflow.split("- name: Validate approved reserve target and plan deterministic shards", 1)[1].split("- name: Run offline readiness suite", 1)[0]
        self.assertIn("validate_reserve_activation", section)
        self.assertIn('status.get("reserve_reconciliation_enabled") is not True', section)
        self.assertIn('target.get("ready") is not True', section)
        self.assertIn('target.get("completed") is not False', section)
        self.assertIn('target.get("task_scope") != "approved_reserve"', section)
        self.assertIn("expected != 41", section)
        self.assertIn("activation_manifest_sha256", section)

    def test_reusable_pilot_keeps_manual_dispatch_primary_only(self):
        dispatch = self.pilot.split("  workflow_call:", 1)[0]
        reusable = self.pilot.split("  workflow_call:", 1)[1].split("\npermissions:", 1)[0]
        self.assertNotIn("task_scope:", dispatch)
        self.assertIn("task_scope:", reusable)
        self.assertIn('default: "primary"', reusable)
        self.assertIn("TASK_SCOPE:", self.pilot)

    def test_pilot_selects_only_hash_approved_reserve_ids(self):
        section = self.pilot.split("- name: Select deterministic task chunk", 1)[1].split("- name: Create protected execution configs", 1)[0]
        self.assertIn('scope == "approved_reserve"', section)
        self.assertIn("validate_reserve_activation", section)
        self.assertIn("activated reserve tasks missing from Factory output", section)
        self.assertIn('candidate_slot_kind") != "reserve"', section)
        self.assertIn('"reserve_activation_sha256"', section)

    def test_pilot_reconciliation_requires_activation_only_for_reserve_scope(self):
        section = self.pilot.split("- name: Reconcile source evidence and policy gates", 1)[1].split("- name: Build redacted run summary", 1)[0]
        self.assertIn('if [ "$TASK_SCOPE" = "approved_reserve" ]', section)
        self.assertIn("--reserve-activation", section)
        self.assertIn('status["reserve_activation"]["evidence_path"]', section)
        self.assertIn('"${extra[@]}"', section)

    def test_campaign_runs_all_41_slots_in_bounded_parallel_shards(self):
        self.assertIn("shard_size = 8", self.workflow)
        self.assertIn("max-parallel: 4", self.workflow)
        self.assertIn("fail-fast: false", self.workflow)
        self.assertIn("uses: ./.github/workflows/h392-curation-pilot.yml", self.workflow)
        self.assertIn("task_scope: approved_reserve", self.workflow)
        self.assertIn("skip_readiness: true", self.workflow)

    def test_aggregate_requires_exact_redacted_coverage(self):
        section = self.workflow.split("- name: Aggregate approved reserve outcomes", 1)[1].split("- name: Publish approved reserve campaign summary", 1)[0]
        self.assertIn("CURATION_RUN_SUMMARY.json", section)
        self.assertNotIn("curator-responses.jsonl", section)
        self.assertNotIn("verifier-responses.jsonl", section)
        self.assertNotIn("adjudication.jsonl", section)
        self.assertIn('row.get("task_scope") != "approved_reserve"', section)
        self.assertIn("activation_sha_mismatch", section)
        self.assertIn("gap_or_overlap", section)
        self.assertIn("task_count_mismatch", section)
        self.assertIn("outcome_accounting_mismatch", section)
        self.assertIn('"contains_source_text": False', section)
        self.assertIn('"contains_gold_payloads": False', section)

    def test_pilot_encrypts_source_bearing_reserve_evidence(self):
        self.assertIn("benchmark_campaign.artifact_crypto encrypt", self.pilot)
        self.assertIn("h392-curation-source-bearing.tar.gz.aesgcm", self.pilot)
        upload = self.pilot.split("- name: Upload encrypted curation bundle and redacted summary", 1)[1]
        self.assertIn("path: /tmp/h392-curation/redacted", upload)
        self.assertNotIn("RUN_DIR", upload)

    def test_integrity_ci_covers_reserve_execution_workflow(self):
        self.assertIn('\".github/workflows/h392-reserve-campaign.yml\"', self.integrity)


if __name__ == "__main__":
    unittest.main()
