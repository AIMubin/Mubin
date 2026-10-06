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
from benchmark_campaign.postconsolidation import prepare_postconsolidation_bindings


class PostConsolidationTests(unittest.TestCase):
    def _fixture(self, root: Path):
        (root / "artifacts").mkdir(parents=True)
        cumulative = root / "cumulative"
        cumulative.mkdir()

        primary_slots = []
        reserve_slots = []
        for i in range(210):
            primary_id = f"external-critical-commentary:non_holdout:s{i % 6}:{i + 1:04d}"
            primary = {
                "slot_id": primary_id,
                "benchmark_id": "external-critical-commentary",
                "partition": "non_holdout",
                "anchor_source_id": f"s{i % 6}",
                "ordinal": i + 1,
                "task_type": "classification",
                "allowed_labels": ["a", "b"],
                "auto_promotion": True,
                "risk_tier": 1,
                "visibility": "development_safe",
            }
            reserve = {
                **primary,
                "slot_id": f"{primary_id}:reserve:01",
                "candidate_slot_kind": "reserve",
                "replacement_for_slot_id": primary_id,
                "reserve_attempt": 1,
            }
            primary_slots.append(primary)
            reserve_slots.append(reserve)

        plan = {
            "campaign_id": "H3.9.2",
            "factory_version": 1,
            "slot_count": 420,
            "target_total": 210,
            "primary_slot_count": 210,
            "reserve_slot_count": 210,
            "reserve_slots_per_primary": 1,
            "primary_holdout_slots": 0,
            "primary_non_holdout_slots": 210,
            "holdout_slots": 0,
            "non_holdout_slots": 210,
            "candidate_holdout_slots": 0,
            "candidate_non_holdout_slots": 420,
            "slots": primary_slots + reserve_slots,
        }
        factory_plan_sha = sha256_bytes(canonical_json_bytes(plan))

        ledger = []
        adjudication = []
        eligible = []
        for i, slot in enumerate(primary_slots):
            tid = slot["slot_id"]
            fp = sha256_bytes(canonical_json_bytes({"task_id": tid, "n": i}))
            if i < 40:
                outcome = "promoted"
                canonical_reason = "promoted"
                reconcile_reason = None
                replaceable = False
            elif i < 169:
                outcome = "adjudication"
                canonical_reason = "curator_requested_adjudication"
                reconcile_reason = "curator_requested_adjudication"
                replaceable = False
            else:
                outcome = "skipped"
                canonical_reason = "curator_no_candidate"
                reconcile_reason = "no_curator_candidate"
                replaceable = True
            row = {
                "task_id": tid,
                "slot_id": slot["slot_id"],
                "task_fingerprint": fp,
                "benchmark_id": "external-critical-commentary",
                "anchor_source_id": slot["anchor_source_id"],
                "primary_offset": i,
                "outcome": outcome,
                "reconcile_reason": reconcile_reason,
                "canonical_reason": canonical_reason,
                "case_id": f"case-{i}" if outcome == "promoted" else None,
                "replacement_eligible": replaceable,
                "source_run_id": 1000 + (i // 64),
                "source_run_attempt": 1,
                "source_sha": "a" * 40,
                "source_artifact_id": 5000 + (i // 8),
                "source_artifact_sha256": "b" * 64,
                "source_encrypted_bundle_sha256": "c" * 64,
            }
            ledger.append(row)
            if outcome == "adjudication":
                adjudication.append({
                    "task_id": tid,
                    "reason": reconcile_reason,
                    "canonical_reason": canonical_reason,
                    "source_run_id": row["source_run_id"],
                    "source_sha": row["source_sha"],
                })
            if replaceable:
                reserve = reserve_slots[i]
                eligible.append({
                    "primary_slot_id": slot["slot_id"],
                    "primary_slot_binding_sha256": sha256_bytes(
                        canonical_json_bytes(slot)
                    ),
                    "primary_task_id": tid,
                    "primary_task_fingerprint": fp,
                    "primary_offset": i,
                    "primary_outcome": "skipped",
                    "eligibility_reason": canonical_reason,
                    "reserve_slots": [{
                        "slot_id": reserve["slot_id"],
                        "slot_binding_sha256": sha256_bytes(
                            canonical_json_bytes(reserve)
                        ),
                    }],
                    "cumulative_ledger_sha256": None,
                })

        ledger_path = cumulative / "CUMULATIVE_LEDGER.jsonl"
        adjudication_path = cumulative / "CUMULATIVE_ADJUDICATION.jsonl"
        dump_jsonl(ledger_path, ledger)
        dump_jsonl(adjudication_path, adjudication)
        ledger_sha = sha256_file(ledger_path)
        for row in eligible:
            row["cumulative_ledger_sha256"] = ledger_sha

        eligibility = {
            "schema_version": 1,
            "campaign_id": "H3.9.2",
            "kind": "primary_replacement_eligibility",
            "freeze_schema_version": 25,
            "factory_plan_sha256": factory_plan_sha,
            "cumulative_ledger_sha256": ledger_sha,
            "rules": {
                "promoted_is_replaceable": False,
                "pending_adjudication_is_replaceable": False,
                "terminal_primary_failure_is_replaceable": True,
                "reserve_reconciliation_enabled": False,
            },
            "eligible_primary_count": 41,
            "eligible": eligible,
        }
        eligibility_path = cumulative / "REPLACEMENT_ELIGIBILITY.json"
        write_json(eligibility_path, eligibility)
        eligibility_sha = sha256_file(eligibility_path)

        manifest = {
            "schema_version": 1,
            "campaign_id": "H3.9.2",
            "kind": "cumulative_non_holdout_primary_evidence",
            "freeze_schema_version": 25,
            "factory_plan_sha256": factory_plan_sha,
            "input_artifacts": [],
            "input_artifact_count": 27,
            "input_run_ids": [37280971913, 37295517184, 37326459365, 37426135905],
            "input_run_count": 4,
            "task_count": 210,
            "coverage_ranges": [{"start": 0, "end": 210}],
            "cumulative_ledger_sha256": ledger_sha,
            "cumulative_adjudication_sha256": sha256_file(adjudication_path),
            "replacement_eligibility_sha256": eligibility_sha,
            "reviewed_files": [],
            "reviewed_record_count": 40,
            "adjudication_count": 129,
            "replacement_eligible_primary_count": 41,
        }
        write_json(cumulative / "CUMULATIVE_MANIFEST.json", manifest)

        control = {
            "schema_version": 1,
            "campaign_id": "H3.9.2",
            "evidence_kind": "cumulative_non_holdout_primary_consolidation",
            "canonical_main_evidence": True,
            "runner_commit": "e1422b3262ee308084ce2212a2f2825fdc737032",
            "workflow": {
                "path": ".github/workflows/h392-cumulative-consolidation.yml",
                "run_id": 37471731102,
                "run_attempt": 1,
                "event": "workflow_dispatch",
                "conclusion": "success",
            },
            "artifact": {
                "id": 11416657955,
                "name": "h392-cumulative-primary-evidence",
                "digest": "sha256:" + "d" * 64,
                "redacted_summary_sha256": "e" * 64,
                "encrypted_bundle_sha256": "f" * 64,
            },
            "canonical_input": {
                "campaign_run_ids": [37280971913, 37295517184, 37326459365, 37426135905],
                "expected_primary_task_count": 210,
                "benchmark_id": "external-critical-commentary",
                "primary_offset_start": 0,
                "primary_offset_end_inclusive": 209,
                "exact_zero_based_prefix": True,
            },
            "result": {
                "task_count": 210,
                "promoted": 40,
                "pending_adjudication": 129,
                "skipped": 41,
                "replacement_eligible_primary_count": 41,
                "reviewed_record_count": 40,
                "canonical_reason_counts": {
                    "curator_requested_adjudication": 129,
                    "curator_no_candidate": 41,
                },
            },
            "bindings": {
                "cumulative_ledger_sha256": ledger_sha,
                "replacement_eligibility_sha256": eligibility_sha,
            },
            "reserve_policy": {
                "reserve_reconciliation_enabled": False,
                "pending_adjudication_is_replacement_eligible": False,
                "replacement_eligible_primary_count": 41,
                "activation_requires_separate_reviewed_protocol": True,
            },
        }
        control_path = root / "artifacts" / "CUMULATIVE_PRIMARY_EVIDENCE_210.json"
        write_json(control_path, control)

        status = {
            "campaign_id": "H3.9.2",
            "freeze_schema_version": 26,
            "reserve_reconciliation_enabled": False,
            "last_completed_cumulative_consolidation": {
                "expected_primary_tasks": 210,
                "successful_run_id": 37471731102,
                "cumulative_ledger_sha256": ledger_sha,
                "replacement_eligibility_sha256": eligibility_sha,
                "evidence_path": "artifacts/CUMULATIVE_PRIMARY_EVIDENCE_210.json",
            },
            "cumulative_consolidation_target": {
                "ready": False,
                "completed": True,
                "expected_primary_tasks": 210,
                "successful_run_id": 37471731102,
            },
        }
        write_json(root / "artifacts" / "H3.9.2-STATUS.json", status)
        return plan, cumulative, control_path

    def test_preparation_emits_only_opaque_public_commitments(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan, cumulative, control = self._fixture(root)
            public = root / "public"
            private = root / "private"
            with patch(
                "benchmark_campaign.postconsolidation.build_factory_plan",
                return_value=plan,
            ):
                summary = prepare_postconsolidation_bindings(
                    root,
                    cumulative,
                    control,
                    public,
                    private,
                    commitment_secret="test-secret",
                )

            self.assertEqual(summary["reserve_authorized_count"], 41)
            self.assertEqual(summary["pending_adjudication_count"], 129)
            self.assertFalse(summary["reserve_reconciliation_enabled"])
            self.assertFalse(summary["adjudication_execution_enabled"])

            binding = json.loads(
                (public / "POSTCONSOLIDATION_BINDING.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(binding["reserve"]["commitment_leaf_sha256"]), 41)
            self.assertEqual(len(binding["adjudication"]["commitment_leaf_sha256"]), 129)
            self.assertFalse(binding["contains_task_ids"])
            self.assertFalse(binding["contains_slot_ids"])
            rendered = json.dumps(binding, ensure_ascii=False)
            self.assertNotIn("external-critical-commentary:non_holdout:", rendered)
            self.assertNotIn('"task_id"', rendered)
            self.assertNotIn('"slot_id"', rendered)

            private_reserve = json.loads(
                (private / "RESERVE_AUTHORIZATION_PRIVATE.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(private_reserve["rows"]), 41)
            private_adjudication = [
                json.loads(line)
                for line in (private / "ADJUDICATION_QUEUE_PRIVATE.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
                if line.strip()
            ]
            self.assertEqual(len(private_adjudication), 129)

    def test_same_secret_and_evidence_produce_same_commitment_sets(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan, cumulative, control = self._fixture(root)
            with patch(
                "benchmark_campaign.postconsolidation.build_factory_plan",
                return_value=plan,
            ):
                first = prepare_postconsolidation_bindings(
                    root,
                    cumulative,
                    control,
                    root / "public-1",
                    root / "private-1",
                    commitment_secret="stable-secret",
                )
                second = prepare_postconsolidation_bindings(
                    root,
                    cumulative,
                    control,
                    root / "public-2",
                    root / "private-2",
                    commitment_secret="stable-secret",
                )
            self.assertEqual(
                first["reserve_commitment_set_sha256"],
                second["reserve_commitment_set_sha256"],
            )
            self.assertEqual(
                first["adjudication_commitment_set_sha256"],
                second["adjudication_commitment_set_sha256"],
            )

    def test_tampered_eligibility_binding_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan, cumulative, control = self._fixture(root)
            eligibility_path = cumulative / "REPLACEMENT_ELIGIBILITY.json"
            eligibility = json.loads(eligibility_path.read_text(encoding="utf-8"))
            eligibility["eligible"][0]["reserve_slots"][0]["slot_binding_sha256"] = "0" * 64
            write_json(eligibility_path, eligibility)

            with patch(
                "benchmark_campaign.postconsolidation.build_factory_plan",
                return_value=plan,
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "materialized replacement eligibility hash differs",
                ):
                    prepare_postconsolidation_bindings(
                        root,
                        cumulative,
                        control,
                        root / "public",
                        root / "private",
                        commitment_secret="test-secret",
                    )


if __name__ == "__main__":
    unittest.main()
