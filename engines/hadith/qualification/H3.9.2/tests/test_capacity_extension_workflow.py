from __future__ import annotations

import json
import unittest
from pathlib import Path


class CapacityExtensionWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        project = Path(__file__).resolve().parents[1]
        repo_root = project.parents[3]
        cls.workflow = (
            repo_root / ".github" / "workflows" / "h392-capacity-extension.yml"
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
        self.assertIn("Refusing stale capacity extension proposal", self.workflow)
        self.assertIn(
            "Main advanced while capacity source evidence was acquired",
            self.workflow,
        )
        self.assertIn(
            "Main advanced before capacity proposal publication",
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

    def test_target_is_exactly_canonical_schema26_consolidation(self):
        target = self.status["capacity_extension_target"]
        self.assertFalse(target["ready"])
        self.assertTrue(target["completed"])
        self.assertEqual(target["protocol_freeze_schema"], 27)
        self.assertEqual(target["source_reserve_consolidation_freeze_schema"], 26)
        self.assertEqual(target["source_reserve_consolidation_run_id"], 37578659973)
        self.assertEqual(
            target["source_reserve_consolidation_runner_commit"],
            "b3888b24b20571884465b349c9764c669b0e66f9",
        )
        self.assertEqual(target["source_reserve_consolidation_artifact_id"], 11464000900)
        self.assertEqual(
            target["source_reserve_consolidation_artifact_digest"],
            "sha256:00385663166059b3701c0581bd460ba2f2d39a796d3cca1c1b015fb96170b64e",
        )
        self.assertEqual(target["expected_exhausted_slot_count"], 10)
        self.assertEqual(target["expected_new_reserve_slot_count"], 10)
        self.assertEqual(target["new_reserve_attempt"], 2)
        self.assertFalse(target["execution_authorized"])
        self.assertFalse(target["base_factory_plan_mutated"])
        self.assertEqual(target["successful_run_id"], 37588897387)
        self.assertEqual(target["run_attempt"], 1)
        self.assertEqual(
            target["runner_commit"],
            "174da564ff8158c86898575e3097d15394a2ffae",
        )
        self.assertEqual(target["artifact_id"], 11467766861)
        self.assertEqual(
            target["artifact_digest"],
            "sha256:2b36aef77dfa885a01f271377d4f6164698c9d6cd56adb1c59aaba906c045115",
        )
        self.assertEqual(
            target["manifest_sha256"],
            "9bd2468737d0cd1b89227b3b625814dfc1a3cab25512fece98ae377ef1ac4fce",
        )

    def test_workflow_fetches_exact_artifact_and_verifies_all_hashes(self):
        self.assertIn('actions/artifacts/{artifact_id}', self.workflow)
        self.assertIn('target["source_reserve_consolidation_artifact_id"]', self.workflow)
        self.assertIn("canonical reserve consolidation ZIP digest mismatch", self.workflow)
        self.assertIn("canonical reserve consolidation summary hash mismatch", self.workflow)
        self.assertIn(
            "canonical reserve consolidation encrypted bundle hash mismatch",
            self.workflow,
        )
        self.assertIn("canonical reserve consolidation bundle declaration mismatch", self.workflow)
        self.assertNotIn("pattern:", self.workflow)

    def test_builder_uses_exact_ledger_exhausted_hashes_and_count(self):
        section = self.workflow.split(
            "- name: Build selective reserve attempt 2 proposal", 1
        )[1].split(
            "- name: Prove proposal is redacted and non-executable", 1
        )[0]
        self.assertIn("build-capacity-extension", section)
        self.assertIn("--expected-reserve-ledger-sha256", section)
        self.assertIn("--expected-exhausted-slots-sha256", section)
        self.assertIn("--expected-exhausted-slot-count", section)
        self.assertIn('target["reserve_ledger_sha256"]', section)
        self.assertIn('target["exhausted_slots_sha256"]', section)

    def test_proposal_is_non_executable_and_redacted_before_upload(self):
        section = self.workflow.split(
            "- name: Prove proposal is redacted and non-executable", 1
        )[1].split(
            "- name: Reconfirm main before publishing proposal", 1
        )[0]
        self.assertIn('obj.get("execution_authorized") is not False', section)
        self.assertIn('obj.get("requires_repository_approval") is not True', section)
        self.assertIn('not value.endswith(":reserve:02")', section)
        self.assertIn("source/model-bearing key leaked into proposal", section)
        self.assertIn('rm -rf "$SOURCE_DIR"', section)
        upload = self.workflow.split(
            "- name: Upload redacted capacity extension proposal", 1
        )[1]
        self.assertIn("h392-capacity-extension-proposal", upload)
        self.assertIn("CAPACITY_EXTENSION.json", upload)
        self.assertNotIn("source-bearing", upload)

    def test_integrity_ci_covers_capacity_extension_workflow(self):
        self.assertIn(
            '".github/workflows/h392-capacity-extension.yml"',
            self.integrity,
        )


if __name__ == "__main__":
    unittest.main()
