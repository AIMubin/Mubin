"""Security and completeness regressions for the private W1/W2 pair verifier."""
import copy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from engines.usul.pilots.waraqat_extract import extract as w1_extract
from engines.usul.waraqat_batch import inventory
from engines.usul.pilots.waraqat_w2_full_extract import (
    extract_sections, build_export, VERSION as EXTRACTOR_VERSION,
)
from engines.usul.pilots.waraqat_w2_pair_compare import (
    compare_all, validate_w2_manifest, PairComparisonError,
)


def sha(v):
    return hashlib.sha256(v).hexdigest()


def canon(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


W1 = ('<html><div id="content">\nتمهيد<br><h5>الأمر</h5>'
      'أمر بسيط<br><h5>النهي</h5>نهي بسيط<br></div></html>').encode("utf-8")
W2 = ('<html><body><div id="content"><h2>كتاب الورقات</h2><p>عنوان</p>'
      '<h2>الأمر</h2><p>أمر بسيط</p>'
      '<h2>النهي</h2><p>نهي بسيط</p></div>'
      '<div class="footer">خارج الكتاب</div></body></html>').encode("utf-8")


class PairIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.w1, _ = w1_extract(W1)
        self.inv = inventory(W1, expected_html_sha=sha(W1),
                             expected_export_sha=sha(self.w1),
                             require_frozen_amr=False)[1]
        self.sections = extract_sections(W2)
        self.w2_bytes = build_export(self.sections)
        files, summaries, cursor = [], [], 0
        for s in self.sections:
            data = (s["title"]+"\n"+s["text"]+"\n").encode("utf-8")
            filename = f"w2-h2-{s['h2_ordinal']:03d}.txt"
            (self.root/filename).write_bytes(data)
            files.append({"h2_ordinal": s["h2_ordinal"], "path": filename,
                          "bytes": len(data), "sha256": sha(data)})
            summaries.append({
                "h2_ordinal": s["h2_ordinal"],
                "title_sha256": sha(s["title"].encode("utf-8")),
                "title_folded_sha256": sha(s["title_folded"].encode("utf-8")),
                "derived_byte_start": cursor,
                "derived_byte_end_exclusive": cursor+len(data),
                "chars": len(s["text"]),
            })
            cursor += len(data)
        self.manifest = {
            "schema_version": "0.1.1",
            "engine": EXTRACTOR_VERSION,
            "status": "W2_FULL_EXTRACTION_PASS",
            "source_html_sha256": sha(W2),
            "source_html_bytes": len(W2),
            "offset_basis": "w2_derived_text_export (NOT original HTML offsets)",
            "sections_total": 3,
            "sections": summaries,
            "paired_with_w1": 2,
            "unresolved": [],
            "extras": [{"h2_ordinal": 1, "title_folded_sha256":
                        sha("كتاب الورقات".encode("utf-8")),
                        "kind": "TITLE_HEADING"}],
            "export_sha256": sha(self.w2_bytes),
            "export_bytes": len(self.w2_bytes),
            "section_files": files,
            "source_text_included": False,
            "scholarly_verified": False,
            "redistribution_approved": False,
        }
        self.rehash()

    def rehash(self):
        self.manifest["manifest_sha256"] = sha(canon({
            k:v for k,v in self.manifest.items() if k != "manifest_sha256"}))

    def run_pair(self):
        return compare_all(self.inv, self.w1, self.manifest, W2, self.root,
                           trusted_w1_export_sha=sha(self.w1),
                           trusted_w1_html_sha=sha(W1),
                           trusted_w2_sha=sha(W2))

    def test_full_pair_is_complete_and_stable(self):
        a = self.run_pair()
        b = self.run_pair()
        self.assertEqual(a, b)
        self.assertEqual(a["status"], "W2_PAIR_COMPARE_COMPLETE")
        self.assertEqual(a["compared_sections"], 2)
        self.assertEqual(len(a["skipped"]), 1)
        self.assertFalse(a["source_text_included"])

    def test_modified_saved_w2_section_cannot_self_pin(self):
        path = self.root/"w2-h2-002.txt"
        path.write_bytes(path.read_bytes()+b"tamper")
        with self.assertRaisesRegex(PairComparisonError, "changed since extraction"):
            self.run_pair()

    def test_rehashed_manifest_cannot_authorize_mutated_section(self):
        self.manifest["section_files"][1]["sha256"] = "0"*64
        self.rehash()
        with self.assertRaisesRegex(PairComparisonError, "manifest contents"):
            self.run_pair()

    def test_deleted_section_is_never_complete(self):
        (self.root/"w2-h2-003.txt").unlink()
        with self.assertRaises(OSError):
            self.run_pair()

    def test_changed_w2_html_and_export_pin_refused(self):
        with self.assertRaisesRegex(PairComparisonError, "W2 provenance"):
            validate_w2_manifest(self.manifest, W2+b"mutation", self.root,
                                 trusted_w2_sha=sha(W2))
        self.manifest["export_sha256"] = "0"*64
        self.rehash()
        with self.assertRaisesRegex(PairComparisonError, "HTML replay differs"):
            self.run_pair()

    def test_corrupted_w1_inventory_rejected(self):
        old = self.inv
        self.inv = copy.deepcopy(old)
        self.inv["sections"].pop()
        with self.assertRaises(ValueError):
            self.run_pair()
        self.inv = old

    def test_manifest_extra_heading_cannot_be_forged(self):
        self.manifest["extras"][0]["kind"] = "UNPAIRED"
        self.rehash()
        with self.assertRaisesRegex(PairComparisonError, "extra heading invalid"):
            self.run_pair()


if __name__ == "__main__":
    unittest.main()
