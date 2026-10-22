"""Byte-fidelity section audit with fully synthetic, bounded Arabic text."""
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from engines.usul.source_snapshot_coverage import (
    SnapshotContractError, audit,
)

TEXT = "تقديم\nالأمر\nصيغة الأمر\nاختبار اصطناعي\nالنهي\nصيغة النهي\nخاتمة\n"
FIRST = "الأمر\nصيغة الأمر\nاختبار اصطناعي\n"
SECOND = "النهي\nصيغة النهي\n"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def manifest(raw=TEXT.encode("utf-8")):
    return {
        "schema_version": "0.1.0",
        "source_id": "pilot:tiny-snapshot",
        "work_title": "Synthetic Arabic section export",
        "author": "Mubin Test Fixture",
        "edition": "Synthetic test only",
        "source_url": "https://example.invalid/no-real-original",
        "locator": "test section bounds",
        "input_format": "UTF8_PLAINTEXT_EXPORT_V1",
        "transcription_provenance": "Synthetic fixture; no real-world provenance",
        "source_sha256": sha(raw),
        "source_size_bytes": len(raw),
        "sections": [
            {
                "id": "pilot:amr",
                "start_line": "الأمر",
                "end_line": "النهي",
                "section_sha256": sha(FIRST.encode("utf-8")),
                "expected_line_count": 3,
            },
            {
                "id": "pilot:nahy",
                "start_line": "النهي",
                "end_line": "خاتمة",
                "section_sha256": sha(SECOND.encode("utf-8")),
                "expected_line_count": 2,
            },
        ],
    }


class SnapshotCoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.source = self.dir / "private-source.txt"
        self.manifest = self.dir / "metadata.json"
        self.source.write_bytes(TEXT.encode("utf-8"))
        self.save_manifest(manifest())

    def save_manifest(self, data):
        self.manifest.write_bytes((json.dumps(data, ensure_ascii=False,
                         separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8"))
        self.pin = sha(self.manifest.read_bytes())

    def audited(self):
        return audit(self.source, self.manifest,
                     trusted_manifest_sha256=self.pin)

    def test_complete_coverage_and_metadata_without_copying_text(self):
        result = self.audited()
        self.assertEqual(result["status"], "SNAPSHOT_COVERAGE_PASS")
        self.assertEqual(result["sections_passed"], 2)
        self.assertEqual(result["total_source_lines"], 7)
        self.assertTrue(result["total_source_byte_partition_coverage"])
        self.assertEqual([v["line_count"] for v in result["sections"]], [3, 2])
        self.assertEqual(result["sections"][0]["section_sha256"], sha(FIRST.encode()))
        self.assertFalse(result["external_original_html_or_print_equivalence_verified"])
        self.assertFalse(result["scholarly_verified"])
        self.assertFalse(result["redistribution_approved"])
        self.assertFalse(result["source_text_reproduced"])
        self.assertNotIn("صيغة الأمر", json.dumps(result, ensure_ascii=False))
        self.assertEqual(result, self.audited())

    def test_snapshot_mutation_fails(self):
        # Keep byte count unchanged so this tests the digest gate, not size.
        self.source.write_bytes(self.source.read_bytes().replace(b"\n", b"!", 1))
        with self.assertRaisesRegex(SnapshotContractError, "SHA-256 mismatch"):
            self.audited()

    def test_newlines_are_not_silently_normalized(self):
        self.source.write_bytes(self.source.read_bytes().replace(b"\n", b"\r\n"))
        with self.assertRaises(SnapshotContractError):
            self.audited()

    def test_manifests_must_have_independently_pinned_digest(self):
        self.manifest.write_bytes(self.manifest.read_bytes() + b" ")
        with self.assertRaisesRegex(SnapshotContractError, "trust anchor"):
            self.audited()

    def test_invalid_manifest_claims_and_unknown_fields_are_rejected(self):
        for mutate in (
            lambda m: m.update({"unknown": True}),
            lambda m: m.update({"input_format": "RAW_HTML"}),
            lambda m: m.update({"source_size_bytes": "1"}),
            lambda m: m["sections"].append(copy.deepcopy(m["sections"][0])),
        ):
            value = manifest()
            mutate(value)
            self.save_manifest(value)
            with self.subTest(value=value), self.assertRaises(SnapshotContractError):
                self.audited()

    def test_duplicate_headings_refused_even_with_repinned_source(self):
        extra = ("الأمر\n" + TEXT).encode("utf-8")
        self.source.write_bytes(extra)
        value = manifest(extra)
        self.save_manifest(value)
        with self.assertRaisesRegex(SnapshotContractError, "ambiguous"):
            self.audited()

    def test_wrong_count_cannot_be_silently_passed(self):
        value = manifest()
        value["sections"][0]["expected_line_count"] = 2
        self.save_manifest(value)
        with self.assertRaisesRegex(SnapshotContractError, "count mismatch"):
            self.audited()

    def test_wrong_section_digest_with_valid_manifest_pin_still_fails(self):
        value = manifest()
        value["sections"][0]["section_sha256"] = "0" * 64
        self.save_manifest(value)
        with self.assertRaisesRegex(SnapshotContractError, "anchored section hash"):
            self.audited()

    def test_overlapping_ranges_are_refused(self):
        value = manifest()
        value["sections"][1]["start_line"] = "صيغة الأمر"
        value["sections"][1]["expected_line_count"] = 4
        value["sections"][1]["section_sha256"] = sha(
            "صيغة الأمر\nاختبار اصطناعي\nالنهي\nصيغة النهي\n".encode("utf-8")
        )
        self.save_manifest(value)
        with self.assertRaisesRegex(SnapshotContractError, "overlap"):
            self.audited()

    def test_missing_boundary_or_backward_ranges_fail(self):
        for start, end in (("unknown heading", "النهي"), ("النهي", "الأمر")):
            value = manifest()
            value["sections"][0]["start_line"] = start
            value["sections"][0]["end_line"] = end
            self.save_manifest(value)
            with self.subTest(start=start), self.assertRaises(SnapshotContractError):
                self.audited()

    def test_reject_binary_and_non_utf8(self):
        for data in (b"bad\x00file", b"bad\xff"):
            self.source.write_bytes(data)
            value = manifest(data)
            self.save_manifest(value)
            with self.subTest(data=data), self.assertRaises(SnapshotContractError):
                self.audited()

    def test_cli_produces_only_metadata_and_nonzero_for_missing(self):
        report = self.dir / "result.json"
        def run(snapshot):
            return subprocess.run(
                [sys.executable, "-m", "engines.usul.source_snapshot_coverage",
                 "--source", str(snapshot), "--manifest", str(self.manifest),
                 "--trusted-manifest-sha256", self.pin, "--report", str(report)],
                capture_output=True, text=True, check=False,
                cwd=Path(__file__).resolve().parents[3],
            )
        ok = run(self.source)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["status"],
                         "SNAPSHOT_COVERAGE_PASS")
        missing = run(self.dir / "not-present.txt")
        self.assertEqual(missing.returncode, 3)
        self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["status"],
                         "PENDING_SOURCE")
        self.assertTrue(ok.stdout.isascii())

    def test_safe_read_only_no_file_mutation(self):
        before = self.source.read_bytes()
        self.audited()
        self.assertEqual(before, self.source.read_bytes())


if __name__ == "__main__":
    unittest.main()
