"""Prospective tracked-tree and historical redaction checks use synthetic text only."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from qa.publication_guard import (
    WITNESS_PATH, _has_unredacted_witness_field, history_summary,
    path_violation, scan_tip,
)


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class PublicationGuardTests(unittest.TestCase):
    def test_denies_sensitive_tracked_paths_but_not_ordinary_code(self):
        for path in (
            "corpus-data/raw-source.txt", "operator-vault/witness.dat",
            "local/.env", "local/.env.production", "keys/host.pem",
            "keys/id_ed25519", "storage/corpus.db", "storage/cache.db-wal",
            "data/corpus.parquet", "private/accounts.json",
        ):
            with self.subTest(path=path):
                self.assertIsNotNone(path_violation(path))
        for path in ("docs/preview-data.json", "corpus/registry.py",
                     "engines/hadith/qualification/H3.9.2/benchmarks/README.md",
                     "docs/.env.example", "qa/publication_guard.py"):
            with self.subTest(path=path):
                self.assertIsNone(path_violation(path))

    def test_unredacted_historical_marker_is_structural_only(self):
        original = {"negative_control": {
            "shared_span_containment_check": {
                "shared_span_folded": "SYNTHETIC_ONLY_EXCERPT"}}}
        redacted = {"negative_control": {
            "shared_span_containment_check": {
                "shared_span_folded_sha256": "0" * 64,
                "shared_span_folded_codepoints": 22}}}
        self.assertTrue(_has_unredacted_witness_field(original))
        self.assertFalse(_has_unredacted_witness_field(redacted))

    def test_history_reports_old_version_without_publishing_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git(root, "init", "-q")
            git(root, "config", "user.email", "test@example.invalid")
            git(root, "config", "user.name", "Synthetic Test")
            source = root / WITNESS_PATH
            source.parent.mkdir(parents=True)
            source.write_text(json.dumps({"shared_span_folded":
                                         "SYNTHETIC_ONLY_EXCERPT"}), encoding="utf-8")
            git(root, "add", WITNESS_PATH)
            git(root, "commit", "-qm", "synthetic old excerpt")
            source.write_text(json.dumps({"shared_span_folded_sha256": "0" * 64}),
                              encoding="utf-8")
            git(root, "add", WITNESS_PATH)
            git(root, "commit", "-qm", "synthetic redaction")
            self.assertEqual(scan_tip(root)["status"], "PASS")
            audit = history_summary(root)
            self.assertEqual(audit["historical_unredacted_versions_found"], 1)
            self.assertEqual(audit["witness_versions_examined"], 2)
            self.assertFalse(audit["historical_eradication_verified"])
            self.assertNotIn("SYNTHETIC_ONLY_EXCERPT", json.dumps(audit))
            (root / "local").mkdir()
            (root / "local/.env").write_text("SYNTHETIC_ONLY_SECRET", encoding="utf-8")
            git(root, "add", "-f", "local/.env")
            failed = scan_tip(root)
            self.assertEqual(failed["status"], "FAIL")
            self.assertTrue(any(x["code"] == "ENVIRONMENT_CREDENTIALS_TRACKED"
                                for x in failed["violations"]))
            self.assertNotIn("SYNTHETIC_ONLY_SECRET", json.dumps(failed))
            self.assertNotIn("local/.env", json.dumps(failed))


if __name__ == "__main__":
    unittest.main()
