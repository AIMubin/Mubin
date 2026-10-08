from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from benchmark_campaign.decision_template import build_schema31_decision_template


class Schema31DecisionTemplateTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]

    def _packet(self, path: Path) -> str:
        with path.open("w", encoding="utf-8", newline="\n") as f:
            for i in range(158):
                row = {
                    "schema_version": 1,
                    "campaign_id": "H3.9.2",
                    "packet_id": hashlib.sha256(f"packet-{i}".encode()).hexdigest(),
                    "ordinal": i,
                    "task_id": f"task-{i:03d}",
                    "benchmark_id": "external-critical-commentary",
                }
                f.write(json.dumps(row, sort_keys=True) + "\n")
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_builds_blank_schema31_layout_without_legacy_decision(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            packet = work / "packet.jsonl"
            expected = self._packet(packet)
            out = work / "out"
            manifest = build_schema31_decision_template(
                self.root,
                packet,
                out,
                expected_packet_sha256=expected,
            )
            rows = [
                json.loads(line)
                for line in (out / "SCHEMA31_ADJUDICATION_DECISION_TEMPLATE.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
                if line.strip()
            ]
            self.assertEqual(len(rows), 158)
            self.assertEqual(manifest["case_count"], 158)
            self.assertEqual(manifest["source_packet_sha256"], expected)
            self.assertTrue(manifest["blank_template"])
            self.assertFalse(manifest["contains_terminal_decisions"])
            self.assertFalse(manifest["legacy_top_level_decision_field_present"])
            self.assertEqual(
                manifest["canonical_terminal_decision_path"],
                "terminal_signoff.decision",
            )
            for row in rows:
                self.assertNotIn("decision", row)
                self.assertEqual(row["protocol_freeze_schema"], 31)
                self.assertEqual(row["reviews"], [])
                self.assertIsNone(row["material_disagreement"])
                self.assertIsNone(row["terminal_signoff"])
                self.assertIsNone(row["reviewer_registry_snapshot_sha256"])

    def test_rejects_wrong_packet_hash(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            packet = work / "packet.jsonl"
            self._packet(packet)
            with self.assertRaisesRegex(ValueError, "packet SHA-256 mismatch"):
                build_schema31_decision_template(
                    self.root,
                    packet,
                    work / "out",
                    expected_packet_sha256="0" * 64,
                )

    def test_rejects_duplicate_human_review_bindings(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            packet = work / "packet.jsonl"
            expected = self._packet(packet)
            rows = [
                json.loads(line)
                for line in packet.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            rows[1]["packet_id"] = rows[0]["packet_id"]
            with packet.open("w", encoding="utf-8", newline="\n") as f:
                for row in rows:
                    f.write(json.dumps(row, sort_keys=True) + "\n")
            expected = hashlib.sha256(packet.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "duplicate packet_id"):
                build_schema31_decision_template(
                    self.root,
                    packet,
                    work / "out",
                    expected_packet_sha256=expected,
                )


if __name__ == "__main__":
    unittest.main()
