from __future__ import annotations

import json
import unittest
from pathlib import Path


class ReserveConsolidationWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        project = Path(__file__).resolve().parents[1]
        repo_root = project.parents[3]
        cls.workflow = (
            repo_root / ".github" / "workflows" / "h392-reserve-consolidation.yml"
        ).read_text(encoding="utf-8")
        cls.integrity = (
            repo_root / ".github" / "workflows" / "hadith-h392.yml"
        ).read_text(encoding="utf-8")
        cls.status = json.loads(
            (project / "artifacts" / "H3.9.2-STATUS.json").read_text(encoding="utf-8")
        )

    def test_workflow_is_manual_main_only_and_stale_resistant(self):
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertIn('GITHUB_REF_NAME:-', self.workflow)
        self.assertGreaterEqual(
            self.workflow.count("git ls-remote origin refs/heads/main"), 3
        )
        self.assertIn("Refusing stale reserve consolidation", self.workflow)
        self.assertIn(
            "Main advanced while reserve evidence was being acquired",
            self.workflow,
        )
        self.assertIn(
            "Main advanced before reserve consolidation publication",
            self.workflow,
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

    def test_workflow_consumes_only_repository_reviewed_exact_artifacts(self):
        self.assertIn('actions/artifacts/{aggregate_id}', self.workflow)
        self.assertIn('actions/artifacts/{artifact_id}', self.workflow)
        self.assertNotIn("pattern: h392-curation-chunk-*", self.workflow)
        self.assertIn('target["source_artifacts"]', self.workflow)
        self.assertIn('target["aggregate_artifact_id"]', self.workflow)
        self.assertIn("artifact ZIP digest mismatch", self.workflow)
        self.assertIn("summary SHA-256 mismatch", self.workflow)
        self.assertIn("encrypted bundle SHA-256 mismatch", self.workflow)

    def test_mixed_attempt_provenance_is_bound_to_exact_job_ids(self):
        self.assertIn('actions/jobs/{job_id}', self.workflow)
        self.assertIn('job.get("run_attempt"', self.workflow)
        self.assertIn('reviewed["run_attempt"]', self.workflow)
        self.assertIn('"source_job_id": job_id', self.workflow)
        self.assertIn('"github_run_attempt": int(reviewed["run_attempt"])', self.workflow)
        self.assertIn("artifact timestamp escapes bound shard job", self.workflow)

    def test_aggregate_success_is_verified_before_source_bearing_decryption(self):
        fetch = self.workflow.split(
            "- name: Fetch exact reserve aggregate and shard artifacts", 1
        )[1].split(
            "- name: Decrypt reserve source-bearing evidence into ephemeral workspace", 1
        )[0]
        self.assertIn("approved_non_holdout_reserve_campaign_summary", fetch)
        self.assertIn('coverage_complete") is not True', fetch)
        self.assertIn('shard_job_result") != "success"', fetch)
        self.assertIn('target["expected_outcomes"]', fetch)
        self.assertIn('target["activation_manifest_sha256"]', fetch)

    def test_consolidation_reacquires_sources_and_uses_activation_bound_cli(self):
        self.assertIn("acquire-sources", self.workflow)
        self.assertIn("verify-source-cache", self.workflow)
        section = self.workflow.split(
            "- name: Consolidate approved reserve evidence", 1
        )[1].split(
            "- name: Encrypt consolidated reserve source-bearing evidence", 1
        )[0]
        self.assertIn("consolidate-reserve", section)
        self.assertIn("--activation", section)
        self.assertIn("--source-cache-dir", section)
        self.assertIn("reserve_activation", section)

    def test_upload_surface_is_exactly_redacted_summary_and_encrypted_bundle(self):
        section = self.workflow.split(
            "- name: Remove decrypted reserve evidence and prove upload is redacted", 1
        )[1].split(
            "- name: Reconfirm main before publishing reserve consolidation", 1
        )[0]
        self.assertIn("RESERVE_CONSOLIDATION_SUMMARY.json", section)
        self.assertIn(
            "h392-reserve-consolidated-source-bearing.tar.gz.aesgcm", section
        )
        self.assertIn(
            "ENCRYPTED_RESERVE_CONSOLIDATED_BUNDLE_SHA256.txt", section
        )
        self.assertIn("actual != expected", section)
        upload = self.workflow.split(
            "- name: Upload encrypted reserve consolidation and redacted summary", 1
        )[1]
        self.assertIn("h392-reserve-consolidated-evidence", upload)
        self.assertIn("/tmp/h392-reserve-consolidation/redacted", upload)

    def test_repository_target_is_hash_bound_to_successful_execution(self):
        target = self.status["reserve_consolidation_target"]
        self.assertEqual(target["source_run_id"], 37532437191)
        self.assertEqual(target["source_run_final_attempt"], 2)
        self.assertEqual(
            target["source_head_sha"],
            "5fdeb0d8a7446a319c0bf21477d1ac916e2d7fc7",
        )
        self.assertEqual(target["aggregate_artifact_id"], 11460611920)
        self.assertEqual(
            target["aggregate_artifact_digest"],
            "sha256:f00b363321838289034388af9953cb11fde6709acf4780c210acd931bb3003a9",
        )
        self.assertEqual(
            target["aggregate_summary_sha256"],
            "8638a50d177ea716fa429fe0f5cc356203a2ff081072212c3edaf47e05b394d0",
        )
        self.assertEqual(
            target["activation_manifest_sha256"],
            self.status["reserve_activation"]["manifest_sha256"],
        )

    def test_integrity_ci_covers_reserve_consolidation_workflow(self):
        self.assertIn(
            '".github/workflows/h392-reserve-consolidation.yml"',
            self.integrity,
        )


if __name__ == "__main__":
    unittest.main()
