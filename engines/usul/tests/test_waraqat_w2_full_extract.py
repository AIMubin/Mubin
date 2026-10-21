"""Synthetic tests for the full W2 section extractor (mirrors islam.ms layout)."""
from __future__ import annotations

import unittest

from engines.usul.pilots.waraqat_w2_full_extract import (
    _ExtractionError, build_export, extract_sections, pair_with_w1,
)

FIXTURE = """<html><head><title>كتاب الورقات</title></head><body>
<div class="menu"><a href="/">الرئيسية</a></div>
<div id="content" class="content">
<h2>كتاب الورقات</h2>
<p>تمهيد تركيبي</p>
<h2>الأمر</h2>
<p>والأمر استدعاء الفعل <br /> ووصيغته افعل</p>
<h2>النهي</h2>
<p>والنهي استدعاء الترك</p>
</div>
<div class="footer">تذييل خارجي</div>
</body></html>
"""


class W2FullExtractTests(unittest.TestCase):
    def setUp(self):
        self.sections = extract_sections(FIXTURE.encode("utf-8"))

    def test_extracts_three_sections_with_ordinals(self):
        self.assertEqual([s["h2_ordinal"] for s in self.sections], [1, 2, 3])
        self.assertEqual(self.sections[0]["title_folded"], "كتاب الورقات")
        self.assertEqual(self.sections[1]["title_folded"], "الأمر")
        self.assertEqual(self.sections[2]["title_folded"], "النهي")

    def test_br_converts_to_newline_and_entities_survive(self):
        import re
        joined = re.sub(r"\s+", " ", "\n".join(s["text"] for s in self.sections))
        self.assertIn("والأمر استدعاء الفعل ووصيغته افعل", joined)

    def test_chrome_excluded(self):
        joined = "\n".join(s["text"] for s in self.sections)
        self.assertNotIn("الرئيسية", joined)
        self.assertNotIn("تذييل خارجي", joined)

    def test_book_title_heading_identified_as_extra(self):
        export = build_export(self.sections)
        inv = {"sections": [
            {"kind": "PRELUDE", "id": "waraqat:w1:prologue",
             "source_byte_start": 0, "source_byte_end_exclusive": 5,
             "source_line_start": 1, "source_line_end_exclusive": 2,
             "section_sha256": "0" * 64, "byte_count": 5, "line_count": 1,
             "heading_folded_sha256": "0" * 64},
        ] + [
            {"kind": "HEADING_SECTION", "id": f"waraqat:w1:chapter-{i:03d}",
             "heading_folded_sha256": __import__("hashlib").sha256(
                 t.encode("utf-8")).hexdigest()}
            for i, t in enumerate(["الأمر", "النهي"], 1)
        ]}
        paired, unresolved, extras = pair_with_w1(self.sections, inv)
        self.assertEqual(len(paired), 2)
        self.assertEqual(len(extras), 1)
        self.assertEqual(extras[0]["kind"], "TITLE_HEADING")
        self.assertEqual(extras[0]["h2_ordinal"], 1)

    def test_nested_layout_div_cannot_truncate_book_content(self):
        html = FIXTURE.replace("<h2>النهي</h2>",
                               '<div class="nested"><p>نص محاط</p></div><h2>النهي</h2>')
        sections = extract_sections(html.encode("utf-8"))
        self.assertEqual(len(sections), 3)
        self.assertIn("نص محاط", sections[1]["text"])
        self.assertIn("والنهي استدعاء الترك", sections[2]["text"])

    def test_duplicate_content_root_rejected(self):
        html = FIXTURE.replace("</body>", '<div id="content">duplicate</div></body>')
        with self.assertRaises(_ExtractionError):
            extract_sections(html.encode("utf-8"))

    def test_missing_h2_close_is_error_not_false_full_coverage(self):
        html = FIXTURE.replace("<h2>النهي</h2>", "<h2>النهي")
        with self.assertRaises(_ExtractionError):
            extract_sections(html.encode("utf-8"))

    def test_disallowed_markup_is_not_silently_indexed(self):
        html = FIXTURE.replace("<h2>النهي</h2>",
                               '<script>unrelated()</script><h2>النهي</h2>')
        with self.assertRaises(_ExtractionError):
            extract_sections(html.encode("utf-8"))

    def test_missing_content_scope_refused(self):
        with self.assertRaises(_ExtractionError):
            extract_sections(b"<html><body>no content div</body></html>")


if __name__ == "__main__":
    unittest.main()
