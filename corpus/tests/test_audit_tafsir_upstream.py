import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from corpus.audit_tafsir_upstream import compare, FLAGGED
from corpus.verify_quran import EXPECTED_COUNTS

class UpstreamComparisonTests(unittest.TestCase):
    def test_verifies_all_rows_and_catches_any_import_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            original,linked=Path(temp)/"upstream.sqlite",Path(temp)/"linked.sqlite"
            a,b=sqlite3.connect(original),sqlite3.connect(linked)
            b.execute("CREATE TABLE tafsirs(source TEXT,sura INT,aya INT,text TEXT)")
            try:
                for name in ("tabary","katheer","baghawy","saadi","moyassar"):
                    a.execute(f"CREATE TABLE tafsir_{name}(sura INT,aya INT,tafsir TEXT)")
                    rows=[(s,aya,"<br>" if (s,aya) in FLAGGED.get(name,set()) else "SYNTHETIC")
                          for s,n in enumerate(EXPECTED_COUNTS,1) for aya in range(1,n+1)]
                    a.executemany(f"INSERT INTO tafsir_{name} VALUES(?,?,?)",rows)
                    b.executemany("INSERT INTO tafsirs VALUES(?,?,?,?)",
                                  ((name,s,aya,t) for s,aya,t in rows))
                a.commit()
                b.commit()
            finally:
                a.close()
                b.close()
            sha=hashlib.sha256(original.read_bytes()).hexdigest()
            report=compare(original,linked,sha)
            self.assertEqual(sum(v["identical_source_and_import_rows"] for v in report["tafsir_sources"].values()),31180)
            self.assertEqual(len(report["flagged_source_records"]),11)
            self.assertFalse(report["scholarly_verified"])
            with self.assertRaises(ValueError):
                compare(original,linked,"f"*64)
            # sqlite3.Connection.__exit__ only commits/rolls back; it does not
            # close the file handle. Explicit close is required on Windows.
            db = sqlite3.connect(linked)
            try:
                db.execute("UPDATE tafsirs SET text='CORRUPTED' WHERE source='tabary' AND sura=4 AND aya=168")
                db.commit()
            finally:
                db.close()
            with self.assertRaises(ValueError):
                compare(original,linked,sha)

if __name__=="__main__":
    unittest.main()
