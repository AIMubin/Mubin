import sqlite3
import tempfile
import unittest
from pathlib import Path
from corpus.audit_tafsir_crossverse import audit, heading_numbers, FLAGGED_TABARY


class CrossverseTests(unittest.TestCase):
    def test_header_extraction_only(self):
        self.assertEqual(heading_numbers("<br>القول في الآيات (10) و(11)<br>المتن (999)"), [10, 11])
        self.assertEqual(heading_numbers("<br>فقرة بدون عنوان"), [])

    def test_all_seven_candidates_in_synthetic_fixture(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "synthetic.sqlite"
            conn = sqlite3.connect(db)
            try:
                conn.execute("CREATE TABLE tafsirs(source TEXT,sura INT,aya INT,text TEXT)")
                for sura, aya in FLAGGED_TABARY:
                    conn.execute("INSERT INTO tafsirs VALUES('tabary',?,?,?)", (sura, aya, "<br>"))
                    conn.execute("INSERT INTO tafsirs VALUES('tabary',?,?,?)", (
                        sura, aya + 1, f"<br>القول في ({aya}) و({aya+1})<br>نص اصطناعي"))
                conn.commit()
            finally:
                conn.close()
            result = audit(db)
            self.assertEqual(result["rows_with_unique_adjacent_heading"], 7)
            self.assertTrue(all(len(row["adjacent_shared_heading_candidates"]) == 1
                                for row in result["records"]))
            self.assertFalse(result["source_text_mutated"])


if __name__ == "__main__":
    unittest.main()
