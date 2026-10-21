"""Full W1 chapter campaign: source partition, failure isolation and no source leak."""
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

from engines.usul.arabic_evidence_retrieval import FOLD_MARKS
from engines.usul.pilots import waraqat_chapter_batch as batch
from engines.usul.pilots.waraqat_extract import extract


HTML = """<!doctype html><html><body>
<div id="header">PRIVATE SITE HEADER</div><div id="content">
مقدمة دون عنوان<br />
<h5>أبواب أصول الفقه</h5>
مسألة تمهيدية لا تتصل بالاستدلال<br />
<h5>الأمر</h5>
الأمر ليس الندب ولا <br />
<h5>النهي</h5>
النهي نهي ولا تنس<br />
<h5>العام</h5>
العام لفظ وله سياق<br />
</div><footer>site chrome not book</footer></body></html>
"""
QUERIES = [
    {"id": "pilot:amr", "literal": "الأمر", "candidate_profiles": [FOLD_MARKS]},
    {"id": "pilot:negation", "literal": "ليس", "candidate_profiles": [FOLD_MARKS]},
]


class ChapterBatchTests(unittest.TestCase):
    def setUp(self):
        self.raw = HTML.encode("utf-8")
        self.source, _ = extract(self.raw)
        self.raw_sha = hashlib.sha256(self.raw).hexdigest()
        self.source_sha = hashlib.sha256(self.source).hexdigest()
        lines = self.source.splitlines(keepends=True)
        indexes = [i for i, line in enumerate(lines) if line.strip() in
                   ("الأمر".encode(), "النهي".encode())]
        self.assertEqual(len(indexes), 2)
        left, right = indexes
        self.amr_line = left + 1
        self.amr_start = sum(map(len, lines[:left]))
        self.amr_end = sum(map(len, lines[:right]))
        self.amr_sha = hashlib.sha256(
            self.source[self.amr_start:self.amr_end]).hexdigest()
        self.patchers = [
            patch.object(batch, "EXPECTED_AMR_LINE", self.amr_line),
            patch.object(batch, "EXPECTED_AMR_BEGIN", self.amr_start),
            patch.object(batch, "EXPECTED_AMR_END", self.amr_end),
            patch.object(batch, "W1_SECTION_SHA", self.amr_sha),
        ]
        for obj in self.patchers:
            obj.start()
            self.addCleanup(obj.stop)

    def inventory(self, raw=None, export=None, **opts):
        raw = self.raw if raw is None else raw
        export = self.source if export is None else export
        return batch.inventory(
            raw, export,
            raw_pin=opts.get("raw_pin", self.raw_sha),
            export_pin=opts.get("export_pin", self.source_sha),
        )

    def campaign(self, raw=None, export=None, queries=None):
        return batch.campaign(
            self.raw if raw is None else raw,
            self.source if export is None else export,
            QUERIES if queries is None else queries,
            raw_pin=self.raw_sha,
            export_pin=self.source_sha,
        )

    def test_inventory_identifies_every_heading_and_full_source_byte_partition(self):
        index = self.inventory()
        self.assertEqual(index["status"], "PRIMARY_WITNESS_CHAPTER_INVENTORY_PASS")
        self.assertEqual(index["heading_count"], 4)
        self.assertEqual(index["chapter_count"], 4)
        self.assertGreater(index["preface"]["bytes"], 0)
        self.assertEqual(index["chapters"][0]["heading"], "أبواب أصول الفقه")
        self.assertEqual(index["chapters"][-1]["heading"], "العام")
        self.assertTrue(index["complete_original_byte_partition_verified"])
        self.assertTrue(index["bab_amr_frozen_stage04_replay_verified"])
        offsets = [0, index["preface"]["byte_end_exclusive"]]
        offsets.extend(c["source_byte_end_exclusive"] for c in index["chapters"])
        self.assertEqual(offsets, sorted(offsets))
        self.assertEqual(offsets[-1], len(self.source))
        prev = offsets[1]
        for c in index["chapters"]:
            self.assertEqual(c["source_byte_start"], prev)
            chunk = self.source[c["source_byte_start"]:c["source_byte_end_exclusive"]]
            self.assertEqual(hashlib.sha256(chunk).hexdigest(), c["section_sha256"])
            prev = c["source_byte_end_exclusive"]
        self.assertNotIn("PRIVATE SITE HEADER", json.dumps(index, ensure_ascii=False))

    def test_batch_runs_search_and_context_for_all_chapters_without_p0(self):
        result = self.campaign()
        self.assertEqual(result, self.campaign())
        self.assertEqual(result["status"], "PRIMARY_WITNESS_BATCH_COVERAGE_PASS")
        self.assertEqual(result["chapters_processed"], 4)
        self.assertEqual(result["chapters_passed"], 4)
        self.assertEqual(result["chapters_blocked"], 0)
        self.assertTrue(result["inventory"]["complete_original_byte_partition_verified"])
        self.assertFalse(result["w2_comparator_available_for_all_chapters"])
        self.assertFalse(result["scholarly_verified"])
        self.assertFalse(result["juristic_inference_allowed"])
        self.assertFalse(result["redistribution_approved"])
        self.assertTrue(all(c["w2_alignment"] == "PENDING_COMPARATOR_CHAPTER_INVENTORY"
                            for c in result["chapter_results"]))
        self.assertEqual(len(result["report_sha256"]), 64)
        report = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("الأمر ليس الندب", report)
        self.assertNotIn("مسألة تمهيدية", report)

    def test_dangerous_source_change_and_self_pinning_refused(self):
        mutated = self.raw.replace("ليس".encode(), "لم".encode())
        with self.assertRaisesRegex(batch.BatchCoverageError, "frozen"):
            self.inventory(raw=mutated)
        mutated_source = self.source.replace("ليس".encode(), "لم".encode())
        with self.assertRaisesRegex(batch.BatchCoverageError, "frozen"):
            self.inventory(export=mutated_source)
        with self.assertRaisesRegex(batch.BatchCoverageError, "does not reconstruct"):
            self.inventory(export=self.source + b"\n",
                           export_pin=hashlib.sha256(self.source + b"\n").hexdigest())

    def test_absent_or_duplicate_headings_refused(self):
        for value in (HTML.replace("<h5>النهي</h5>", "<p>النهي</p>"),
                      HTML.replace("<h5>العام</h5>", "<h5>الأمر</h5>"),
                      HTML.replace("</h5>", "", 1),
                      HTML.replace("<h5>النهي</h5>", "<h5><b>النهي</b></h5>")):
            raw = value.encode("utf-8")
            source, _ = extract(raw)
            with self.subTest(value=value[:55]), self.assertRaises(batch.BatchCoverageError):
                self.inventory(raw=raw, export=source,
                               raw_pin=hashlib.sha256(raw).hexdigest(),
                               export_pin=hashlib.sha256(source).hexdigest())

    def test_prior_amr_pin_must_never_regress(self):
        with patch.object(batch, "EXPECTED_AMR_END", self.amr_end + 1):
            with self.assertRaisesRegex(batch.BatchCoverageError, "regress"):
                self.inventory()

    def test_chunk_too_large_marks_only_affected_chapter(self):
        with patch.object(batch, "MAX_SECTION_BYTES", 40):
            result = self.campaign()
        self.assertEqual(result["status"], "PRIMARY_WITNESS_BATCH_PARTIAL")
        self.assertTrue(result["chapters_blocked"] >= 1)
        self.assertTrue(any(x["status"] == "SECTION_TOO_LARGE_REQUIRES_CHUNKING"
                            for x in result["chapter_results"]))
        self.assertEqual(result["chapters_passed"] + result["chapters_blocked"],
                         result["chapters_processed"])

    def test_cli_missing_private_sources_is_pending_not_fake_coverage(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            queryfile = root / "query.json"
            queryfile.write_text(json.dumps(QUERIES, ensure_ascii=False), encoding="utf-8")
            report = root / "result.json"
            cmd = [sys.executable, "-m", "engines.usul.pilots.waraqat_chapter_batch",
                   "--primary-html", str(root / "absent.html"),
                   "--primary-export", str(root / "absent.txt"),
                   "--queries", str(queryfile), "--report", str(report)]
            result = subprocess.run(cmd, cwd=Path(__file__).resolve().parents[3],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 3, result.stderr)
            self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["status"],
                             "PENDING_PRIVATE_WITNESS_FILES")
            self.assertNotIn("PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
