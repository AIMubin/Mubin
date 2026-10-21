"""Synthetic Stage09 CLI/frozen graph pin checks; no historical text."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from engines.usul.pilots.waraqat_stage09 import WARAQAT_STAGE08_GRAPH_SHA256


class WaraqatStage09Tests(unittest.TestCase):
    def test_frozen_graph_hash_is_stage08_closure_digest(self):
        root = Path(__file__).resolve().parents[3]
        receipt = json.loads((root/"corpus/reviews/u01-stage08-waraqat-context-graph.json")
                             .read_text(encoding="utf-8"))
        self.assertEqual(WARAQAT_STAGE08_GRAPH_SHA256, receipt["graph_sha256"])
        self.assertEqual(receipt["campaign_decision"],
                         "STAGE08_DUAL_SOURCE_CONTEXT_GRAPH_PASS")

    def test_missing_local_p0_attested_input_is_pending(self):
        with tempfile.TemporaryDirectory() as temp:
            t = Path(temp)
            report = t/"result.json"
            cmd = [
                sys.executable, "-m", "engines.usul.pilots.waraqat_stage09",
                "--stage08-graph", str(t/"private-graph.json"),
                "--p0-bundle", str(t/"private-p0.json"),
                "--proposals", str(t/"private-proposals.json"),
                "--report", str(report),
            ]
            process = subprocess.run(
                cmd, cwd=Path(__file__).resolve().parents[3],
                capture_output=True, text=True,
            )
            self.assertEqual(process.returncode, 3, process.stderr)
            data = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(data["status"], "PENDING_STAGE09_SOURCE_BINDING_INPUTS")
            self.assertFalse(data["scholarly_verified"])
            self.assertTrue(process.stdout.isascii())


if __name__ == "__main__":
    unittest.main()
