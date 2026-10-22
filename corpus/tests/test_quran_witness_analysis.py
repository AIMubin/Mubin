import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from corpus.quran_witness_analysis import analyze, classify, segment_first_verse
from corpus.verify_quran import EXPECTED_COUNTS

BASE = "بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ"

class WitnessAnalysisTests(unittest.TestCase):
    def test_basmala_is_not_included_in_first_verse_text(self):
        verse,opening=segment_first_verse(2,1,BASE+" الٓمٓ",BASE)
        self.assertEqual((verse,opening),("الٓمٓ",BASE))
        variant=BASE.replace("بِسْمِ","بِّسْمِ",1)
        self.assertEqual(segment_first_verse(95,1,variant+" وَٱلتِّينِ",BASE),("وَٱلتِّينِ",variant))
        self.assertEqual(segment_first_verse(1,1,BASE,BASE),(BASE,None))
        self.assertEqual(segment_first_verse(9,1,"بَرَاءَةٌ",BASE),("بَرَاءَةٌ",None))
        with self.assertRaises(ValueError):
            segment_first_verse(2,1,"الٓمٓ",BASE)

    def test_diagnostic_only_categories(self):
        self.assertEqual(classify("نصر","نصر"),"EXACT")
        self.assertEqual(classify("بسم","بِسْم"),"MARKS_ONLY_CANDIDATE")
        self.assertEqual(classify("الناس","ٱلنَّاس"),"ALEF_VARIANTS_CANDIDATE")
        self.assertEqual(classify("يا/أيها","يَٰٓأَيُّهَا"),"UNRESOLVED_SCRIPT_DIFFERENCE")

    def test_all_6236_synthetic_rows_and_sha(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            db,ref=root/"sample.sqlite",root/"reference.txt"
            conn=sqlite3.connect(db)
            conn.execute("CREATE TABLE verses(sura INT,aya INT,text TEXT)")
            rows=[]; lines=[]
            for s,n in enumerate(EXPECTED_COUNTS,1):
                for a in range(1,n+1):
                    value=BASE if (s,a)==(1,1) else "SYNTHETIC"
                    rows.append((s,a,value))
                    opening=BASE.replace("بِسْمِ","بِّسْمِ",1) if s in (95,97) else BASE
                    line=opening+" "+value if a==1 and s not in (1,9) else value
                    lines.append(f"{s}|{a}|{line}\n")
            conn.executemany("INSERT INTO verses VALUES(?,?,?)",rows)
            conn.commit()
            conn.close()
            ref.write_text("".join(lines),encoding="utf-8")
            pin=hashlib.sha256(ref.read_bytes()).hexdigest()
            out=analyze(db,ref,pin)
            self.assertEqual(out["categories_after_boundary_segmentation"],{"EXACT":6236})
            self.assertEqual(out["first_verse_openings"]["record_with_unnumbered_opening"],112)
            self.assertEqual(out["first_verse_openings"]["alternate_opening_diacritics"],2)
            self.assertFalse(out["scholarly_verified"])
            with self.assertRaises(ValueError):
                analyze(db,ref,"f"*64)

if __name__=="__main__":unittest.main()
