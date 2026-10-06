from __future__ import annotations

import unittest
from pathlib import Path


class ReserveActivationWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        project = Path(__file__).resolve().parents[1]
        repo_root = project.parents[3]
        cls.workflow = (
            repo_root / ".github" / "workflows" / "h392-reserve-activation.yml"
        ).read_text(encoding="utf-8")
        cls.integrity = (
            repo_root / ".github" / "workflows" / "hadith-h392.yml"
        ).read_text(encoding="utf-8")

    def test_workflow_is_manual_main_only_and_stale_resistant(self):
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertIn('test "${GITHUB_REF_NAME:-}" = "main"', self.workflow)
        self.assertIn("git ls-remote origin refs/heads/main", self.workflow)
        self.assertIn("Refusing stale workflow execution", self.workflow)
        self.assertGreaterEqual(
            self.workflow.count("git ls-remote origin refs/heads/main"),
            2,
        )

    def test_secret_bearing_actions_are_commit_pinned(self):
        self.assertIn(
            "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
            self.workflow,
        )
        self.assertIn(
            "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
            self.workflow,
        )
        self.assertIn(
            "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
            self.workflow,
        )
        self.assertNotIn("actions/checkout@v", self.workflow)
        self.assertNotIn("actions/setup-python@v", self.workflow)
        self.assertNotIn("actions/upload-artifact@v", self.workflow)

    def test_target_is_bound_to_completed_cumulative_evidence(self):
        section = self.workflow.split(
            "- name: Validate reviewed activation target", 1
        )[1].split("- name: Fetch and verify frozen cumulative artifact", 1)[0]
        self.assertIn('status.get("freeze_schema_version", 0)) != 26', section)
        self.assertIn('status.get("reserve_reconciliation_enabled") is not False', section)
        self.assertIn('status.get("reserve_activation_target")', section)
        self.assertIn('target.get("ready") is not True', section)
        self.assertIn('target.get("completed") is not False', section)
        self.assertIn('"source_cumulative_run_id"', section)
        self.assertIn('"cumulative_ledger_sha256"', section)
        self.assertIn('"replacement_eligibility_sha256"', section)
        self.assertIn('"expected_eligible_primary_count"', section)

    def test_source_artifact_is_digest_and_provenance_bound(self):
        section = self.workflow.split(
            "- name: Fetch and verify frozen cumulative artifact", 1
        )[1].split("- name: Decrypt cumulative evidence ephemerally", 1)[0]
        self.assertIn('run.get("run_attempt", 0)', section)
        self.assertIn('run.get("head_branch") != "main"', section)
        self.assertIn('run.get("path") != ".github/workflows/h392-cumulative-consolidation.yml"', section)
        self.assertIn('artifact.get("digest") != expected_digest', section)
        self.assertIn("hashlib.sha256(archive.read_bytes()).hexdigest()", section)
        self.assertIn("unsafe artifact ZIP member", section)
        self.assertIn("CUMULATIVE_SUMMARY.json", section)
        self.assertIn("h392-cumulative-source-bearing.tar.gz.aesgcm", section)
        self.assertIn("encrypted cumulative bundle digest mismatch", section)

    def test_decrypt_step_matches_artifact_crypto_cli_contract(self):
        section = self.workflow.split(
            "- name: Decrypt cumulative evidence ephemerally", 1
        )[1].split("- name: Build hash-bound reserve activation manifest", 1)[0]
        self.assertIn("--input", section)
        self.assertIn("--output", section)
        self.assertIn("--passphrase-env", section)
        self.assertNotIn("--in ", section)
        self.assertNotIn("--out ", section)
        self.assertNotIn("--key-env", section)

    def test_activation_builder_consumes_exact_reviewed_hashes(self):
        section = self.workflow.split(
            "- name: Build hash-bound reserve activation manifest", 1
        )[1].split(
            "- name: Prove activation upload is redacted", 1
        )[0]
        self.assertIn("build-reserve-activation", section)
        self.assertIn("--expected-cumulative-ledger-sha256", section)
        self.assertIn("--expected-replacement-eligibility-sha256", section)

    def test_only_redacted_activation_manifest_is_uploaded(self):
        section = self.workflow.split(
            "- name: Prove activation upload is redacted", 1
        )[1].split(
            "- name: Reconfirm main before publishing activation evidence", 1
        )[0]
        self.assertIn('files != ["RESERVE_ACTIVATION.json"]', section)
        self.assertIn("reserve_reconciliation_authorized", section)
        self.assertIn("requires_repository_approval", section)
        self.assertIn("expected_activated_reserve_slot_count", section)
        self.assertIn("activated_reserve_slot_count", section)
        for forbidden in ("source_refs", "excerpt", "payload", "gold", "model_ref", "model_family"):
            self.assertIn(forbidden, section)
        upload = self.workflow.split("- name: Upload reserve activation evidence", 1)[1]
        self.assertIn("h392-reserve-activation-evidence", upload)
        self.assertIn("/tmp/h392-post-consolidation/redacted", upload)
        self.assertNotIn("CUMULATIVE_DIR", upload)

    def test_integrity_ci_covers_activation_workflow(self):
        self.assertIn(
            '".github/workflows/h392-reserve-activation.yml"',
            self.integrity,
        )


if __name__ == "__main__":
    unittest.main()
