"""Synthetic regressions: forensic audit must catch disappearing word boundaries."""
from __future__ import annotations

import hashlib
import json
import unittest
from unittest.mock import patch

from engines.usul.pilots import waraqat_w2_representation_audit as audit_mod
from engines.usul.pilots.waraqat_w2_representation_audit import _compare, audit


def make_html(bab_body):
    heads = []
    for n in range(1, 22):
        title = ("كتاب الورقات" if n == 1 else "الأمر" if n == 7
                 else "النهي" if n == 8 else f"فصل{n}")
        heads.append(f"<h2>{title}</h2>")
        heads.append(bab_body if n == 7 else "<p>مادة اصطناعية</p>")
    return ('<html><body><div id="content">' +
            "".join(heads) + '</div><div class="footer">footer</div>'
            '</body></html>').encode("utf-8")


class RepresentationAuditTests(unittest.TestCase):
    def test_blank_lines_only_identical_content_lines_and_tokens(self):
        a = "الأمر\nكلمة\n\nثانية\n".encode("utf-8")
        b = "الأمر\nكلمة\nثانية\n".encode("utf-8")
        profile = _compare(a,b)
        self.assertFalse(profile["raw_byte_identical"])
        self.assertTrue(profile["nonempty_lines_identical"])
        self.assertTrue(profile["whitespace_delimited_tokens_identical"])
        self.assertTrue(profile["nonwhitespace_codepoints_identical"])

    def test_removed_paragraph_separator_is_not_format_only(self):
        a = "الأمر\nكلمة\nثانية\n".encode("utf-8")
        b = "الأمر\nكلمةثانية\n".encode("utf-8")
        profile = _compare(a,b)
        self.assertTrue(profile["nonwhitespace_codepoints_identical"])
        self.assertFalse(profile["whitespace_delimited_tokens_identical"])
        self.assertFalse(profile["nonempty_lines_identical"])

    def test_actual_three_extraction_methods_catch_concatenation(self):
        source = make_html("<p>كلمة</p><p>ثانية</p>")
        with patch.object(audit_mod, "W2_RAW_SHA",
                          hashlib.sha256(source).hexdigest()):
            report = audit(source, enforce_historical_bytes=False)
        self.assertEqual(report["status"], "REPRESENTATION_DIFFERENCE_UNRESOLVED")
        self.assertFalse(report["comparisons"]
                         ["stage06_vs_hardened_full"]
                         ["whitespace_delimited_tokens_identical"])
        self.assertTrue(report["comparisons"]
                        ["stage06_vs_hardened_full"]
                        ["nonwhitespace_codepoints_identical"])
        self.assertFalse(report["source_text_included"])
        encoded = json.dumps(report, ensure_ascii=False)
        self.assertNotIn("كلمةثانية", encoded)
        self.assertNotIn("مادة اصطناعية", encoded)

    def test_windows_write_text_crlf_expansion_is_detected(self):
        # Old full-book code used Path.write_text() on Windows. The
        # metadata "right_bytes" therefore counted CRLF, not LF.
        data = "الأمر\nكلمة\n\nثانية\n".encode("utf-8")
        legacy_windows = data.replace(b"\n", b"\r\n")
        self.assertEqual(len(legacy_windows)-len(data), data.count(b"\n"))
        profile = _compare(legacy_windows, data)
        self.assertTrue(profile["nonempty_lines_identical"])
        self.assertTrue(profile["whitespace_delimited_tokens_identical"])
        self.assertFalse(profile["raw_byte_identical"])

    def test_three_replays_report_legacy_windows_newline_metadata(self):
        source = make_html("<p>كلمة</p><p>ثانية</p>")
        with patch.object(audit_mod, "W2_RAW_SHA",
                          hashlib.sha256(source).hexdigest()):
            report = audit(source, enforce_historical_bytes=False)
        self.assertEqual(report["legacy_disk_encoding"],
                         "Windows newline=None text-mode UTF-8 (CRLF)")
        self.assertEqual(report["legacy_windows_extra_cr_bytes"],
                         report["legacy_lf_linefeed_count"])
        self.assertEqual(report["variants"]["legacy_full"]["bytes"],
                         report["legacy_lf_serialized_bytes"] +
                         report["legacy_windows_extra_cr_bytes"])

    def test_pin_mismatch_is_rejected(self):
        source = make_html("<p>كلمة</p>")
        with self.assertRaisesRegex(ValueError, "frozen pin"):
            audit(source)

    def test_report_is_deterministic(self):
        source = make_html("<p>كلمة</p><p>ثانية</p>")
        with patch.object(audit_mod, "W2_RAW_SHA",
                          hashlib.sha256(source).hexdigest()):
            self.assertEqual(audit(source, enforce_historical_bytes=False),
                             audit(source, enforce_historical_bytes=False))


if __name__ == "__main__":
    unittest.main()
