import sqlite3
import tempfile
import unittest
from pathlib import Path
from corpus.audit_tafsir_quality import audit, plaintext


class TafsirQualityTests(unittest.TestCase):
    def test_plaintext(self):
        self.assertEqual(plaintext('<br>'), '')
        self.assertEqual(plaintext('<p>نص</p>'), 'نص')

    def test_flags_with_synthetic_fixture(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / 'test.sqlite'
            conn = sqlite3.connect(db)
            try:
                conn.execute('CREATE TABLE tafsirs(source TEXT,sura INT,aya INT,text TEXT)')
                conn.executemany('INSERT INTO tafsirs VALUES(?,?,?,?)', [
                    ('tabary', 1, 1, '<br>'),
                    ('baghawy', 1, 1, 'س'*32767),
                    ('moyassar', 1, 1, 'نص واضح')])
                conn.commit()
            finally:
                conn.close()
            result = audit(db)
            self.assertEqual(result['status'], 'REQUIRES_EDITORIAL_REVIEW')
            self.assertEqual(len(result['review_queue']), 2)
            self.assertEqual(result['summary']['tabary']['markup_only'], 1)
            self.assertEqual(result['summary']['baghawy']['length_32767'], 1)


if __name__ == '__main__':
    unittest.main()
