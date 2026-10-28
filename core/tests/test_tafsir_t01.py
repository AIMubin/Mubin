"""T0.1 synthetic tests: no original Quran or Tafsir text stored in Git."""
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from engines.tafsir.t01 import _lookup, lookup_verse, main, TafsirError


class TafsirT01Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "synthetic.db"
        with sqlite3.connect(self.db) as con:
            con.execute("CREATE TABLE verses(sura INTEGER,aya INTEGER,text TEXT)")
            con.execute("CREATE TABLE tafsirs(source TEXT,sura INTEGER,aya INTEGER,text TEXT)")
            con.execute("INSERT INTO verses VALUES (2,43,'FABRICATED FIXTURE NOT QURAN')")
            con.execute("INSERT INTO verses VALUES (4,43,'FABRICATED FIXTURE NOT QURAN')")
            con.executemany("INSERT INTO tafsirs VALUES (?,?,?,?)", [
                ("tabary",2,43,"<br>"),
                ("katheer",2,43,"تفسير اصطناعي <b>للاختبار</b>"),
                ("saadi",2,43,"شرح تجريبي"),
                ("baghawy",4,43,"نص اصطناعي مقيد"),
            ])
        self.pin = hashlib.sha256(self.db.read_bytes()).hexdigest()

    def read(self, ref="2:43", private=False, **kw):
        return _lookup(self.db, ref, expected_sha256=kw.get("pin", self.pin),
                       upstream_declared_sha256="a"*64, include_private_text=private)

    def test_metadata_only_linkage_and_no_derived_quran(self):
        result = self.read()
        self.assertEqual("mubin-tafsir-t01-v1", result["contract"])
        self.assertEqual("2:43", result["quran_reference"])
        self.assertEqual(3, result["tafsir_count"])
        self.assertIsNone(result["quran_anchor"]["quran_text"])
        self.assertFalse(result["quran_anchor"]["derived_quran_text_exposed"])
        self.assertEqual(self.pin, result["corpus"]["linked_sqlite_sha256"])
        self.assertFalse(result["corpus"]["original_upstream_checked_in_this_query"])
        self.assertFalse(result["interpretive_differences_assessed"])
        for key in ("source_authenticated","scholarly_verified","rights_verified",
                    "publication_allowed","juristic_inference_allowed",
                    "public_fatwa_authorized","p1_admitted"):
            self.assertIs(result[key], False, key)
        self.assertTrue(all(r["text"] is None for r in result["tafsirs"]))
        self.assertTrue(all(r["edition"] is None and r["page"] is None
                            and r["volume"] is None for r in result["tafsirs"]))
        self.assertEqual({"tafsir_tabari","tafsir_ibn_kathir","tafsir_saadi"},
                         {r["work_id"] for r in result["tafsirs"]})
        self.assertTrue(all(r["evidence_id"].startswith("tafsir:") for r in result["tafsirs"]))
        self.assertNotIn("FABRICATED FIXTURE", json.dumps(result,ensure_ascii=False))

    def test_explicit_private_read_and_markup_only_suppression(self):
        records = {r["work_id"]:r for r in self.read(private=True)["tafsirs"]}
        self.assertEqual("تفسير اصطناعي للاختبار",records["tafsir_ibn_kathir"]["text"])
        self.assertEqual("PRIVATE_UNVERIFIED_RESEARCH_ONLY",
                         records["tafsir_ibn_kathir"]["text_access"])
        self.assertIsNone(records["tafsir_tabari"]["text"])
        self.assertIn("NO_DISPLAYABLE_TEXT", records["tafsir_tabari"]["quality_flags"])
        self.assertFalse(records["tafsir_ibn_kathir"]["rights_verified"])

    def test_baghawi_editorial_hold_is_not_overridden_by_private_flag(self):
        row = self.read(ref="4:43",private=True)["tafsirs"][0]
        self.assertEqual("tafsir_baghawi",row["work_id"])
        self.assertIsNone(row["text"])
        self.assertTrue(row["editorial_review_required"])
        self.assertEqual("NOT_DISPLAYABLE_OR_EDITORIAL_HOLD",row["text_access"])

    def test_pin_rejects_tampering(self):
        with self.assertRaisesRegex(TafsirError,"T01_DATABASE_PIN_MISMATCH"):
            self.read(pin="0"*64)
        with sqlite3.connect(self.db) as con:
            con.execute("UPDATE tafsirs SET text='تبديل' WHERE source='saadi'")
        with self.assertRaisesRegex(TafsirError,"T01_DATABASE_PIN_MISMATCH"):
            self.read()

    def test_bad_reference_missing_record_and_missing_vault(self):
        for ref in ("2:0","2:287","0:1","2:043","2:43%00","2:43; DROP",""):
            with self.subTest(ref=ref),self.assertRaisesRegex(TafsirError,"T01_INVALID_REFERENCE"):
                self.read(ref)
        with self.assertRaisesRegex(TafsirError,"T01_LOCAL_SOURCE_UNREADABLE"):
            self.read("3:1")
        with self.assertRaisesRegex(TafsirError,"T01_LOCAL_VAULT_UNAVAILABLE"):
            _lookup(Path(self.tmp.name)/"missing.db","2:43",
                    expected_sha256=self.pin,upstream_declared_sha256="a"*64)

    def test_symlink_is_refused(self):
        alias = Path(self.tmp.name)/"alias.db"
        try:
            alias.symlink_to(self.db)
        except (NotImplementedError,OSError):
            self.skipTest("Symlink unavailable")
        with self.assertRaisesRegex(TafsirError,"T01_LOCAL_VAULT_UNAVAILABLE"):
            _lookup(alias,"2:43",expected_sha256=self.pin,
                    upstream_declared_sha256="a"*64)

    def test_duplicate_source_rows_refused(self):
        with sqlite3.connect(self.db) as con:
            con.execute("INSERT INTO tafsirs VALUES ('katheer',2,43,'مكرر')")
        self.pin = hashlib.sha256(self.db.read_bytes()).hexdigest()
        with self.assertRaisesRegex(TafsirError,"T01_AMBIGUOUS_SOURCE_RECORDS"):
            self.read()

    def test_public_operator_api_refuses_synthetic_source(self):
        with self.assertRaisesRegex(TafsirError,"T01_DATABASE_PIN_MISMATCH"):
            lookup_verse(self.db,"2:43")
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["2:43","--database",str(self.db)])
        self.assertEqual(2,code)
        self.assertEqual({"status":"REFUSED","code":"T01_DATABASE_PIN_MISMATCH"},
                         json.loads(out.getvalue()))
        self.assertNotIn(str(self.db),out.getvalue())
