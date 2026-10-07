from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmark_campaign import capacity_extension, factory
from benchmark_campaign.core import canonical_json_bytes, load_jsonl, sha256_bytes


class Reserve2FactoryOverlayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.index = self.root / "index"
        self.index.mkdir()
        self.plan_path = self.root / "plan.json"
        self.tasks_path = self.root / "tasks.jsonl"
        self.extension_path = self.root / "CAPACITY_EXTENSION.json"
        self.extension_path.write_text("{}\n", encoding="utf-8")

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
            "slot_id": self.primary["slot_id"] + ":reserve:01",
            "candidate_slot_kind": "reserve",
            "replacement_for_slot_id": self.primary["slot_id"],
            "reserve_attempt": 1,
        }
        self.reserve2 = {
            **self.primary,
            "slot_id": self.primary["slot_id"] + ":reserve:02",
            "candidate_slot_kind": "reserve",
            "replacement_for_slot_id": self.primary["slot_id"],
            "reserve_attempt": 2,
        }
        self.plan = {
            "campaign_id": "H3.9.2",
            "factory_version": 1,
            "slots": [self.primary, self.reserve1],
        }
        self.plan_path.write_text(
            json.dumps(self.plan, indent=2) + "\n", encoding="utf-8"
        )
        self.extension = {
            "new_reserve_slot_count": 1,
            "extensions": [{
                "new_reserve_slot_id": self.reserve2["slot_id"],
                "new_reserve_slot": self.reserve2,
            }],
        }
        self.policy = {
            "factory_version": 1,
            "benchmarks": {"b": {"candidate_keywords": []}},
        }
        self.cplan = {
            "benchmarks": {
                "b": {
                    "non_holdout_source_pool": ["s"],
                    "holdout_source_pool": ["h"],
                }
            }
        }

        source_blob = "a" * 40
        segments = []
        for i, text in enumerate(("alpha", "beta", "gamma"), 1):
            segments.append({
                "source_id": "s",
                "source_blob_sha": source_blob,
                "segment_id": f"seg-{i}",
                "locator": f"gitblob:{source_blob}#char={i}:{i+len(text)}",
                "char_start": i,
                "char_end": i + len(text),
                "text": text,
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            })
        segments_path = self.index / "segments.jsonl"
        with segments_path.open("w", encoding="utf-8", newline="\n") as fh:
            for row in segments:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
        (self.index / "INDEX_MANIFEST.json").write_text(
            json.dumps({
                "partition": "non_holdout",
                "segments_sha256": hashlib.sha256(
                    segments_path.read_bytes()
                ).hexdigest(),
            }) + "\n",
            encoding="utf-8",
        )
        self.registry = {"s": {"source_blob_sha": source_blob}}

    def tearDown(self):
        self.tmp.cleanup()

    def _patches(self):
        return (
            patch.object(factory, "build_factory_plan", return_value=self.plan),
            patch.object(factory, "_policy", return_value=self.policy),
            patch.object(factory, "_curation_plan", return_value=self.cplan),
            patch.object(
                capacity_extension,
                "validate_frozen_capacity_extension",
                return_value=self.extension,
            ),
        )

    def test_overlay_appends_reserve2_without_mutating_base_plan(self):
        patches = self._patches()
        for p in patches:
            p.start()
        try:
            report = factory.build_factory_tasks(
                self.root,
                self.plan_path,
                self.index,
                self.tasks_path,
                "non_holdout",
                False,
                capacity_extension_path=self.extension_path,
            )
        finally:
            for p in reversed(patches):
                p.stop()

        self.assertEqual(report["task_count"], 3)
        rows = load_jsonl(self.tasks_path)
        self.assertEqual(
            [row["task_id"] for row in rows],
            [self.primary["slot_id"], self.reserve1["slot_id"], self.reserve2["slot_id"]],
        )
        segment_ids = [row["anchor_segment"]["segment_id"] for row in rows]
        self.assertEqual(len(set(segment_ids)), 3)
        self.assertEqual(rows[-1]["reserve_attempt"], 2)
        self.assertEqual(
            rows[-1]["replacement_for_slot_id"],
            self.primary["slot_id"],
        )
        unsigned = dict(rows[-1])
        stored = unsigned.pop("task_fingerprint")
        self.assertEqual(stored, sha256_bytes(canonical_json_bytes(unsigned)))
        self.assertEqual(self.plan["slots"], [self.primary, self.reserve1])

    def test_without_overlay_base_factory_output_is_unchanged(self):
        with patch.object(
            factory, "build_factory_plan", return_value=self.plan
        ), patch.object(
            factory, "_policy", return_value=self.policy
        ), patch.object(
            factory, "_curation_plan", return_value=self.cplan
        ):
            report = factory.build_factory_tasks(
                self.root,
                self.plan_path,
                self.index,
                self.tasks_path,
                "non_holdout",
                False,
            )
        self.assertEqual(report["task_count"], 2)
        self.assertEqual(
            [row["task_id"] for row in load_jsonl(self.tasks_path)],
            [self.primary["slot_id"], self.reserve1["slot_id"]],
        )

    def test_overlay_task_validation_requires_explicit_capacity_context(self):
        patches = self._patches()
        for p in patches:
            p.start()
        try:
            factory.build_factory_tasks(
                self.root,
                self.plan_path,
                self.index,
                self.tasks_path,
                "non_holdout",
                False,
                capacity_extension_path=self.extension_path,
            )
            reserve2_task = [row for row in load_jsonl(self.tasks_path) if row.get("reserve_attempt") == 2]
            with patch.object(
                factory, "load_source_registry", return_value=[]
            ), patch.object(
                factory, "source_map", return_value=self.registry
            ):
                with self.assertRaisesRegex(ValueError, "unknown frozen slot"):
                    factory._validate_tasks_against_frozen_plan(
                        self.root, reserve2_task
                    )
                factory._validate_tasks_against_frozen_plan(
                    self.root,
                    reserve2_task,
                    capacity_extension_path=self.extension_path,
                    require_capacity_execution=True,
                )
        finally:
            for p in reversed(patches):
                p.stop()


if __name__ == "__main__":
    unittest.main()
