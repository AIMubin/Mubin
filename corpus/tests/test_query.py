import sqlite3
import tempfile
import unittest
from pathlib import Path
from corpus.query import get_ayah

class QueryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db = Path(self.directory.name) / "sample.db"
        with sqlite3.connect(self.db) as db:
            db.execute("CREATE TABLE verses(sura INTEGER,aya INTEGER,text TEXT)")
            db.execute("CREATE TABLE tafsirs(source TEXT,sura INTEGER,aya INTEGER,text TEXT)")
            db.execute("INSERT INTO verses VALUES (1,1,'SYNTHETIC NOT QURAN')")
            db.execute("INSERT INTO tafsirs VALUES ('tabary',1,1,'SYNTHETIC NOT TAFSIR')")
    def tearDown(self):
        self.directory.cleanup()
    def test_provenance_flags(self):
        response = get_ayah(self.db,1,1)
        self.assertFalse(response["scholarly_verification"])
        self.assertIn("DERIVED",response["text_classification"])
        self.assertEqual(response["tafsirs"][0]["source_id"],"tabary")
        self.assertFalse(response["tafsirs"][0]["scholarly_verification"])
    def test_reject_invalid_verse(self):
        with self.assertRaises(ValueError):
            get_ayah(self.db,1,8)
    def test_reject_missing(self):
        with self.assertRaises(ValueError):
            get_ayah(self.db,1,2)
if __name__=="__main__":
    unittest.main()
