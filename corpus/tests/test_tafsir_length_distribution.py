import sqlite3
import tempfile
import unittest
from pathlib import Path

from corpus.audit_tafsir_length_distribution import analyze


class LengthDistributionTests(unittest.TestCase):
    def test_detects_source_specific_ceiling_and_longer_others(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synthetic.sqlite"
            connection = sqlite3.connect(path)
            try:
                connection.execute("CREATE TABLE tafsirs(source TEXT, text TEXT)")
                for source in ("tabary", "katheer", "baghawy", "saadi", "moyassar"):
                    connection.execute("INSERT INTO tafsirs VALUES(?,?)",
                                       (source, "ت" * (32767 if source == "baghawy"
                                                       else 33001 if source == "tabary"
                                                       else 3)))
                connection.commit()
            finally:
                connection.close()
            report = analyze(path)
            self.assertTrue(report["baghawy_specific_32767_ceiling_observed"])
            self.assertEqual(report["summary"]["baghawy"]["boundary_counts"]["32767"], 1)
            self.assertEqual(report["summary"]["tabary"]["above_32767"], 1)
            self.assertFalse(report["scholarly_verified"])


if __name__ == "__main__":
    unittest.main()
