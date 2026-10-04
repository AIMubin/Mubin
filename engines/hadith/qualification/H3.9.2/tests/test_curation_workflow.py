from __future__ import annotations

import unittest
from pathlib import Path


class CurationWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        project = Path(__file__).resolve().parents[1]
        repo_root = project.parents[3]
        cls.workflow = (repo_root / ".github" / "workflows" / "h392-curation-pilot.yml").read_text(
            encoding="utf-8"
        )
        cls.integrity_workflow = (
            repo_root / ".github" / "workflows" / "hadith-h392.yml"
        ).read_text(encoding="utf-8")
        cls.campaign_workflow = (
            repo_root / ".github" / "workflows" / "h392-curation-campaign.yml"
        ).read_text(encoding="utf-8")

    def test_secret_bearing_workflow_pins_third_party_actions_to_commits(self):
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
        self.assertNotIn("actions/checkout@v4", self.workflow)
        self.assertNotIn("actions/setup-python@v5", self.workflow)
        self.assertNotIn("actions/upload-artifact@v4", self.workflow)

    def test_actions_expressions_are_not_backslash_escaped(self):
        escaped = "\\" + "$" + "{{"
        expected = "$" + "{{ secrets.H392_CURATOR_API_KEY }}"
        self.assertNotIn(escaped, self.workflow)
        self.assertIn(expected, self.workflow)

    def test_workflow_refuses_stale_or_non_main_dispatch(self):
        guard = self.workflow.split("- name: Refuse stale or non-main dispatch", 1)[1]
        guard = guard.split("- name: Set up Python", 1)[0]
        self.assertIn('GITHUB_REF_NAME:-', guard)
        self.assertIn('git ls-remote origin refs/heads/main', guard)
        self.assertIn('git rev-parse HEAD', guard)
        self.assertIn('Refusing stale workflow execution', guard)

    def test_integrity_ci_covers_pilot_workflow_changes(self):
        self.assertIn(
            '".github/workflows/h392-curation-pilot.yml"',
            self.integrity_workflow,
        )

    def test_readiness_rechecks_main_before_real_source_acquisition(self):
        live = self.workflow.index("- name: Run live Curator and Verifier readiness canaries")
        recheck = self.workflow.index("- name: Reconfirm main before real curation")
        acquire = self.workflow.index("- name: Acquire and re-verify pinned non-holdout sources")
        self.assertLess(live, recheck)
        self.assertLess(recheck, acquire)
        section = self.workflow[recheck:acquire]
        self.assertIn("git ls-remote origin refs/heads/main", section)
        self.assertIn("Main advanced before real curation", section)

    def test_pilot_is_reusable_but_manual_dispatch_cannot_skip_readiness(self):
        dispatch = self.workflow.split("  workflow_call:", 1)[0]
        self.assertNotIn("skip_readiness:", dispatch)
        reusable = self.workflow.split("  workflow_call:", 1)[1].split(
            "\npermissions:", 1
        )[0]
        self.assertIn("skip_readiness:", reusable)
        self.assertIn("readiness_sha:", reusable)
        self.assertIn("H392_CURATION_ARTIFACT_KEY:", reusable)

        delegated = self.workflow.split(
            "- name: Validate delegated campaign readiness", 1
        )[1].split("- name: Reconfirm main before real curation", 1)[0]
        self.assertIn('if: ${{ inputs.skip_readiness == true }}', delegated)
        self.assertIn('READINESS_SHA: ${{ inputs.readiness_sha }}', delegated)
        self.assertIn('READINESS_SHA" != "$GITHUB_SHA', delegated)
        self.assertIn('"delegated": True', delegated)

    def test_campaign_runs_one_central_readiness_then_parallel_sha_bound_shards(self):
        self.assertIn("name: H3.9.2 campaign batch", self.campaign_workflow)
        self.assertIn("readiness-and-plan:", self.campaign_workflow)
        self.assertEqual(
            self.campaign_workflow.count(
                "Run live Curator and Verifier readiness canaries once"
            ),
            1,
        )
        self.assertIn("max-parallel: 4", self.campaign_workflow)
        self.assertIn("fail-fast: false", self.campaign_workflow)
        self.assertIn(
            "uses: ./.github/workflows/h392-curation-pilot.yml",
            self.campaign_workflow,
        )
        self.assertIn("skip_readiness: true", self.campaign_workflow)
        self.assertIn(
            "readiness_sha: ${{ needs.readiness-and-plan.outputs.readiness_sha }}",
            self.campaign_workflow,
        )

    def test_campaign_first_stage_is_bounded_to_32_tasks_and_eight_per_shard(self):
        self.assertIn("count < 1 or count > 32", self.campaign_workflow)
        self.assertIn("shard_size < 1 or shard_size > 8", self.campaign_workflow)
        self.assertIn("task_offset + task_count exceeds 896", self.campaign_workflow)
        self.assertIn("expected_shards", self.campaign_workflow)

    def test_campaign_aggregate_uses_only_redacted_shard_summaries(self):
        aggregate = self.campaign_workflow.split(
            "- name: Aggregate campaign batch outcomes", 1
        )[1].split("- name: Publish campaign batch summary", 1)[0]
        self.assertIn("CURATION_RUN_SUMMARY.json", aggregate)
        self.assertNotIn("curator-responses.jsonl", aggregate)
        self.assertNotIn("verifier-responses.jsonl", aggregate)
        self.assertNotIn("adjudication.jsonl", aggregate)
        self.assertIn("adjudication_reason_counts", aggregate)
        self.assertIn("outcome_by_benchmark", aggregate)
        self.assertIn("coverage_complete", aggregate)

    def test_campaign_secret_bearing_actions_are_commit_pinned(self):
        self.assertIn(
            "actions/checkout@11d5960a326750d5838078e36cf38b85af677262",
            self.campaign_workflow,
        )
        self.assertIn(
            "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065",
            self.campaign_workflow,
        )
        self.assertIn(
            "actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093",
            self.campaign_workflow,
        )
        self.assertIn(
            "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
            self.campaign_workflow,
        )

    def test_integrity_ci_covers_campaign_workflow_changes(self):
        self.assertIn(
            '".github/workflows/h392-curation-campaign.yml"',
            self.integrity_workflow,
        )

    def test_model_identity_is_not_exposed_as_dispatch_input(self):
        dispatch = self.workflow.split("permissions:", 1)[0]
        self.assertNotIn("model_family", dispatch)
        self.assertNotIn("model_ref", dispatch)

    def test_redacted_summary_omits_model_identity(self):
        summary = self.workflow.split("- name: Build redacted run summary", 1)[1]
        summary = summary.split("- name: Encrypt all source-bearing run evidence", 1)[0]
        self.assertNotIn('"model_family"', summary)
        self.assertNotIn('"model_ref"', summary)

    def test_full_execution_manifests_are_not_written_to_redacted_directory(self):
        self.assertNotIn("curator-execution-report.json", self.workflow)
        self.assertNotIn("verifier-execution-report.json", self.workflow)
        self.assertGreaterEqual(self.workflow.count("> /dev/null"), 3)

    def test_neutral_adapter_and_runtime_key_names(self):
        self.assertIn("adapters/chat_completions.py", self.workflow)
        self.assertIn("MUBIN_MODEL_API_KEY", self.workflow)

    def test_pilot_does_not_expose_inference_tuning_knobs(self):
        dispatch = self.workflow.split("permissions:", 1)[0]
        self.assertNotIn("completion_budget", dispatch)
        self.assertNotIn("reasoning_effort", dispatch)
        self.assertNotIn('"--completion-budget"', self.workflow)
        self.assertNotIn('"--completion-budget-field"', self.workflow)
        self.assertNotIn('"--reasoning-effort"', self.workflow)

    def test_pilot_uses_streaming_one_task_collection_mode_with_generous_request_timeout(self):
        self.assertIn('"--stream"', self.workflow)
        self.assertIn('"--timeout", "600"', self.workflow)
        self.assertIn('"batch_size": 1', self.workflow)
        self.assertIn('"max_attempts": 2', self.workflow)
        self.assertIn('"task_failure_policy": "record_rejection"', self.workflow)
        self.assertIn('"timeout_seconds": 660', self.workflow)

    def test_provider_keys_are_step_scoped_not_job_scoped(self):
        job_env = self.workflow.split("    env:\n", 1)[1].split("\n\n    steps:", 1)[0]
        self.assertNotIn("H392_CURATOR_API_KEY", job_env)
        self.assertNotIn("H392_VERIFIER_API_KEY", job_env)
        self.assertNotIn("H392_CURATION_ARTIFACT_KEY", job_env)
        self.assertNotIn("MUBIN_READINESS_CURATOR_API_KEY", job_env)
        self.assertNotIn("MUBIN_READINESS_VERIFIER_API_KEY", job_env)

    def test_single_dispatch_runs_offline_and_live_readiness_before_real_pilot(self):
        offline = self.workflow.index("- name: Run offline readiness suite")
        live = self.workflow.index("- name: Run live Curator and Verifier readiness canaries")
        acquire = self.workflow.index("- name: Acquire and re-verify pinned non-holdout sources")
        curator = self.workflow.index("- name: Run Curator AI-A")
        self.assertLess(offline, live)
        self.assertLess(live, acquire)
        self.assertLess(acquire, curator)
        self.assertIn("python -m benchmark_campaign.readiness", self.workflow)
        self.assertIn("--offline-only", self.workflow)
        self.assertIn("--offline-report", self.workflow)
        self.assertIn("--live-timeout 600", self.workflow)

    def test_offline_readiness_phase_has_no_provider_secrets(self):
        section = self.workflow.split("- name: Run offline readiness suite", 1)[1]
        section = section.split(
            "- name: Run live Curator and Verifier readiness canaries", 1
        )[0]
        self.assertNotIn("H392_CURATOR_API_KEY", section)
        self.assertNotIn("H392_VERIFIER_API_KEY", section)
        self.assertNotIn("H392_CURATION_ARTIFACT_KEY", section)

    def test_live_readiness_phase_uses_step_scoped_provider_secrets_only(self):
        section = self.workflow.split(
            "- name: Run live Curator and Verifier readiness canaries", 1
        )[1]
        section = section.split(
            "- name: Acquire and re-verify pinned non-holdout sources", 1
        )[0]
        self.assertIn("MUBIN_READINESS_CURATOR_API_KEY", section)
        self.assertIn("MUBIN_READINESS_VERIFIER_API_KEY", section)
        self.assertNotIn("H392_CURATION_ARTIFACT_KEY", section)
        self.assertNotIn("MODEL_FAMILY", section)

    def test_secret_bearing_workflow_pins_action_commits(self):
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

    def test_workflow_uses_authenticated_bundle_encryption(self):
        self.assertIn("benchmark_campaign.artifact_crypto encrypt", self.workflow)
        self.assertIn(".aesgcm", self.workflow)
        self.assertNotIn("aes-256-cbc", self.workflow)

    def test_run_steps_do_not_use_invalid_inline_colon_redirection(self):
        self.assertNotIn("run: : >", self.workflow)

    def test_reconcile_uses_current_cli_flags(self):
        self.assertIn("--adjudication-out", self.workflow)
        self.assertIn("--ledger-out", self.workflow)
        self.assertNotIn("--adjudication \"", self.workflow)
        self.assertNotIn("--ledger \"", self.workflow)

    def test_zero_candidate_path_still_uses_factory_reconcile(self):
        self.assertIn(
            "Materialize empty Verifier response set when Curator found no candidates",
            self.workflow,
        )
        reconcile = self.workflow.split(
            "- name: Reconcile source evidence and policy gates", 1
        )[1]
        self.assertNotIn("if: steps.verifier_tasks.outputs.count != '0'", reconcile.split("run:", 1)[0])
        self.assertIn("factory-reconcile", reconcile)

    def test_redacted_summary_reports_collection_outcomes(self):
        summary = self.workflow.split("- name: Build redacted run summary", 1)[1]
        summary = summary.split("- name: Encrypt all source-bearing run evidence", 1)[0]
        self.assertIn('"attempted_task_count"', summary)
        self.assertIn('"rejected_task_count"', summary)
        self.assertIn('"rejection_counts"', summary)
        self.assertIn('"response_counts"', summary)
        self.assertIn('"verifier_preparation"', summary)
        self.assertIn("verifier-task-report.json", summary)
        self.assertIn('"readiness"', summary)
        self.assertIn("READINESS_GATE.json", summary)
        self.assertIn('"reconciliation"', summary)

    def test_plaintext_source_bearing_outputs_are_not_uploaded(self):
        upload = self.workflow.split(
            "- name: Upload encrypted curation bundle and redacted summary", 1
        )[1]
        self.assertIn("path: /tmp/h392-curation/redacted", upload)
        self.assertNotIn("RUN_DIR", upload)
        self.assertNotIn("INDEX_DIR", upload)
        self.assertNotIn("CACHE_DIR", upload)


if __name__ == "__main__":
    unittest.main()
