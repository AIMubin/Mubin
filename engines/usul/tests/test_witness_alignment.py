"""Stage06 comparison: account for *every* original byte without certifying meaning."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from engines.usul.witness_alignment import (
    WitnessAlignmentError, align_sections,
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


class ComparativeWitnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.a = self.root / "witness-a.txt"
        self.b = self.root / "witness-b.txt"
        self.save("الأمر\nو أما الوجوب فظاهر\n",
                  "الأَمْر\nوأما [الوجوب] فظاهر\n")

    def save(self, a, b):
        self.left = a
        self.right = b
        self.a.write_bytes(a.encode("utf-8"))
        self.b.write_bytes(b.encode("utf-8"))
        self.pin_a = sha(self.a.read_bytes())
        self.pin_b = sha(self.b.read_bytes())

    def compare(self, **kwargs):
        return align_sections(
            self.a, self.b, left_sha256=kwargs.get("left_sha256", self.pin_a),
            right_sha256=kwargs.get("right_sha256", self.pin_b),
            left_source_id="pilot:witness-one",
            right_source_id="pilot:witness-two",
            left_locator="باب الأمر/primary",
            right_locator="باب الأمر/comparator")

    def test_variants_remain_differences_not_lexical_certification(self):
        v = self.compare()
        self.assertEqual(v, self.compare())
        self.assertEqual(v["status"], "PINNED_TEXT_WITNESS_ALIGNMENT_PASS")
        self.assertFalse(v["profiles"]["raw_byte_identical"])
        self.assertFalse(v["profiles"]["after_whitespace_collapsing_identical"])
        self.assertTrue(v["profiles"]["after_all_whitespace_removed_identical"])
        self.assertEqual(v["overall_classification"],
                         "TOKEN_BOUNDARY_DIFFERENCE_CANDIDATE")
        self.assertEqual(v["left"]["raw_whitespace_token_count"], 6)
        self.assertEqual(v["right"]["raw_whitespace_token_count"], 5)
        self.assertFalse(v["lexical_content_equivalence_certified"])
        self.assertFalse(v["meaning_preservation_verified"])
        self.assertGreater(v["strict_change_count"], 0)
        self.assertEqual(v["strict_change_count"], len(v["strict_changes"]))
        self.assertTrue(all(not event["source_text_included"] for event in v["strict_changes"]))

    def test_every_change_has_exact_original_byte_ranges_and_digest(self):
        v = self.compare()
        left_raw, right_raw = self.a.read_bytes(), self.b.read_bytes()
        for item in v["strict_changes"]:
            for side, original in (("left", left_raw), ("right", right_raw)):
                bound = item[side]
                piece = original[bound["byte_start"]:bound["byte_end_exclusive"]]
                self.assertEqual(sha(piece), bound["span_sha256"])
                self.assertGreaterEqual(bound["line_start"], 1)
                self.assertLessEqual(bound["byte_end_exclusive"], len(original))
        serialized = json.dumps(v, ensure_ascii=False)
        self.assertNotIn("الوجوب", serialized)
        self.assertNotIn("وأما", serialized)
        self.assertFalse(v["source_text_included"])

    def test_only_diacritic_changes_remain_visible_and_unapproved(self):
        self.save("عَلِمَ\n", "عُلِمَ\n")
        v = self.compare()
        self.assertEqual(v["overall_classification"],
                         "ARABIC_MARKS_OR_EDITORIAL_BRACKET_DIFFERENCE")
        self.assertTrue(v["profiles"]["marks_and_brackets_ignored_identical"])
        self.assertFalse(v["meaning_preservation_verified"])
        self.assertFalse(v["lexical_content_equivalence_certified"])

    def test_editorial_brackets_do_not_delete_the_enclosed_words(self):
        self.save("الوجوب\n", "[الوجوب]\n")
        v = self.compare()
        self.assertEqual(v["overall_classification"],
                         "ARABIC_MARKS_OR_EDITORIAL_BRACKET_DIFFERENCE")
        self.save("الوجوب\n", "[الندب]\n")
        different = self.compare()
        self.assertEqual(different["overall_classification"],
                         "TEXTUAL_DIFFERENCE_REQUIRES_REVIEW")
        self.assertFalse(different["profiles"]["after_all_whitespace_removed_identical"])

    def test_replacing_negation_is_never_erased(self):
        self.save("لا يجوز\n", "يجوز\n")
        v = self.compare()
        self.assertEqual(v["overall_classification"],
                         "TEXTUAL_DIFFERENCE_REQUIRES_REVIEW")
        self.assertFalse(v["profiles"]["after_all_whitespace_removed_identical"])

    def test_hamza_and_alef_differences_are_not_normalized(self):
        self.save("إن الحكم\n", "ان الحكم\n")
        v = self.compare()
        self.assertEqual(v["overall_classification"],
                         "TEXTUAL_DIFFERENCE_REQUIRES_REVIEW")

    def test_whitespace_only_and_identical(self):
        self.save("باب الأمر\n", "باب  الأمر\n")
        self.assertEqual(self.compare()["overall_classification"],
                         "WHITESPACE_DIFFERENCE")
        self.save("باب الأمر\n", "باب الأمر\n")
        v = self.compare()
        self.assertTrue(v["profiles"]["raw_byte_identical"])
        self.assertEqual(v["strict_changes"], [])
        self.assertEqual(v["overall_classification"], "EXACT_EQUAL")

    def test_missing_clauses_detectable_as_residual_differences(self):
        self.save("الأمر يفيد الوجوب\n", "الأمر\n")
        v = self.compare()
        self.assertEqual(v["overall_classification"],
                         "TEXTUAL_DIFFERENCE_REQUIRES_REVIEW")
        self.assertGreater(v["strict_change_count"], 0)
        self.assertFalse(v["lexical_content_equivalence_certified"])

    def test_pin_mismatch_is_not_repairable_by_normalization(self):
        self.save("و أما\n", "وأما\n")
        with self.assertRaisesRegex(WitnessAlignmentError, "digest"):
            self.compare(left_sha256="0"*64)
        self.b.write_bytes(self.b.read_bytes() + b" ")
        with self.assertRaisesRegex(WitnessAlignmentError, "digest"):
            self.compare()

    def test_binary_oversized_and_malformed_originals_fail(self):
        for contents in (b"\xef\xbb\xbfabc", b"\xff", b"a"*17000,
                         b"abc\x00def"):
            self.b.write_bytes(contents)
            with self.subTest(size=len(contents)), self.assertRaises(WitnessAlignmentError):
                self.compare(right_sha256=sha(contents))

    def test_witness_identity_and_locator_must_be_explicit(self):
        with self.assertRaises(WitnessAlignmentError):
            align_sections(self.a, self.b, left_sha256=self.pin_a,
                           right_sha256=self.pin_b,
                           left_source_id="same", right_source_id="same",
                           left_locator="أ", right_locator="ب")

    def test_cli_metadata_only_and_missing_files_fail_closed(self):
        report = self.root / "report.json"
        cmd = [
            sys.executable, "-m", "engines.usul.witness_alignment",
            "--left", str(self.a), "--right", str(self.b),
            "--left-sha256", self.pin_a, "--right-sha256", self.pin_b,
            "--left-source-id", "pilot:one", "--right-source-id", "pilot:two",
            "--left-locator", "amr", "--right-locator", "amr",
            "--report", str(report)
        ]
        repo = Path(__file__).resolve().parents[3]
        proc = subprocess.run(cmd, cwd=repo, capture_output=True,
                              text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        result = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "PINNED_TEXT_WITNESS_ALIGNMENT_PASS")
        self.assertTrue(proc.stdout.isascii())
        missing = subprocess.run(
            [str(self.root/"nonexistent.txt") if arg == str(self.b) else arg
             for arg in cmd], cwd=repo, capture_output=True, text=True)
        self.assertEqual(missing.returncode, 3)
        self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["status"],
                         "PENDING_PRIVATE_WITNESS_FILES")


if __name__ == "__main__":
    unittest.main()
