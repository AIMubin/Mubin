import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from corpus.local_vault import capture, mirror, restore, verify_snapshot, locate, PIN
from corpus.verify_quran import EXPECTED_COUNTS


class VaultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)
        self.incoming = self.dir / "incoming"
        self.incoming.mkdir()
        self.vault = self.dir / "vault"
        (self.incoming / "linked").mkdir()
        conn = sqlite3.connect(self.incoming / "linked/quran_tafsir.db")
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.executescript("""CREATE TABLE verses(sura INTEGER,aya INTEGER,text TEXT,PRIMARY KEY(sura,aya));
            CREATE TABLE tafsirs(source TEXT,sura INTEGER,aya INTEGER,text TEXT,
                PRIMARY KEY(source,sura,aya),FOREIGN KEY(sura,aya) REFERENCES verses(sura,aya));""")
            verses = [(s, a, "SYNTHETIC NOT SCRIPTURE") for s, count in enumerate(EXPECTED_COUNTS, 1)
                      for a in range(1, count + 1)]
            conn.executemany("INSERT INTO verses VALUES (?,?,?)", verses)
            for name in ("tabary", "katheer", "baghawy", "saadi", "moyassar"):
                conn.executemany("INSERT INTO tafsirs VALUES (?,?,?,?)",
                                 ((name, s, a, "SYNTHETIC NOT TAFSIR") for s, a, _ in verses))
            conn.commit()
        finally:
            conn.close()
        blob = self.incoming / "linked/quran_tafsir.db"
        sha = hashlib.sha256(blob.read_bytes()).hexdigest()
        (self.incoming / "reports").mkdir()
        (self.incoming / "reports/import-manifest.json").write_text(json.dumps({
            "source_sha256": PIN, "output_sha256": sha, "verses": 6236,
            "tafsirs": {name: {"nonempty": 6236} for name in
                        ("tabary", "katheer", "baghawy", "saadi", "moyassar")}}))
        (self.incoming / "reports/audit-report.json").write_text(json.dumps({
            "sha256": sha, "structural_audit_passed": True}))

    def tearDown(self):
        self.temp.cleanup()

    def test_capture_verify_restore(self):
        result = capture(self.incoming, self.vault, "123", allow_missing_source=True)
        manifest = verify_snapshot(result)
        self.assertEqual(manifest["backup_status"], "PARTIAL_NO_UPSTREAM_ORIGINAL")
        self.assertFalse(manifest["canonical_quran_verified"])
        with self.assertRaises(FileExistsError):
            capture(self.incoming, self.vault, "123", allow_missing_source=True)
        restored = restore(self.vault, "123", self.dir / "recovery")
        self.assertTrue((restored / "linked/quran_tafsir.db").is_file())

    def test_corruption_and_distinct_mirror(self):
        snap = capture(self.incoming, self.vault, "234", allow_missing_source=True)
        copy = mirror(self.vault, "234", self.dir / "disk2")
        self.assertEqual(verify_snapshot(copy)["run_id"], "234")
        with open(snap / "reports/audit-report.json", "ab") as f:
            f.write(b"MUTATED")
        with self.assertRaisesRegex(ValueError, "Corrupt"):
            verify_snapshot(snap)

    def test_requires_original_unless_opt_in(self):
        with self.assertRaisesRegex(ValueError, "Full backup requires"):
            capture(self.incoming, self.vault, "345")

    def test_duplicate_artifact_manifest_deduplicates_identical_only(self):
        one = self.incoming / "reports/import-manifest.json"
        duplicate = self.incoming / "copy/import-manifest.json"
        duplicate.parent.mkdir()
        duplicate.write_bytes(one.read_bytes())
        self.assertEqual(locate(self.incoming, "import-manifest.json").read_bytes(), one.read_bytes())
        duplicate.write_text("DIFFERENT", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            locate(self.incoming, "import-manifest.json")


if __name__ == "__main__":
    unittest.main()
