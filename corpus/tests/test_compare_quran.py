import sqlite3,tempfile,unittest
from pathlib import Path
from corpus.compare_quran import compare,witness

class ComparisonTests(unittest.TestCase):
    def test_duplicate_ref_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"w.txt"
            p.write_text("1|1|A\\n1|1|B\\n",encoding="utf-8")
            with self.assertRaises(ValueError): witness(p)
    def test_partial_ref_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"w.txt"; q=Path(d)/"db.sqlite"
            p.write_text("1|1|A\\n",encoding="utf-8")
            with sqlite3.connect(q) as con:
                con.execute("CREATE TABLE verses(sura INT,aya INT,text TEXT)")
                con.execute("INSERT INTO verses VALUES(1,1,'A')")
            with self.assertRaises(ValueError): compare(q,p)
if __name__=="__main__":unittest.main()
