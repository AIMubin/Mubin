from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmark_campaign.core import canonical_json_bytes, sha256_bytes, sha256_file
from benchmark_campaign.post_consolidation import (
    build_reserve_activation_manifest,
    validate_reserve_activation,
)


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


class PostConsolidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "root"
        self.root.mkdir()
        self.cumulative = Path(self.tmp.name) / "cumulative"
        self.cumulative.mkdir()

        self.primary = {
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
        self.reserve = {
            **self.primary,
            "slot_id": "b1:non_holdout:s1:0001:reserve:01",
            "candidate_slot_kind": "reserve",
            "replacement_for_slot_id": self.primary["slot_id"],
            "reserve_attempt": 1,
        }
        self.plan = {
            "campaign_id": "H3.9.2",
            "factory_version": 1,
            "slots": [self.primary, self.reserve],
        }
        self.plan_sha = sha256_bytes(canonical_json_bytes(self.plan))

        task_fp = "a" * 64
        _write_jsonl(self.cumulative / "CUMULATIVE_LEDGER.jsonl", [{
            "task_id": self.primary["slot_id"],
            "slot_id": self.primary["slot_id"],
            "task_fingerprint": task_fp,
            "benchmark_id": "b1",
            "anchor_source_id": "s1",
            "outcome": "skipped",
            "canonical_reason": "curator_no_candidate",
            "replacement_eligible": True,
            "primary_offset": 0,
        }])
        self.ledger_sha = sha256_file(self.cumulative / "CUMULATIVE_LEDGER.jsonl")

        eligibility = {
            "schema_version": 1,
            "campaign_id": "H3.9.2",
            "kind": "primary_replacement_eligibility",
            "freeze_schema_version": 25,
            "factory_plan_sha256": self.plan_sha,
            "cumulative_ledger_sha256": self.ledger_sha,
            "rules": {
                "promoted_is_replaceable": False,
                "pending_adjudication_is_replaceable": False,
                "terminal_primary_failure_is_replaceable": True,
                "reserve_reconciliation_enabled": False,
            },
            "eligible_primary_count": 1,
            "eligible": [{
                "primary_slot_id": self.primary["slot_id"],
                "primary_slot_binding_sha256": sha256_bytes(canonical_json_bytes(self.primary)),
                "primary_task_id": self.primary["slot_id"],
                "primary_task_fingerprint": task_fp,
                "primary_offset": 0,
                "primary_outcome": "skipped",
                "eligibility_reason": "curator_no_candidate",
                "reserve_slots": [{
                    "slot_id": self.reserve["slot_id"],
                    "slot_binding_sha256": sha256_bytes(canonical_json_bytes(self.reserve)),
                }],
                "cumulative_ledger_sha256": self.ledger_sha,
            }],
        }
        _write_json(self.cumulative / "REPLACEMENT_ELIGIBILITY.json", eligibility)
        self.eligibility_sha = sha256_file(
            self.cumulative / "REPLACEMENT_ELIGIBILITY.json"
        )
        _write_json(self.cumulative / "CUMULATIVE_MANIFEST.json", {
            "campaign_id": "H3.9.2",
            "freeze_schema_version": 25,
            "cumulative_ledger_sha256": self.ledger_sha,
            "replacement_eligibility_sha256": self.eligibility_sha,
        })

    def tearDown(self):
        self.tmp.cleanup()

    def _build(self):
        out = Path(self.tmp.name) / "RESERVE_ACTIVATION.json"
        with patch(
            "benchmark_campaign.post_consolidation.build_factory_plan",
            return_value=self.plan,
        ):
            result = build_reserve_activation_manifest(
                self.root,
                self.cumulative,
                out,
                expected_cumulative_ledger_sha256=self.ledger_sha,
                expected_replacement_eligibility_sha256=self.eligibility_sha,
            )
        return out, result

    def test_build_activation_binds_only_hash_verified_terminal_reserve(self):
        out, result = self._build()
        self.assertEqual(result["protocol_freeze_schema"], 26)
        self.assertEqual(result["source_cumulative_freeze_schema"], 25)
        self.assertTrue(result["reserve_reconciliation_enabled"])
        self.assertEqual(result["eligible_primary_count"], 1)
        self.assertEqual(result["activated_reserve_slot_count"], 1)
        self.assertEqual(
            result["activated"][0]["reserve_slot_id"],
            self.reserve["slot_id"],
        )
        self.assertEqual(result["cumulative_ledger_sha256"], self.ledger_sha)
        self.assertEqual(
            result["replacement_eligibility_sha256"],
            self.eligibility_sha,
        )
        self.assertTrue(out.exists())

    def test_build_activation_rejects_repository_binding_mismatch(self):
        with patch(
            "benchmark_campaign.post_consolidation.build_factory_plan",
            return_value=self.plan,
        ):
            with self.assertRaisesRegex(ValueError, "ledger SHA-256 differs"):
                build_reserve_activation_manifest(
                    self.root,
                    self.cumulative,
                    Path(self.tmp.name) / "bad.json",
                    expected_cumulative_ledger_sha256="0" * 64,
                    expected_replacement_eligibility_sha256=self.eligibility_sha,
                )

    def test_pending_adjudication_cannot_be_smuggled_into_activation(self):
        ledger_path = self.cumulative / "CUMULATIVE_LEDGER.jsonl"
        _write_jsonl(ledger_path, [{
            "task_id": self.primary["slot_id"],
            "slot_id": self.primary["slot_id"],
            "task_fingerprint": "a" * 64,
            "benchmark_id": "b1",
            "anchor_source_id": "s1",
            "outcome": "adjudication",
            "canonical_reason": "gold_disagreement",
            "replacement_eligible": True,
            "primary_offset": 0,
        }])
        new_sha = sha256_file(ledger_path)
        eligibility = json.loads(
            (self.cumulative / "REPLACEMENT_ELIGIBILITY.json").read_text(encoding="utf-8")
        )
        eligibility["cumulative_ledger_sha256"] = new_sha
        eligibility["eligible"][0]["cumulative_ledger_sha256"] = new_sha
        _write_json(self.cumulative / "REPLACEMENT_ELIGIBILITY.json", eligibility)
        eligibility_sha = sha256_file(self.cumulative / "REPLACEMENT_ELIGIBILITY.json")
        manifest = json.loads(
            (self.cumulative / "CUMULATIVE_MANIFEST.json").read_text(encoding="utf-8")
        )
        manifest["cumulative_ledger_sha256"] = new_sha
        manifest["replacement_eligibility_sha256"] = eligibility_sha
        _write_json(self.cumulative / "CUMULATIVE_MANIFEST.json", manifest)

        with patch(
            "benchmark_campaign.post_consolidation.build_factory_plan",
            return_value=self.plan,
        ):
            with self.assertRaisesRegex(ValueError, "only terminal skipped primaries"):
                build_reserve_activation_manifest(
                    self.root,
                    self.cumulative,
                    Path(self.tmp.name) / "bad-adjudication.json",
                    expected_cumulative_ledger_sha256=new_sha,
                    expected_replacement_eligibility_sha256=eligibility_sha,
                )

    def test_validate_activation_rejects_unlisted_reserve_task(self):
        out, _result = self._build()
        unlisted = {
            **self.reserve,
            "slot_id": "b1:non_holdout:s1:9999:reserve:01",
            "replacement_for_slot_id": "b1:non_holdout:s1:9999",
            "task_id": "b1:non_holdout:s1:9999:reserve:01",
        }
        listed = {
            **self.reserve,
            "task_id": self.reserve["slot_id"],
        }
        with patch(
            "benchmark_campaign.post_consolidation.build_factory_plan",
            return_value=self.plan,
        ):
            validate_reserve_activation(self.root, out, [listed])
            with self.assertRaisesRegex(ValueError, "not activated"):
                validate_reserve_activation(self.root, out, [unlisted])


if __name__ == "__main__":
    unittest.main()
