"""waraqat_extract: determinism, chrome exclusion and boundary tests.

The fixture mirrors the real witness structure (content div, h5 headings,
<br> separators, entities, site chrome) with wholly synthetic content.
"""
from __future__ import annotations

import hashlib
import unittest

from engines.usul.pilots.waraqat_extract import extract

FIXTURE = """<!DOCTYPE html>
<html lang="ar"><head><title>كتاب : الورقات للجويني</title>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8" /></head>
<body><div id="wrapper"><div id="header"><a name="top"></a></div>
<div id="global"><a href="../quran/">قرآن</a><a href="../asol/">أصول</a></div>
<div id="navbar"><img alt="" src="images/header.jpg" /></div>
<div id="content">
<h5>أبواب أصول الفقه</h5>
مقدمة تركيبية للأبواب <br />
1 -
<h5>النية</h5>
النيةنية نية الفعل<br />
2 -
<h5>الأمر</h5>
والأمر استدعاء الفعل بالقول &quot;على وجه الوجوب&quot; <br />
وصيغته افعل <br />
3 -
<h5>النهي</h5>
والنهي استدعاء الترك بالقول <br />
</div>
<div id="footer"><a href="../">الصفحة الرئيسية</a>
<p>ISLAMICBOOK.WS &copy; 2026</p></div>
</div></body></html>
"""


class WaraqatExtractTests(unittest.TestCase):
    def setUp(self):
        self.data, self.stats = extract(FIXTURE.encode("utf-8"))
        self.text = self.data.decode("utf-8")

    def test_deterministic_byte_identical_replay(self):
        again, again_stats = extract(FIXTURE.encode("utf-8"))
        self.assertEqual(self.data, again)
        self.assertEqual(self.stats["extracted_utf8_sha256"],
                         again_stats["extracted_utf8_sha256"])

    def test_site_chrome_excluded_content_kept(self):
        self.assertNotIn("قرآن</a>", self.text)
        self.assertNotIn("ISLAMICBOOK.WS", self.text)
        self.assertNotIn("header.jpg", self.text)
        self.assertIn("والأمر استدعاء الفعل بالقول", self.text)

    def test_headings_are_standalone_unique_lines(self):
        lines = [line.strip() for line in self.text.splitlines()]
        self.assertEqual(lines.count("الأمر"), 1)
        self.assertEqual(lines.count("النهي"), 1)
        self.assertEqual(lines.count("النية"), 1)
        self.assertIn("الأمر", lines)
        self.assertLess(lines.index("الأمر"), lines.index("النهي"))

    def test_entities_converted_and_sequence_preserved(self):
        self.assertIn('"على وجه الوجوب"', self.text)
        first = next(line for line in self.text.splitlines() if line.strip())
        self.assertEqual(first.strip(), "أبواب أصول الفقه")

    def test_no_bom_no_null_bytes(self):
        self.assertFalse(self.data.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\x00", self.data)

    def test_raw_bytes_change_changes_output(self):
        changed = FIXTURE.replace("استدعاء", "استدعاءَ", 1)
        data_a, _ = extract(FIXTURE.encode("utf-8"))
        data_b, _ = extract(changed.encode("utf-8"))
        self.assertNotEqual(data_a, data_b)


if __name__ == "__main__":
    unittest.main()
