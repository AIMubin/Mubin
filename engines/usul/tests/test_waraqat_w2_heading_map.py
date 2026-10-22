"""W2 H2 title fingerprint candidate mapping; never claims section equivalence."""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engines.usul.pilots.waraqat_extract import extract
from engines.usul.waraqat_batch import inventory
from engines.usul import waraqat_w2_heading_map as mapping


def sha(b):
    return hashlib.sha256(b).hexdigest()


class W2HeadingTests(unittest.TestCase):
    def setUp(self):
        self.w1_html = (
            "<html><div id=\"content\">\nتمهيد<br><h5>الأمر</h5>مثال<br>"
            "<h5>النهي</h5>مثال<br><h5>باب 3</h5>مثال<br>"
            "<h5>باب 4</h5>مثال<br></div></html>"
        ).encode("utf-8")
        exported, _ = extract(self.w1_html)
        self.export_sha = sha(exported)
        self.w1_inventory = inventory(
            self.w1_html, expected_html_sha=sha(self.w1_html),
            expected_export_sha=self.export_sha,
            require_frozen_amr=False,
        )[1]
        self.w2_html = (
            "<html><header>ملاحة</header><article><h2>الأَمْر</h2>"
            "<p>مثال</p><h2>النهي</h2><p>مثال</p>"
            "<h2>باب 3</h2><p>مثال</p><h2>باب 4</h2></article></html>"
        ).encode("utf-8")

    def call(self, w2=None, inventory_report=None):
        w2 = self.w2_html if w2 is None else w2
        with patch.object(mapping, "W1_RAW_SHA", sha(self.w1_html)), \
             patch.object(mapping, "W1_EXPORT_SHA", self.export_sha):
            return mapping.map_headings(
                w2, self.w1_inventory if inventory_report is None else inventory_report,
                trusted_w2_sha=sha(w2),
            )

    def test_single_source_success_remains_independent_of_diagnostic_w2(self):
        result = self.call()
        self.assertEqual(result, self.call())
        self.assertEqual(result["status"], "W2_HEADING_MAPPING_CANDIDATES_RECORDED")
        self.assertEqual(result["w1_chapter_count"], 4)
        self.assertEqual(result["pair_count"], 4)
        self.assertEqual(result["unresolved_count"], 0)
        self.assertFalse(result["whole_book_comparison_verified"])
        self.assertFalse(result["w2_section_extraction_verified"])
        self.assertTrue(all(not x["chapter_section_bytes_aligned"]
                            for x in result["candidate_title_pairs"]))
        self.assertNotIn("ملاحة", json.dumps(result, ensure_ascii=False))
        self.assertNotIn("النهي", json.dumps(result, ensure_ascii=False))

    def test_ambiguous_headings_cannot_be_assumed_same_chapter(self):
        html = self.w2_html.replace("<h2>باب 3</h2>".encode(),
                                     "<h2>النهي</h2><h2>باب 3</h2>".encode())
        report = self.call(w2=html)
        self.assertGreater(report["unresolved_count"], 0)
        self.assertTrue(any(
            x["diagnostic_status"] == "AMBIGUOUS_OR_DUPLICATE_TITLE"
            for x in report["unpaired_or_conflicted_w1"]
        ))

    def test_missing_headings_is_a_diagnostic_not_fake_alignment(self):
        html = self.w2_html.replace("<h2>باب 3</h2>".encode(), b"")
        report = self.call(w2=html)
        self.assertEqual(report["unresolved_count"], 1)
        self.assertFalse(report["whole_book_comparison_verified"])

    def test_w2_root_html_must_have_separately_supplied_frozen_pin(self):
        with patch.object(mapping, "W1_RAW_SHA", sha(self.w1_html)), \
             patch.object(mapping, "W1_EXPORT_SHA", self.export_sha):
            with self.assertRaisesRegex(mapping.HeadingMapError, "independent frozen pin"):
                mapping.map_headings(self.w2_html + b"mutation",
                                     self.w1_inventory,
                                     trusted_w2_sha=sha(self.w2_html))

    def test_w1_inventory_self_hash_unsafe_without_frozen_root(self):
        with self.assertRaisesRegex(mapping.HeadingMapError,
                                    "full original source inventory"):
            mapping.map_headings(
                self.w2_html, self.w1_inventory,
                trusted_w2_sha=sha(self.w2_html))

    def test_changed_w1_manifest_fingerprint_rejected(self):
        tampered=copy.deepcopy(self.w1_inventory)
        tampered["sections"][1]["heading_folded_sha256"] = "0"*64
        with self.assertRaisesRegex(mapping.HeadingMapError, "canonical digest"):
            self.call(inventory_report=tampered)

    def test_malformed_active_markup_in_title_rejected(self):
        altered=self.w2_html.replace("<h2>النهي</h2>".encode(),
                                     "<h2>النهي<script>bad</script></h2>".encode())
        with self.assertRaisesRegex(mapping.HeadingMapError, "unsafe"):
            self.call(w2=altered)

    def test_operator_cli_missing_private_w2_pending_not_false_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)
            result=p/"out.json"
            proc=subprocess.run(
                [sys.executable, "-m", "engines.usul.pilots.waraqat_w2_title_map",
                 "--secondary-html", str(p/"missing.html"),
                 "--w1-inventory", str(p/"missing.json"),
                 "--report", str(result)],
                cwd=Path(__file__).resolve().parents[3],
                capture_output=True,text=True)
            self.assertEqual(proc.returncode,3,proc.stderr)
            self.assertEqual(json.loads(result.read_text(encoding="utf-8"))["status"],
                             "PENDING_SECONDARY_WITNESS_OR_W1_INVENTORY")


if __name__=="__main__":
    unittest.main()
