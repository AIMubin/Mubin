import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from corpus.triage_quran import classify, triage, REFERENCE_SHA256
from corpus.verify_quran import EXPECTED_COUNTS


class QuranTriageTests(unittest.TestCase):
    def test_diagnostic_categories(self):
        self.assertEqual(classify("بسم", "بسم"), "EXACT")
        self.assertEqual(classify("ا\u0654", "أ"), "UNICODE_CANONICAL_ONLY")
        self.assertEqual(classify("بسم  الله", "بسم الله"), "WHITESPACE_ONLY")
        self.assertEqual(classify("بسم", "بِسْم"), "COMBINING_MARKS_ONLY_CANDIDATE")
        self.assertEqual(classify("الرّحمن", "الرّحـمن"), "TATWEEL_OR_MARKS_CANDIDATE")
        self.assertEqual(classify("الدين", "الدار"), "TEXTUAL_REVIEW_REQUIRED")

    def test_realistic_full_synthetic_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database, reference = root / "test.db", root / "reference.txt"
            verses = [(s, a, "SYNTHETIC VERSE") for s, count in enumerate(EXPECTED_COUNTS, 1)
                      for a in range(1, count + 1)]
            conn = sqlite3.connect(database)
            try:
                conn.execute("CREATE TABLE verses(sura INT,aya INT,text TEXT)")
                conn.executemany("INSERT INTO verses VALUES(?,?,?)", verses)
                conn.commit()
            finally:
                conn.close()
            reference.write_text("".join(f"{s}|{a}|{text}\n" for s, a, text in verses), encoding="utf-8")
            digest = hashlib.sha256(reference.read_bytes()).hexdigest()
            result = triage(database, reference, digest)
            self.assertEqual(result["class_counts"]["EXACT"], 6236)
            self.assertFalse(result["canonical_quran_verified"])
            self.assertEqual(result["details_without_verse_text"], [])
            with self.assertRaises(ValueError): triage(database, reference, REFERENCE_SHA256)


if __name__ == "__main__":
    unittest.main()
