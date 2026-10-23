"""Synthetic private-file E2E tests for W1 unassessed definitions intake."""
import copy
import hashlib
import hmac
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from engines.usul.concept_definitions import build_definitions
from engines.usul.concept_rule_catalog import CatalogError, canonical, sha
from engines.usul.pilots.waraqat_definition_private_intake import (
    BASIS_PIN, REPO_ROOT, _private_path, prepare_private_manifest, main,
)

RECEIPT_PATH = REPO_ROOT / "corpus/reviews/u02-waraqat-private-source-acceptance-PASS.json"


class PrivateWaraqatDefinitionIntakeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.files = {
            "w1-amr.txt": "مصطلح اصطناعي للأمر للاختبار فقط",
            "w1-qarinah.txt": "مصطلح اصطناعي للقرينة للاختبار فقط",
            "w1-wujub.txt": "مصطلح اصطناعي للوجوب للاختبار فقط",
            "research-amr.txt": "صياغة اصطناعية بحثية غير معتمدة",
        }
        for name, text in self.files.items():
            (self.root / name).write_text(text, encoding="utf-8")
        self.key = bytes(range(32))
        self.receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        self.intake = {
            "schema_version": "u02-private-intake/0.1.0",
            "commitment_key_id": "key:private-waraqat-2026",
            "definition_files": [
                {"id": "definition:amr-local", "concept_id": "concept:amr-term",
                 "version": "0.1.0", "private_text_file": "w1-amr.txt"},
                {"id": "definition:qarinah-local",
                 "concept_id": "concept:qarinah-candidate",
                 "version": "0.1.0", "private_text_file": "w1-qarinah.txt"},
                {"id": "definition:wujub-local",
                 "concept_id": "concept:wujub-candidate",
                 "version": "0.1.0", "private_text_file": "w1-wujub.txt"},
            ],
            "interpretation_files": [
                {"id": "interpretation:amr-local",
                 "concept_id": "concept:amr-term",
                 "version": "0.1.0",
                 "definition_candidate_ids": ["definition:amr-local"],
                 "private_text_file": "research-amr.txt"},
            ],
        }

    def run_build(self):
        return prepare_private_manifest(
            self.receipt, self.intake, self.root, self.key)

    def test_complete_private_files_to_metadata_contract(self):
        manifest, report = self.run_build()
        self.assertEqual(report["status"], "U02_DEFINITION_METADATA_CANDIDATES_PASS")
        self.assertEqual(manifest["schema_version"],
                         "u02-concept-definitions/0.1.1")
        self.assertEqual((report["definition_candidate_count"],
                          report["interpretation_candidate_count"]), (3, 1))
        self.assertEqual(report, build_definitions(self.receipt, BASIS_PIN, manifest))
        self.assertEqual((manifest, report), self.run_build())
        self.assertEqual(
            manifest["definition_candidates"][0]["commitment_scheme"],
            "HMAC_SHA256_PRIVATE")
        for row in manifest["definition_candidates"]:
            self.assertEqual(row["commitment_key_id"], "key:private-waraqat-2026")
            self.assertEqual(row["review_status"], "UNASSESSED")
            self.assertFalse(row["source_text_included"])
            self.assertEqual(row["claimed_author_id"], "author:unassessed")
        serialized = json.dumps(manifest, ensure_ascii=False)
        for sensitive in list(self.files.values()) + [str(self.root), self.key.hex()]:
            self.assertNotIn(sensitive, serialized)
        self.assertFalse(report["scholarly_verified"])
        self.assertFalse(report["source_support_attested"])
        self.assertFalse(report["public_fatwa_authorized"])

    def test_commitments_exactly_match_private_bytes_using_independent_hmac(self):
        manifest, _ = self.run_build()
        for row, src in zip(manifest["definition_candidates"], [
                "w1-amr.txt", "w1-qarinah.txt", "w1-wujub.txt"]):
            expected = hmac.new(self.key, (self.root / src).read_bytes(),
                                hashlib.sha256).hexdigest()
            self.assertEqual(row["definition_commitment_sha256"], expected)

    def test_reject_private_excerpt_embedded_in_input_metadata(self):
        self.intake["definition_files"][0]["definition"] = "مصدر خاص"
        with self.assertRaisesRegex(CatalogError,
                                    "PRIVATE_DEFINITION_INTAKE_FIELDS_INVALID"):
            self.run_build()

    def test_reject_false_scholarly_promotion_in_private_intake(self):
        self.intake["definition_files"][0]["scholarly_verified"] = True
        with self.assertRaisesRegex(CatalogError,
                                    "PRIVATE_DEFINITION_INTAKE_FIELDS_INVALID"):
            self.run_build()

    def test_reject_unknown_concept(self):
        self.intake["definition_files"][0]["concept_id"] = "concept:not-receipted"
        with self.assertRaisesRegex(CatalogError,
                                    "PRIVATE_DEFINITION_INTAKE_REF_INVALID"):
            self.run_build()

    def test_reject_interpretation_across_unrelated_concept(self):
        self.intake["interpretation_files"][0]["concept_id"] = (
            "concept:wujub-candidate")
        with self.assertRaisesRegex(CatalogError,
                                    "PRIVATE_INTERPRETATION_CROSS_CONCEPT_INVALID"):
            self.run_build()

    def test_no_definition_promoted_by_invalid_version(self):
        self.intake["definition_files"][0]["version"] = "verified"
        with self.assertRaisesRegex(CatalogError,
                                    "DEFINITION_ATTRIBUTION_OR_STATUS_INVALID"):
            self.run_build()

    def test_reject_repeated_same_private_file(self):
        self.intake["definition_files"][1]["private_text_file"] = "w1-amr.txt"
        with self.assertRaisesRegex(CatalogError, "PRIVATE_TEXT_FILE_REUSED"):
            self.run_build()

    def test_reject_parent_traversal(self):
        with self.assertRaisesRegex(CatalogError, "PRIVATE_RELATIVE_PATH_INVALID"):
            _private_path(self.root, "../leak.txt")

    def test_reject_absolute_private_path(self):
        with self.assertRaisesRegex(CatalogError, "PRIVATE_RELATIVE_PATH_INVALID"):
            _private_path(self.root, str(self.root / "w1-amr.txt"))

    def test_symlink_escape_refused(self):
        with tempfile.TemporaryDirectory() as external:
            outside = Path(external) / "outside.txt"
            outside.write_text("synthetic secret outside private root",
                               encoding="utf-8")
            link = self.root / "escape.txt"
            try:
                link.symlink_to(outside)
            except OSError:
                self.skipTest("Symlink creation unavailable")
            with self.assertRaisesRegex(CatalogError, "PRIVATE_PATH_OUTSIDE_ROOT"):
                _private_path(self.root, "escape.txt")

    def test_symlink_loop_rejected_without_private_path_leak(self):
        loop = self.root / "sensitive-symlink-loop.txt"
        try:
            loop.symlink_to(loop)
        except (OSError, RuntimeError):
            self.skipTest("Local OS does not support symlink loop fixture")
        with self.assertRaisesRegex(CatalogError, "PRIVATE_PATH_RESOLUTION_REJECTED") as error:
            _private_path(self.root, loop.name)
        self.assertNotIn(str(self.root), str(error.exception))
        self.assertNotIn(loop.name, str(error.exception))

    def test_cli_symlink_loop_fails_privacy_safely(self):
        loop = self.root / "restricted-source-file-loop.txt"
        try:
            loop.symlink_to(loop)
        except (OSError, RuntimeError):
            self.skipTest("Local OS does not support symlink loop fixture")
        self.intake["definition_files"][0]["private_text_file"] = loop.name
        (self.root / "intake.json").write_text(
            json.dumps(self.intake), encoding="utf-8")
        env = dict(os.environ)
        env["MUBIN_PRIVATE_HMAC_KEY_HEX"] = self.key.hex()
        r = subprocess.run([
            sys.executable, "-m",
            "engines.usul.pilots.waraqat_definition_private_intake",
            "--private-root", str(self.root),
            "--private-intake", "intake.json",
            "--output-manifest", "definitions-metadata.json",
            "--output-report", "definitions-report.json",
        ], cwd=REPO_ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertEqual(json.loads(r.stdout)["status"],
                         "PRIVATE_DEFINITION_INTAKE_REJECTED")
        self.assertNotIn("Traceback", r.stderr)
        self.assertNotIn(str(self.root), r.stdout + r.stderr)
        self.assertNotIn(loop.name, r.stdout + r.stderr)
        self.assertFalse((self.root / "definitions-metadata.json").exists())
        self.assertFalse((self.root / "definitions-report.json").exists())

    def test_cli_emitted_report_digest_covers_intake_specific_fields(self):
        (self.root / "intake.json").write_text(
            json.dumps(self.intake), encoding="utf-8")
        env = dict(os.environ)
        env["MUBIN_PRIVATE_HMAC_KEY_HEX"] = self.key.hex()
        r = subprocess.run([
            sys.executable, "-m",
            "engines.usul.pilots.waraqat_definition_private_intake",
            "--private-root", str(self.root),
            "--private-intake", "intake.json",
            "--output-manifest", "defs.json",
            "--output-report", "report.json",
        ], cwd=REPO_ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        final = json.loads((self.root / "report.json").read_text(encoding="utf-8"))
        full_payload = {key: value for key, value in final.items()
                        if key != "report_sha256"}
        self.assertEqual(final["report_sha256"], sha(canonical(full_payload)))
        self.assertEqual(final["definition_validation_report_sha256"],
                         self.run_build()[1]["report_sha256"])
        self.assertTrue(final["operator_intake_status"].endswith("UNASSESSED"))
        modified = dict(final)
        modified["private_text_attested_as_source_quotation"] = True
        modified.pop("report_sha256")
        self.assertNotEqual(final["report_sha256"], sha(canonical(modified)))

    def test_wrong_receipt_cannot_forge_candidate_provenance(self):
        self.receipt["stage08_graph_sha256"] = "0"*64
        with self.assertRaisesRegex(CatalogError,
                                    "RECEIPT_CANONICAL_DIGEST_MISMATCH"):
            self.run_build()

    def test_cli_produces_only_metadata_in_offrepo_directory(self):
        (self.root / "intake.json").write_text(
            json.dumps(self.intake), encoding="utf-8")
        env = dict(os.environ)
        env["MUBIN_PRIVATE_HMAC_KEY_HEX"] = self.key.hex()
        r = subprocess.run([
            sys.executable, "-m",
            "engines.usul.pilots.waraqat_definition_private_intake",
            "--private-root", str(self.root),
            "--private-intake", "intake.json",
            "--output-manifest", "definitions-metadata.json",
            "--output-report", "definitions-report.json",
        ], cwd=REPO_ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["status"], "PRIVATE_CANDIDATES_PREPARED_UNASSESSED")
        public = self.root / "definitions-metadata.json"
        report = self.root / "definitions-report.json"
        self.assertTrue(public.is_file())
        self.assertTrue(report.is_file())
        data = json.loads(public.read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"],
                         "u02-concept-definitions/0.1.1")
        self.assertEqual(data["definition_candidates"][0]["commitment_scheme"],
                         "HMAC_SHA256_PRIVATE")
        combined = r.stdout + report.read_text(encoding="utf-8") + public.read_text(encoding="utf-8")
        for value in list(self.files.values())+[str(self.root), self.key.hex()]:
            self.assertNotIn(value, combined)
        self.assertEqual(json.loads(report.read_text(encoding="utf-8"))[
            "operator_intake_status"], "PRIVATE_CANDIDATES_PREPARED_UNASSESSED")

    def test_cli_rejects_output_collision_without_overwriting_original(self):
        (self.root / "intake.json").write_text(
            json.dumps(self.intake), encoding="utf-8")
        env = dict(os.environ)
        env["MUBIN_PRIVATE_HMAC_KEY_HEX"] = self.key.hex()
        r = subprocess.run([
            sys.executable, "-m",
            "engines.usul.pilots.waraqat_definition_private_intake",
            "--private-root", str(self.root),
            "--private-intake", "intake.json",
            "--output-manifest", "intake.json",
            "--output-report", "report.json",
        ], cwd=REPO_ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(json.loads(r.stdout)["status"],
                         "PRIVATE_DEFINITION_INTAKE_REJECTED")
        self.assertFalse((self.root/"report.json").exists())

    def test_cli_requires_hmac_key_and_never_writes_files_if_missing(self):
        (self.root / "intake.json").write_text(
            json.dumps(self.intake), encoding="utf-8")
        env = dict(os.environ)
        env.pop("MUBIN_PRIVATE_HMAC_KEY_HEX", None)
        r = subprocess.run([
            sys.executable, "-m",
            "engines.usul.pilots.waraqat_definition_private_intake",
            "--private-root", str(self.root),
            "--private-intake", "intake.json",
            "--output-manifest", "definitions-metadata.json",
            "--output-report", "definitions-report.json",
        ], cwd=REPO_ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("w1-amr.txt", r.stdout+r.stderr)
        self.assertFalse((self.root / "definitions-metadata.json").exists())


    def test_two_output_second_publish_failure_leaves_no_partial_receipt(self):
        # Synthetic local private text only. Real Stage09/P0 evidence unused.
        self.intake_path = self.root / "intake.json"
        self.intake_path.write_text(json.dumps(self.intake), encoding="utf-8")
        args = ["--private-root", str(self.root), "--private-intake", "intake.json",
                "--output-manifest", "defs.json",
                "--output-report", "receipt.json"]
        before = {name: (self.root / name).read_bytes() for name in self.files}
        real_link = os.link
        calls = []

        def fail_second(src, dst, *a, **kw):
            calls.append(str(dst))
            if len(calls) == 2:
                raise OSError("synthetic second-publication failure")
            return real_link(src, dst, *a, **kw)

        with patch.dict(os.environ, {"MUBIN_PRIVATE_HMAC_KEY_HEX": self.key.hex()}):
            with patch("engines.usul.pilots.waraqat_definition_private_intake.os.link",
                       side_effect=fail_second):
                self.assertEqual(main(args), 2)
        self.assertEqual(len(calls), 2)
        self.assertFalse((self.root / "defs.json").exists())
        self.assertFalse((self.root / "receipt.json").exists())
        self.assertEqual(list(self.root.glob(".private-definition-*.tmp")), [])
        for name, data in before.items():
            self.assertEqual((self.root / name).read_bytes(), data)

    def test_race_collision_does_not_overwrite_unrelated_report(self):
        (self.root / "intake.json").write_text(json.dumps(self.intake),
                                                encoding="utf-8")
        args = ["--private-root", str(self.root), "--private-intake", "intake.json",
                "--output-manifest", "defs.json",
                "--output-report", "receipt.json"]
        report = self.root / "receipt.json"
        real_link = os.link
        count = 0

        def appear_before_second(src, dst, *a, **kw):
            nonlocal count
            count += 1
            if count == 2:
                report.write_bytes(b"PREEXISTING_UNRELATED_PRIVATE_FILE")
            return real_link(src, dst, *a, **kw)

        with patch.dict(os.environ, {"MUBIN_PRIVATE_HMAC_KEY_HEX": self.key.hex()}):
            with patch("engines.usul.pilots.waraqat_definition_private_intake.os.link",
                       side_effect=appear_before_second):
                self.assertEqual(main(args), 2)
        self.assertEqual(report.read_bytes(), b"PREEXISTING_UNRELATED_PRIVATE_FILE")
        self.assertFalse((self.root / "defs.json").exists())
        self.assertEqual(list(self.root.glob(".private-definition-*.tmp")), [])

    def test_success_pair_is_complete_and_cannot_be_replaced(self):
        (self.root / "intake.json").write_text(json.dumps(self.intake),
                                                encoding="utf-8")
        args = ["--private-root", str(self.root), "--private-intake", "intake.json",
                "--output-manifest", "defs.json",
                "--output-report", "receipt.json"]
        with patch.dict(os.environ, {"MUBIN_PRIVATE_HMAC_KEY_HEX": self.key.hex()}):
            self.assertEqual(main(args), 0)
            original = [(self.root / file).read_bytes()
                        for file in ("defs.json", "receipt.json")]
            self.assertEqual(main(args), 2)
        self.assertEqual(original, [(self.root / file).read_bytes()
                                   for file in ("defs.json", "receipt.json")])
        self.assertEqual(list(self.root.glob(".private-definition-*.tmp")), [])
        receipt = json.loads(original[1].decode("utf-8"))
        payload = {key: val for key, val in receipt.items() if key != "report_sha256"}
        self.assertEqual(receipt["report_sha256"], sha(canonical(payload)))
        self.assertFalse(receipt["scholarly_verified"])


if __name__ == "__main__":
    unittest.main()
