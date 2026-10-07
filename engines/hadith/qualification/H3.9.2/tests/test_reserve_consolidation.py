from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmark_campaign.core import canonical_json_bytes, load_json, load_jsonl, sha256_bytes, sha256_file
from benchmark_campaign import reserve_consolidation


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class ReserveConsolidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "root"
        self.root.mkdir()
        (self.root / "artifacts").mkdir()
        self.evidence_root = Path(self.tmp.name) / "evidence"
        self.evidence_root.mkdir()
        self.source_cache = Path(self.tmp.name) / "source-cache"
        self.source_cache.mkdir()
        self.out = Path(self.tmp.name) / "out"

        self.primary0 = {
            "slot_id": "p0",
            "benchmark_id": "b1",
            "partition": "non_holdout",
        }
        self.primary1 = {
            "slot_id": "p1",
            "benchmark_id": "b1",
            "partition": "non_holdout",
        }
        self.reserve0 = {
            "slot_id": "r0",
            "benchmark_id": "b1",
            "partition": "non_holdout",
            "candidate_slot_kind": "reserve",
            "replacement_for_slot_id": "p0",
            "reserve_attempt": 1,
        }
        self.reserve1 = {
            "slot_id": "r1",
            "benchmark_id": "b1",
            "partition": "non_holdout",
            "candidate_slot_kind": "reserve",
            "replacement_for_slot_id": "p1",
            "reserve_attempt": 1,
        }
        self.plan = {
            "campaign_id": "H3.9.2",
            "slots": [self.primary0, self.primary1, self.reserve0, self.reserve1],
        }
        self.plan_sha = sha256_bytes(canonical_json_bytes(self.plan))

        self.activation_path = self.root / "artifacts" / "RESERVE_ACTIVATION.json"
        self.activation = {
            "campaign_id": "H3.9.2",
            "kind": "reserve_activation_manifest",
            "factory_plan_sha256": self.plan_sha,
            "cumulative_ledger_sha256": "a" * 64,
            "replacement_eligibility_sha256": "b" * 64,
            "activated_reserve_slot_count": 2,
            "activated": [
                {
                    "reserve_slot_id": "r0",
                    "replacement_for_slot_id": "p0",
                    "primary_task_id": "p0",
                    "primary_task_fingerprint": "0" * 64,
                    "primary_offset": 0,
                    "eligibility_reason": "terminal",
                },
                {
                    "reserve_slot_id": "r1",
                    "replacement_for_slot_id": "p1",
                    "primary_task_id": "p1",
                    "primary_task_fingerprint": "1" * 64,
                    "primary_offset": 1,
                    "eligibility_reason": "terminal",
                },
            ],
        }
        _write_json(self.activation_path, self.activation)
        self.activation_sha = sha256_file(self.activation_path)

        self.artifacts = []
        self.validated = {}
        for offset, (task_id, outcome) in enumerate((("r0", "promoted"), ("r1", "skipped"))):
            artifact_id = 100 + offset
            evidence = self.evidence_root / f"run-99-artifact-{artifact_id}"
            evidence.mkdir()
            summary = {
                "task_offset": offset,
                "task_limit": 1,
                "selected_task_count": 1,
            }
            _write_json(evidence / "CURATION_RUN_SUMMARY.json", summary)
            summary_sha = sha256_file(evidence / "CURATION_RUN_SUMMARY.json")
            origin = {
                "github_run_id": 99,
                "github_run_attempt": 1 if offset else 2,
                "source_job_id": 200 + offset,
                "head_sha": "c" * 40,
                "artifact_id": artifact_id,
                "artifact_name": f"h392-curation-chunk-{offset}-1",
                "artifact_sha256": str(offset + 2) * 64,
                "summary_sha256": summary_sha,
                "encrypted_bundle_sha256": str(offset + 4) * 64,
            }
            _write_json(evidence / "ORIGIN.json", origin)
            self.artifacts.append({
                "task_offset": offset,
                "task_limit": 1,
                "run_attempt": origin["github_run_attempt"],
                "source_job_id": origin["source_job_id"],
                "artifact_id": artifact_id,
                "artifact_name": origin["artifact_name"],
                "artifact_digest": "sha256:" + origin["artifact_sha256"],
                "summary_sha256": summary_sha,
                "encrypted_bundle_sha256": origin["encrypted_bundle_sha256"],
            })
            task = self.reserve0 if task_id == "r0" else self.reserve1
            ledger_row = {
                "task_id": task_id,
                "slot_id": task_id,
                "task_fingerprint": ("d" if task_id == "r0" else "e") * 64,
                "benchmark_id": "b1",
                "anchor_source_id": "s1",
                "outcome": outcome,
                "reconcile_reason": None if outcome == "promoted" else "no_curator_candidate",
                "canonical_reason": "promoted" if outcome == "promoted" else "curator_no_candidate",
                "case_id": "case-r0" if outcome == "promoted" else None,
                "replacement_eligible": False,
                "source_run_id": 99,
                "source_run_attempt": origin["github_run_attempt"],
                "source_sha": "c" * 40,
                "source_artifact_id": artifact_id,
                "source_artifact_sha256": origin["artifact_sha256"],
                "source_encrypted_bundle_sha256": origin["encrypted_bundle_sha256"],
                "candidate_slot_kind": "reserve",
                "replacement_for_slot_id": task["replacement_for_slot_id"],
                "reserve_attempt": 1,
                "reserve_activation_sha256": self.activation_sha,
                "terminal_failure": outcome == "skipped",
            }
            reviewed = {}
            if outcome == "promoted":
                reviewed = {
                    task_id: {
                        "case_id": "case-r0",
                        "benchmark_id": "b1",
                        "factory_slot_id": "r0",
                        "factory_verification": {
                            "slot_binding_sha256": sha256_bytes(
                                canonical_json_bytes(self.reserve0)
                            )
                        },
                    }
                }
            self.validated[str(evidence)] = {
                "origin": origin,
                "summary": summary,
                "tasks": {task_id: task},
                "ledger_rows": [ledger_row],
                "reviewed": reviewed,
                "adjudication": {},
                "reserve_activation": self.activation,
                "reserve_activation_sha256": self.activation_sha,
            }

        self.status = {
            "freeze_schema_version": 26,
            "reserve_execution_target": {
                "ready": False,
                "completed": False,
                "execution_succeeded": True,
                "consolidation_pending": True,
                "expected_task_count": 2,
                "activation_manifest_sha256": self.activation_sha,
                "successful_run_id": 99,
                "successful_run_final_attempt": 2,
                "runner_commit": "c" * 40,
                "aggregate_artifact_id": 500,
                "aggregate_artifact_digest": "sha256:" + "f" * 64,
                "aggregate_summary_sha256": "9" * 64,
            },
            "reserve_consolidation_target": {
                "ready": True,
                "completed": False,
                "workflow": ".github/workflows/h392-reserve-consolidation.yml",
                "protocol_freeze_schema": 26,
                "source_run_id": 99,
                "source_run_final_attempt": 2,
                "source_head_sha": "c" * 40,
                "expected_task_count": 2,
                "expected_shards": 2,
                "activation_manifest_sha256": self.activation_sha,
                "cumulative_ledger_sha256": "a" * 64,
                "replacement_eligibility_sha256": "b" * 64,
                "aggregate_artifact_id": 500,
                "aggregate_artifact_digest": "sha256:" + "f" * 64,
                "aggregate_summary_sha256": "9" * 64,
                "expected_outcomes": {
                    "promoted": 1,
                    "adjudication": 0,
                    "skipped": 1,
                },
                "source_artifacts": self.artifacts,
            },
            "last_completed_cumulative_consolidation": {
                "expected_primary_tasks": 2,
                "promoted_primary_count": 0,
                "pending_adjudication_count": 0,
                "skipped_primary_count": 2,
            },
        }
        _write_json(self.root / "artifacts" / "H3.9.2-STATUS.json", self.status)

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, plan=None, activation=None):
        def fake_validate(_root, evidence, _activation, source_cache_dir=None):
            return self.validated[str(evidence)]

        with patch.object(
            reserve_consolidation,
            "validate_reserve_activation",
            return_value=activation or self.activation,
        ), patch.object(
            reserve_consolidation, "build_factory_plan", return_value=plan or self.plan
        ), patch.object(
            reserve_consolidation, "validate_reserve_run_evidence", side_effect=fake_validate
        ):
            return reserve_consolidation.consolidate_reserve_evidence(
                self.root,
                self.evidence_root,
                self.out,
                source_cache_dir=self.source_cache,
                activation_path=self.activation_path,
            )

    def test_consolidation_derives_exhaustion_and_minimum_shortfall(self):
        summary = self._run()
        self.assertEqual(summary["outcomes"], {"promoted": 1, "skipped": 1})
        self.assertEqual(summary["reviewed_record_count"], 1)
        self.assertEqual(summary["exhausted_slot_count"], 1)
        self.assertEqual(summary["maximum_fillable_slots_under_current_capacity"], 1)
        self.assertEqual(summary["minimum_capacity_shortfall"], 1)
        ledger = load_jsonl(self.out / "RESERVE_LEDGER.jsonl")
        self.assertEqual([row["reserve_offset"] for row in ledger], [0, 1])
        self.assertEqual([row["slot_state"] for row in ledger], [
            "replacement_promoted", "exhausted"
        ])
        exhausted = load_json(self.out / "EXHAUSTED_SLOTS.json")
        self.assertEqual(exhausted["exhausted_slot_count"], 1)
        self.assertFalse(exhausted["policy"]["automatic_second_reserve_authorized"])

    def test_repository_artifact_attempt_binding_fails_closed(self):
        self.validated[str(self.evidence_root / "run-99-artifact-101")][
            "origin"
        ]["github_run_attempt"] = 2
        with self.assertRaisesRegex(ValueError, "origin github_run_attempt differs"):
            self._run()

    def test_exhaustion_requires_no_unconsumed_preregistered_reserve(self):
        extra = {
            **self.reserve1,
            "slot_id": "r1-second",
            "reserve_attempt": 2,
        }
        plan = {
            **self.plan,
            "slots": [*self.plan["slots"], extra],
        }
        activation = dict(self.activation)
        activation["factory_plan_sha256"] = sha256_bytes(canonical_json_bytes(plan))
        with self.assertRaisesRegex(ValueError, "unconsumed preregistered reserve capacity"):
            self._run(plan=plan, activation=activation)


class RepositoryReserveConsolidationTargetTests(unittest.TestCase):
    def test_real_target_preserves_mixed_attempt_provenance_and_exact_coverage(self):
        root = Path(__file__).resolve().parents[1]
        status = json.loads(
            (root / "artifacts" / "H3.9.2-STATUS.json").read_text(encoding="utf-8")
        )
        execution = status["reserve_execution_target"]
        self.assertFalse(execution["ready"])
        self.assertFalse(execution["completed"])
        self.assertTrue(execution["execution_succeeded"])
        self.assertTrue(execution["consolidation_pending"])
        self.assertEqual(execution["successful_run_id"], 37532437191)
        self.assertEqual(execution["successful_run_final_attempt"], 2)

        target = status["reserve_consolidation_target"]
        self.assertTrue(target["ready"])
        self.assertFalse(target["completed"])
        self.assertEqual(target["expected_task_count"], 41)
        self.assertEqual(target["expected_shards"], 6)
        self.assertEqual(
            target["expected_outcomes"],
            {"promoted": 7, "adjudication": 24, "skipped": 10},
        )
        artifacts = sorted(target["source_artifacts"], key=lambda row: row["task_offset"])
        self.assertEqual(
            [(row["task_offset"], row["task_limit"]) for row in artifacts],
            [(0, 8), (8, 8), (16, 8), (24, 8), (32, 8), (40, 1)],
        )
        self.assertEqual([row["run_attempt"] for row in artifacts], [2, 1, 1, 1, 1, 1])
        self.assertEqual(len({row["artifact_id"] for row in artifacts}), 6)
        self.assertEqual(len({row["source_job_id"] for row in artifacts}), 6)


if __name__ == "__main__":
    unittest.main()
