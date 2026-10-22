"""Stage 05 lexical evidence index tests using synthetic Arabic, not book text."""
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from engines.usul.source_lexical_index import (
    LexicalContractError, index_and_search,
)
from engines.usul.source_snapshot_prepare import propose

TEXT = "مقدمة\nالأمر\nالأمر والأمر\nسطر تجريبي مكرر مكرر\nالنهي\n"
META = {
    "source_id": "pilot:synthetic-witness",
    "work_title": "Synthetic source only",
    "author": "Mubin fixture",
    "edition": "Synthetic; no printed edition",
    "source_url": "https://example.invalid/synthetic",
    "locator": "synthetic:amr",
    "transcription_provenance": "Created by test, no historical origin",
}


def queries():
    return [
        {"id": "pilot:present", "literal": "الأمر", "profile": "literal_exact_v1"},
        {"id": "pilot:phrase", "literal": "سطر تجريبي", "profile": "literal_exact_v1"},
        {"id": "pilot:absent", "literal": "كلمة غير موجودة",
         "profile": "literal_exact_v1"},
        {"id": "pilot:overlap", "literal": "مكرر", "profile": "literal_exact_v1"},
    ]


class LexicalIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source = root / "source.txt"
        self.manifest = root / "manifest.json"
        self.report = root / "report.json"
        self.source.write_bytes(TEXT.encode("utf-8"))
        m = propose(self.source, META, "pilot:amr", "الأمر", "النهي")
        self.manifest.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
        self.pin = hashlib.sha256(self.manifest.read_bytes()).hexdigest()

    def run_index(self, queries_=None, **kwargs):
        return index_and_search(
            self.source, self.manifest, self.pin, "pilot:amr",
            queries() if queries_ is None else queries_, **kwargs)

    def test_every_line_exactly_indexed_and_reproducible(self):
        result = self.run_index()
        self.assertEqual(result, self.run_index())
        self.assertEqual(result["status"], "LEXICAL_INDEX_PASS")
        self.assertEqual(result["coverage_status"], "SNAPSHOT_COVERAGE_PASS")
        self.assertEqual(result["indexed_line_count"], 3)
        self.assertEqual(result["section_start_line"], 2)
        self.assertEqual(result["section_end_line_exclusive"], 5)
        self.assertEqual(result["indexed_byte_count"],
                         len("الأمر\nالأمر والأمر\nسطر تجريبي مكرر مكرر\n".encode("utf-8")))
        self.assertEqual(result["indexed_line_count"], len(result["line_index"]))
        self.assertTrue(result["line_index_complete_within_section"])
        self.assertTrue(all(len(row["line_sha256"]) == 64 for row in result["line_index"]))
        self.assertFalse(result["scholarly_verified"])
        self.assertFalse(result["redistribution_approved"])

    def test_multiple_matches_include_provable_utf8_byte_offsets(self):
        result = self.run_index()
        rows = {r["query_id"]: r for r in result["queries"]}
        self.assertEqual(rows["pilot:present"]["match_count"], 3)
        self.assertEqual(rows["pilot:phrase"]["match_count"], 1)
        self.assertEqual(rows["pilot:overlap"]["match_count"], 2)
        self.assertEqual([m["line_number"] for m in rows["pilot:present"]["matches"]],
                         [2, 3, 3])
        raw = self.source.read_bytes()
        expected = "الأمر".encode("utf-8")
        for match in rows["pilot:present"]["matches"]:
            self.assertEqual(raw[match["byte_start"]:match["byte_end_exclusive"]],
                             expected)
            self.assertEqual(match["match_sha256"],
                             hashlib.sha256(expected).hexdigest())
        self.assertEqual(rows["pilot:phrase"]["matches"][0]["column_codepoints_zero_based"], 0)
        self.assertNotIn("سطر تجريبي", json.dumps(result, ensure_ascii=False))
        self.assertFalse(result["source_text_included"])

    def test_no_hit_is_not_a_qarinah_absence_claim(self):
        result = self.run_index()
        miss = next(q for q in result["queries"] if q["query_id"] == "pilot:absent")
        self.assertEqual(miss["result_status"],
                         "NO_EXACT_LITERAL_MATCH_IN_PINNED_SECTION")
        self.assertEqual(miss["match_count"], 0)
        self.assertEqual(miss["classification"], "LEXICAL_MATCH_ONLY")
        self.assertFalse(miss["absence_of_legal_qarinah_verified"])
        self.assertFalse(miss["juristic_inference_allowed"])
        self.assertFalse(result["lexical_search_is_semantic_qarinah_detection"])

    def test_no_normalization_or_spurious_equivalence(self):
        only = [{"id": "pilot:unaccented", "literal": "الامر",
                 "profile": "literal_exact_v1"}]
        self.assertEqual(self.run_index(only)["queries"][0]["match_count"], 0)
        only[0]["profile"] = "normalize_arabic_aggressively"
        with self.assertRaises(LexicalContractError):
            self.run_index(only)

    def test_changed_snapshot_and_changed_manifest_are_refused(self):
        self.source.write_bytes(self.source.read_bytes().replace(b"\n", b"!", 1))
        with self.assertRaises(ValueError):
            self.run_index()
        self.source.write_bytes(TEXT.encode("utf-8"))
        self.manifest.write_bytes(self.manifest.read_bytes() + b" ")
        with self.assertRaises(ValueError):
            self.run_index()

    def test_section_id_unknown_rejected_without_full_source_fallback(self):
        with self.assertRaisesRegex(LexicalContractError, "section not uniquely"):
            index_and_search(self.source, self.manifest, self.pin, "pilot:other", queries())

    def test_query_shape_and_length_boundaries(self):
        invalid = [
            [],
            [{"id": "pilot:bad", "literal": "", "profile": "literal_exact_v1"}],
            [{"id": "pilot:bad", "literal": "abc\nxyz", "profile": "literal_exact_v1"}],
            [{"id": "pilot:bad", "literal": "x" * 257, "profile": "literal_exact_v1"}],
            [{"id": "pilot:bad", "literal": "x", "profile": "other"}],
            [{"id": "pilot:bad", "literal": "x", "profile": "literal_exact_v1",
              "raw_source": True}],
            [queries()[0], queries()[0]],
        ]
        for case in invalid:
            with self.subTest(case=repr(case)[:80]), self.assertRaises(ValueError):
                self.run_index(case)

    def test_missing_html_pin_or_one_sided_pair_fails(self):
        with self.assertRaises(LexicalContractError):
            self.run_index(raw_html_path=self.source)
        with self.assertRaises(LexicalContractError):
            self.run_index(trusted_raw_html_sha256="0" * 64)

    def test_raw_html_digest_and_replay_on_synthetic_witness(self):
        from engines.usul.tests.test_waraqat_extract import FIXTURE
        from engines.usul.pilots.waraqat_extract import extract
        root = Path(self.temp.name)
        raw_html = root / "original.html"
        raw_html.write_bytes(FIXTURE.encode("utf-8"))
        text, _ = extract(raw_html.read_bytes())
        self.source.write_bytes(text)
        new_m = propose(self.source, META, "pilot:amr", "الأمر", "النهي")
        self.manifest.write_text(json.dumps(new_m, ensure_ascii=False), encoding="utf-8")
        self.pin = hashlib.sha256(self.manifest.read_bytes()).hexdigest()
        html_pin = hashlib.sha256(raw_html.read_bytes()).hexdigest()
        outcome = self.run_index(raw_html_path=raw_html,
                                 trusted_raw_html_sha256=html_pin)
        self.assertTrue(outcome["upstream_replay"]["source_export_reproduced_from_html"])
        self.assertEqual(outcome["upstream_replay"]["raw_html_sha256"], html_pin)
        # An unrelated HTML capture cannot authorize another snapshot.
        raw_html.write_bytes(raw_html.read_bytes() + b"<!-- changed -->")
        with self.assertRaisesRegex(LexicalContractError, "SHA-256"):
            self.run_index(raw_html_path=raw_html, trusted_raw_html_sha256=html_pin)

    def test_cli_is_utf8_safe_and_never_displays_source_excerpt(self):
        qfile = Path(self.temp.name) / "queries.json"
        qfile.write_text(json.dumps(queries(), ensure_ascii=False), encoding="utf-8")
        cmd = [
            sys.executable, "-m", "engines.usul.source_lexical_index",
            "--source", str(self.source), "--manifest", str(self.manifest),
            "--trusted-manifest-sha256", self.pin,
            "--section-id", "pilot:amr", "--queries", str(qfile),
            "--report", str(self.report),
        ]
        proc = subprocess.run(cmd, cwd=Path(__file__).resolve().parents[3],
                              capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(proc.stdout.isascii())
        report = json.loads(self.report.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "LEXICAL_INDEX_PASS")
        self.assertNotIn("سطر تجريبي", self.report.read_text(encoding="utf-8"))
        self.assertFalse(report["source_text_included"])
        missing = subprocess.run(
            [v if v != str(self.source) else str(self.source.parent / "missing.txt")
             for v in cmd],
            cwd=Path(__file__).resolve().parents[3], capture_output=True, text=True,
        )
        self.assertEqual(missing.returncode, 3)
        self.assertEqual(json.loads(self.report.read_text(encoding="utf-8"))["status"],
                         "PENDING_SOURCE")


if __name__ == "__main__":
    unittest.main()
