from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmark_campaign import reserve2_consolidation
from benchmark_campaign.core import (
    canonical_json_bytes,
    load_json,
    load_jsonl,
    sha256_bytes,
    sha256_file,
)


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class Reserve2ConsolidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root = base / "root"
        (self.root / "artifacts").mkdir(parents=True)
        self.evidence_root = base / "evidence"
        self.evidence_root.mkdir()
        self.source_cache = base / "source-cache"
        self.source_cache.mkdir()
        self.out = base / "out"

        self.slot0 = {
            "slot_id": "p0:reserve:02",
            "benchmark_id": "b1",
            "partition": "non_holdout",
            "candidate_slot_kind": "reserve",
            "replacement_for_slot_id": "p0",
            "reserve_attempt": 2,
        }
        self.slot1 = {
            "slot_id": "p1:reserve:02",
            "benchmark_id": "b1",
            "partition": "non_holdout",
            "candidate_slot_kind": "reserve",
            "replacement_for_slot_id": "p1",
            "reserve_attempt": 2,
        }
        self.extension = {
            "schema_version": 1,
            "campaign_id": "H3.9.2",
            "kind": "selective_reserve_capacity_extension_manifest",
            "protocol_freeze_schema": 27,
            "source_reserve_consolidation_freeze_schema": 26,
            "base_factory_plan_sha256": "a" * 64,
            "reserve_ledger_sha256": "b" * 64,
            "exhausted_slots_sha256": "c" * 64,
            "new_reserve_slot_count": 2,
            "extensions": [
                {
                    "primary_slot_id": "p0",
                    "prior_reserve_slot_id": "p0:reserve:01",
                    "prior_reserve_offset": 0,
                    "prior_reserve_task_fingerprint": "d" * 64,
                    "new_reserve_slot_id": self.slot0["slot_id"],
                    "new_reserve_slot": self.slot0,
                },
                {
                    "primary_slot_id": "p1",
                    "prior_reserve_slot_id": "p1:reserve:01",
                    "prior_reserve_offset": 1,
                    "prior_reserve_task_fingerprint": "e" * 64,
                    "new_reserve_slot_id": self.slot1["slot_id"],
                    "new_reserve_slot": self.slot1,
                },
            ],
        }
        self.extension_path = self.root / "artifacts" / "CAPACITY_EXTENSION.json"
        _write_json(self.extension_path, self.extension)
        self.extension_sha = sha256_file(self.extension_path)

        self.prior_path = self.root / "artifacts" / "PRIOR_PROMOTED_CASE_IDS.json"
        self.primary_prior_binding = {
            "source_run_id": 80,
            "source_run_attempt": 1,
            "source_head_sha": "a" * 40,
            "workflow": ".github/workflows/h392-cumulative-consolidation.yml",
            "artifact_id": 81,
            "artifact_name": "h392-cumulative-primary-evidence",
            "artifact_digest": "sha256:" + "3" * 64,
            "summary_sha256": "4" * 64,
            "encrypted_bundle_sha256": "5" * 64,
            "ledger_sha256": "6" * 64,
            "promoted_count": 2,
        }
        self.reserve_prior_binding = {
            "source_run_id": 90,
            "source_run_attempt": 1,
            "source_head_sha": "b" * 40,
            "workflow": ".github/workflows/h392-reserve-consolidation.yml",
            "artifact_id": 91,
            "artifact_name": "h392-reserve-consolidated-evidence",
            "artifact_digest": "sha256:" + "7" * 64,
            "summary_sha256": "8" * 64,
            "encrypted_bundle_sha256": "9" * 64,
            "ledger_sha256": "a" * 64,
            "promoted_count": 1,
        }
        self._write_prior_ids(["prior-a", "prior-b", "prior-c"])

        self.artifacts = []
        self.validated = {}
        for offset, (slot, outcome) in enumerate(
            ((self.slot0, "promoted"), (self.slot1, "skipped"))
        ):
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
                "github_run_attempt": 1,
                "source_job_id": 200 + offset,
                "head_sha": "f" * 40,
                "artifact_id": artifact_id,
                "artifact_name": f"h392-curation-chunk-{offset}-1",
                "artifact_sha256": str(offset + 2) * 64,
                "summary_sha256": summary_sha,
                "encrypted_bundle_sha256": str(offset + 4) * 64,
            }
            _write_json(evidence / "ORIGIN.json", origin)
            self.artifacts.append(
                {
                    "task_offset": offset,
                    "task_limit": 1,
                    "run_attempt": 1,
                    "source_job_id": origin["source_job_id"],
                    "artifact_id": artifact_id,
                    "artifact_name": origin["artifact_name"],
                    "artifact_digest": "sha256:" + origin["artifact_sha256"],
                    "summary_sha256": summary_sha,
                    "encrypted_bundle_sha256": origin["encrypted_bundle_sha256"],
                }
            )

            task_id = slot["slot_id"]
            ledger = {
                "task_id": task_id,
                "slot_id": task_id,
                "task_fingerprint": ("1" if offset == 0 else "2") * 64,
                "benchmark_id": "b1",
                "anchor_source_id": "s1",
                "outcome": outcome,
                "reconcile_reason": None if outcome == "promoted" else "no_curator_candidate",
                "canonical_reason": "promoted" if outcome == "promoted" else "curator_no_candidate",
                "case_id": "case-r2" if outcome == "promoted" else None,
                "replacement_eligible": False,
                "source_run_id": 99,
                "source_run_attempt": 1,
                "source_sha": "f" * 40,
                "source_artifact_id": artifact_id,
                "source_artifact_sha256": origin["artifact_sha256"],
                "source_encrypted_bundle_sha256": origin["encrypted_bundle_sha256"],
                "candidate_slot_kind": "reserve",
                "replacement_for_slot_id": slot["replacement_for_slot_id"],
                "reserve_attempt": 2,
                "capacity_extension_sha256": self.extension_sha,
                "terminal_failure": outcome == "skipped",
            }
            reviewed = {}
            if outcome == "promoted":
                reviewed[task_id] = {
                    "case_id": "case-r2",
                    "benchmark_id": "b1",
                    "factory_slot_id": task_id,
                    "factory_verification": {
                        "slot_binding_sha256": sha256_bytes(canonical_json_bytes(slot))
                    },
                }
            self.validated[str(evidence)] = {
                "origin": origin,
                "summary": summary,
                "tasks": {task_id: slot},
                "ledger_rows": [ledger],
                "reviewed": reviewed,
                "adjudication": {},
                "capacity_extension": self.extension,
                "capacity_extension_sha256": self.extension_sha,
            }

        self.status = {
            "freeze_schema_version": 29,
            "capacity_extension_proposal": {
                "frozen": True,
                "evidence_path": "artifacts/CAPACITY_EXTENSION.json",
            },
            "reserve2_execution_target": {
                "ready": False,
                "completed": False,
                "execution_succeeded": True,
                "consolidation_pending": True,
                "expected_task_count": 2,
                "successful_run_id": 99,
                "successful_run_attempt": 1,
                "runner_commit": "f" * 40,
                "aggregate_artifact_id": 500,
                "aggregate_artifact_digest": "sha256:" + "9" * 64,
                "aggregate_summary_sha256": "8" * 64,
                "capacity_extension_manifest_sha256": self.extension_sha,
            },
            "reserve2_consolidation_target": {
                "ready": True,
                "completed": False,
                "workflow": ".github/workflows/h392-reserve2-consolidation.yml",
                "protocol_freeze_schema": 29,
                "source_run_id": 99,
                "source_run_attempt": 1,
                "source_head_sha": "f" * 40,
                "expected_task_count": 2,
                "expected_shards": 2,
                "capacity_extension_manifest_sha256": self.extension_sha,
                "aggregate_artifact_id": 500,
                "aggregate_artifact_digest": "sha256:" + "9" * 64,
                "aggregate_summary_sha256": "8" * 64,
                "prior_promoted_case_id_surface": {
                    "expected_promoted_case_id_count": 3,
                    "primary": self.primary_prior_binding,
                    "reserve": self.reserve_prior_binding,
                },
                "expected_outcomes": {
                    "promoted": 1,
                    "adjudication": 0,
                    "skipped": 1,
                },
                "source_artifacts": self.artifacts,
            },
            "last_completed_cumulative_consolidation": {
                "successful_run_id": 80,
                "runner_commit": "a" * 40,
                "artifact_id": 81,
                "artifact_digest": "sha256:" + "3" * 64,
                "summary_sha256": "4" * 64,
                "encrypted_bundle_sha256": "5" * 64,
                "cumulative_ledger_sha256": "6" * 64,
                "promoted_primary_count": 2,
            },
            "last_completed_reserve_consolidation": {
                "successful_run_id": 90,
                "runner_commit": "b" * 40,
                "artifact_id": 91,
                "artifact_digest": "sha256:" + "7" * 64,
                "summary_sha256": "8" * 64,
                "encrypted_bundle_sha256": "9" * 64,
                "reserve_ledger_sha256": "a" * 64,
                "promoted_reserve_count": 1,
                "validated_promoted_record_count": 3,
                "total_pending_adjudication_count": 5,
                "exhausted_slot_count": 2,
                "record_quota": 10,
            },
        }
        _write_json(self.root / "artifacts" / "H3.9.2-STATUS.json", self.status)

    def _write_prior_ids(self, case_ids):
        payload = {
            "schema_version": 1,
            "campaign_id": "H3.9.2",
            "kind": "canonical_prior_promoted_case_id_set",
            "primary": dict(self.primary_prior_binding),
            "reserve": dict(self.reserve_prior_binding),
            "promoted_case_id_count": len(case_ids),
            "promoted_case_ids": sorted(case_ids),
        }
        _write_json(self.prior_path, payload)

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self):
        def fake_validate(_root, evidence, _extension, source_cache_dir=None):
            return self.validated[str(evidence)]

        with patch.object(
            reserve2_consolidation,
            "validate_frozen_capacity_extension",
            return_value=self.extension,
        ), patch.object(
            reserve2_consolidation,
            "validate_reserve2_run_evidence",
            side_effect=fake_validate,
        ):
            return reserve2_consolidation.consolidate_reserve2_evidence(
                self.root,
                self.evidence_root,
                self.out,
                source_cache_dir=self.source_cache,
                capacity_extension_path=self.extension_path,
                prior_promoted_case_ids_path=self.prior_path,
            )

    def test_consolidation_closes_prior_exhausted_surface(self):
        summary = self._run()
        self.assertEqual(summary["outcomes"], {"promoted": 1, "skipped": 1})
        self.assertEqual(summary["validated_promoted_record_count"], 4)
        self.assertEqual(summary["total_pending_adjudication_count"], 5)
        self.assertEqual(summary["remaining_exhausted_slot_count"], 1)
        self.assertEqual(summary["maximum_fillable_slots_under_current_capacity"], 9)
        self.assertEqual(summary["minimum_capacity_shortfall"], 1)

        ledger = load_jsonl(self.out / "RESERVE2_LEDGER.jsonl")
        self.assertEqual([row["reserve2_offset"] for row in ledger], [0, 1])
        self.assertEqual(
            [row["slot_state"] for row in ledger],
            ["replacement_promoted", "exhausted"],
        )
        exhausted = load_json(self.out / "RESERVE2_EXHAUSTED_SLOTS.json")
        self.assertEqual(exhausted["exhausted_slot_count"], 1)
        self.assertFalse(exhausted["policy"]["automatic_reserve3_authorized"])

    def test_artifact_provenance_mismatch_fails_closed(self):
        evidence = self.evidence_root / "run-99-artifact-101"
        self.validated[str(evidence)]["origin"]["source_job_id"] = 999
        with self.assertRaisesRegex(ValueError, "job binding mismatch"):
            self._run()

    def test_prior_canonical_case_id_collision_fails_closed(self):
        self._write_prior_ids(["case-r2", "prior-b", "prior-c"])
        with self.assertRaisesRegex(
            ValueError, "collides with prior canonical record"
        ):
            self._run()

    def test_prior_promoted_binding_mismatch_fails_closed(self):
        payload = load_json(self.prior_path)
        payload["primary"]["ledger_sha256"] = "f" * 64
        _write_json(self.prior_path, payload)
        with self.assertRaisesRegex(
            ValueError, "primary binding mismatch: ledger_sha256"
        ):
            self._run()

    def test_unapproved_reserve2_task_fails_closed(self):
        evidence = self.evidence_root / "run-99-artifact-101"
        self.validated[str(evidence)]["ledger_rows"][0]["task_id"] = "unapproved"
        with self.assertRaisesRegex(ValueError, "not in frozen capacity extension"):
            self._run()


class RepositoryReserve2ConsolidationTargetTests(unittest.TestCase):
    def test_real_schema29_target_is_exact_execution_observation(self):
        root = Path(__file__).resolve().parents[1]
        status = load_json(root / "artifacts" / "H3.9.2-STATUS.json")
        self.assertEqual(status["freeze_schema_version"], 29)

        execution = status["reserve2_execution_target"]
        self.assertFalse(execution["ready"])
        self.assertTrue(execution["completed"])
        self.assertTrue(execution["execution_succeeded"])
        self.assertFalse(execution["consolidation_pending"])
        self.assertEqual(
            execution["canonical_evidence_path"],
            "artifacts/RESERVE2_CONSOLIDATION_EVIDENCE_10.json",
        )
        self.assertEqual(execution["successful_run_id"], 37613354755)
        self.assertEqual(execution["successful_run_attempt"], 1)
        self.assertEqual(
            execution["runner_commit"],
            "d6e04fc061426d2248dba0e9e4f7e5e484b6ae1b",
        )

        target = status["reserve2_consolidation_target"]
        self.assertFalse(target["ready"])
        self.assertTrue(target["completed"])
        self.assertEqual(target["expected_task_count"], 10)
        self.assertEqual(target["expected_shards"], 5)
        self.assertEqual(
            target["expected_outcomes"],
            {"promoted": 3, "adjudication": 5, "skipped": 2},
        )
        self.assertEqual(target["aggregate_artifact_id"], 11478509807)
        self.assertEqual(
            target["aggregate_artifact_digest"],
            "sha256:dc02b20177f70f86d6f404f30d4733ccd204e309acef817b9c3d665d265754a1",
        )
        self.assertEqual(
            target["aggregate_summary_sha256"],
            "22aa91a82d7b35eda0480806c89a417b222282edcd6aff86b7ff851210a75b73",
        )
        artifacts = sorted(target["source_artifacts"], key=lambda row: row["task_offset"])
        self.assertEqual(
            [(row["task_offset"], row["task_limit"]) for row in artifacts],
            [(0, 2), (2, 2), (4, 2), (6, 2), (8, 2)],
        )
        self.assertEqual([row["run_attempt"] for row in artifacts], [1, 1, 1, 1, 1])
        self.assertEqual(
            [row["artifact_id"] for row in artifacts],
            [11479539417, 11478512577, 11479629639, 11479158705, 11479910101],
        )
        self.assertEqual(len({row["source_job_id"] for row in artifacts}), 5)
        self.assertEqual(target["successful_run_id"], 37673850809)
        self.assertEqual(
            target["runner_commit"],
            "f01b6a15bf3a2f270bbb524a85519a2a3a4994f4",
        )
        self.assertEqual(target["artifact_id"], 11506885302)
        self.assertEqual(
            target["artifact_digest"],
            "sha256:d671e473fd5011af7908d05c3aa26246477a7b6af6bde7363ad91f14aab13191",
        )
        self.assertEqual(
            target["summary_sha256"],
            "bc6549c0dff231a56c3c2a4cc51c66cf3547a2d65943628b01a43ba9f2954459",
        )
        self.assertEqual(
            target["encrypted_bundle_sha256"],
            "9290c795b632bb40bc529176998b8adfe5c15698fbc7438c28271279796a1326",
        )

    def test_repository_frozen_reserve2_evidence_matches_completed_status(self):
        root = Path(__file__).resolve().parents[1]
        status = load_json(root / "artifacts" / "H3.9.2-STATUS.json")
        completed = status["last_completed_reserve2_consolidation"]
        evidence = load_json(root / completed["evidence_path"])
        self.assertTrue(evidence["canonical_main_evidence"])
        self.assertEqual(evidence["protocol_freeze_schema"], 29)
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
            evidence["bindings"]["reserve2_ledger_sha256"],
            completed["reserve2_ledger_sha256"],
        )
        self.assertEqual(
            evidence["bindings"]["reserve2_exhausted_slots_sha256"],
            completed["exhausted_slots_sha256"],
        )
        self.assertEqual(evidence["result"]["promoted"], 3)
        self.assertEqual(evidence["result"]["pending_reserve2_adjudication"], 5)
        self.assertEqual(evidence["result"]["exhausted"], 2)
        self.assertEqual(evidence["result"]["validated_promoted_record_count"], 50)
        self.assertEqual(evidence["result"]["total_pending_adjudication_count"], 158)
        self.assertEqual(evidence["result"]["minimum_capacity_shortfall"], 2)
        self.assertFalse(evidence["next_action"]["automatic_reserve3_authorized"])


if __name__ == "__main__":
    unittest.main()
