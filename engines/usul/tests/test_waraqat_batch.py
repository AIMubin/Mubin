"""Synthetic full Waraqat witness inventory/batch; privacy, contiguous bytes and isolation."""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from engines.usul.waraqat_batch import (
    BatchCoverageError, batch_retrieve_and_graph, inventory,
)
from engines.usul.arabic_evidence_retrieval import FOLD_MARKS
from engines.usul.pilots.waraqat_extract import extract


def _digest(b):
    return hashlib.sha256(b).hexdigest()


def _html(n=3, *, large_chapter=False):
    names = ["الأمر", "النهي"] + [f"باب {i}" for i in range(3,n+1)]
    blocks = ['<div id="content">\nمقدمة<br>']
    for k, name in enumerate(names):
        body = "الأمر لا يعني شيئًا<br>" if k == 0 else "المثال الدلالي<br>"
        if large_chapter and k == 1:
            body += ("ف" * 17000) + "<br>"
        blocks.append(f"<h5>{name}</h5>{body}")
    blocks.append("</div><footer>خارج المصدر</footer>")
    return ("<html>"+"".join(blocks)+"</html>").encode("utf-8")


QUERIES = [{"id": "pilot:amr", "literal": "الأمر",
            "candidate_profiles": [FOLD_MARKS]}]


class FullBookBatchTests(unittest.TestCase):
    def data(self, *, n=3, large_chapter=False):
        source = _html(n, large_chapter=large_chapter)
        export, _ = extract(source)
        return source, export

    def inv(self, *, n=3, large_chapter=False):
        source, export = self.data(n=n, large_chapter=large_chapter)
        got, meta = inventory(source, expected_html_sha=_digest(source),
                              expected_export_sha=_digest(export),
                              require_frozen_amr=False)
        self.assertEqual(got, export)
        return got, meta

    def test_full_original_utf8_bytes_partitioned_without_leaks(self):
        export, meta = self.inv(n=20)
        self.assertEqual(meta["status"], "FULL_W1_SOURCE_INVENTORY_PASS")
        self.assertEqual(meta["chapter_heading_count"], 20)
        self.assertEqual(meta["partition_count_including_prelude"], 21)
        self.assertTrue(meta["all_original_bytes_partitioned_once"])
        self.assertEqual(meta["source_export_byte_count"], len(export))
        self.assertEqual(meta["source_export_line_count"],
                         len(export.splitlines(keepends=True)))
        sections = meta["sections"]
        self.assertEqual(sections[0]["kind"], "PRELUDE")
        self.assertEqual(sections[0]["source_byte_start"], 0)
        self.assertEqual(sections[-1]["source_byte_end_exclusive"], len(export))
        pos = 0
        for section in sections:
            self.assertEqual(section["source_byte_start"], pos)
            pos = section["source_byte_end_exclusive"]
            raw = export[section["source_byte_start"]:pos]
            self.assertTrue(raw)
            self.assertEqual(section["byte_count"], len(raw))
            self.assertEqual(section["section_sha256"], _digest(raw))
            self.assertFalse(section["source_text_included"])
        self.assertEqual(pos, len(export))
        self.assertEqual((export, meta), self.inv(n=20))
        self.assertNotIn("المثال الدلالي", json.dumps(meta, ensure_ascii=False))
        self.assertNotIn("مقدمة", json.dumps(meta, ensure_ascii=False))

    def test_each_chapter_is_separately_indexed_with_hash_only_context(self):
        export, meta = self.inv(n=4)
        result = batch_retrieve_and_graph(export, meta, QUERIES)
        self.assertEqual(result["status"], "FULL_W1_BATCH_PASS")
        self.assertEqual(result["sections_total"], 5)
        self.assertEqual(result["sections_failed"], 0)
        self.assertEqual(result, batch_retrieve_and_graph(export, meta, QUERIES))
        self.assertEqual(sum(x["exact_match_count"] for x in result["sections"]), 2)
        self.assertEqual(result["sections"][0]["exact_match_count"], 0)
        self.assertTrue(all(x["comparison_status"] ==
                            "SECOND_WITNESS_COMPARISON_NOT_RUN" for x in result["sections"]))
        self.assertTrue(all(x["semantic_interpretation_status"] ==
                            "NOT_EVALUATED" for x in result["sections"]))
        self.assertFalse(result["scholarly_verified"])
        self.assertFalse(result["cross_witness_comparison_verified"])
        self.assertFalse(result["public_fatwa_authorized"])
        self.assertNotIn("المثال الدلالي", json.dumps(result, ensure_ascii=False))

    def test_individual_oversize_section_isolated_from_healthy_chapters(self):
        export, meta = self.inv(n=4, large_chapter=True)
        result = batch_retrieve_and_graph(export, meta, QUERIES)
        self.assertEqual(result["status"], "W1_BATCH_PARTIAL_REQUIRES_REVIEW")
        self.assertEqual(result["sections_total"], 5)
        self.assertEqual(result["sections_failed"], 1)
        self.assertEqual(result["sections_passed"], 4)
        self.assertEqual(sum(x["status"] == "SECTION_PROCESSING_FAILED"
                             for x in result["sections"]), 1)
        self.assertTrue(all(x["status"] == "PASS" for x in result["sections"]
                            if x["section_id"] != "waraqat:w1:chapter-002"))

    def test_original_html_pin_tamper_fails_closed(self):
        src, exported = self.data()
        with self.assertRaisesRegex(BatchCoverageError, "HTML pin"):
            inventory(src + b"X", expected_html_sha=_digest(src),
                      expected_export_sha=_digest(exported),
                      require_frozen_amr=False)
        with self.assertRaisesRegex(BatchCoverageError, "export pin"):
            inventory(src, expected_html_sha=_digest(src),
                      expected_export_sha="0"*64, require_frozen_amr=False)

    def test_duplicate_heading_markup_disallowed(self):
        html = _html().replace(b"<h5>", b"<h5 class='invalid'>", 1)
        utf8, _ = extract(html)
        with self.assertRaisesRegex(BatchCoverageError, "heading markup"):
            inventory(html, expected_html_sha=_digest(html),
                      expected_export_sha=_digest(utf8),
                      require_frozen_amr=False)

    def test_nested_title_markup_rejected(self):
        source = _html().replace("الأمر</h5>".encode("utf8"),
                                  "<b>الأمر</b></h5>".encode("utf8"), 1)
        exported, _ = extract(source)
        with self.assertRaisesRegex(BatchCoverageError, "nested HTML"):
            inventory(source, expected_html_sha=_digest(source),
                      expected_export_sha=_digest(exported),
                      require_frozen_amr=False)

    def test_no_ambiguous_newline_in_heading(self):
        source = _html().replace("النهي</h5>".encode("utf8"),
                                  "النهي<br>كلمة</h5>".encode("utf8"), 1)
        exported, _ = extract(source)
        with self.assertRaisesRegex(BatchCoverageError, "nested HTML|multiline heading"):
            inventory(source, expected_html_sha=_digest(source),
                      expected_export_sha=_digest(exported),
                      require_frozen_amr=False)

    def test_internal_manifest_tamper_blocks_batch_even_with_matching_export(self):
        exported, meta = self.inv()
        meta = copy.deepcopy(meta)
        meta["sections"][1]["section_sha256"] = "0"*64
        with self.assertRaisesRegex(BatchCoverageError, "listed section hash"):
            batch_retrieve_and_graph(exported, meta, QUERIES)

    def test_deleted_sections_rejected_even_when_inventory_digest_recomputed(self):
        for removed in (0, 1, -1):
            with self.subTest(removed=removed):
                exported, meta = self.inv(n=4)
                altered = copy.deepcopy(meta)
                altered["sections"].pop(removed)
                altered["partition_count_including_prelude"] = len(altered["sections"])
                altered["chapter_heading_count"] = len(altered["sections"])-1
                altered["inventory_sha256"] = _digest(
                    json.dumps({k:v for k,v in altered.items()
                                if k != "inventory_sha256"},
                               ensure_ascii=False, sort_keys=True,
                               separators=(",", ":"), allow_nan=False).encode("utf-8"))
                with self.assertRaises(BatchCoverageError):
                    batch_retrieve_and_graph(exported, altered, QUERIES)

    def test_reordered_duplicate_and_coordinate_tampering_rejected(self):
        exported, meta = self.inv(n=4)
        for change in ("duplicate", "reorder", "overlap", "line", "digest"):
            with self.subTest(change=change):
                altered = copy.deepcopy(meta)
                if change == "duplicate":
                    altered["sections"][2]["id"] = altered["sections"][1]["id"]
                elif change == "reorder":
                    altered["sections"][1], altered["sections"][2] = (
                        altered["sections"][2], altered["sections"][1])
                elif change == "overlap":
                    altered["sections"][2]["source_byte_start"] -= 1
                elif change == "line":
                    altered["sections"][2]["source_line_start"] += 1
                else:
                    altered["inventory_sha256"] = "0"*64
                with self.assertRaises(BatchCoverageError):
                    batch_retrieve_and_graph(exported, altered, QUERIES)

    def test_independent_trusted_digest_anchor(self):
        from engines.usul.waraqat_batch import validate_inventory
        exported, meta = self.inv(n=4)
        self.assertTrue(validate_inventory(exported, meta,
                                          trusted_export_sha=_digest(exported),
                                          trusted_html_sha=meta["source_raw_html_sha256"]))
        with self.assertRaisesRegex(BatchCoverageError, "trusted source digest"):
            validate_inventory(exported, meta, trusted_export_sha="0"*64)

    def test_missing_private_source_does_not_claim_pass(self):
        with tempfile.TemporaryDirectory() as name:
            p = Path(name)
            query = p/"queries.json"
            query.write_text(json.dumps(QUERIES, ensure_ascii=False), encoding="utf-8")
            report, manifest = p/"report.json", p/"inventory.json"
            cmd = [sys.executable, "-m",
                   "engines.usul.pilots.waraqat_full_book_batch",
                   "--primary-html", str(p/"missing.html"),
                   "--primary-export", str(p/"missing.txt"),
                   "--queries", str(query),
                   "--inventory", str(manifest),
                   "--report", str(report)]
            proc = subprocess.run(cmd,
                                  cwd=Path(__file__).resolve().parents[3],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 3, proc.stderr)
            self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["status"],
                             "PENDING_PRIVATE_WITNESS_FILES")
            self.assertTrue(proc.stdout.isascii())


if __name__ == "__main__":
    unittest.main()
