import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from corpus.verify_evidence_package import EvidencePackageError, verify_package


class EvidencePackageTests(unittest.TestCase):
    def build(self, dest, payload=b"synthetic-test", bad=False, dup=False):
        manifest = {
            "files": [{
                "path": "proof/page.png",
                "sha256": "0" * 64 if bad else hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload) - 1 if bad else len(payload),
            }]
        }
        with zipfile.ZipFile(dest, "w") as z:
            z.writestr("proof\\page.png", payload)
            z.writestr("sha256-manifest.json", json.dumps(manifest))
            if dup:
                z.writestr("proof/page.png", payload)

    def test_windows_paths_and_manifest_self_omission(self):
        with tempfile.TemporaryDirectory() as d:
            zip_path = Path(d) / "synthetic.zip"
            self.build(zip_path)
            result = verify_package(zip_path)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["zip_file_count"], 2)
            self.assertEqual(result["manifest_listed_files"], 1)
            self.assertEqual(result["verified_member_count"], 1)

    def test_hash_size_corruption_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            zip_path = Path(d) / "synthetic.zip"
            self.build(zip_path, bad=True)
            result = verify_package(zip_path)
            self.assertEqual(result["status"], "FAIL")
            self.assertTrue(any(s.startswith("HASH_MISMATCH:") for s in result["errors"]))
            self.assertTrue(any(s.startswith("SIZE_MISMATCH:") for s in result["errors"]))

    def test_duplicate_normalized_members_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            zip_path = Path(d) / "synthetic.zip"
            self.build(zip_path, dup=True)
            with self.assertRaises(EvidencePackageError):
                verify_package(zip_path)


if __name__ == "__main__":
    unittest.main()
