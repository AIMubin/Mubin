from __future__ import annotations

import unittest
from pathlib import Path


class PostConsolidationWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project = Path(__file__).resolve().parents[1]
        cls.workflow = (cls.project.parents[3] / '.github' / 'workflows' / 'h392-post-consolidation-plan.yml').read_text(encoding='utf-8')

    def test_workflow_is_manual_main_only_and_stale_dispatch_resistant(self):
        self.assertIn('workflow_dispatch:', self.workflow)
        self.assertIn('GITHUB_REF_NAME:-}', self.workflow)
        self.assertGreaterEqual(self.workflow.count('git ls-remote origin refs/heads/main'), 3)

    def test_source_cumulative_run_and_artifact_are_explicitly_reviewed(self):
        self.assertIn('SOURCE_RUN_ID: "37471731102"', self.workflow)
        self.assertIn('SOURCE_ARTIFACT_ID: "11416657955"', self.workflow)
        self.assertIn('actions/artifacts/{artifact_id}', self.workflow)
        self.assertIn('source cumulative artifact digest mismatch', self.workflow)
        self.assertIn('source cumulative run SHA mismatch', self.workflow)

    def test_download_action_is_pinned_and_uses_exact_artifact_id(self):
        self.assertIn('actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093', self.workflow)
        self.assertIn('artifact-ids: 11416657955', self.workflow)
        self.assertIn('run-id: 37471731102', self.workflow)
        self.assertIn('github-token:', self.workflow)

    def test_planning_target_must_remain_execution_disabled(self):
        self.assertIn('post_consolidation_protocol', self.workflow)
        self.assertIn('post-consolidation planning requires freeze schema 26', self.workflow)
        self.assertIn('adjudication_execution_enabled', self.workflow)
        self.assertIn('reserve_execution_enabled', self.workflow)
        self.assertIn('reserve_reconciliation_enabled', self.workflow)
        self.assertIn('repository reserve reconciliation must remain disabled', self.workflow)

    def test_downloaded_payload_is_content_bound_before_decryption(self):
        self.assertIn('CUMULATIVE_SUMMARY.json', self.workflow)
        self.assertIn('h392-cumulative-source-bearing.tar.gz.aesgcm', self.workflow)
        self.assertIn('ENCRYPTED_CUMULATIVE_BUNDLE_SHA256.txt', self.workflow)
        self.assertIn('downloaded cumulative summary digest mismatch', self.workflow)
        self.assertIn('downloaded cumulative bundle digest mismatch', self.workflow)

    def test_tar_extraction_is_fail_closed(self):
        self.assertIn('unsafe cumulative tar member', self.workflow)
        self.assertIn('member.issym()', self.workflow)
        self.assertIn('member.islnk()', self.workflow)
        self.assertIn('member.isdev()', self.workflow)
        self.assertIn('filter="data"', self.workflow)

    def test_planner_publishes_only_redacted_control_plane(self):
        self.assertIn('plan-post-consolidation', self.workflow)
        self.assertIn('ADJUDICATION_PLAN.json', self.workflow)
        self.assertIn('RESERVE_ACTIVATION_PLAN.json', self.workflow)
        self.assertIn('POST_CONSOLIDATION_MANIFEST.json', self.workflow)
        self.assertIn('POST_CONSOLIDATION_SUMMARY.json', self.workflow)
        self.assertIn('unexpected post-consolidation upload files', self.workflow)
        upload = self.workflow.split('- name: Upload redacted post-consolidation plan', 1)[1]
        self.assertNotIn('CUMULATIVE_LEDGER.jsonl', upload)

    def test_expected_counts_are_locked_to_frozen_evidence(self):
        self.assertIn('reviewed adjudication count must be 129', self.workflow)
        self.assertIn('reviewed eligible-primary count must be 41', self.workflow)
        self.assertIn('reviewed reserve-task count must be 41', self.workflow)
        self.assertIn('planned adjudication count mismatch', self.workflow)
        self.assertIn('planned reserve-task count mismatch', self.workflow)


if __name__ == '__main__':
    unittest.main()
