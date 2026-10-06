from __future__ import annotations

import json
import unittest
from pathlib import Path


class CumulativeEvidenceRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project = Path(__file__).resolve().parents[1]
        cls.status = json.loads(
            (cls.project / "artifacts" / "H3.9.2-STATUS.json").read_text(encoding="utf-8")
        )
        cls.evidence_path = cls.project / cls.status["cumulative_evidence_path"]
        cls.evidence = json.loads(cls.evidence_path.read_text(encoding="utf-8"))

    def test_status_is_bound_to_successful_168_primary_evidence(self):
        evidence = self.evidence
        status = self.status

        self.assertTrue(status["cumulative_consolidation_ready"])
        self.assertTrue(status["cumulative_consolidation_completed"])
        self.assertTrue(evidence["canonical_main_evidence"])
        self.assertEqual(evidence["campaign_id"], status["campaign_id"])
        self.assertEqual(
            evidence["workflow"]["run_id"],
            status["cumulative_consolidation_successful_run_id"],
        )
        self.assertEqual(
            evidence["runner_commit"],
            status["cumulative_consolidation_runner_commit"],
        )
        self.assertEqual(
            evidence["artifact"]["id"],
            status["cumulative_consolidation_artifact_id"],
        )
        self.assertEqual(
            evidence["artifact"]["digest"],
            status["cumulative_consolidation_artifact_digest"],
        )
        self.assertEqual(
            evidence["artifact"]["redacted_summary_sha256"],
            status["cumulative_consolidation_summary_sha256"],
        )
        self.assertEqual(
            evidence["artifact"]["encrypted_bundle_sha256"],
            status["encrypted_cumulative_bundle_sha256"],
        )
        self.assertEqual(
            evidence["bindings"]["cumulative_ledger_sha256"],
            status["cumulative_ledger_sha256"],
        )
        self.assertEqual(
            evidence["bindings"]["replacement_eligibility_sha256"],
            status["replacement_eligibility_sha256"],
        )

    def test_canonical_prefix_accounting_and_next_batch_are_exact(self):
        evidence = self.evidence
        status = self.status
        result = evidence["result"]
        canonical = evidence["canonical_input"]
        next_action = evidence["next_action"]

        self.assertEqual(
            canonical["campaign_run_ids"],
            status["cumulative_consolidation_run_ids"],
        )
        self.assertEqual(
            canonical["expected_primary_task_count"],
            status["cumulative_consolidation_expected_primary_tasks"],
        )
        self.assertEqual(result["task_count"], canonical["expected_primary_task_count"])
        self.assertEqual(
            result["promoted"] + result["pending_adjudication"] + result["skipped"],
            result["task_count"],
        )
        self.assertEqual(
            result["replacement_eligible_primary_count"],
            status["cumulative_replacement_eligible_primary_count"],
        )
        self.assertEqual(result["replacement_eligible_primary_count"], result["skipped"])
        self.assertFalse(evidence["reserve_policy"]["reserve_reconciliation_enabled"])
        self.assertFalse(status["reserve_reconciliation_enabled"])

        self.assertEqual(next_action["task_offset"], result["task_count"])
        self.assertEqual(next_action["task_count"], 42)
        self.assertEqual(next_action["task_offset"] + next_action["task_count"], 210)
        self.assertEqual(next_action["shard_size"], 8)


if __name__ == "__main__":
    unittest.main()
