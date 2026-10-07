from __future__ import annotations

import json
import unittest
from pathlib import Path


class Reserve2ConsolidationWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        project = Path(__file__).resolve().parents[1]
        repo_root = project.parents[3]
        cls.workflow = (
            repo_root / ".github" / "workflows" / "h392-reserve2-consolidation.yml"
        ).read_text(encoding="utf-8")
        cls.integrity = (
            repo_root / ".github" / "workflows" / "hadith-h392.yml"
        ).read_text(encoding="utf-8")
        cls.status = json.loads(
            (project / "artifacts" / "H3.9.2-STATUS.json").read_text(encoding="utf-8")
        )

    def test_workflow_is_manual_main_only_and_has_no_editable_evidence_inputs(self):
        self.assertIn("workflow_dispatch:", self.workflow)
        dispatch = self.workflow.split("workflow_dispatch:", 1)[1].split(
            "permissions:", 1
        )[0]
        self.assertNotIn("inputs:", dispatch)
        self.assertIn('GITHUB_REF_NAME:-', self.workflow)
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
        self.assertNotIn("actions/checkout@v", self.workflow)
        self.assertNotIn("actions/setup-python@v", self.workflow)
        self.assertNotIn("actions/upload-artifact@v", self.workflow)

    def test_schema29_target_and_exact_execution_provenance_are_verified(self):
        self.assertIn('status.get("freeze_schema_version", 0)) != 29', self.workflow)
        self.assertIn('status.get("reserve2_consolidation_target")', self.workflow)
        self.assertIn('"successful_run_attempt", "source_run_attempt"', self.workflow)
        self.assertIn("validate_frozen_capacity_extension", self.workflow)
        self.assertIn("require_execution_enabled=False", self.workflow)
        self.assertIn("reserve2 expected outcome accounting mismatch", self.workflow)

    def test_artifact_acquisition_is_id_hash_and_job_bound(self):
        self.assertIn('actions/artifacts/{aggregate_id}', self.workflow)
        self.assertIn('actions/artifacts/{artifact_id}', self.workflow)
        self.assertIn('actions/jobs/{job_id}', self.workflow)
        self.assertNotIn("pattern: h392-curation-chunk-*", self.workflow)
        self.assertIn('target["aggregate_artifact_digest"]', self.workflow)
        self.assertIn('reviewed["artifact_digest"]', self.workflow)
        self.assertIn('reviewed["summary_sha256"]', self.workflow)
        self.assertIn('reviewed["encrypted_bundle_sha256"]', self.workflow)
        self.assertIn("artifact timestamp escapes bound shard job", self.workflow)

    def test_aggregate_and_shards_are_reserve2_capacity_bound(self):
        fetch = self.workflow.split(
            "- name: Fetch exact reserve2 aggregate and shard artifacts", 1
        )[1].split(
            "- name: Decrypt reserve2 source-bearing evidence into ephemeral workspace", 1
        )[0]
        self.assertIn("approved_non_holdout_reserve2_campaign_summary", fetch)
        self.assertIn("RESERVE2_CAMPAIGN_SUMMARY.json", fetch)
        self.assertIn('capacity_extension_manifest_sha256', fetch)
        self.assertIn('task_scope") != "approved_capacity_extension"', fetch)
        self.assertIn('capacity_extension_sha256', fetch)
        self.assertIn('source_job_id', fetch)
        self.assertIn('"github_run_attempt": int(reviewed["run_attempt"])', fetch)

    def test_consolidation_reacquires_sources_and_uses_capacity_bound_cli(self):
        self.assertIn("acquire-sources", self.workflow)
        self.assertIn("verify-source-cache", self.workflow)
        section = self.workflow.split(
            "- name: Consolidate approved reserve2 evidence", 1
        )[1].split(
            "- name: Encrypt consolidated reserve2 source-bearing evidence", 1
        )[0]
        self.assertIn("consolidate-reserve2", section)
        self.assertIn("--capacity-extension", section)
        self.assertIn("--source-cache-dir", section)
        self.assertNotIn("--activation", section)

    def test_upload_surface_is_only_redacted_summary_and_encrypted_bundle(self):
        section = self.workflow.split(
            "- name: Remove decrypted reserve2 evidence and prove upload is redacted", 1
        )[1].split(
            "- name: Reconfirm main before publishing reserve2 consolidation", 1
        )[0]
        self.assertIn("RESERVE2_CONSOLIDATION_SUMMARY.json", section)
        self.assertIn(
            "h392-reserve2-consolidated-source-bearing.tar.gz.aesgcm", section
        )
        self.assertIn(
            "ENCRYPTED_RESERVE2_CONSOLIDATED_BUNDLE_SHA256.txt", section
        )
        self.assertIn("actual != expected", section)
        upload = self.workflow.split(
            "- name: Upload encrypted reserve2 consolidation and redacted summary", 1
        )[1]
        self.assertIn("h392-reserve2-consolidated-evidence", upload)
        self.assertIn("/tmp/h392-reserve2-consolidation/redacted", upload)

    def test_repository_target_preserves_exact_five_artifact_lineage(self):
        target = self.status["reserve2_consolidation_target"]
        self.assertEqual(target["source_run_id"], 37613354755)
        self.assertEqual(target["source_run_attempt"], 1)
        self.assertEqual(target["aggregate_artifact_id"], 11478509807)
        artifacts = sorted(target["source_artifacts"], key=lambda row: row["task_offset"])
        self.assertEqual(
            [(row["task_offset"], row["task_limit"]) for row in artifacts],
            [(0, 2), (2, 2), (4, 2), (6, 2), (8, 2)],
        )
        self.assertEqual(len({row["artifact_id"] for row in artifacts}), 5)
        self.assertEqual(len({row["source_job_id"] for row in artifacts}), 5)

    def test_integrity_ci_covers_schema29_workflow_and_is_pinned(self):
        self.assertIn(
            '".github/workflows/h392-reserve2-consolidation.yml"',
            self.integrity,
        )
        self.assertIn(
            "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
            self.integrity,
        )
        self.assertIn(
            "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
            self.integrity,
        )


if __name__ == "__main__":
    unittest.main()
