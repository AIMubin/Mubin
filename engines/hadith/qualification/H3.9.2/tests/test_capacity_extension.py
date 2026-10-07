from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmark_campaign import capacity_extension
from benchmark_campaign.core import canonical_json_bytes, dump_jsonl, load_json, sha256_bytes, sha256_file


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class CapacityExtensionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "root"
        self.root.mkdir()
        (self.root / "artifacts").mkdir()
        self.reserve_dir = Path(self.tmp.name) / "reserve"
        self.reserve_dir.mkdir()
        self.out = Path(self.tmp.name) / "CAPACITY_EXTENSION.json"

        self.primary = {
            "slot_id": "b:non_holdout:s:0001",
            "benchmark_id": "b",
            "partition": "non_holdout",
            "anchor_source_id": "s",
            "ordinal": 1,
            "task_type": "classification",
            "allowed_labels": ["yes", "no"],
            "auto_promotion": True,
            "risk_tier": 1,
            "visibility": "development_safe",
        }
        self.reserve1 = {
            **self.primary,
            "slot_id": "b:non_holdout:s:0001:reserve:01",
            "candidate_slot_kind": "reserve",
            "replacement_for_slot_id": self.primary["slot_id"],
            "reserve_attempt": 1,
        }
        self.plan = {
            "campaign_id": "H3.9.2",
            "factory_version": 1,
            "slot_count": 2,
            "target_total": 1,
            "primary_slot_count": 1,
            "reserve_slot_count": 1,
            "reserve_slots_per_primary": 1,
            "primary_holdout_slots": 0,
            "primary_non_holdout_slots": 1,
            "holdout_slots": 0,
            "non_holdout_slots": 1,
            "candidate_holdout_slots": 0,
            "candidate_non_holdout_slots": 2,
            "slots": [self.primary, self.reserve1],
        }
        self.plan_sha = sha256_bytes(canonical_json_bytes(self.plan))

        self.activation_path = self.root / "artifacts" / "ACTIVATION.json"
        _write_json(self.activation_path, {"placeholder": True})
        self.activation_sha = sha256_file(self.activation_path)
        self.activation = {
            "factory_plan_sha256": self.plan_sha,
            "activated": [{
                "reserve_slot_id": self.reserve1["slot_id"],
                "replacement_for_slot_id": self.primary["slot_id"],
            }],
        }

        self.ledger = [{
            "task_id": self.reserve1["slot_id"],
            "slot_id": self.reserve1["slot_id"],
            "task_fingerprint": "a" * 64,
            "reserve_offset": 0,
            "primary_slot_id": self.primary["slot_id"],
            "slot_state": "exhausted",
            "outcome": "skipped",
            "terminal_failure": True,
            "canonical_reason": "curator_rejection:adapter:contract_support_not_verbatim",
        }]
        dump_jsonl(self.reserve_dir / "RESERVE_LEDGER.jsonl", self.ledger)
        self.ledger_sha = sha256_file(self.reserve_dir / "RESERVE_LEDGER.jsonl")

        self.exhausted = {
            "schema_version": 1,
            "campaign_id": "H3.9.2",
            "kind": "exhausted_non_holdout_slots",
            "protocol_freeze_schema": 26,
            "activation_manifest_sha256": self.activation_sha,
            "reserve_ledger_sha256": self.ledger_sha,
            "exhausted_slot_count": 1,
            "exhausted": [{
                "primary_slot_id": self.primary["slot_id"],
                "reserve_slot_id": self.reserve1["slot_id"],
                "reserve_task_fingerprint": "a" * 64,
                "reserve_offset": 0,
                "canonical_reason": self.ledger[0]["canonical_reason"],
                "activation_manifest_sha256": self.activation_sha,
                "reserve_ledger_sha256": self.ledger_sha,
            }],
            "policy": {
                "automatic_second_reserve_authorized": False,
                "capacity_extension_requires_reviewed_protocol_change": True,
            },
        }
        _write_json(self.reserve_dir / "EXHAUSTED_SLOTS.json", self.exhausted)
        self.exhausted_sha = sha256_file(self.reserve_dir / "EXHAUSTED_SLOTS.json")

        self.reserve_manifest = {
            "campaign_id": "H3.9.2",
            "kind": "consolidated_approved_non_holdout_reserve_evidence",
            "protocol_freeze_schema": 26,
            "factory_plan_sha256": self.plan_sha,
            "activation_manifest_sha256": self.activation_sha,
            "reserve_ledger_sha256": self.ledger_sha,
            "exhausted_slots_sha256": self.exhausted_sha,
            "exhausted_slot_count": 1,
        }
        _write_json(self.reserve_dir / "RESERVE_MANIFEST.json", self.reserve_manifest)

        self.evidence_path = self.root / "artifacts" / "RESERVE_CONSOLIDATION_EVIDENCE.json"
        self.repository_evidence = {
            "evidence_kind": "approved_non_holdout_reserve_consolidation",
            "protocol_freeze_schema": 26,
            "bindings": {
                "reserve_ledger_sha256": self.ledger_sha,
                "exhausted_slots_sha256": self.exhausted_sha,
            },
            "result": {"exhausted": 1},
        }
        _write_json(self.evidence_path, self.repository_evidence)

        self.status = {
            "freeze_schema_version": 27,
            "reserve_activation": {
                "enabled": True,
                "evidence_path": "artifacts/ACTIVATION.json",
            },
            "last_completed_reserve_consolidation": {
                "successful_run_id": 500,
                "artifact_id": 600,
                "artifact_digest": "sha256:" + "b" * 64,
                "reserve_ledger_sha256": self.ledger_sha,
                "exhausted_slots_sha256": self.exhausted_sha,
                "exhausted_slot_count": 1,
                "minimum_capacity_shortfall": 1,
                "evidence_path": "artifacts/RESERVE_CONSOLIDATION_EVIDENCE.json",
            },
            "capacity_extension_target": {
                "ready": True,
                "completed": False,
                "workflow": ".github/workflows/h392-capacity-extension.yml",
                "protocol_freeze_schema": 27,
                "expected_exhausted_slot_count": 1,
                "new_reserve_attempt": 2,
                "reserve_ledger_sha256": self.ledger_sha,
                "exhausted_slots_sha256": self.exhausted_sha,
                "activation_manifest_sha256": self.activation_sha,
                "base_factory_plan_sha256": self.plan_sha,
            },
        }
        _write_json(self.root / "artifacts" / "H3.9.2-STATUS.json", self.status)

    def tearDown(self):
        self.tmp.cleanup()

    def _build(self):
        with patch.object(
            capacity_extension,
            "build_factory_plan",
            return_value=self.plan,
        ), patch.object(
            capacity_extension,
            "validate_reserve_activation",
            return_value=self.activation,
        ):
            return capacity_extension.build_capacity_extension_manifest(
                self.root,
                self.reserve_dir,
                self.out,
                expected_reserve_ledger_sha256=self.ledger_sha,
                expected_exhausted_slots_sha256=self.exhausted_sha,
                expected_exhausted_slot_count=1,
            )

    def test_builds_exact_append_only_reserve_attempt_2_proposal(self):
        result = self._build()
        self.assertEqual(result["protocol_freeze_schema"], 27)
        self.assertEqual(result["source_reserve_consolidation_freeze_schema"], 26)
        self.assertEqual(result["extended_primary_count"], 1)
        self.assertEqual(result["new_reserve_slot_count"], 1)
        self.assertEqual(result["new_reserve_attempt"], 2)
        self.assertFalse(result["execution_authorized"])
        self.assertTrue(result["requires_repository_approval"])
        self.assertTrue(result["policy"]["extension_is_append_only_overlay"])
        self.assertFalse(result["policy"]["base_factory_plan_is_mutated"])
        row = result["extensions"][0]
        self.assertEqual(
            row["new_reserve_slot_id"],
            self.primary["slot_id"] + ":reserve:02",
        )
        self.assertEqual(row["new_reserve_attempt"], 2)
        self.assertEqual(
            row["new_reserve_slot"]["replacement_for_slot_id"],
            self.primary["slot_id"],
        )
        self.assertEqual(
            row["new_reserve_slot_binding_sha256"],
            sha256_bytes(canonical_json_bytes(row["new_reserve_slot"])),
        )
        self.assertNotIn(row["new_reserve_slot_id"], {
            slot["slot_id"] for slot in self.plan["slots"]
        })

    def test_non_exhausted_reserve_cannot_receive_extension(self):
        self.ledger[0]["slot_state"] = "pending_adjudication"
        dump_jsonl(self.reserve_dir / "RESERVE_LEDGER.jsonl", self.ledger)
        new_sha = sha256_file(self.reserve_dir / "RESERVE_LEDGER.jsonl")
        self.status["last_completed_reserve_consolidation"]["reserve_ledger_sha256"] = new_sha
        self.status["capacity_extension_target"]["reserve_ledger_sha256"] = new_sha
        self.exhausted["reserve_ledger_sha256"] = new_sha
        self.exhausted["exhausted"][0]["reserve_ledger_sha256"] = new_sha
        _write_json(self.reserve_dir / "EXHAUSTED_SLOTS.json", self.exhausted)
        new_exhausted_sha = sha256_file(self.reserve_dir / "EXHAUSTED_SLOTS.json")
        self.status["last_completed_reserve_consolidation"]["exhausted_slots_sha256"] = new_exhausted_sha
        self.status["capacity_extension_target"]["exhausted_slots_sha256"] = new_exhausted_sha
        self.repository_evidence["bindings"]["reserve_ledger_sha256"] = new_sha
        self.repository_evidence["bindings"]["exhausted_slots_sha256"] = new_exhausted_sha
        _write_json(self.evidence_path, self.repository_evidence)
        self.reserve_manifest["reserve_ledger_sha256"] = new_sha
        self.reserve_manifest["exhausted_slots_sha256"] = new_exhausted_sha
        _write_json(self.reserve_dir / "RESERVE_MANIFEST.json", self.reserve_manifest)
        _write_json(self.root / "artifacts" / "H3.9.2-STATUS.json", self.status)
        with patch.object(
            capacity_extension, "build_factory_plan", return_value=self.plan
        ), patch.object(
            capacity_extension,
            "validate_reserve_activation",
            return_value=self.activation,
        ):
            with self.assertRaisesRegex(ValueError, "not exhausted"):
                capacity_extension.build_capacity_extension_manifest(
                    self.root,
                    self.reserve_dir,
                    self.out,
                    expected_reserve_ledger_sha256=new_sha,
                    expected_exhausted_slots_sha256=new_exhausted_sha,
                    expected_exhausted_slot_count=1,
                )

    def test_base_plan_must_not_already_contain_reserve_attempt_2(self):
        reserve2 = {
            **self.reserve1,
            "slot_id": self.primary["slot_id"] + ":reserve:02",
            "reserve_attempt": 2,
        }
        plan = {**self.plan, "slots": [*self.plan["slots"], reserve2], "slot_count": 3}
        plan_sha = sha256_bytes(canonical_json_bytes(plan))
        self.reserve_manifest["factory_plan_sha256"] = plan_sha
        _write_json(self.reserve_dir / "RESERVE_MANIFEST.json", self.reserve_manifest)
        self.activation["factory_plan_sha256"] = plan_sha
        self.status["capacity_extension_target"]["base_factory_plan_sha256"] = plan_sha
        _write_json(self.root / "artifacts" / "H3.9.2-STATUS.json", self.status)
        with patch.object(
            capacity_extension, "build_factory_plan", return_value=plan
        ), patch.object(
            capacity_extension,
            "validate_reserve_activation",
            return_value=self.activation,
        ):
            with self.assertRaisesRegex(ValueError, "already exists"):
                capacity_extension.build_capacity_extension_manifest(
                    self.root,
                    self.reserve_dir,
                    self.out,
                    expected_reserve_ledger_sha256=self.ledger_sha,
                    expected_exhausted_slots_sha256=self.exhausted_sha,
                    expected_exhausted_slot_count=1,
                )


class RepositoryCapacityExtensionTargetTests(unittest.TestCase):
    def test_real_target_is_exactly_the_canonical_ten_slot_shortfall(self):
        root = Path(__file__).resolve().parents[1]
        status = load_json(root / "artifacts" / "H3.9.2-STATUS.json")
        self.assertEqual(status["freeze_schema_version"], 28)
        self.assertTrue(status["capacity_extension_enabled"])
        target = status["capacity_extension_target"]
        self.assertFalse(target["ready"])
        self.assertTrue(target["completed"])
        self.assertEqual(target["protocol_freeze_schema"], 27)
        self.assertEqual(target["source_reserve_consolidation_freeze_schema"], 26)
        self.assertEqual(target["source_reserve_consolidation_run_id"], 37578659973)
        self.assertEqual(target["expected_exhausted_slot_count"], 10)
        self.assertEqual(target["minimum_capacity_shortfall"], 10)
        self.assertEqual(target["new_reserve_attempt"], 2)
        self.assertEqual(target["expected_new_reserve_slot_count"], 10)
        self.assertFalse(target["execution_authorized"])
        self.assertFalse(target["base_factory_plan_mutated"])
        adjudication = status["adjudication_review_surface"]
        self.assertEqual(adjudication["combined_pending_case_count"], 153)
        self.assertTrue(adjudication["human_or_authority_decision_required"])
        self.assertFalse(adjudication["ai_may_self_authorize_acceptance"])
        self.assertTrue(status["capacity_extension_proposal_frozen"])
        proposal = status["capacity_extension_proposal"]
        self.assertTrue(proposal["frozen"])
        self.assertTrue(proposal["enabled_for_execution"])
        self.assertFalse(proposal["execution_authorized"])
        self.assertTrue(proposal["requires_repository_approval"])
        self.assertEqual(proposal["workflow_run_id"], 37588897387)
        self.assertEqual(proposal["artifact_id"], 11467766861)
        self.assertEqual(
            proposal["artifact_digest"],
            "sha256:2b36aef77dfa885a01f271377d4f6164698c9d6cd56adb1c59aaba906c045115",
        )
        self.assertEqual(
            proposal["manifest_sha256"],
            "9bd2468737d0cd1b89227b3b625814dfc1a3cab25512fece98ae377ef1ac4fce",
        )

    def test_frozen_capacity_proposal_is_execution_enabled_only_by_schema28_status(self):
        root = Path(__file__).resolve().parents[1]
        status = load_json(root / "artifacts" / "H3.9.2-STATUS.json")
        path = root / status["capacity_extension_proposal"]["evidence_path"]
        manifest = capacity_extension.validate_frozen_capacity_extension(
            root,
            path,
            require_execution_enabled=True,
        )
        self.assertEqual(manifest["new_reserve_slot_count"], 10)
        self.assertFalse(manifest["execution_authorized"])
        self.assertTrue(status["capacity_extension_enabled"])
        execution = status["reserve2_execution_target"]
        self.assertTrue(execution["ready"])
        self.assertFalse(execution["completed"])
        self.assertEqual(execution["task_scope"], "approved_capacity_extension")
        self.assertEqual(
            execution["capacity_extension_manifest_sha256"],
            status["capacity_extension_proposal"]["manifest_sha256"],
        )

    def test_committed_capacity_proposal_is_exact_artifact_payload(self):
        root = Path(__file__).resolve().parents[1]
        status = load_json(root / "artifacts" / "H3.9.2-STATUS.json")
        proposal = status["capacity_extension_proposal"]
        path = root / proposal["evidence_path"]
        self.assertEqual(sha256_file(path), proposal["manifest_sha256"])
        obj = load_json(path)
        self.assertEqual(obj["kind"], "selective_reserve_capacity_extension_manifest")
        self.assertEqual(obj["protocol_freeze_schema"], 27)
        self.assertEqual(obj["extended_primary_count"], 10)
        self.assertEqual(obj["new_reserve_slot_count"], 10)
        self.assertEqual(obj["new_reserve_attempt"], 2)
        self.assertFalse(obj["execution_authorized"])
        self.assertTrue(obj["requires_repository_approval"])
        self.assertFalse(obj["policy"]["base_factory_plan_is_mutated"])
        self.assertTrue(obj["policy"]["extension_is_append_only_overlay"])
        rows = obj["extensions"]
        self.assertEqual(len(rows), 10)
        self.assertEqual(
            [row["prior_reserve_offset"] for row in rows],
            [0, 1, 2, 3, 4, 5, 13, 20, 21, 32],
        )
        self.assertEqual(len({row["primary_slot_id"] for row in rows}), 10)
        self.assertEqual(len({row["prior_reserve_slot_id"] for row in rows}), 10)
        self.assertEqual(len({row["new_reserve_slot_id"] for row in rows}), 10)
        for row in rows:
            self.assertEqual(
                row["new_reserve_slot_id"],
                row["primary_slot_id"] + ":reserve:02",
            )
            self.assertEqual(
                row["prior_reserve_slot_id"],
                row["primary_slot_id"] + ":reserve:01",
            )
            self.assertEqual(row["new_reserve_attempt"], 2)
            self.assertEqual(
                row["new_reserve_slot_binding_sha256"],
                sha256_bytes(canonical_json_bytes(row["new_reserve_slot"])),
            )
            self.assertEqual(
                row["prior_reserve_terminal_reason"],
                "curator_rejection:adapter:contract_support_not_verbatim",
            )


if __name__ == "__main__":
    unittest.main()
