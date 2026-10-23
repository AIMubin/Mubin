"""Synthetic Stage09 CLI/frozen graph pin checks; no historical text."""
import json
import os
from unittest.mock import patch
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from engines.usul.pilots.waraqat_stage09 import (
    WARAQAT_STAGE08_GRAPH_SHA256, REPORT_KIND, RUNNER, main,
)


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



class Stage09PrivateReportSafetyTests(unittest.TestCase):
    """Only fully synthetic private fixtures are ever placed in these paths."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.graph = self.root / "sensitive-stage08.json"
        self.p0 = self.root / "sensitive-p0.json"
        self.proposals = self.root / "sensitive-proposals.json"
        self.report = self.root / "stage09-report.json"
        self.graph.write_text('{"private":"STAGE08_SECRET_SENTINEL"}',
                              encoding="utf-8")
        self.p0.write_text('{"private":"P0_SECRET_SENTINEL"}',
                           encoding="utf-8")
        self.proposals.write_text('[]', encoding="utf-8")
        self.inputs = (self.graph, self.p0, self.proposals)

    def args(self, report=None):
        return [
            "--stage08-graph", str(self.graph),
            "--p0-bundle", str(self.p0),
            "--proposals", str(self.proposals),
            "--report", str(self.report if report is None else report),
        ]

    def test_report_cannot_equal_any_private_input(self):
        original = {p: p.read_bytes() for p in self.inputs}
        for sensitive in self.inputs:
            with self.subTest(path=sensitive.name):
                self.assertEqual(main(self.args(sensitive)), 1)
                for item in self.inputs:
                    self.assertEqual(item.read_bytes(), original[item])

    def test_hardlink_alias_cannot_overwrite_any_private_input(self):
        original = {p: p.read_bytes() for p in self.inputs}
        alias = self.root / "report-alias.json"
        for protected in self.inputs:
            alias.unlink(missing_ok=True)
            try:
                alias.hardlink_to(protected)
            except OSError:
                self.skipTest("Hardlinks unavailable on runner")
            with self.subTest(name=protected.name):
                self.assertEqual(main(self.args(alias)), 1)
                for item in self.inputs:
                    self.assertEqual(item.read_bytes(), original[item])
        alias.unlink(missing_ok=True)

    def test_existing_unrelated_file_and_git_path_never_overwritten(self):
        secret = self.root / "do-not-overwrite.json"
        secret.write_text('{"private":"NON_STAGE09_PRIVATE_RECORD"}',
                          encoding="utf-8")
        self.assertEqual(main(self.args(secret)), 1)
        self.assertIn("NON_STAGE09_PRIVATE_RECORD",
                      secret.read_text(encoding="utf-8"))
        git = self.root / "git-repository"
        (git / ".git").mkdir(parents=True)
        self.assertEqual(main(self.args(git / "report.json")), 1)
        self.assertFalse((git / "report.json").exists())

    def test_missing_input_receipt_replaced_by_fresh_failure(self):
        self.proposals.unlink()
        self.assertEqual(main(self.args()), 3)
        first = json.loads(self.report.read_text(encoding="utf-8"))
        self.assertEqual(first["status"], "PENDING_STAGE09_SOURCE_BINDING_INPUTS")
        self.assertEqual(first["report_kind"], REPORT_KIND)
        self.assertEqual(first["runner"], RUNNER)
        self.proposals.write_text('[]', encoding="utf-8")
        self.assertEqual(main(self.args()), 1)
        second = json.loads(self.report.read_text(encoding="utf-8"))
        self.assertEqual(second["status"], "FAIL")
        self.assertEqual(second["reason_code"], "STAGE09_BINDING_FAILED")
        self.assertFalse(second["public_fatwa_authorized"])
        self.assertFalse(second["scholarly_verified"])
        self.assertNotIn("SECRET_SENTINEL", self.report.read_text(encoding="utf-8"))
        self.assertEqual(list(self.root.glob(".stage09-report-*.tmp")), [])

    def test_mocked_positive_runner_writes_only_safe_receipt(self):
        # Tests report IO only; actual Stage09 byte/graph contract is covered
        # independently by test_typed_evidence_binding.py.
        mock_result = {
            "status": "STAGE09_TYPED_REFERENCE_PROPOSALS_PASS",
            "proposal_count": 1,
            "scholarly_verified": False,
            "source_text_included": False,
        }
        with patch("engines.usul.pilots.waraqat_stage09.bind_exact_observations",
                   return_value=mock_result):
            self.assertEqual(main(self.args()), 0)
            self.assertEqual(main(self.args()), 0)
        result = json.loads(self.report.read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "STAGE09_TYPED_REFERENCE_PROPOSALS_PASS")
        self.assertFalse(result["juristic_inference_allowed"])
        self.assertFalse(result["redistribution_approved"])
        self.assertEqual(result["report_kind"], REPORT_KIND)
        self.assertEqual(list(self.root.glob(".stage09-report-*.tmp")), [])
        self.assertTrue(all(path.exists() for path in self.inputs))

    def test_stale_pass_replaced_when_graph_moved_into_git(self):
        mock_result = {
            "status": "STAGE09_TYPED_REFERENCE_PROPOSALS_PASS",
            "proposal_count": 1, "source_text_included": False,
        }
        with patch("engines.usul.pilots.waraqat_stage09.bind_exact_observations",
                   return_value=mock_result):
            self.assertEqual(main(self.args()), 0)
        self.assertEqual(json.loads(self.report.read_text(encoding="utf-8"))["status"],
                         "STAGE09_TYPED_REFERENCE_PROPOSALS_PASS")
        git = self.root / "repo"
        (git / ".git").mkdir(parents=True)
        moved = git / "private-graph.json"
        self.graph.replace(moved)
        argv = self.args()
        argv[1] = str(moved)
        original = moved.read_bytes()
        self.assertEqual(main(argv), 1)
        receipt = json.loads(self.report.read_text(encoding="utf-8"))
        self.assertEqual(receipt["status"], "REFUSED")
        self.assertEqual(receipt["reason_code"], "PRIVATE_STAGE09_PATH_REFUSED")
        self.assertEqual(moved.read_bytes(), original)
        self.assertNotIn("SECRET_SENTINEL", self.report.read_text(encoding="utf-8"))

    def test_stale_pass_replaced_when_input_becomes_symlink(self):
        mock_result = {
            "status": "STAGE09_TYPED_REFERENCE_PROPOSALS_PASS",
            "proposal_count": 1, "source_text_included": False,
        }
        with patch("engines.usul.pilots.waraqat_stage09.bind_exact_observations",
                   return_value=mock_result):
            self.assertEqual(main(self.args()), 0)
        old_bytes = self.graph.read_bytes()
        moved = self.root / "new-private-graph.json"
        moved.write_bytes(old_bytes)
        self.graph.unlink()
        try:
            self.graph.symlink_to(moved)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink privilege unavailable")
        self.assertEqual(main(self.args()), 1)
        receipt = json.loads(self.report.read_text(encoding="utf-8"))
        self.assertEqual(receipt["status"], "REFUSED")
        self.assertEqual(receipt["reason_code"], "PRIVATE_STAGE09_PATH_REFUSED")
        self.assertEqual(moved.read_bytes(), old_bytes)

    def test_report_symlink_to_input_is_refused(self):
        target = self.root / "report-linked.json"
        try:
            target.symlink_to(self.graph)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink privilege unavailable")
        before = self.graph.read_bytes()
        self.assertEqual(main(self.args(target)), 1)
        self.assertEqual(self.graph.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
