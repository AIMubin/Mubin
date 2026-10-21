"""Stage08 source replay runner tests; synthetic only, no historical excerpt."""
import json
import subprocess
import sys
import tempfile
import unittest
import hashlib
from pathlib import Path
from unittest.mock import patch

from engines.usul.arabic_evidence_retrieval import retrieve, FOLD_MARKS
from engines.usul.pilots import waraqat_stage08 as runner
from engines.usul.evidence_context_graph import ContextGraphError


class Stage08RunnerTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.w1 = self.root / "first.txt"
        self.w2 = self.root / "second.txt"
        self.w1.write_bytes("الأمر\nو أما دليل\n".encode("utf-8"))
        self.w2.write_bytes("الْأَمْر\nوأما دليل\n".encode("utf-8"))
        self.pin1 = hashlib.sha256(self.w1.read_bytes()).hexdigest()
        self.pin2 = hashlib.sha256(self.w2.read_bytes()).hexdigest()
        self.queries = [{"id": "pilot:amr", "literal": "الأمر",
                         "candidate_profiles": [FOLD_MARKS]}]
        self.pointers = [{
            "id": "pilot:rule-review", "kind": "RULE_RESEARCH_POINTER",
            "reference_id": "pilot:rule-amr-default",
            "witness_id": "pilot:waraqat-primary",
            "query_id": "pilot:amr", "review_status": "UNASSESSED",
        }]
        self.files = [self.root / "original1.html",
                      self.root / "full.txt",
                      self.root / "manifest.json",
                      self.w1,
                      self.root / "original2.html",
                      self.w2]

    def _stage07(self):
        witnesses = [{
            "source_id": "pilot:waraqat-primary",
            "section_path": self.w1, "section_sha256": self.pin1,
            "source_url": runner.W1_URL, "section_locator":
            "الورقات / باب الأمر / 86–107",
            "offset_basis": "utf8_export",
            "source_byte_base": 3735, "source_line_base": 86,
        }, {
            "source_id": "pilot:waraqat-comparator",
            "section_path": self.w2, "section_sha256": self.pin2,
            "source_url": runner.W2_URL, "section_locator":
            "الورقات / باب الأمر / شاهد رقمي ثان",
            "offset_basis": "extracted_section",
            "source_byte_base": 0, "source_line_base": 1,
        }]
        report = retrieve(witnesses, self.queries)
        report.update({
            "status": "STAGE07_DUAL_WITNESS_ARABIC_RETRIEVAL_PASS",
            "stage06_strict_provenance": {
                "status": "STAGE06_DUAL_SOURCE_EXTRACTION_REPLAY_PASS",
                "both_html_to_section_replays_verified": True,
            },
        })
        return report

    def test_runner_constructs_source_pinned_graph_after_stage07(self):
        with patch.object(runner, "W1_SECTION_SHA", self.pin1), \
             patch.object(runner, "W2_SECTION_SHA", self.pin2), \
             patch.object(runner, "replay_and_search",
                          return_value=self._stage07()) as verify:
            result = runner.replay_and_graph(*self.files,
                                             self.queries, self.pointers)
            verify.assert_called_once_with(*self.files, self.queries)
            self.assertEqual(result["status"], "STAGE08_DUAL_SOURCE_CONTEXT_GRAPH_PASS")
            self.assertEqual(result["stage07_witness_count"], 2)
            self.assertTrue(result["source_replay_verified_by_runner"])
            self.assertEqual(result["nodes_by_kind"]["RULE_RESEARCH_POINTER"], 1)
            self.assertFalse(result["rule_citation_truth_verified"])
            self.assertFalse(result["juristic_inference_allowed"])

    def test_runner_refuses_partial_source_replay(self):
        report = self._stage07()
        report["stage06_strict_provenance"]["both_html_to_section_replays_verified"] = False
        with patch.object(runner, "replay_and_search", return_value=report):
            with self.assertRaises(ContextGraphError):
                runner.replay_and_graph(*self.files,
                                        self.queries, self.pointers)

    def test_local_private_files_absent_gives_pending_not_qualified_graph(self):
        p = self.root / "result.json"
        args = [sys.executable, "-m", "engines.usul.pilots.waraqat_stage08",
                "--primary-html", str(self.files[0]),
                "--primary-export", str(self.files[1]),
                "--primary-manifest", str(self.files[2]),
                "--primary-section", str(self.files[3]),
                "--secondary-html", str(self.files[4]),
                "--secondary-section", str(self.files[5]),
                "--queries", str(self.root/"queries.json"),
                "--pointers", str(self.root/"pointers.json"),
                "--report", str(p)]
        result = subprocess.run(args, cwd=Path(__file__).resolve().parents[3],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertTrue(result.stdout.isascii())
        self.assertEqual(json.loads(p.read_text(encoding="utf-8"))["status"],
                         "PENDING_PRIVATE_WITNESS_FILES")


if __name__ == "__main__":
    unittest.main()
