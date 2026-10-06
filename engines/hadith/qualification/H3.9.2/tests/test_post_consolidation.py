from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmark_campaign.core import (
    canonical_json_bytes,
    dump_jsonl,
    sha256_bytes,
    sha256_file,
    write_json,
)
from benchmark_campaign.post_consolidation import build_post_consolidation_plan


class PostConsolidationPlannerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "campaign"
        self.root.mkdir()
        (self.root / "artifacts").mkdir()
        self.cumulative = Path(self.tmp.name) / "cumulative"
        self.cumulative.mkdir()
        self.out = Path(self.tmp.name) / "out"

        self.primary0 = {
            "slot_id": "b1:non_holdout:s1:0001",
            "benchmark_id": "b1",
            "partition": "non_holdout",
            "anchor_source_id": "s1",
            "ordinal": 1,
            "task_type": "classification",
            "allowed_labels": ["yes", "no"],
            "auto_promotion": True,
            "risk_tier": 1,
            "visibility": "development_safe",
        }
        self.primary1 = {
            **self.primary0,
            "slot_id": "b1:non_holdout:s1:0002",
            "ordinal": 2,
        }
        self.primary2 = {
            **self.primary0,
            "slot_id": "b1:non_holdout:s1:0003",
            "ordinal": 3,
        }
        self.reserve2 = {
            **self.primary2,
            "slot_id": "b1:non_holdout:s1:0003:reserve:01",
            "candidate_slot_kind": "reserve",
            "replacement_for_slot_id": self.primary2["slot_id"],
            "reserve_attempt": 1,
        }
        self.plan = {
            "campaign_id": "H3.9.2",
            "factory_version": 1,
            "slot_count": 4,
            "target_total": 3,
            "primary_slot_count": 3,
            "reserve_slot_count": 1,
            "reserve_slots_per_primary": 1,
            "primary_holdout_slots": 0,
            "primary_non_holdout_slots": 3,
            "holdout_slots": 0,
            "non_holdout_slots": 3,
            "candidate_holdout_slots": 0,
            "candidate_non_holdout_slots": 4,
            "slots": [self.primary0, self.primary1, self.primary2, self.reserve2],
        }
        self.plan_sha = sha256_bytes(canonical_json_bytes(self.plan))

        self.ledger = [
            self._ledger_row(self.primary0, 0, "promoted", "promoted", False),
            self._ledger_row(self.primary1, 1, "adjudication", "gold_disagreement", False),
            self._ledger_row(self.primary2, 2, "skipped", "curator_no_candidate", True),
        ]
        dump_jsonl(self.cumulative / "CUMULATIVE_LEDGER.jsonl", self.ledger)
        ledger_sha = sha256_file(self.cumulative / "CUMULATIVE_LEDGER.jsonl")

        adjudication = [{
            "task_id": self.primary1["slot_id"],
            "reason": "gold_disagreement",
            "source_run_id": 11,
            "source_sha": "1" * 40,
            "canonical_reason": "gold_disagreement",
        }]
        dump_jsonl(self.cumulative / "CUMULATIVE_ADJUDICATION.jsonl", adjudication)

        eligibility = {
            "schema_version": 1,
            "campaign_id": "H3.9.2",
            "kind": "primary_replacement_eligibility",
            "freeze_schema_version": 25,
            "factory_plan_sha256": self.plan_sha,
            "cumulative_ledger_sha256": ledger_sha,
            "rules": {
                "promoted_is_replaceable": False,
                "pending_adjudication_is_replaceable": False,
                "terminal_primary_failure_is_replaceable": True,
                "reserve_reconciliation_enabled": False,
            },
            "eligible_primary_count": 1,
            "eligible": [{
                "primary_slot_id": self.primary2["slot_id"],
                "primary_slot_binding_sha256": sha256_bytes(
                    canonical_json_bytes(self.primary2)
                ),
                "primary_task_id": self.primary2["slot_id"],
                "primary_task_fingerprint": "c" * 64,
                "primary_offset": 2,
                "primary_outcome": "skipped",
                "eligibility_reason": "curator_no_candidate",
                "reserve_slots": [{
                    "slot_id": self.reserve2["slot_id"],
                    "slot_binding_sha256": sha256_bytes(
                        canonical_json_bytes(self.reserve2)
                    ),
                }],
                "cumulative_ledger_sha256": ledger_sha,
            }],
        }
        write_json(self.cumulative / "REPLACEMENT_ELIGIBILITY.json", eligibility)

        manifest = {
            "schema_version": 1,
            "campaign_id": "H3.9.2",
            "kind": "cumulative_non_holdout_primary_evidence",
            "freeze_schema_version": 25,
            "factory_plan_sha256": self.plan_sha,
            "input_run_ids": [10, 11],
            "task_count": 3,
            "coverage_ranges": [{"start": 0, "end": 3}],
            "cumulative_ledger_sha256": ledger_sha,
            "cumulative_adjudication_sha256": sha256_file(
                self.cumulative / "CUMULATIVE_ADJUDICATION.jsonl"
            ),
            "replacement_eligibility_sha256": sha256_file(
                self.cumulative / "REPLACEMENT_ELIGIBILITY.json"
            ),
            "reviewed_record_count": 1,
            "adjudication_count": 1,
            "replacement_eligible_primary_count": 1,
        }
        write_json(self.cumulative / "CUMULATIVE_MANIFEST.json", manifest)

        self.evidence_path = self.root / "artifacts" / "CUMULATIVE_PRIMARY_EVIDENCE_210.json"
        write_json(self.evidence_path, {
            "schema_version": 1,
            "campaign_id": "H3.9.2",
            "evidence_kind": "cumulative_non_holdout_primary_consolidation",
            "canonical_main_evidence": True,
            "runner_commit": "f" * 40,
            "workflow": {
                "path": ".github/workflows/h392-cumulative-consolidation.yml",
                "run_id": 99,
                "run_attempt": 1,
                "event": "workflow_dispatch",
                "conclusion": "success",
            },
            "artifact": {
                "id": 100,
                "digest": "sha256:" + "a" * 64,
            },
            "canonical_input": {
                "campaign_run_ids": [10, 11],
                "expected_primary_task_count": 3,
                "benchmark_id": "b1",
                "primary_offset_start": 0,
                "primary_offset_end_inclusive": 2,
                "exact_zero_based_prefix": True,
            },
            "result": {
                "task_count": 3,
                "promoted": 1,
                "pending_adjudication": 1,
                "skipped": 1,
                "replacement_eligible_primary_count": 1,
                "reviewed_record_count": 1,
            },
            "bindings": {
                "cumulative_ledger_sha256": ledger_sha,
                "replacement_eligibility_sha256": sha256_file(
                    self.cumulative / "REPLACEMENT_ELIGIBILITY.json"
                ),
            },
        })

        evidence = json.loads(self.evidence_path.read_text(encoding="utf-8"))
        eligibility_sha = evidence["bindings"]["replacement_eligibility_sha256"]
        self.status_path = self.root / "artifacts" / "H3.9.2-STATUS.json"
        write_json(self.status_path, {
            "campaign_id": "H3.9.2",
            "freeze_schema_version": 26,
            "reserve_reconciliation_enabled": False,
            "post_consolidation_protocol": {
                "version": 1,
                "freeze_schema_version": 26,
                "source_cumulative_run_id": 99,
                "source_cumulative_evidence_path": "artifacts/CUMULATIVE_PRIMARY_EVIDENCE_210.json",
                "source_cumulative_ledger_sha256": ledger_sha,
                "source_replacement_eligibility_sha256": eligibility_sha,
                "expected_pending_adjudication_count": 1,
                "expected_eligible_primary_count": 1,
                "expected_reserve_task_count": 1,
                "planning_ready": True,
                "planning_completed": False,
                "adjudication_execution_enabled": False,
                "reserve_execution_enabled": False,
                "reserve_reconciliation_enabled": False,
            },
            "last_completed_cumulative_consolidation": {
                "expected_primary_tasks": 3,
                "source_run_ids": [10, 11],
                "successful_run_id": 99,
                "runner_commit": "f" * 40,
                "artifact_id": 100,
                "artifact_digest": "sha256:" + "a" * 64,
                "cumulative_ledger_sha256": ledger_sha,
                "replacement_eligibility_sha256": eligibility_sha,
                "pending_adjudication_count": 1,
                "replacement_eligible_primary_count": 1,
                "reviewed_record_count": 1,
                "evidence_path": "artifacts/CUMULATIVE_PRIMARY_EVIDENCE_210.json",
            },
        })

    def tearDown(self):
        self.tmp.cleanup()

    def _ledger_row(self, slot, offset, outcome, reason, eligible):
        return {
            "task_id": slot["slot_id"],
            "slot_id": slot["slot_id"],
            "task_fingerprint": ["a" * 64, "b" * 64, "c" * 64][offset],
            "benchmark_id": "b1",
            "anchor_source_id": "s1",
            "outcome": outcome,
            "reconcile_reason": None if outcome == "promoted" else reason,
            "canonical_reason": reason,
            "case_id": "case-0" if outcome == "promoted" else None,
            "replacement_eligible": eligible,
            "source_run_id": 10 + offset,
            "source_run_attempt": 1,
            "source_sha": str(offset + 1) * 40,
            "source_artifact_id": 1000 + offset,
            "source_artifact_sha256": str(offset + 1) * 64,
            "source_encrypted_bundle_sha256": str(offset + 2) * 64,
            "primary_offset": offset,
        }

    def _rebind_status(self, *, ledger_sha=None, eligibility_sha=None):
        status = json.loads(self.status_path.read_text(encoding="utf-8"))
        if ledger_sha is not None:
            status["post_consolidation_protocol"]["source_cumulative_ledger_sha256"] = ledger_sha
            status["last_completed_cumulative_consolidation"]["cumulative_ledger_sha256"] = ledger_sha
        if eligibility_sha is not None:
            status["post_consolidation_protocol"]["source_replacement_eligibility_sha256"] = eligibility_sha
            status["last_completed_cumulative_consolidation"]["replacement_eligibility_sha256"] = eligibility_sha
        write_json(self.status_path, status)

    def _run(self, evidence_path=None):
        with patch(
            "benchmark_campaign.post_consolidation.build_factory_plan",
            return_value=self.plan,
        ):
            return build_post_consolidation_plan(
                self.root,
                self.cumulative,
                self.out,
                evidence_path or self.evidence_path,
            )

    def test_planner_derives_exact_fail_closed_control_plane(self):
        summary = self._run()
        self.assertEqual(summary["source_task_count"], 3)
        self.assertEqual(summary["pending_adjudication_count"], 1)
        self.assertEqual(summary["eligible_primary_count"], 1)
        self.assertEqual(summary["reserve_task_count"], 1)
        self.assertFalse(summary["adjudication_execution_enabled"])
        self.assertFalse(summary["reserve_execution_enabled"])
        self.assertFalse(summary["reserve_reconciliation_enabled"])

        adjudication = json.loads(
            (self.out / "ADJUDICATION_PLAN.json").read_text(encoding="utf-8")
        )
        self.assertEqual(adjudication["pending_adjudication_count"], 1)
        self.assertEqual(adjudication["items"][0]["primary_offset"], 1)
        self.assertEqual(adjudication["items"][0]["canonical_reason"], "gold_disagreement")
        self.assertFalse(adjudication["execution_enabled"])

        reserve = json.loads(
            (self.out / "RESERVE_ACTIVATION_PLAN.json").read_text(encoding="utf-8")
        )
        self.assertEqual(reserve["reserve_task_count"], 1)
        self.assertEqual(
            reserve["items"][0]["reserve_slot_id"],
            self.reserve2["slot_id"],
        )
        self.assertEqual(
            reserve["items"][0]["primary_slot_id"],
            self.primary2["slot_id"],
        )
        self.assertFalse(reserve["execution_enabled"])
        self.assertFalse(reserve["reconciliation_enabled"])

    def test_tampered_eligibility_fails_repository_evidence_binding(self):
        eligibility = json.loads(
            (self.cumulative / "REPLACEMENT_ELIGIBILITY.json").read_text(encoding="utf-8")
        )
        eligibility["eligible"][0]["eligibility_reason"] = "tampered"
        write_json(self.cumulative / "REPLACEMENT_ELIGIBILITY.json", eligibility)
        with self.assertRaisesRegex(ValueError, "replacement eligibility differs"):
            self._run()

    def test_pending_adjudication_cannot_be_replacement_eligible(self):
        ledger = list(self.ledger)
        ledger[1]["replacement_eligible"] = True
        dump_jsonl(self.cumulative / "CUMULATIVE_LEDGER.jsonl", ledger)
        new_sha = sha256_file(self.cumulative / "CUMULATIVE_LEDGER.jsonl")
        manifest = json.loads(
            (self.cumulative / "CUMULATIVE_MANIFEST.json").read_text(encoding="utf-8")
        )
        manifest["cumulative_ledger_sha256"] = new_sha
        write_json(self.cumulative / "CUMULATIVE_MANIFEST.json", manifest)
        evidence = json.loads(self.evidence_path.read_text(encoding="utf-8"))
        evidence["bindings"]["cumulative_ledger_sha256"] = new_sha
        write_json(self.evidence_path, evidence)
        eligibility = json.loads(
            (self.cumulative / "REPLACEMENT_ELIGIBILITY.json").read_text(encoding="utf-8")
        )
        eligibility["cumulative_ledger_sha256"] = new_sha
        eligibility["eligible"][0]["cumulative_ledger_sha256"] = new_sha
        write_json(self.cumulative / "REPLACEMENT_ELIGIBILITY.json", eligibility)
        new_elig_sha = sha256_file(self.cumulative / "REPLACEMENT_ELIGIBILITY.json")
        manifest["replacement_eligibility_sha256"] = new_elig_sha
        write_json(self.cumulative / "CUMULATIVE_MANIFEST.json", manifest)
        evidence["bindings"]["replacement_eligibility_sha256"] = new_elig_sha
        write_json(self.evidence_path, evidence)
        self._rebind_status(ledger_sha=new_sha, eligibility_sha=new_elig_sha)

        with self.assertRaisesRegex(ValueError, "replacement eligibility set differs"):
            self._run()

    def test_reserve_must_link_to_exact_eligible_primary(self):
        eligibility = json.loads(
            (self.cumulative / "REPLACEMENT_ELIGIBILITY.json").read_text(encoding="utf-8")
        )
        eligibility["eligible"][0]["reserve_slots"][0]["slot_id"] = "wrong-reserve"
        write_json(self.cumulative / "REPLACEMENT_ELIGIBILITY.json", eligibility)
        new_sha = sha256_file(self.cumulative / "REPLACEMENT_ELIGIBILITY.json")
        manifest = json.loads(
            (self.cumulative / "CUMULATIVE_MANIFEST.json").read_text(encoding="utf-8")
        )
        manifest["replacement_eligibility_sha256"] = new_sha
        write_json(self.cumulative / "CUMULATIVE_MANIFEST.json", manifest)
        evidence = json.loads(self.evidence_path.read_text(encoding="utf-8"))
        evidence["bindings"]["replacement_eligibility_sha256"] = new_sha
        write_json(self.evidence_path, evidence)
        self._rebind_status(eligibility_sha=new_sha)

        with self.assertRaisesRegex(ValueError, "not a frozen reserve"):
            self._run()

    def test_superseded_cumulative_checkpoint_is_rejected_even_if_canonical(self):
        superseded = self.root / "artifacts" / "CUMULATIVE_PRIMARY_EVIDENCE_168.json"
        superseded.write_bytes(self.evidence_path.read_bytes())
        with self.assertRaisesRegex(
            ValueError,
            "evidence path is not the reviewed post-consolidation source",
        ):
            self._run(superseded)

    def test_nonempty_output_directory_fails_closed(self):
        self.out.mkdir()
        (self.out / "stale.txt").write_text("stale", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "output directory must be empty"):
            self._run()


if __name__ == "__main__":
    unittest.main()
