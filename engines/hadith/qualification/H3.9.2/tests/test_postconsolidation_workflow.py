from __future__ import annotations

import unittest
from pathlib import Path


class PostConsolidationWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        project = Path(__file__).resolve().parents[1]
        cls.workflow = (
            project.parents[3]
            / ".github"
            / "workflows"
            / "h392-postconsolidation-prepare.yml"
        ).read_text(encoding="utf-8")

    def test_workflow_is_manual_main_only_and_stale_resistant(self):
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertIn("GITHUB_REF_NAME:-", self.workflow)
        self.assertIn("git ls-remote origin refs/heads/main", self.workflow)
        self.assertGreaterEqual(
            self.workflow.count("Refusing stale") + self.workflow.count("Main advanced"),
            2,
        )

    def test_actions_are_commit_pinned(self):
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

    def test_secret_is_step_scoped_and_never_a_dispatch_input(self):
        self.assertNotIn("commitment_secret:", self.workflow)
        self.assertNotIn("artifact_key:", self.workflow)
        self.assertGreaterEqual(
            self.workflow.count(
                "ARTIFACT_KEY: ${{ secrets.H392_CURATION_ARTIFACT_KEY }}"
            ),
            3,
        )
        job_env = self.workflow.split("steps:", 1)[0]
        self.assertNotIn("H392_CURATION_ARTIFACT_KEY", job_env)

    def test_protocol_state_is_frozen_and_fail_closed(self):
        for needle in (
            'freeze_schema_version", 0)) != 26',
            'prep.get("ready") is not True',
            'prep.get("completed") is not False',
            'source_cumulative_freeze_schema", 0)) != 25',
            'expected_primary_task_count", 0)) != 210',
            'expected_pending_adjudication_count", -1)) != 129',
            'expected_authorized_reserve_count", -1)) != 41',
            'status.get("reserve_reconciliation_enabled") is not False',
            'prep.get("reserve_reconciliation_enabled") is not False',
            'prep.get("adjudication_execution_enabled") is not False',
        ):
            self.assertIn(needle, self.workflow)

    def test_cumulative_artifact_download_is_digest_bound_without_token_forwarding(self):
        self.assertIn("class NoRedirect", self.workflow)
        self.assertIn("artifact_download_location", self.workflow)
        self.assertIn('parsed.scheme != "https"', self.workflow)
        self.assertIn("archive_download_url", self.workflow)
        self.assertIn("unauthenticated = urllib.request.Request", self.workflow)
        self.assertIn("downloaded cumulative artifact ZIP digest mismatch", self.workflow)
        self.assertIn("frozen cumulative summary digest mismatch", self.workflow)
        self.assertIn("frozen cumulative encrypted-bundle digest mismatch", self.workflow)
        self.assertIn("frozen cumulative artifact is not owned by the bound run", self.workflow)
        self.assertIn("frozen cumulative artifact head SHA differs from the bound run", self.workflow)
        self.assertIn(
            'len([p for p in extracted.rglob("*") if p.is_file()]) != 3',
            self.workflow,
        )

    def test_archive_extraction_rejects_links_and_devices(self):
        self.assertIn('p.is_absolute() or ".." in p.parts or stat.S_ISLNK(mode)', self.workflow)
        self.assertIn("member.issym()", self.workflow)
        self.assertIn("member.islnk()", self.workflow)
        self.assertIn("member.isdev()", self.workflow)
        self.assertIn('filter="data"', self.workflow)

    def test_preparation_uses_schema26_cli_and_keeps_execution_disabled(self):
        self.assertIn("prepare-postconsolidation", self.workflow)
        self.assertIn(
            "--control-evidence artifacts/CUMULATIVE_PRIMARY_EVIDENCE_210.json",
            self.workflow,
        )
        self.assertIn("--commitment-secret-env ARTIFACT_KEY", self.workflow)
        self.assertIn("preparation output unexpectedly enables reserves", self.workflow)
        self.assertIn("preparation output unexpectedly enables adjudication", self.workflow)
        self.assertIn("len(leaves) != 41", self.workflow)
        self.assertIn("len(adjudication) != 129", self.workflow)

    def test_plaintext_cleanup_runs_even_after_failure(self):
        self.assertIn("name: Cleanup decrypted and private plaintext", self.workflow)
        self.assertIn("if: always()", self.workflow)
        self.assertIn(
            'rm -rf "$CUMULATIVE_DIR" "$PRIVATE_DIR" "$CUMULATIVE_ARTIFACT_DIR"',
            self.workflow,
        )
        self.assertIn(
            'rm -f "$RUNNER_TEMP/h392-postconsolidation-private.tar.gz"',
            self.workflow,
        )

    def test_only_redacted_bindings_and_encrypted_private_map_are_uploaded(self):
        for name in (
            "POSTCONSOLIDATION_BINDING.json",
            "POSTCONSOLIDATION_SUMMARY.json",
            "h392-postconsolidation-private.tar.gz.aesgcm",
            "ENCRYPTED_POSTCONSOLIDATION_PRIVATE_SHA256.txt",
        ):
            self.assertIn(name, self.workflow)
        self.assertIn(
            'find "$PUBLIC_DIR" -mindepth 1 -maxdepth 1 | wc -l)" -eq 4',
            self.workflow,
        )
        self.assertIn(
            'find "$PUBLIC_DIR" -mindepth 1 -maxdepth 1 -type f | wc -l)" -eq 4',
            self.workflow,
        )
        self.assertIn('test ! -e "$PUBLIC_DIR/PRIVATE_MANIFEST.json"', self.workflow)
        self.assertIn(
            'test ! -e "$PUBLIC_DIR/RESERVE_AUTHORIZATION_PRIVATE.json"',
            self.workflow,
        )
        self.assertIn(
            'test ! -e "$PUBLIC_DIR/ADJUDICATION_QUEUE_PRIVATE.jsonl"',
            self.workflow,
        )
        self.assertIn("name: h392-postconsolidation-preparation", self.workflow)
        self.assertIn("retention-days: 30", self.workflow)


if __name__ == "__main__":
    unittest.main()
