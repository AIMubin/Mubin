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
        cls.batch_evidence = json.loads(
            (cls.project / cls.status["canonical_primary_batch_evidence_path"]).read_text(
                encoding="utf-8"
            )
        )
        cls.completed = cls.status["last_completed_cumulative_consolidation"]
        cls.completed_evidence = json.loads(
            (cls.project / cls.completed["evidence_path"]).read_text(encoding="utf-8")
        )

    def test_210_primary_cumulative_result_is_authoritative_and_immutably_bound(self):
        evidence = self.completed_evidence
        completed = self.completed

        self.assertTrue(evidence["canonical_main_evidence"])
        self.assertEqual(evidence["campaign_id"], self.status["campaign_id"])
        self.assertEqual(evidence["workflow"]["run_id"], 37471731102)
        self.assertEqual(evidence["workflow"]["run_attempt"], 1)
        self.assertEqual(evidence["workflow"]["conclusion"], "success")
        self.assertEqual(
            evidence["runner_commit"],
            "e1422b3262ee308084ce2212a2f2825fdc737032",
        )

        self.assertEqual(evidence["workflow"]["run_id"], completed["successful_run_id"])
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

        canonical = evidence["canonical_input"]
        result = evidence["result"]
        self.assertEqual(canonical["expected_primary_task_count"], 210)
        self.assertEqual(canonical["primary_offset_start"], 0)
        self.assertEqual(canonical["primary_offset_end_inclusive"], 209)
        self.assertTrue(canonical["exact_zero_based_prefix"])
        self.assertEqual(
            canonical["campaign_run_ids"],
            [37280971913, 37295517184, 37326459365, 37426135905],
        )
        self.assertEqual(result["task_count"], 210)
        self.assertEqual(
            result["promoted"] + result["pending_adjudication"] + result["skipped"],
            210,
        )
        self.assertEqual(result["promoted"], 40)
        self.assertEqual(result["pending_adjudication"], 129)
        self.assertEqual(result["skipped"], 41)
        self.assertEqual(result["replacement_eligible_primary_count"], 41)

    def test_cumulative_history_preserves_168_checkpoint_and_210_result(self):
        history = self.status["cumulative_consolidation_history"]
        self.assertEqual([row["expected_primary_tasks"] for row in history], [168, 210])

        prior, current = history
        self.assertEqual(prior["successful_run_id"], 37409931064)
        self.assertEqual(
            prior["evidence_path"],
            "artifacts/CUMULATIVE_PRIMARY_EVIDENCE_168.json",
        )
        prior_evidence = json.loads(
            (self.project / prior["evidence_path"]).read_text(encoding="utf-8")
        )
        self.assertEqual(prior_evidence["workflow"]["run_id"], prior["successful_run_id"])
        self.assertEqual(
            prior_evidence["bindings"]["cumulative_ledger_sha256"],
            prior["cumulative_ledger_sha256"],
        )
        self.assertEqual(
            prior_evidence["bindings"]["replacement_eligibility_sha256"],
            prior["replacement_eligibility_sha256"],
        )

        self.assertEqual(current, self.status["last_completed_cumulative_consolidation"])
        self.assertEqual(current["successful_run_id"], 37471731102)
        self.assertEqual(
            current["evidence_path"],
            "artifacts/CUMULATIVE_PRIMARY_EVIDENCE_210.json",
        )

    def test_final_primary_batch_and_cumulative_result_agree_on_exact_210_accounting(self):
        batch = self.batch_evidence
        cumulative = self.completed_evidence
        execution = self.status["non_holdout_execution_evidence"]

        self.assertTrue(batch["canonical_main_evidence"])
        self.assertEqual(batch["workflow"]["run_id"], 37426135905)
        self.assertEqual(batch["workflow"]["run_attempt"], 1)
        self.assertEqual(batch["workflow"]["conclusion"], "success")

        surface = batch["requested_surface"]
        self.assertEqual(surface["task_offset"], 168)
        self.assertEqual(surface["task_count"], 42)
        self.assertEqual(surface["primary_offset_end_inclusive"], 209)
        self.assertTrue(surface["exact_contiguous_coverage"])

        self.assertEqual(execution["primary_tasks_executed"], 210)
        self.assertEqual(execution["primary_offset_coverage"], "0..209")
        self.assertEqual(
            execution["workflow_runs"],
            cumulative["canonical_input"]["campaign_run_ids"],
        )
        self.assertEqual(
            execution["promoted_in_encrypted_shards"],
            cumulative["result"]["promoted"],
        )
        self.assertEqual(
            execution["adjudication_in_encrypted_shards"],
            cumulative["result"]["pending_adjudication"],
        )
        self.assertEqual(
            execution["skipped_or_rejected_from_reconciliation"],
            cumulative["result"]["skipped"],
        )
        self.assertTrue(execution["cumulative_evidence_verified"])
        self.assertEqual(
            execution["last_completed_cumulative_evidence_path"],
            "artifacts/CUMULATIVE_PRIMARY_EVIDENCE_210.json",
        )

    def test_completed_target_is_fail_closed_for_redispatch_and_preserves_historical_reserve_state(self):
        target = self.status["cumulative_consolidation_target"]
        evidence = self.completed_evidence

        self.assertFalse(target["ready"])
        self.assertTrue(target["completed"])
        self.assertEqual(target["expected_primary_tasks"], 210)
        self.assertEqual(target["protocol_freeze_schema"], 25)
        self.assertEqual(target["successful_run_id"], 37471731102)
        self.assertEqual(
            target["evidence_path"],
            "artifacts/CUMULATIVE_PRIMARY_EVIDENCE_210.json",
        )
        self.assertEqual(
            target["run_ids"],
            evidence["canonical_input"]["campaign_run_ids"],
        )

        # Schema-25 cumulative evidence remains immutable historical input:
        # reserves were disabled when this evidence was created and pending
        # adjudications were not replacement eligible. Schema-26 repository
        # approval may enable only the separately hash-bound reserve set.
        self.assertFalse(evidence["reserve_policy"]["reserve_reconciliation_enabled"])
        self.assertFalse(
            evidence["reserve_policy"]["pending_adjudication_is_replacement_eligible"]
        )
        self.assertEqual(
            evidence["reserve_policy"]["replacement_eligible_primary_count"],
            41,
        )

        self.assertTrue(self.status["reserve_reconciliation_enabled"])
        activation = self.status["reserve_activation"]
        self.assertTrue(activation["enabled"])
        self.assertEqual(activation["activated_reserve_slot_count"], 41)
        self.assertEqual(
            activation["cumulative_ledger_sha256"],
            self.status["last_completed_cumulative_consolidation"]["cumulative_ledger_sha256"],
        )
        self.assertEqual(
            activation["replacement_eligibility_sha256"],
            self.status["last_completed_cumulative_consolidation"]["replacement_eligibility_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
