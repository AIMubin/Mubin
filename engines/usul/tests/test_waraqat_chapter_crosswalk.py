"""Candidate W2 chapter-heading crosswalk: never certify actual textual equivalence."""
import hashlib
import unittest

from engines.usul.pilots.waraqat_chapter_crosswalk import (
    HeadingCrosswalkError, candidate_crosswalk, discover_w2_headings,
)

HTML = """<html><header><h2>عنوان الموقع</h2></header><main>
<h2>الأمر</h2><p>الأَمْرُ في المادة</p><h2>النهي</h2>
<p>والنهي اختبار</p><h2>العام</h2><p>مادة ثانية</p>
</main></html>"""
W1 = {
    "status": "PRIMARY_WITNESS_CHAPTER_INVENTORY_PASS",
    "complete_original_byte_partition_verified": True,
    "chapters": [
        {"id": "pilot:waraqat-w1-section-001", "heading": "الأمر",
         "section_sha256": "1"*64},
        {"id": "pilot:waraqat-w1-section-002", "heading": "النهي",
         "section_sha256": "2"*64},
        {"id": "pilot:waraqat-w1-section-003", "heading": "العام",
         "section_sha256": "3"*64},
        {"id": "pilot:waraqat-w1-section-004", "heading": "الخاص",
         "section_sha256": "4"*64},
    ],
}


class CrosswalkTests(unittest.TestCase):
    def setUp(self):
        self.raw = HTML.encode()
        self.pin = hashlib.sha256(self.raw).hexdigest()

    def test_explicit_heading_candidates_do_not_certify_chapter_text(self):
        result = candidate_crosswalk(W1, self.raw, w2_pin=self.pin)
        self.assertEqual(result, candidate_crosswalk(W1, self.raw, w2_pin=self.pin))
        self.assertEqual(result["status"], "W2_HEADING_CROSSWALK_CANDIDATES_ONLY")
        self.assertEqual(result["w2_h2_count"], 4)
        self.assertEqual(len(result["w1_chapter_links"]), 4)
        self.assertEqual(result["w1_chapter_links"][0]["w2_h2_ordinal_candidates"], [2])
        self.assertEqual(result["w1_chapter_links"][-1]["status"], "NO_HEADING_CANDIDATE")
        self.assertFalse(result["w2_chapter_byte_extraction_verified"])
        self.assertFalse(result["full_witness_comparison_qualified"])
        self.assertFalse(result["semantic_equivalence_verified"])
        self.assertFalse(result["redistribution_approved"])
        self.assertNotIn("والنهي اختبار", str(result))

    def test_repeated_headings_are_ambiguous_not_automatically_aligned(self):
        raw = self.raw.replace(b"</main>", "<h2>الأمر</h2></main>".encode())
        result = candidate_crosswalk(W1, raw, w2_pin=hashlib.sha256(raw).hexdigest())
        self.assertEqual(result["w1_chapter_links"][0]["status"],
                         "AMBIGUOUS_HEADING_CANDIDATES")
        self.assertEqual(len(result["w1_chapter_links"][0]["w2_h2_ordinal_candidates"]), 2)

    def test_modified_html_and_unbalanced_heading_fail(self):
        for raw in (self.raw + b"X", b"<html><h2>broken"):
            with self.subTest(raw=raw[:28]), self.assertRaises(HeadingCrosswalkError):
                discover_w2_headings(raw, independently_pinned_sha=self.pin)

    def test_bad_w1_inventory_rejected(self):
        with self.assertRaisesRegex(HeadingCrosswalkError, "W1"):
            candidate_crosswalk({"status": "not verified"}, self.raw, w2_pin=self.pin)

    def test_w2_unicode_cannot_be_treated_as_valid_markup(self):
        raw = b"\xff<h2>no</h2>"
        with self.assertRaisesRegex(HeadingCrosswalkError, "UTF-8"):
            discover_w2_headings(raw, independently_pinned_sha=hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    unittest.main()
