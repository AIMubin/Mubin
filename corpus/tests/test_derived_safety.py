import sqlite3
import tempfile
import unittest
from pathlib import Path
from corpus.audit_quran_derived import audit
from corpus.query import get_ayah
from corpus.verify_quran import EXPECTED_COUNTS

class DerivedSafetyTests(unittest.TestCase):
    def test_slash_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/"test.sqlite"
            conn=sqlite3.connect(p)
            try:
                conn.execute("CREATE TABLE verses(sura INT,aya INT,text TEXT)")
                conn.executemany("INSERT INTO verses VALUES(?,?,?)",
                    [(s,a,"يا/أيها" if (s,a)==(2,21) else "SYNTHETIC")
                     for s,n in enumerate(EXPECTED_COUNTS,1) for a in range(1,n+1)])
                conn.commit()
            finally:
                conn.close()
            result=audit(p)
            self.assertEqual(result["slash_marked_verse_count"],1)
            self.assertIn("2:21",result["slash_marked_verse_ids"])
            self.assertFalse(result["quran_text_safe_to_display_as_canonical"])

    def test_no_quran_text_without_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/"test.sqlite"
            conn=sqlite3.connect(p)
            try:
                conn.execute("CREATE TABLE verses(sura INT,aya INT,text TEXT)")
                conn.execute("CREATE TABLE tafsirs(source TEXT,sura INT,aya INT,text TEXT)")
                conn.execute("INSERT INTO verses VALUES(1,1,'SYNTHETIC')")
                conn.execute("INSERT INTO tafsirs VALUES('tabary',1,1,'<b>text</b>')")
                conn.commit()
            finally:
                conn.close()
            result=get_ayah(p,1,1)
            self.assertIsNone(result["text"])
            self.assertEqual(result["text_classification"],"REFERENCE_REQUIRED_NO_QURAN_TEXT")
            self.assertEqual(result["tafsirs"][0]["display_text"],"text")
            opt_in=get_ayah(p,1,1,allow_unverified_derived_text=True)
            self.assertEqual(opt_in["text"],"SYNTHETIC")
            self.assertIn("NOT_CANONICALLY_VERIFIED",opt_in["text_classification"])

if __name__=="__main__":
    unittest.main()
