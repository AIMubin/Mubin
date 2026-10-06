from __future__ import annotations

import unittest
from pathlib import Path


class ConsolidationWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        project = Path(__file__).resolve().parents[1]
        repo_root = project.parents[3]
        cls.workflow = (
            repo_root / ".github" / "workflows" / "h392-cumulative-consolidation.yml"
        ).read_text(encoding="utf-8")
        cls.integrity = (
            repo_root / ".github" / "workflows" / "hadith-h392.yml"
        ).read_text(encoding="utf-8")

    def test_integrity_ci_covers_consolidation_workflow(self):
        self.assertGreaterEqual(
            self.integrity.count(
                '".github/workflows/h392-cumulative-consolidation.yml"'
            ),
            2,
        )

    def test_secret_bearing_workflow_pins_third_party_actions(self):
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

    def test_workflow_is_main_only_and_refuses_stale_dispatch(self):
        self.assertIn('GITHUB_REF_NAME:-', self.workflow)
        self.assertIn("git ls-remote origin refs/heads/main", self.workflow)
        self.assertIn("Refusing stale cumulative consolidation", self.workflow)

    def test_workflow_binds_each_input_to_successful_campaign_main_run(self):
        self.assertIn('run.get("conclusion") != "success"', self.workflow)
        self.assertIn('run.get("head_branch") != "main"', self.workflow)
        self.assertIn(
            'run.get("path") != ".github/workflows/h392-curation-campaign.yml"',
            self.workflow,
        )
        self.assertIn('run.get("event") != "workflow_dispatch"', self.workflow)
        self.assertIn('artifact.get("digest")', self.workflow)
        self.assertIn("artifact ZIP digest mismatch", self.workflow)
        self.assertIn("encrypted source-bearing bundle digest mismatch", self.workflow)

    def test_canonical_history_rejects_rerun_ambiguity(self):
        self.assertIn('int(run.get("run_attempt", 0)) != 1', self.workflow)
        self.assertIn(
            "canonical consolidation accepts only attempt 1",
            self.workflow,
        )

    def test_promotions_are_regrounded_in_verified_source_cache(self):
        self.assertIn(
            "Acquire and verify pinned non-holdout sources for evidence grounding",
            self.workflow,
        )
        self.assertIn(
            'python -m benchmark_campaign verify-source-cache',
            self.workflow,
        )
        self.assertIn(
            '--source-cache-dir "$SOURCE_CACHE_DIR"',
            self.workflow,
        )
        self.assertIn(
            'rm -rf "$EVIDENCE_ROOT" "$CUMULATIVE_DIR" "$SOURCE_CACHE_DIR"',
            self.workflow,
        )

    def test_artifact_redirect_does_not_forward_github_token(self):
        self.assertIn("class NoRedirect", self.workflow)
        self.assertIn("artifact_download_location", self.workflow)
        self.assertIn("urllib.parse.urlparse(location)", self.workflow)
        self.assertIn('headers={"User-Agent": "mubin-h392-consolidation"}', self.workflow)
        download_block = self.workflow.split(
            "download_url = artifact_download_location", 1
        )[1].split("safe_unzip(archive, raw_dir)", 1)[0]
        self.assertNotIn('"Authorization"', download_block)

    def test_archive_extraction_is_fail_closed(self):
        self.assertIn("unsafe artifact ZIP member", self.workflow)
        self.assertIn("unsafe source-bearing tar member", self.workflow)
        self.assertIn("member.issym()", self.workflow)
        self.assertIn("member.islnk()", self.workflow)
        self.assertIn('filter="data"', self.workflow)

    def test_artifact_key_is_not_job_scoped(self):
        job_env = self.workflow.split("    env:\n", 1)[1].split(
            "\n\n    steps:", 1
        )[0]
        self.assertNotIn("H392_CURATION_ARTIFACT_KEY", job_env)
        self.assertNotIn("ARTIFACT_KEY", job_env)
        self.assertIn(
            "ARTIFACT_KEY: ${{ secrets.H392_CURATION_ARTIFACT_KEY }}",
            self.workflow,
        )

    def test_workflow_uploads_only_redacted_summary_and_encrypted_bundle(self):
        upload = self.workflow.split(
            "- name: Upload encrypted cumulative evidence and redacted summary", 1
        )[1]
        self.assertIn("path: /tmp/h392-cumulative/redacted", upload)
        self.assertNotIn("EVIDENCE_ROOT", upload)
        self.assertNotIn("CUMULATIVE_DIR", upload)
        proof = self.workflow.split(
            "- name: Remove decrypted evidence and prove upload is redacted", 1
        )[1].split(
            "- name: Upload encrypted cumulative evidence and redacted summary", 1
        )[0]
        self.assertIn('rm -rf "$EVIDENCE_ROOT" "$CUMULATIVE_DIR"', proof)
        self.assertIn("CUMULATIVE_LEDGER.jsonl", proof)
        self.assertIn("REPLACEMENT_ELIGIBILITY.json", proof)

    def test_dispatch_inputs_must_match_repository_reviewed_history(self):
        self.assertIn(
            'status["cumulative_consolidation_target"]',
            self.workflow,
        )
        self.assertIn('target["run_ids"]', self.workflow)
        self.assertIn(
            'target["expected_primary_tasks"]',
            self.workflow,
        )
        self.assertIn(
            "run_ids differ from the repository-reviewed canonical campaign history",
            self.workflow,
        )
        self.assertIn(
            "expected_task_count differs from the repository-reviewed canonical prefix",
            self.workflow,
        )
        self.assertIn(
            'status.get("reserve_reconciliation_enabled") is not False',
            self.workflow,
        )
        self.assertIn('status["non_holdout_execution_evidence"]', self.workflow)
        self.assertIn(
            "canonical target run IDs disagree with execution evidence",
            self.workflow,
        )
        self.assertIn(
            "canonical target count disagrees with execution evidence",
            self.workflow,
        )
        self.assertIn(
            "canonical target prefix disagrees with execution evidence",
            self.workflow,
        )

    def test_main_is_reconfirmed_before_consolidation_and_publication(self):
        self.assertGreaterEqual(
            self.workflow.count("git ls-remote origin refs/heads/main"),
            3,
        )
        self.assertIn(
            "Main advanced while cumulative evidence was being acquired",
            self.workflow,
        )
        self.assertIn(
            "Main advanced before cumulative evidence publication",
            self.workflow,
        )

    def test_current_canonical_history_is_explicit(self):
        self.assertIn(
            'default: "37280971913,37295517184,37326459365,37426135905"',
            self.workflow,
        )
        self.assertIn('default: "210"', self.workflow)
        self.assertIn('target.get("ready") is not True', self.workflow)
        self.assertIn('target.get("completed") is not False', self.workflow)
        self.assertIn('target.get("protocol_freeze_schema", 0)', self.workflow)


if __name__ == "__main__":
    unittest.main()
