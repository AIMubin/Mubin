import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from corpus.query import get_ayah
from corpus.verify_quran import EXPECTED_COUNTS


class QueryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db = Path(self.directory.name) / "sample.db"
        connection = sqlite3.connect(self.db)
        try:
            connection.execute("CREATE TABLE verses(sura INTEGER,aya INTEGER,text TEXT)")
            connection.execute("CREATE TABLE tafsirs(source TEXT,sura INTEGER,aya INTEGER,text TEXT)")
            connection.execute("INSERT INTO verses VALUES (1,1,'SYNTHETIC NOT QURAN')")
            connection.executemany("INSERT INTO tafsirs VALUES (?,?,?,?)", [
                ('tabary', 1, 1, '<br>'), ('baghawy', 1, 1, 'س'*32767)])
            connection.commit()
        finally:
            connection.close()

    def tearDown(self):
        self.directory.cleanup()

    def test_provenance_flags(self):
        response = get_ayah(self.db, 1, 1)
        self.assertFalse(response["scholarly_verification"])
        self.assertEqual(response["text_classification"], "REFERENCE_REQUIRED_NO_QURAN_TEXT")
        self.assertIsNone(response["text"])
        tafsirs = {x['source_id']:x for x in response['tafsirs']}
        self.assertFalse(tafsirs['tabary']['displayable'])
        self.assertIsNone(tafsirs['tabary']['text'])
        self.assertIn('POSSIBLE_TRUNCATION_32767', tafsirs['baghawy']['quality_flags'])

    def test_reject_invalid_verse(self):
        with self.assertRaises(ValueError):
            get_ayah(self.db, 1, 8)

    def test_reference_override_requires_pinned_and_complete_witness(self):
        p = Path(self.directory.name)/'ref.txt'
        p.write_text(''.join(f'{s}|{a}|VERBATIM SYNTHETIC\n'
                             for s,n in enumerate(EXPECTED_COUNTS,1) for a in range(1,n+1)), encoding='utf-8')
        h=hashlib.sha256(p.read_bytes()).hexdigest()
        self.assertEqual(get_ayah(self.db,1,1,p,h)['text'], 'VERBATIM SYNTHETIC')
        self.assertIn('tanzil.net',get_ayah(self.db,1,1,p,h)['quran_text_attribution'])
        self.assertFalse(get_ayah(self.db,1,1,p,h)['scholarly_verification'])
        with self.assertRaises(ValueError): get_ayah(self.db,1,1,p,'a'*64)


if __name__ == '__main__': unittest.main()
