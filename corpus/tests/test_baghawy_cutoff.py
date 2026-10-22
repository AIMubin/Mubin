import sqlite3
import tempfile
import unittest
from pathlib import Path

from corpus.audit_baghawy_cutoff import diagnostic_letters, inspect_cutoff


class BaghawyCutoffTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "synthetic.sqlite"
        conn = sqlite3.connect(self.path)
        try:
            conn.execute("CREATE TABLE tafsirs(source TEXT,sura INT,aya INT,text TEXT)")
            # Synthetic data must NEVER be mistaken for a tafsir edition.
            suffix = "أخبرنا أبو القاسم بن جعفر الهاشمي أنا أب"
            padding = ("تَجْرِبَةُ مُقَارَنَةِ النُّصُوصِ " * 1300)
            self.original = padding[:32767 - len(suffix)] + suffix
            assert len(self.original) == 32767
            conn.execute("INSERT INTO tafsirs VALUES ('baghawy',4,43,?)", (self.original,))
            conn.commit()
        finally:
            conn.close()
        self.meta = {"source_type": "independent_online_transcription",
                     "source_url": "https://example.org/synthetic-not-a-book",
                     "work": "Synthetic test document"}

    def tearDown(self):
        self.temporary.cleanup()

    def test_suffix_with_real_continuation(self):
        # Create a complete normalization-compatible continuation.
        witness = self.original + "و علي اللؤلؤي ثم يتابع هذا النص الاصطناعي الطويل للتأكد من الاستمرار"
        result = inspect_cutoff(self.path, 4, 43, witness, self.meta)
        self.assertEqual(result["status"], "UNIQUE_CUTOFF_TAIL_WITH_LATER_TEXT_IN_WITNESS")
        self.assertTrue(result["diagnostic_match"]["match_unique"])
        self.assertGreaterEqual(result["diagnostic_match"]["anchor_characters"], 48)
        self.assertFalse(result["scholarly_verified"])

    def test_cannot_infer_continuation_from_truncated_witness(self):
        result = inspect_cutoff(self.path, 4, 43, self.original, self.meta)
        self.assertNotEqual(result["status"], "UNIQUE_CUTOFF_TAIL_WITH_LATER_TEXT_IN_WITNESS")

    def test_unaligned_and_metadata_validation(self):
        out = inspect_cutoff(self.path, 4, 43, "نص مختلف تماما عن الشاهد" * 100, self.meta)
        self.assertEqual(out["status"], "NOT_ALIGNED")
        with self.assertRaises(ValueError):
            inspect_cutoff(self.path, 4, 43, self.original, {"source_type": "printed_edition_transcription",
                                                            "work": "Synthetic", "source_url": "https://example.org"})
        with self.assertRaises(ValueError):
            inspect_cutoff(self.path, 2, 43, self.original, self.meta)

    def test_normalization_does_not_rewrite_text(self):
        original = "بِسْمِ اللَّهِ"
        self.assertEqual(diagnostic_letters(original), "بسمالله")
        self.assertEqual(original, "بِسْمِ اللَّهِ")


if __name__ == "__main__":
    unittest.main()
