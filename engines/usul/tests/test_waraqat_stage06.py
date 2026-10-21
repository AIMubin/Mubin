"""Stage06 published digital witness pins and private-source gates."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engines.usul.pilots import waraqat_stage06 as runner
from engines.usul.witness_alignment import WitnessAlignmentError


class WaraqatComparativeRunnerTests(unittest.TestCase):
    def test_both_real_html_hashes_come_from_independent_public_receipts(self):
        root = Path(__file__).resolve().parents[3]
        first = json.loads((root/"corpus/reviews/u01-stage04-waraqat-source-link.json")
                           .read_text(encoding="utf-8"))
        second = json.loads((root/"corpus/reviews/u01-stage05-witness2-comparison.json")
                            .read_text(encoding="utf-8"))
        self.assertEqual(runner.W1_RAW_SHA, first["chain"]["raw_html_capture"]["sha256"])
        self.assertEqual(runner.W1_MANIFEST_SHA,
                         first["chain"]["manifest"]["sha256_independently_pinned"])
        self.assertEqual(runner.W1_SECTION_SHA, first["chain"]["coverage"]["section_sha256"])
        self.assertEqual(runner.W2_RAW_SHA, second["witness2_comparator"]["raw_html_sha256"])
        self.assertEqual(runner.W1_URL, first["chain"]["raw_html_capture"]["url"])
        self.assertEqual(runner.W2_URL, second["witness2_comparator"]["url"])

    def test_missing_original_witnesses_never_emit_success(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report = root / "result.json"
            command = [
                sys.executable, "-m", "engines.usul.pilots.waraqat_stage06",
                "--primary-html", str(root/"a.html"),
                "--primary-export", str(root/"a.txt"),
                "--primary-manifest", str(root/"a.json"),
                "--primary-section", str(root/"a-section.txt"),
                "--secondary-html", str(root/"b.html"),
                "--secondary-section", str(root/"b-section.txt"),
                "--secondary-section-sha256", "0"*64,
                "--report", str(report),
            ]
            proc = subprocess.run(
                command, cwd=Path(__file__).resolve().parents[3],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 3)
            self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["status"],
                             "PENDING_PRIVATE_WITNESS_FILES")
            self.assertNotIn("PASS", proc.stdout)

    def test_comparison_workflow_checks_both_html_digests_and_never_full_certifies(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            file_names = ["a.html", "a.txt", "a.json", "a-section.txt",
                          "b.html", "b-section.txt"]
            files = [root/n for n in file_names]
            left_html, left_export, manifest, left_section, right_html, right_section = files
            # Synthetic bytes and patched trust pins, never historical text.
            prefix = ("ب" * 3735).encode("utf-8")  # dummy, later sliced by byte
            actual_section = ("أ" * 616).encode("utf-8")  # 1232 UTF-8 bytes
            exported = b"x"*3735 + actual_section + b"after"
            left_html.write_bytes(b"mock-left-html")
            right_html.write_bytes(b"mock-right-html")
            left_export.write_bytes(exported)
            left_section.write_bytes(actual_section)
            right_section.write_bytes(actual_section)
            manifest.write_bytes(b"{}")
            section_proof = {"section_id": runner.SECTION,
                             "section_sha256": hashlib.sha256(actual_section).hexdigest(),
                             "line_count": 22, "start_byte": 3735,
                             "end_byte_exclusive": 4967}
            mocked_coverage = {
                "source_url": runner.W1_URL,
                "snapshot_sha256": hashlib.sha256(exported).hexdigest(),
                "sections": [section_proof],
            }
            with patch.object(runner, "audit", return_value=mocked_coverage), \
                 patch.object(runner, "extract", return_value=(exported, {})), \
                 patch.object(runner, "W1_RAW_SHA",
                              hashlib.sha256(left_html.read_bytes()).hexdigest()), \
                 patch.object(runner, "W2_RAW_SHA",
                              hashlib.sha256(right_html.read_bytes()).hexdigest()), \
                 patch.object(runner, "W1_EXPORT_SHA", mocked_coverage["snapshot_sha256"]), \
                 patch.object(runner, "W1_SECTION_SHA", section_proof["section_sha256"]):
                result = runner.compare_captured_witnesses(
                    *files, hashlib.sha256(right_section.read_bytes()).hexdigest())
                self.assertEqual(result["status"],
                                 "STAGE06_TEXT_ALIGNMENT_PROVENANCE_PARTIAL")
                self.assertTrue(result["primary_html_to_section_replay_verified"])
                self.assertFalse(result["secondary_html_to_section_replay_verified"])
                self.assertFalse(result["full_witness_comparison_qualified"])
                self.assertFalse(result["zero_lexical_difference_certified"])
                # Mutating W2's supposedly frozen raw capture must fail.
                right_html.write_bytes(right_html.read_bytes() + b"tampered")
                with self.assertRaises(WitnessAlignmentError):
                    runner.compare_captured_witnesses(
                        *files, hashlib.sha256(right_section.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
