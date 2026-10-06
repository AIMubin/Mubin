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

        completed = cls.status["last_completed_cumulative_consolidation"]
        cls.completed = completed
        cls.completed_evidence = json.loads(
            (cls.project / completed["evidence_path"]).read_text(encoding="utf-8")
        )

        cls.batch_evidence = json.loads(
            (cls.project / cls.status["canonical_primary_batch_evidence_path"]).read_text(
                encoding="utf-8"
            )
        )

    def test_last_completed_168_primary_consolidation_remains_immutably_bound(self):
        evidence = self.completed_evidence
        completed = self.completed

        self.assertTrue(evidence["canonical_main_evidence"])
        self.assertEqual(evidence["campaign_id"], self.status["campaign_id"])
        self.assertEqual(
            evidence["workflow"]["run_id"],
            completed["successful_run_id"],
        )
        self.assertEqual(evidence["runner_commit"], completed["runner_commit"])
        self.assertEqual(evidence["artifact"]["id"], completed["artifact_id"])
        self.assertEqual(evidence["artifact"]["digest"], completed["artifact_digest"])
        self.assertEqual(
            evidence["artifact"]["redacted_summary_sha256"],
            completed["summary_sha256"],
        )
        self.assertEqual(
            evidence["artifact"]["encrypted_bundle_sha256"],
            completed["encrypted_bundle_sha256"],
        )
        self.assertEqual(
            evidence["bindings"]["cumulative_ledger_sha256"],
            completed["cumulative_ledger_sha256"],
        )
        self.assertEqual(
            evidence["bindings"]["replacement_eligibility_sha256"],
            completed["replacement_eligibility_sha256"],
        )
        self.assertEqual(
            evidence["canonical_input"]["campaign_run_ids"],
            completed["source_run_ids"],
        )
        self.assertEqual(
            evidence["canonical_input"]["expected_primary_task_count"],
            completed["expected_primary_tasks"],
        )
        self.assertEqual(completed["expected_primary_tasks"], 168)

    def test_final_primary_batch_is_canonical_and_exactly_completes_210_prefix(self):
        evidence = self.batch_evidence
        execution = self.status["non_holdout_execution_evidence"]

        self.assertTrue(evidence["canonical_main_evidence"])
        self.assertEqual(evidence["workflow"]["run_id"], 37426135905)
        self.assertEqual(evidence["workflow"]["run_attempt"], 1)
        self.assertEqual(evidence["workflow"]["conclusion"], "success")
        self.assertEqual(
            evidence["workflow"]["head_sha"],
            "fe55559fd97d1731204264341cfa6ddb1b28821d",
        )

        surface = evidence["requested_surface"]
        self.assertTrue(surface["exact_contiguous_coverage"])
        self.assertEqual(surface["task_offset"], 168)
        self.assertEqual(surface["task_count"], 42)
        self.assertEqual(surface["primary_offset_end_inclusive"], 209)

        aggregate = evidence["aggregate"]
        self.assertTrue(aggregate["coverage_complete"])
        self.assertEqual(aggregate["coverage_errors"], [])
        self.assertEqual(aggregate["completed_shards"], aggregate["expected_shards"])
        self.assertEqual(aggregate["selected_tasks"], 42)
        self.assertEqual(
            aggregate["promoted"] + aggregate["adjudication"] + aggregate["skipped"],
            42,
        )

        self.assertEqual(execution["primary_tasks_executed"], 210)
        self.assertEqual(execution["primary_offset_coverage"], "0..209")
        self.assertEqual(
            execution["workflow_runs"],
            [37280971913, 37295517184, 37326459365, 37426135905],
        )
        self.assertFalse(execution["preconsolidation_outcomes_are_authoritative"])
        self.assertFalse(self.status["reserve_reconciliation_enabled"])

    def test_210_primary_cumulative_target_is_reviewed_but_not_yet_completed(self):
        target = self.status["cumulative_consolidation_target"]
        evidence = self.batch_evidence

        self.assertTrue(target["ready"])
        self.assertFalse(target["completed"])
        self.assertEqual(target["expected_primary_tasks"], 210)
        self.assertEqual(target["protocol_freeze_schema"], 25)
        self.assertEqual(
            target["run_ids"],
            [37280971913, 37295517184, 37326459365, 37426135905],
        )
        self.assertEqual(
            evidence["next_action"]["canonical_run_ids"],
            target["run_ids"],
        )
        self.assertEqual(
            evidence["next_action"]["expected_primary_task_count"],
            target["expected_primary_tasks"],
        )

        excluded = {
            row["run_id"]: row["reason"]
            for row in evidence["excluded_noncanonical_runs"]
        }
        self.assertIn(37412193331, excluded)


if __name__ == "__main__":
    unittest.main()
