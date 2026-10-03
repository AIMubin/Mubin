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

    def test_model_identity_is_not_exposed_as_dispatch_input(self):
        dispatch = self.workflow.split("permissions:", 1)[0]
        self.assertNotIn("model_family", dispatch)
        self.assertNotIn("model_ref", dispatch)

    def test_redacted_summary_omits_model_identity(self):
        summary = self.workflow.split("- name: Build redacted run summary", 1)[1]
        summary = summary.split("- name: Encrypt all source-bearing run evidence", 1)[0]
        self.assertNotIn('"model_family"', summary)
        self.assertNotIn('"model_ref"', summary)

    def test_neutral_adapter_and_runtime_key_names(self):
        self.assertIn("adapters/chat_completions.py", self.workflow)
        self.assertIn("MUBIN_MODEL_API_KEY", self.workflow)

    def test_completion_budget_is_explicit_and_bounded(self):
        dispatch = self.workflow.split("permissions:", 1)[0]
        self.assertIn("curator_max_tokens:", dispatch)
        self.assertIn("verifier_max_tokens:", dispatch)
        self.assertIn('default: "4096"', dispatch)
        self.assertIn('"--max-tokens", str(max_tokens)', self.workflow)
        self.assertIn('if value < 256 or value > 8192:', self.workflow)

    def test_provider_keys_are_step_scoped_not_job_scoped(self):
        job_env = self.workflow.split("    env:\n", 1)[1].split("\n\n    steps:", 1)[0]
        self.assertNotIn("H392_CURATOR_API_KEY", job_env)
        self.assertNotIn("H392_VERIFIER_API_KEY", job_env)
        self.assertNotIn("H392_CURATION_ARTIFACT_KEY", job_env)

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
