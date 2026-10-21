"""Synthetic W2 h2 HTML extraction; no published book text copied."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engines.usul.pilots import waraqat_witness2_extract as w2

HTML = """<!DOCTYPE html><html><body>
<nav>unrelated</nav><h2>مقدمة</h2><p>non-book sample</p>
<h2>الْأَمر</h2>
<p>وَأَمَّا [الوجوب] في هذا المثال الاصطناعي.</p>
<p>سطر ثانٍ<br>بعد فاصل</p>
<h2>النَّهْي</h2><p>exclude next chapter</p>
<h2>عنوان آخر</h2></body></html>"""


class Witness2ExtractTests(unittest.TestCase):
    def test_retains_original_Arabic_diacritics_and_bracket_contents(self):
        data, meta = w2.extract(HTML.encode("utf-8"))
        text = data.decode("utf-8")
        self.assertIn("وَأَمَّا [الوجوب]", text)
        self.assertIn("بعد فاصل", text)
        self.assertIn("الْأَمر", text)
        self.assertNotIn("exclude next chapter", text)
        self.assertNotIn("non-book sample", text)
        self.assertEqual(meta["start_heading_matches"], 1)
        self.assertEqual(meta["end_heading_matches"], 1)
        self.assertEqual(meta["status"], "DETERMINISTIC_HTML_PARSER_CANDIDATE")
        self.assertFalse(meta["comparison_to_original_edition_verified"])
        self.assertFalse(meta["private_witness_replay_performed_by_ci"])
        self.assertEqual(w2.extract(HTML.encode()), (data, meta))

    def test_unique_heading_matches_and_correct_order_required(self):
        for replacement in (
            HTML.replace("<h2>النَّهْي</h2>", "<h2>مبحث ثالث</h2>"),
            HTML.replace("<h2>النَّهْي</h2>", "<h2>الْأَمر</h2>"),
            HTML.replace("<h2>الْأَمر</h2>", "<h2>النَّهْي</h2>"),
            HTML.replace("<h2>النَّهْي</h2>", "<h2>مبحث آخر</h2><h2>النَّهْي</h2>"),
        ):
            with self.subTest(example=replacement[-75:]), self.assertRaises(ValueError):
                w2.extract(replacement.encode("utf-8"))

    def test_unexpected_active_html_inside_section_fails(self):
        with self.assertRaises(ValueError):
            w2.extract(HTML.replace("<p>سطر ثانٍ", "<script>window.BAD=true</script><p>سطر ثانٍ").encode())

    def test_editorial_brackets_not_removed_or_interpreted(self):
        a, _ = w2.extract(HTML.encode())
        changed = HTML.replace("[الوجوب]", "[الندب]")
        b, _ = w2.extract(changed.encode())
        self.assertNotEqual(a, b)
        self.assertIn("الندب", b.decode())

    def test_oversize_invalid_utf8_and_bom_rejected(self):
        for value in (b"\xff", b"\xef\xbb\xbfhello", b"\x00",
                      b"x"*(w2.MAX_BYTES+1)):
            with self.subTest(length=len(value)), self.assertRaises(ValueError):
                w2.extract(value)

    def test_cli_requires_exact_frozen_raw_html_sha_before_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            raw = root/"html.html"
            exported = root/"section.txt"
            report = root/"receipt.json"
            raw.write_bytes(HTML.encode("utf-8"))
            command = [
                sys.executable, "-m", "engines.usul.pilots.waraqat_witness2_extract",
                "--raw-html", str(raw), "--out", str(exported),
                "--report", str(report)]
            root_repo = Path(__file__).resolve().parents[3]
            bad = subprocess.run(command, cwd=root_repo, capture_output=True, text=True)
            self.assertEqual(bad.returncode, 1)
            self.assertFalse(exported.exists())
            self.assertEqual(json.loads(report.read_text())["status"], "FAIL")
            # The standalone converter must also be independently reproducible.
            digest = hashlib.sha256(raw.read_bytes()).hexdigest()
            with patch.object(w2, "W2_RAW_SHA", digest):
                result = w2.extract(raw.read_bytes())
                self.assertEqual(result[1]["raw_html_sha256"], digest)
            self.assertFalse(json.loads(report.read_text()).get(
                "private_witness_replay_performed_by_ci", False))


if __name__ == "__main__":
    unittest.main()
