import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from corpus.q03_engineering_gate import replay
from corpus.verify_quran import EXPECTED_COUNTS


def digest(file):
    h = hashlib.sha256()
    with open(file, "rb") as fd:
        for b in iter(lambda: fd.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


class Q03EngineeringReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.temp.name)
        cls.linked = cls.base / "linked.sqlite"
        cls.orig = cls.base / "original.sqlite"
        data = [(s, a) for s, n in enumerate(EXPECTED_COUNTS, 1) for a in range(1, n + 1)]
        flagged_b = {(4, 43), (17, 4), (18, 10), (33, 9)}
        flagged_t = {(4, 168), (26, 16), (26, 205), (37, 25),
                     (37, 62), (37, 103), (50, 13)}
        linked = sqlite3.connect(cls.linked)
        source = sqlite3.connect(cls.orig)
        try:
            linked.execute("CREATE TABLE verses(sura INT, aya INT, text TEXT, PRIMARY KEY(sura,aya))")
            linked.execute("CREATE TABLE tafsirs(source TEXT,sura INT,aya INT,text TEXT,"
                           "PRIMARY KEY(source,sura,aya))")
            linked.executemany("INSERT INTO verses VALUES(?,?,?)",
                               [(s, a, "SYNTHETIC " + ("/" * (2 if i < 7 else 1 if i < 364 else 0)))
                                for i, (s, a) in enumerate(data)])
            for name in ("baghawy", "tabary", "katheer", "saadi", "moyassar"):
                source.execute(f"CREATE TABLE tafsir_{name}(sura INT,aya INT,tafsir TEXT)")
                rows = [(s, a,
                         "ش" * 32767 if name == "baghawy" and (s, a) in flagged_b
                         else "<br>" if name == "tabary" and (s, a) in flagged_t
                         else "SYNTHETIC TAfsir, not a publication")
                        for (s, a) in data]
                source.executemany(f"INSERT INTO tafsir_{name} VALUES(?,?,?)", rows)
                linked.executemany("INSERT INTO tafsirs VALUES(?,?,?,?)",
                                   [(name, s, a, t) for (s, a, t) in rows])
            source.commit()
            linked.commit()
        finally:
            source.close()
            linked.close()
        cls.linked_sha = digest(cls.linked)
        cls.orig_sha = digest(cls.orig)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_replay(self, original=None, linked_sha=None, source_sha=None):
        return replay(
            self.linked, original,
            linked_sha256=self.linked_sha if linked_sha is None else linked_sha,
            source_sha256=self.orig_sha if source_sha is None else source_sha,
        )

    def test_complete_replay_on_synthetic_upstream(self):
        result = self.run_replay(self.orig)
        self.assertEqual(result["status"], "DATA_REPLAY_PASS", result["checks"])
        self.assertTrue(result["engineering_data_gate_passed"])
        self.assertFalse(result["engineering_milestone_qualified_by_this_tool"])
        self.assertEqual(len(result["checks_passed"]), result["check_count"])
        self.assertFalse(result["canonical_quran_verified"])
        self.assertFalse(result["redistribution_approved"])

    def test_missing_source_remains_pending_not_pass(self):
        result = self.run_replay()
        self.assertEqual(result["status"], "PENDING_UPSTREAM")
        self.assertFalse(result["engineering_data_gate_passed"])
        self.assertEqual(result["checks_pending"], ["upstream_verbatim_comparison"])

    def test_source_hash_mismatch_fails(self):
        result = self.run_replay(self.orig, source_sha="0" * 64)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("upstream_verbatim_comparison", result["checks_failed"])

    def test_linked_hash_mismatch_fails_before_read(self):
        result = self.run_replay(self.orig, linked_sha="0" * 64)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("pinned_linked_database", result["checks_failed"])

    def test_upstream_row_difference_is_detected(self):
        altered = self.base / "altered.sqlite"
        with open(self.orig, "rb") as source, open(altered, "wb") as dest:
            for block in iter(lambda: source.read(1 << 20), b""):
                dest.write(block)
        db = sqlite3.connect(altered)
        try:
            db.execute("UPDATE tafsir_saadi SET tafsir='CHANGED' WHERE sura=2 AND aya=21")
            db.commit()
        finally:
            db.close()
        result = self.run_replay(altered, source_sha=digest(altered))
        self.assertIn("upstream_verbatim_comparison", result["checks_failed"])


if __name__ == "__main__":
    unittest.main()
