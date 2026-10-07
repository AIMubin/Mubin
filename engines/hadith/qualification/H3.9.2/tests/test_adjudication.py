from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmark_campaign import adjudication
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


def _write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


class AdjudicationPacketTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root = base / "root"
        (self.root / "artifacts").mkdir(parents=True)
        self.canonical = base / "canonical"
        self.evidence = base / "evidence"
        self.cache = base / "cache"
        self.out = base / "out"
        self.evidence.mkdir()
        self.cache.mkdir()
        self.activation = self.root / "artifacts" / "activation.json"
        self.extension = self.root / "artifacts" / "extension.json"
        _write_json(self.activation, {"x": 1})
        _write_json(self.extension, {"x": 2})

        self.layer_specs = (
            ("primary", 129, "CUMULATIVE_LEDGER.jsonl", "CUMULATIVE_ADJUDICATION.jsonl", "CUMULATIVE_MANIFEST.json", "cumulative_ledger_sha256", "cumulative_adjudication_sha256", "primary_offset"),
            ("reserve01", 24, "RESERVE_LEDGER.jsonl", "RESERVE_ADJUDICATION.jsonl", "RESERVE_MANIFEST.json", "reserve_ledger_sha256", "reserve_adjudication_sha256", "reserve_offset"),
            ("reserve02", 5, "RESERVE2_LEDGER.jsonl", "RESERVE2_ADJUDICATION.jsonl", "RESERVE2_MANIFEST.json", "reserve2_ledger_sha256", "reserve2_adjudication_sha256", "reserve2_offset"),
        )
        self.bindings = {}
        ordinal = 0
        for layer_index, (layer, count, ledger_name, adjudication_name, manifest_name, ledger_field, adjudication_field, offset_field) in enumerate(self.layer_specs):
            d = self.canonical / layer
            d.mkdir(parents=True)
            ledger = []
            adj = []
            for i in range(count):
                tid = f"{layer}-task-{i:03d}"
                ledger.append({
                    "task_id": tid,
                    "slot_id": f"{layer}-slot-{i:03d}",
                    "task_fingerprint": sha256_bytes(f"{layer}:{i}".encode()),
                    "benchmark_id": "external-critical-commentary",
                    "anchor_source_id": "openiti:test",
                    "outcome": "adjudication",
                    "reconcile_reason": "gold_disagreement",
                    "canonical_reason": "gold_disagreement",
                    "case_id": None,
                    "replacement_eligible": False,
                    "source_run_id": 1000 + layer_index,
                    "source_run_attempt": 1,
                    "source_sha": str(layer_index + 1) * 40,
                    "source_artifact_id": 2000 + layer_index,
                    "source_artifact_sha256": str(layer_index + 2) * 64,
                    "source_encrypted_bundle_sha256": str(layer_index + 5) * 64,
                    offset_field: i,
                })
                adj.append({
                    "task_id": tid,
                    "reason": "gold_disagreement",
                    "canonical_reason": "gold_disagreement",
                })
                ordinal += 1
            _write_jsonl(d / ledger_name, ledger)
            _write_jsonl(d / adjudication_name, adj)
            manifest = {
                ledger_field: sha256_file(d / ledger_name),
                adjudication_field: sha256_file(d / adjudication_name),
            }
            _write_json(d / manifest_name, manifest)
            self.bindings[layer] = {
                "ledger_sha256": manifest[ledger_field],
                "artifact_id": 3000 + layer_index,
                "artifact_digest": "sha256:" + str(layer_index + 6) * 64,
                "encrypted_bundle_sha256": str(layer_index + 9) * 64,
                "successful_run_id": 4000 + layer_index,
                "runner_commit": str(layer_index + 7) * 40,
            }

        status = {
            "freeze_schema_version": 30,
            "adjudication_review_surface": {
                "combined_pending_case_count": 158,
                "human_or_authority_decision_required": True,
                "ai_may_self_authorize_acceptance": False,
            },
            "adjudication_packet_target": {
                "ready": True,
                "completed": False,
                "workflow": ".github/workflows/h392-adjudication-packet.yml",
                "expected_case_count": 158,
                "layer_counts": {"primary": 129, "reserve01": 24, "reserve02": 5},
            },
            "last_completed_cumulative_consolidation": {
                "cumulative_ledger_sha256": self.bindings["primary"]["ledger_sha256"],
                "artifact_id": self.bindings["primary"]["artifact_id"],
                "artifact_digest": self.bindings["primary"]["artifact_digest"],
                "encrypted_bundle_sha256": self.bindings["primary"]["encrypted_bundle_sha256"],
                "successful_run_id": self.bindings["primary"]["successful_run_id"],
                "runner_commit": self.bindings["primary"]["runner_commit"],
            },
            "last_completed_reserve_consolidation": {
                "reserve_ledger_sha256": self.bindings["reserve01"]["ledger_sha256"],
                "artifact_id": self.bindings["reserve01"]["artifact_id"],
                "artifact_digest": self.bindings["reserve01"]["artifact_digest"],
                "encrypted_bundle_sha256": self.bindings["reserve01"]["encrypted_bundle_sha256"],
                "successful_run_id": self.bindings["reserve01"]["successful_run_id"],
                "runner_commit": self.bindings["reserve01"]["runner_commit"],
            },
            "last_completed_reserve2_consolidation": {
                "reserve2_ledger_sha256": self.bindings["reserve02"]["ledger_sha256"],
                "artifact_id": self.bindings["reserve02"]["artifact_id"],
                "artifact_digest": self.bindings["reserve02"]["artifact_digest"],
                "encrypted_bundle_sha256": self.bindings["reserve02"]["encrypted_bundle_sha256"],
                "successful_run_id": self.bindings["reserve02"]["successful_run_id"],
                "runner_commit": self.bindings["reserve02"]["runner_commit"],
            },
        }
        _write_json(self.root / "artifacts" / "H3.9.2-STATUS.json", status)

    def tearDown(self):
        self.tmp.cleanup()

    def test_derive_target_is_exact_158_case_surface(self):
        target = adjudication.derive_adjudication_source_target(
            self.root, self.canonical
        )
        self.assertEqual(target["case_count"], 158)
        self.assertEqual(
            target["layer_counts"],
            {"primary": 129, "reserve01": 24, "reserve02": 5},
        )
        self.assertEqual(target["source_artifact_count"], 3)
        self.assertEqual(len(target["tasks"]), 158)
        unsigned = dict(target)
        stored = unsigned.pop("target_sha256")
        self.assertEqual(stored, sha256_bytes(canonical_json_bytes(unsigned)))

    def test_ai_self_authority_fails_closed(self):
        path = self.root / "artifacts" / "H3.9.2-STATUS.json"
        status = load_json(path)
        status["adjudication_review_surface"]["ai_may_self_authorize_acceptance"] = True
        _write_json(path, status)
        with self.assertRaisesRegex(ValueError, "AI self-authorization"):
            adjudication.derive_adjudication_source_target(self.root, self.canonical)

    def test_packet_builder_emits_encrypted_review_inputs_not_decisions(self):
        target = adjudication.derive_adjudication_source_target(
            self.root, self.canonical
        )
        by_artifact = {}
        for row in target["source_artifacts"]:
            key = (row["layer"], row["artifact_id"])
            by_artifact[key] = {
                "tasks": {},
                "ledger_rows": [],
                "adjudication": {},
            }
            e = self.evidence / f'{row["layer"]}-run-{row["source_run_id"]}-artifact-{row["artifact_id"]}'
            bundle = e / "source-bearing"
            bundle.mkdir(parents=True)
            _write_json(e / "ORIGIN.json", {
                "adjudication_layer": row["layer"],
                "github_run_id": row["source_run_id"],
                "github_run_attempt": row["source_run_attempt"],
                "head_sha": row["source_head_sha"],
                "artifact_id": row["artifact_id"],
                "artifact_sha256": row["artifact_sha256"],
                "encrypted_bundle_sha256": row["encrypted_bundle_sha256"],
            })

        for row in target["tasks"]:
            key = (row["layer"], row["source_artifact_id"])
            slot = {
                "task_id": row["task_id"],
                "slot_id": row["slot_id"],
                "task_fingerprint": row["task_fingerprint"],
                "benchmark_id": row["benchmark_id"],
                "anchor_source_id": row["anchor_source_id"],
            }
            by_artifact[key]["tasks"][row["task_id"]] = slot
            by_artifact[key]["ledger_rows"].append({
                "task_id": row["task_id"],
                "outcome": "adjudication",
                "task_fingerprint": row["task_fingerprint"],
                "canonical_reason": row["canonical_reason"],
            })
            by_artifact[key]["adjudication"][row["task_id"]] = {
                "task_id": row["task_id"],
                "reason": row["reconcile_reason"],
            }

        validated_by_evidence = {}
        for row in target["source_artifacts"]:
            key = (row["layer"], row["artifact_id"])
            e = self.evidence / f'{row["layer"]}-run-{row["source_run_id"]}-artifact-{row["artifact_id"]}'
            bundle = e / "source-bearing"
            tasks = []
            curator = []
            verifier_tasks = []
            verifier = []
            adj = []
            for tid in row["task_ids"]:
                task = by_artifact[key]["tasks"][tid]
                tasks.append(task)
                curator.append({"task_id": tid, "status": "candidate", "candidate": {"source_refs": [], "payload": {"gold": {}}}})
                verifier_tasks.append({"task_id": tid, "verifier_task_fingerprint": "a" * 64})
                verifier.append({"task_id": tid, "status": "candidate", "answer": {"gold": {}}})
                adj.append(by_artifact[key]["adjudication"][tid])
            _write_jsonl(bundle / "curator-tasks.jsonl", tasks)
            _write_jsonl(bundle / "curator-responses.jsonl", curator)
            _write_jsonl(bundle / "verifier-tasks.jsonl", verifier_tasks)
            _write_jsonl(bundle / "verifier-responses.jsonl", verifier)
            _write_jsonl(bundle / "adjudication.jsonl", adj)
            validated_by_evidence[str(e)] = {
                "tasks": by_artifact[key]["tasks"],
                "ledger_rows": by_artifact[key]["ledger_rows"],
                "adjudication": by_artifact[key]["adjudication"],
            }

        def fake_validate(_root, evidence, *args, **kwargs):
            return validated_by_evidence[str(evidence)]

        with patch.object(
            adjudication,
            "validate_primary_run_evidence",
            side_effect=fake_validate,
        ), patch.object(
            adjudication,
            "validate_reserve_run_evidence",
            side_effect=fake_validate,
        ), patch.object(
            adjudication,
            "validate_reserve2_run_evidence",
            side_effect=fake_validate,
        ):
            summary = adjudication.build_adjudication_packet(
                self.root,
                self.canonical,
                self.evidence,
                self.cache,
                self.out,
                activation_path=self.activation,
                capacity_extension_path=self.extension,
            )

        self.assertEqual(summary["case_count"], 158)
        self.assertTrue(summary["human_or_authority_decision_required"])
        self.assertFalse(summary["ai_may_self_authorize_acceptance"])
        packet = load_jsonl(self.out / "ADJUDICATION_PACKET.jsonl")
        decisions = load_jsonl(self.out / "ADJUDICATION_DECISION_TEMPLATE.jsonl")
        self.assertEqual(len(packet), 158)
        self.assertEqual(len(decisions), 158)
        self.assertTrue(all(row["decision"] is None for row in decisions))
        self.assertTrue(
            all(row["decision_policy"]["ai_may_self_authorize_acceptance"] is False for row in packet)
        )


class RepositoryAdjudicationTargetTests(unittest.TestCase):
    def test_repository_schema30_target_is_158_human_authority_cases(self):
        root = Path(__file__).resolve().parents[1]
        status = load_json(root / "artifacts" / "H3.9.2-STATUS.json")
        self.assertEqual(status["freeze_schema_version"], 30)
        target = status["adjudication_packet_target"]
        self.assertTrue(target["ready"])
        self.assertFalse(target["completed"])
        self.assertEqual(target["expected_case_count"], 158)
        self.assertEqual(
            target["layer_counts"],
            {"primary": 129, "reserve01": 24, "reserve02": 5},
        )
        self.assertFalse(target["automatic_decision_authorized"])
        self.assertFalse(target["automatic_reserve_authorization_from_rejection"])
        surface = status["adjudication_review_surface"]
        self.assertEqual(surface["combined_pending_case_count"], 158)
        self.assertTrue(surface["human_or_authority_decision_required"])
        self.assertFalse(surface["ai_may_self_authorize_acceptance"])
        self.assertFalse(
            status["post_consolidation_protocol"]["automatic_reserve3_authorized"]
        )


if __name__ == "__main__":
    unittest.main()
