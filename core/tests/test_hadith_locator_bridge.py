"""P1.1 Phase B: exact H3.9.2 character to raw UTF-8 byte-span mapping."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from core.source_authority import verify_hadith_locator

CHUNK_BYTES = 1024 * 1024


def pin(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


class TestHadithLocatorBridge(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.cache = Path(temp.name)
        self.source_id = "openiti:001Example.Work"
        self.raw = "Header\nنص عربي 😀 وحروف\nFoot".encode("utf-8")
        self.source = {
            "source_id": self.source_id, "work_id": "001Example.Work",
            "title_ar": "نص اختباري", "qualification_eligible": True,
            "provider": "OpenITI", "source_repo": "OpenITI/RELEASE",
            "source_path": "data/001Example/001Example.Work/test",
            "repo_ref": "a" * 40, "source_blob_sha": pin(self.raw),
            "version_id": "001Example.Work.test", "format": "OpenITI-mARkdown",
        }
        self.registry = {
            "schema_version": 2,
            "registry_id": "frozen-unit-test-only",
            "sources": [self.source],
        }
        self.file = self.cache / "openiti__001Example.Work.source"
        self.file.write_bytes(self.raw)

    def match(self, excerpt: str, *, text: str | None = None, **kwargs):
        full = text if text is not None else self.raw.decode("utf-8")
        start = full.index(excerpt)
        locator = f"gitblob:{self.source['source_blob_sha']}#char={start}:{start + len(excerpt)}"
        return verify_hadith_locator(
            self.registry, self.cache, self.source_id, locator, excerpt, **kwargs
        )

    def test_arabic_emoji_codepoints_and_raw_byte_offsets(self):
        excerpt = "نص عربي 😀"
        result = self.match(excerpt)
        self.assertTrue(result["valid"], result)
        receipt = result["receipt"]
        start = self.raw.index(excerpt.encode("utf-8"))
        self.assertEqual(start, receipt["start_byte"])
        self.assertEqual(start + len(excerpt.encode("utf-8")), receipt["end_byte"])
        self.assertEqual(len("Header\n"), receipt["start_char"])
        self.assertEqual(hashlib.sha256(excerpt.encode("utf-8")).hexdigest(), receipt["excerpt_sha256"])
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), receipt["source_sha256"])
        self.assertEqual("pinned_bytes_and_exact_excerpt_only", result["scope"])
        self.assertEqual("not_authenticated", result["authority"]["edition"])
        self.assertNotIn(excerpt, json.dumps(result, ensure_ascii=False))

    def test_utf8_bom_is_a_character_at_offset_zero(self):
        self.raw = b"\xef\xbb\xbf" + "لفظ 😀 آخر".encode("utf-8")
        self.file.write_bytes(self.raw)
        self.source["source_blob_sha"] = pin(self.raw)
        got = self.match("لفظ", text=self.raw.decode("utf-8"))
        self.assertTrue(got["valid"], got)
        self.assertEqual(3, got["receipt"]["start_byte"])
        self.assertEqual(1, got["receipt"]["start_char"])

    def test_boundary_at_chunk_edge_does_not_split_multibyte_sequence(self):
        self.raw = b"x" * (CHUNK_BYTES - 1) + "ق😀خ".encode("utf-8")
        self.file.write_bytes(self.raw)
        self.source["source_blob_sha"] = pin(self.raw)
        got = self.match("ق😀")
        self.assertTrue(got["valid"], got)
        self.assertEqual(CHUNK_BYTES - 1, got["receipt"]["start_byte"])
        self.assertEqual(CHUNK_BYTES - 1 + len("ق😀".encode()), got["receipt"]["end_byte"])

    def test_quote_mismatch_fails_with_no_receipt(self):
        excerpt = "نص عربي"
        full = self.raw.decode("utf-8")
        start = full.index(excerpt)
        locator = f"gitblob:{pin(self.raw)}#char={start}:{start + len(excerpt)}"
        got = verify_hadith_locator(self.registry, self.cache, self.source_id, locator, "مختلف تمامًا")
        self.assertFalse(got["valid"])
        self.assertIsNone(got["receipt"])
        self.assertTrue(any("excerpt" in e for e in got["errors"]), got)

    def test_same_length_different_quote_cannot_be_substituted(self):
        full = self.raw.decode("utf-8")
        excerpt = "نص عربي"
        wrong = "نص مزيف"  # same Unicode codepoint and UTF-8 byte length
        self.assertEqual(len(excerpt), len(wrong))
        self.assertEqual(len(excerpt.encode("utf-8")), len(wrong.encode("utf-8")))
        start = full.index(excerpt)
        loc = f"gitblob:{pin(self.raw)}#char={start}:{start + len(excerpt)}"
        r = verify_hadith_locator(self.registry, self.cache, self.source_id, loc, wrong)
        self.assertFalse(r["valid"], r)
        self.assertIsNone(r["receipt"])
        self.assertTrue(any("excerpt" in e for e in r["errors"]), r)

    def test_non_ascii_prefix_and_middle_excerpt_map_correctly(self):
        self.raw = "تمهيد 😀\nالنص المختار والنهاية".encode("utf-8")
        self.file.write_bytes(self.raw)
        self.source["source_blob_sha"] = pin(self.raw)
        phrase = "النص المختار"
        result = self.match(phrase)
        self.assertTrue(result["valid"], result)
        self.assertEqual(self.raw.index(phrase.encode("utf-8")), result["receipt"]["start_byte"])
        self.assertEqual(self.raw.decode().index(phrase), result["receipt"]["start_char"])

    def test_out_of_bounds_char_span_fails_without_receipt(self):
        loc = f"gitblob:{pin(self.raw)}#char=1000000:1000006"
        r = verify_hadith_locator(self.registry, self.cache, self.source_id, loc, "Header")
        self.assertFalse(r["valid"], r)
        self.assertIsNone(r["receipt"])

    def test_wrong_locator_git_pin_rejected(self):
        got = verify_hadith_locator(
            self.registry, self.cache, self.source_id,
            "gitblob:" + "b" * 40 + "#char=0:4", "Head"
        )
        self.assertFalse(got["valid"])
        self.assertTrue(any("pin" in e for e in got["errors"]), got)

    def test_noncanonical_or_reversed_locator_rejected(self):
        for span in ["0:0", "4:2", "-1:4", "0:999999999", "1:2junk", "01:2", "0:02"]:
            with self.subTest(span=span):
                got = verify_hadith_locator(
                    self.registry, self.cache, self.source_id,
                    f"gitblob:{pin(self.raw)}#char={span}", "ab"
                )
                self.assertFalse(got["valid"], got)
                self.assertIsNone(got["receipt"])

    def test_excessively_long_decimal_offsets_fail_without_exception(self):
        giant = "9" * 5000
        got = verify_hadith_locator(
            self.registry, self.cache, self.source_id,
            f"gitblob:{pin(self.raw)}#char=1:{giant}", "abc"
        )
        self.assertFalse(got["valid"])
        self.assertIsNone(got["receipt"])
        self.assertTrue(got["errors"])

    def test_unpaired_surrogate_quote_does_not_crash(self):
        got = verify_hadith_locator(
            self.registry, self.cache, self.source_id,
            f"gitblob:{pin(self.raw)}#char=0:1", "\ud800"
        )
        self.assertFalse(got["valid"])
        self.assertIsNone(got["receipt"])
        self.assertTrue(any("UTF-8" in issue for issue in got["errors"]), got)

    def test_invalid_utf8_file_rejected_despite_self_consistent_pin(self):
        self.raw = b"abc\xffz"
        self.file.write_bytes(self.raw)
        self.source["source_blob_sha"] = pin(self.raw)
        got = verify_hadith_locator(
            self.registry, self.cache, self.source_id,
            f"gitblob:{pin(self.raw)}#char=0:3", "abc"
        )
        self.assertFalse(got["valid"])
        self.assertTrue(any("UTF-8" in e for e in got["errors"]), got)

    def test_lf_normalization_risk_fails_closed_even_outside_span(self):
        for raw in [b"heading\r\n" + "نص".encode(), b"heading\r" + "نص".encode(),
                    "نص".encode() + b"\r\nsuffix"]:
            with self.subTest(raw=raw):
                self.file.write_bytes(raw)
                self.source["source_blob_sha"] = pin(raw)
                got = verify_hadith_locator(
                    self.registry, self.cache, self.source_id,
                    f"gitblob:{pin(raw)}#char=0:3", "hea"
                )
                self.assertFalse(got["valid"], got)
                self.assertTrue(any("CR" in e for e in got["errors"]), got)

    def test_modified_cache_pin_does_not_pass(self):
        self.file.write_bytes(self.raw + b"!")
        result = self.match("نص عربي")
        self.assertFalse(result["valid"], result)
        self.assertIsNone(result["receipt"])
        self.assertTrue(any("pin" in e for e in result["errors"]), result)

    def test_missing_source_and_unknown_id_are_rejected(self):
        locator = f"gitblob:{pin(self.raw)}#char=0:6"
        got = verify_hadith_locator(self.registry, self.cache, "openiti:999Absent.Work", locator, "Header")
        self.assertFalse(got["valid"])
        self.file.unlink()
        got = verify_hadith_locator(self.registry, self.cache, self.source_id, locator, "Header")
        self.assertFalse(got["valid"])
        self.assertIsNone(got["receipt"])

    def test_large_excerpt_bound_applies_before_reading(self):
        got = self.match("نص عربي", max_excerpt_bytes=3)
        self.assertFalse(got["valid"])
        self.assertTrue(any("excerpt" in e for e in got["errors"]), got)

    def test_oversized_excerpt_is_rejected_before_encoding(self):
        class HugeExcerpt(str):
            def encode(self, *args, **kwargs):
                raise AssertionError("oversized quote should not be encoded")

        giant = HugeExcerpt("a" * (1024 * 1024 + 1))
        locator = f"gitblob:{pin(self.raw)}#char=0:1"
        r = verify_hadith_locator(
            self.registry, self.cache, self.source_id, locator, giant
        )
        self.assertFalse(r["valid"], r)
        self.assertIsNone(r["receipt"])
        self.assertTrue(any("limit" in issue for issue in r["errors"]), r)

    def test_nonpositive_byte_caps_rejected(self):
        for caps in [{"max_source_bytes": 0}, {"max_excerpt_bytes": 0},
                     {"max_source_bytes": True}, {"max_excerpt_bytes": False}]:
            with self.subTest(caps=caps):
                got = self.match("نص عربي", **caps)
                self.assertFalse(got["valid"])

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW"), "POSIX no-follow required")
    def test_symlink_file_rejected(self):
        alternate = self.cache / "actual.source"
        alternate.write_bytes(self.raw)
        self.file.unlink()
        self.file.symlink_to(alternate)
        got = self.match("نص عربي")
        self.assertFalse(got["valid"])
        self.assertTrue(any("unsafe" in e for e in got["errors"]), got)


if __name__ == "__main__":
    unittest.main()
