"""Published Stage04 receipt is a fixed Stage05 source identity, not a new claim."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from engines.usul.pilots.waraqat_stage05 import (
    RAW_SHA, EXPORT_SHA, MANIFEST_SHA, SECTION_SHA, SECTION, RULE,
    EXPECTED_SOURCE_ID, EXPECTED_SOURCE_URL,
    verify_stage04_receipt,
)
from engines.usul.source_lexical_index import LexicalContractError


class RealSourceRunnerTests(unittest.TestCase):
    def test_hardcoded_trust_anchors_match_public_stage04_record(self):
        repo = Path(__file__).resolve().parents[3]
        receipt = json.loads(
            (repo / "corpus/reviews/u01-stage04-waraqat-source-link.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(RAW_SHA, receipt["chain"]["raw_html_capture"]["sha256"])
        self.assertEqual(EXPORT_SHA,
                         receipt["chain"]["deterministic_extraction"]["extracted_utf8"]["sha256"])
        self.assertEqual(MANIFEST_SHA, receipt["chain"]["manifest"]["sha256_independently_pinned"])
        self.assertEqual(SECTION_SHA, receipt["chain"]["coverage"]["section_sha256"])
        self.assertEqual(SECTION, receipt["chain"]["coverage"]["section_id"])
        self.assertEqual(RULE, receipt["engine_link"]["rule_id"])
        self.assertEqual(EXPECTED_SOURCE_ID, receipt["engine_link"]["source_id"])
        self.assertEqual(EXPECTED_SOURCE_URL, receipt["chain"]["raw_html_capture"]["url"])

    def test_pinned_replay_rejects_even_valid_synthetic_source(self):
        # This passes against an abstract metadata record (not fake private
        # al-Waraqat bytes), showing that ordinary "PASS" is not sufficient.
        result = {
            "snapshot_sha256": EXPORT_SHA, "trusted_manifest_sha256": MANIFEST_SHA,
            "source_id": EXPECTED_SOURCE_ID, "source_url": EXPECTED_SOURCE_URL,
            "section_id": SECTION, "section_sha256": SECTION_SHA,
            "section_start_line": 86, "section_end_line_exclusive": 108,
            "indexed_line_count": 22, "indexed_byte_count": 1232,
            "upstream_replay": {
                "raw_html_sha256": RAW_SHA,
                "source_export_reproduced_from_html": True,
            },
        }
        self.assertEqual(verify_stage04_receipt(result), result)
        for field, invalid in (("snapshot_sha256", "0" * 64),
                               ("section_sha256", "0" * 64),
                               ("indexed_line_count", 21)):
            changed = copy.deepcopy(result)
            changed[field] = invalid
            with self.subTest(field=field), self.assertRaises(LexicalContractError):
                verify_stage04_receipt(changed)
        changed = copy.deepcopy(result)
        changed["upstream_replay"]["source_export_reproduced_from_html"] = False
        with self.assertRaises(LexicalContractError):
            verify_stage04_receipt(changed)

    def test_missing_private_files_returns_pending_not_fabricated_pass(self):
        repo = Path(__file__).resolve().parents[3]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            qpath = root / "queries.json"
            report = root / "result.json"
            qpath.write_text(json.dumps([{
                "id": "pilot:query", "literal": "الأمر",
                "profile": "literal_exact_v1",
            }], ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-m", "engines.usul.pilots.waraqat_stage05",
                 "--raw-html", str(root / "missing.html"),
                 "--source", str(root / "missing.txt"),
                 "--manifest", str(root / "missing-manifest.json"),
                 "--queries", str(qpath), "--report", str(report)],
                cwd=repo, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 3)
            self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["status"],
                             "PENDING_PRIVATE_STAGE04_FILES")
            self.assertNotIn("STAGE05_REAL_SOURCE_LEXICAL_REPLAY_PASS",
                             result.stdout)


if __name__ == "__main__":
    unittest.main()
