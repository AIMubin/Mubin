"""P1 adversarial tests against local operator-provided synthetic source files."""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from core.provenance import verify_bundle
from test_inference_foundation import ROOT, fixture


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class TestP1Provenance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bundle = fixture()
        excerpt = self.bundle["evidence"][0]["excerpt"].encode("utf-8")
        self.raw = b"Preface\n" + excerpt + b"\nEnd\n"
        self.path = self.root / "snapshots" / "sample.txt"
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(self.raw)
        a = len(b"Preface\n")
        b = a + len(excerpt)
        source = self.bundle["sources"][0]
        source["content_sha256"] = sha(self.raw)
        self.manifest = {
            "contract_version": "0.1.0",
            "sources": [{
                "id": source["id"], "relative_path": "snapshots/sample.txt",
                "work_title": source["work_title"], "edition": source["edition"],
                "scope_locator": source["locator"], "content_sha256": sha(self.raw),
                "rights": {"status": "operator_cleared",
                           "basis": "Synthetic sample generated locally for unit tests",
                           "reference": "tests:synthetic-only"},
                "spans": [{"locator": "folio-1", "start_byte": a, "end_byte": b}],
            }],
        }

    def verify(self):
        return verify_bundle(self.bundle, self.manifest, self.root)

    def assert_failed(self, contains):
        result = self.verify()
        self.assertFalse(result["valid"], result)
        self.assertEqual([], result["receipts"])
        self.assertTrue(any(contains in msg for msg in result["errors"]), result["errors"])

    def test_exact_local_receipt(self):
        result = self.verify()
        self.assertTrue(result["valid"], result)
        self.assertEqual("local_byte_exact_match_only", result["scope"])
        self.assertEqual("operator_assertion_only", result["rights_assurance"])
        self.assertEqual(1, len(result["receipts"]))
        self.assertEqual("ev.001", result["receipts"][0]["evidence_id"])

    def test_deterministic_receipt_and_no_mutation(self):
        original_bundle = copy.deepcopy(self.bundle)
        original_manifest = copy.deepcopy(self.manifest)
        self.assertEqual(self.verify(), self.verify())
        self.assertEqual(original_bundle, self.bundle)
        self.assertEqual(original_manifest, self.manifest)

    def test_tampered_source_file_fails_digest(self):
        self.path.write_bytes(self.raw + b"extra")
        self.assert_failed("full snapshot SHA-256 mismatch")

    def test_self_consistent_quote_digest_but_wrong_original_bytes(self):
        text = "Invented statement not in the alleged edition."
        quote = self.bundle["evidence"][0]
        quote["excerpt"] = text
        quote["excerpt_sha256"] = sha(text.encode("utf-8"))
        self.assert_failed("byte-exact excerpt mismatch")

    def test_wrong_locator_interval_is_detected(self):
        self.manifest["sources"][0]["spans"][0]["start_byte"] = 0
        self.assert_failed("byte-exact excerpt mismatch")

    def test_utf8_arabic_quote_at_exact_byte_offsets(self):
        excerpt = "هذا نص عربي تجريبي فقط."
        raw = ("البداية\n" + excerpt + "\nالنهاية").encode("utf-8")
        self.path.write_bytes(raw)
        self.bundle["sources"][0]["content_sha256"] = sha(raw)
        quote = self.bundle["evidence"][0]
        quote["excerpt"] = excerpt
        quote["excerpt_sha256"] = sha(excerpt.encode("utf-8"))
        entry = self.manifest["sources"][0]
        entry["content_sha256"] = sha(raw)
        a = len("البداية\n".encode("utf-8"))
        entry["spans"][0].update(start_byte=a, end_byte=a + len(excerpt.encode("utf-8")))
        self.assertTrue(self.verify()["valid"], self.verify())

    def test_locator_that_splits_utf8_codepoint_rejected(self):
        self.test_utf8_arabic_quote_at_exact_byte_offsets()
        self.manifest["sources"][0]["spans"][0]["start_byte"] += 1
        self.assert_failed("splits UTF-8 character")

    def test_duplicate_locator_rejected(self):
        self.manifest["sources"][0]["spans"].append(
            dict(self.manifest["sources"][0]["spans"][0])
        )
        self.assert_failed("duplicate locator")

    def test_overlapping_locator_spans_rejected(self):
        a = self.manifest["sources"][0]["spans"][0]["start_byte"]
        b = self.manifest["sources"][0]["spans"][0]["end_byte"]
        self.manifest["sources"][0]["spans"].append({
            "locator": "another", "start_byte": a + 1, "end_byte": b
        })
        self.assert_failed("overlapping locator spans")

    def test_invalid_byte_span_rejected(self):
        self.manifest["sources"][0]["spans"][0]["end_byte"] = len(self.raw) + 10
        self.assert_failed("invalid byte span")

    def test_reject_unknown_rights(self):
        self.manifest["sources"][0]["rights"]["status"] = "unknown"
        self.assert_failed("rights not operator-cleared")

    def test_reject_restricted_rights(self):
        self.manifest["sources"][0]["rights"]["status"] = "restricted"
        self.assert_failed("rights not operator-cleared")

    def test_license_basis_is_required_not_legally_verified(self):
        self.manifest["sources"][0]["rights"]["basis"] = ""
        self.assert_failed("manifest:")

    def test_different_edition_fails(self):
        self.manifest["sources"][0]["edition"] = "not-the-pinned-edition"
        self.assert_failed("mismatched edition")

    def test_different_work_title_fails(self):
        self.manifest["sources"][0]["work_title"] = "other work"
        self.assert_failed("mismatched work_title")

    def test_different_source_locator_fails(self):
        self.manifest["sources"][0]["scope_locator"] = "other-scope"
        self.assert_failed("mismatched scope_locator")

    def test_missing_citation_locator_fails(self):
        self.manifest["sources"][0]["spans"][0]["locator"] = "different"
        self.assert_failed("missing verified snapshot locator")

    def test_path_traversal_rejected(self):
        self.manifest["sources"][0]["relative_path"] = "../outside.txt"
        self.assert_failed("unsafe relative snapshot path")

    def test_backslash_path_rejected(self):
        self.manifest["sources"][0]["relative_path"] = "snapshots\\sample.txt"
        self.assert_failed("unsafe relative snapshot path")

    def test_symlinked_source_rejected(self):
        link = self.root / "snapshots" / "linked.txt"
        link.symlink_to(self.path)
        self.manifest["sources"][0]["relative_path"] = "snapshots/linked.txt"
        self.assert_failed("symbolic links")

    def test_symlinked_parent_rejected(self):
        link = self.root / "shortcut"
        link.symlink_to(self.path.parent, target_is_directory=True)
        self.manifest["sources"][0]["relative_path"] = "shortcut/sample.txt"
        self.assert_failed("symbolic links")

    def test_missing_file_rejected(self):
        self.path.unlink()
        self.assert_failed("not an existing regular file")

    def test_invalid_source_utf8_rejected(self):
        bad = b"\xff\xfe\xfc"
        self.path.write_bytes(bad)
        self.bundle["sources"][0]["content_sha256"] = sha(bad)
        self.manifest["sources"][0]["content_sha256"] = sha(bad)
        self.assert_failed("unreadable or unsafe UTF-8")

    def test_source_over_size_limit(self):
        raw = b"Z" * (8 * 1024 * 1024 + 1)
        self.path.write_bytes(raw)
        self.bundle["sources"][0]["content_sha256"] = sha(raw)
        self.manifest["sources"][0]["content_sha256"] = sha(raw)
        self.assert_failed("snapshot exceeds")

    def test_missing_source_in_manifest_rejected(self):
        self.manifest["sources"][0]["id"] = "src.other"
        self.assert_failed("manifest source IDs do not match")

    def test_duplicate_manifest_source_rejected(self):
        self.manifest["sources"].append(copy.deepcopy(self.manifest["sources"][0]))
        self.assert_failed("duplicate source")

    def test_self_asserted_human_source_check_not_p1_verified(self):
        self.bundle["evidence"][0]["verification_method"] = "human_source_check"
        self.assert_failed("requires exact_source_match")

    def test_p0_invalid_graph_blocks_receipts(self):
        self.bundle["inferences"][0]["rule_ids"] = ["rule.nonexistent"]
        self.assert_failed("P0:")

    def test_rights_gate_rejects_without_reading_restricted_file(self):
        # A restricted snapshot is never opened, even when the file is missing.
        self.manifest["sources"][0]["rights"]["status"] = "restricted"
        self.path.unlink()
        result = self.verify()
        self.assertFalse(result["valid"])
        self.assertEqual([], result["receipts"])
        self.assertTrue(any("rights not operator-cleared" in e for e in result["errors"]))
        self.assertFalse(any("not an existing regular file" in e for e in result["errors"]))

    def test_per_source_span_cap_blocks_excessive_locator_input(self):
        original = self.manifest["sources"][0]["spans"][0]
        self.manifest["sources"][0]["spans"] = [
            {"locator": f"line:{i}", "start_byte": original["start_byte"],
             "end_byte": original["end_byte"]} for i in range(1025)
        ]
        self.assert_failed("exceeds 1024 spans per source")

    def test_multiple_nonoverlapping_locators(self):
        # An additional quote must get a distinct, pinned byte range and receipt.
        text = "Preface"
        ev = dict(self.bundle["evidence"][0])
        ev["id"] = "ev.second"
        ev["excerpt"] = text
        ev["excerpt_sha256"] = sha(text.encode("utf-8"))
        ev["locator"] = "folio-0"
        self.bundle["evidence"].append(ev)
        self.manifest["sources"][0]["spans"].append({
            "locator": "folio-0", "start_byte": 0,
            "end_byte": len(text.encode("utf-8"))
        })
        result = self.verify()
        self.assertTrue(result["valid"], result)
        self.assertEqual(["ev.001", "ev.second"],
                         [receipt["evidence_id"] for receipt in result["receipts"]])

    def test_cli_valid_json_receipts_and_exit_codes(self):
        bundle_file = self.root / "bundle.json"
        manifest_file = self.root / "manifest.json"
        bundle_file.write_text(json.dumps(self.bundle), encoding="utf-8")
        manifest_file.write_text(json.dumps(self.manifest), encoding="utf-8")
        cmd = [sys.executable, "-m", "core.provenance",
               str(bundle_file), str(manifest_file), str(self.root), "--json"]
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        data = json.loads(result.stdout)
        self.assertTrue(data["valid"])
        self.assertEqual("operator_assertion_only", data["rights_assurance"])

        self.manifest["sources"][0]["rights"]["status"] = "unknown"
        manifest_file.write_text(json.dumps(self.manifest), encoding="utf-8")
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(1, result.returncode)
        self.assertIn("rights not operator-cleared", result.stderr)
        self.assertEqual("", result.stdout)

        manifest_file.unlink()
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(2, result.returncode)
        self.assertIn("INPUT_ERROR", result.stderr)

    def test_cli_malformed_json_input(self):
        bundle_file = self.root / "broken.json"
        bundle_file.write_text("{bad json", encoding="utf-8")
        manifest_file = self.root / "manifest.json"
        manifest_file.write_text(json.dumps(self.manifest), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-m", "core.provenance",
             str(bundle_file), str(manifest_file), str(self.root)],
            cwd=ROOT, capture_output=True, text=True
        )
        self.assertEqual(2, result.returncode)
        self.assertIn("INPUT_ERROR", result.stderr)


if __name__ == "__main__":
    unittest.main()
