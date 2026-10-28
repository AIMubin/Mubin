"""T0.2.1/T0.2.2 adversarial synthetic source-grounding tests."""
from __future__ import annotations

from contextlib import closing, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from engines.tafsir.t01 import _lookup, TafsirError
from engines.quran.tafsir.catalog import load_catalog
from engines.tafsir.t02 import (
    TafsirT02Error, extract_from_t01_record, make_record,
    segment_statements, summarize, validate_record, CONTRACT,
    CONTEXT, SPAN_UNIT, STATUS_RULE_EXTRACTED_UNVERIFIED,
)
from engines.tafsir.t02_cli import extract_local_verse, main

TEXT = ("قال المفسرون تفسيرًا اصطناعيًا غير حقيقي. "
        "وفي المقطع بيان تجريبي مختلف للاختبار. "
        "وقد ترد قرينة اصطناعية أخرى في السياق.")
HTML = ("شرح <b>اصطناعي</b> طويل في أول جملة من المصدر. "
        "ومثال آخر لا يمثل تفسيرًا حقيقيًا.")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def source_record(text=TEXT, work="tafsir_tabari", ref="2:43",
                  display=None, raw=True) -> dict:
    digest = sha(text)
    return {
        "evidence_id": f"tafsir:{work}:{ref}:{digest}",
        "work_id": work, "author_ar": next(
            item["author_ar"] for item in load_catalog()["sources"]
            if item["id"] == work),
        "imported_record_sha256": digest,
        "verse_locator": ref,
        "text": text if display is None else display,
        **({"raw_original_text": text} if raw else {}),
    }


def record(text=TEXT, span=(0, 45)) -> dict:
    s = source_record(text)
    return make_record(
        quran_reference=s["verse_locator"], work_id=s["work_id"],
        author_id=s["author_ar"], source_record_id=s["evidence_id"],
        source_sha256=s["imported_record_sha256"], original_text=text,
        span=span, interpretation_type=None, context_scope=CONTEXT)


class T02GroundingTests(unittest.TestCase):
    def test_build_and_validate_exact_source_span(self):
        r = record()
        validate_record(r, original_text=TEXT)
        self.assertEqual(TEXT[r["evidence_span"][0]:r["evidence_span"][1]],
                         r["interpretation_statement"])
        self.assertEqual(SPAN_UNIT, r["evidence_span_unit"])
        self.assertEqual("UNCLASSIFIED_TEXT_SEGMENT", r["candidate_kind"])

    def test_extraction_produces_candidate_segments_not_semantic_opinions(self):
        out = extract_from_t01_record(source_record())
        self.assertGreaterEqual(len(out), 2)
        self.assertEqual(len(out), len({row["interpretation_id"] for row in out}))
        for row in out:
            self.assertIsNone(row["interpretation_type"])
            self.assertEqual(STATUS_RULE_EXTRACTED_UNVERIFIED, row["verification_status"])
        self.assertIn("NOT_DISTINCT_EXEGETICAL_OPINIONS",summarize(out)["count_semantics"])

    def test_unpinned_display_text_is_rejected(self):
        with self.assertRaisesRegex(TafsirT02Error,"T02_T01_FIELD_MISSING"):
            extract_from_t01_record(source_record(raw=False))
        bad = source_record(text=TEXT, display="تفسير عرض مختلف")
        bad["raw_original_text"] = bad["text"]
        with self.assertRaisesRegex(TafsirT02Error,"T02_SOURCE_BYTES_MISMATCH"):
            extract_from_t01_record(bad)

    def test_exact_raw_html_offsets_not_display_transform(self):
        s = source_record(text=HTML, display="شرح اصطناعي طويل في أول جملة من المصدر.")
        out = extract_from_t01_record(s)
        self.assertTrue(out)
        self.assertIn("<b>", out[0]["interpretation_statement"])
        self.assertEqual(sha(HTML), out[0]["source_sha256"])
        self.assertEqual(out[0]["interpretation_statement"],
                         HTML[slice(*out[0]["evidence_span"])])

    def test_tampered_source_sha_refused(self):
        bad = record()
        bad["source_sha256"] = "0"*64
        with self.assertRaisesRegex(TafsirT02Error,"T02_SOURCE_BYTES_MISMATCH"):
            validate_record(bad, original_text=TEXT)

    def test_statement_elsewhere_in_same_source_cannot_pass(self):
        bad = record()
        bad["interpretation_statement"] = "بيان تجريبي مختلف للاختبار"
        self.assertIn(bad["interpretation_statement"],TEXT)
        with self.assertRaisesRegex(TafsirT02Error,"T02_STATEMENT_NOT_EXACT_SPAN"):
            validate_record(bad, original_text=TEXT)

    def test_work_ref_and_authority_forgery_refused(self):
        bad = record()
        bad["work_id"] = "tafsir_baghawi"
        with self.assertRaisesRegex(TafsirT02Error,"T02_SOURCE_IDENTITY_MISMATCH"):
            validate_record(bad, original_text=TEXT)
        bad = record()
        bad["author_id"] = "نسبة خاطئة إلى مؤلف آخر"
        with self.assertRaisesRegex(TafsirT02Error,"T02_AUTHOR_MISMATCH"):
            validate_record(bad, original_text=TEXT)
        bad = record()
        bad["publication_allowed"] = True
        with self.assertRaisesRegex(TafsirT02Error,"T02_AUTHORITY_PROMOTION_FORBIDDEN"):
            validate_record(bad, original_text=TEXT)

    def test_wrong_evidence_hash_and_interpretation_id_refused(self):
        for key, value, code in (
            ("evidence_sha256","f"*64,"T02_EVIDENCE_NOT_GROUNDED"),
            ("interpretation_id","interp:"+"0"*40,"T02_INTERPRETATION_ID_INVALID"),
        ):
            bad = record()
            bad[key] = value
            with self.subTest(key=key),self.assertRaisesRegex(TafsirT02Error,code):
                validate_record(bad, original_text=TEXT)

    def test_edition_and_semantic_promotion_refused(self):
        for key,value in (
            ("edition","طبعة افتراضية"),
            ("volume",1),
            ("page",20),
        ):
            bad=record()
            bad[key]=value
            with self.subTest(key=key), self.assertRaisesRegex(
                TafsirT02Error, "T02_EDITION_OR_RIGHTS_PROMOTION"):
                validate_record(bad, original_text=TEXT)
        bad=record()
        bad["interpretation_type"]="FIQH_RULING"
        with self.assertRaisesRegex(TafsirT02Error,"T02_SEMANTIC_PROMOTION_FORBIDDEN"):
            validate_record(bad, original_text=TEXT)

    def test_invalid_reference_or_unrecognized_field_refused(self):
        bad=record()
        bad["quran_reference"]="115:1"
        with self.assertRaisesRegex(TafsirT02Error,"T02_REFERENCE_INVALID"):
            validate_record(bad, original_text=TEXT)
        bad=record()
        bad["source_authenticated"]=True
        with self.assertRaisesRegex(TafsirT02Error,"T02_RECORD_SHAPE_INVALID"):
            validate_record(bad, original_text=TEXT)

    def test_missing_or_held_text_is_not_extracted(self):
        s=source_record()
        s["text"]=None
        self.assertEqual([],extract_from_t01_record(s))
        s=source_record()
        s["raw_original_text"]=None
        with self.assertRaisesRegex(TafsirT02Error,"T02_RAW_SOURCE_MISSING"):
            extract_from_t01_record(s)

    def test_span_out_of_bounds_and_deterministic_segmentation(self):
        s=source_record()
        with self.assertRaisesRegex(TafsirT02Error,"T02_SPAN_INVALID"):
            make_record(quran_reference="2:43",work_id=s["work_id"],
                        author_id=None,source_record_id=s["evidence_id"],
                        source_sha256=sha(TEXT),original_text=TEXT,
                        span=(0,99999))
        self.assertEqual(segment_statements(TEXT),segment_statements(TEXT))

    def test_summary_never_copies_text(self):
        out=extract_from_t01_record(source_record())
        summary=json.dumps(summarize(out),ensure_ascii=False)
        self.assertNotIn("المفسرون",summary)
        self.assertFalse(summarize(out)["publication_allowed"])


class T02LocalSQLiteTests(unittest.TestCase):
    def setUp(self):
        self.dir=tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path=Path(self.dir.name)/"synthetic.db"
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute("CREATE TABLE verses(sura INTEGER,aya INTEGER,text TEXT)")
            db.execute("CREATE TABLE tafsirs(source TEXT,sura INTEGER,aya INTEGER,text TEXT)")
            db.execute("INSERT INTO verses VALUES (2,43,'SYNTHETIC - NOT QURAN')")
            db.execute("INSERT INTO tafsirs VALUES ('tabary',2,43,?)",(HTML,))
        self.lookup=self.read_t01()

    def read_t01(self):
        return _lookup(self.path,"2:43",
                       expected_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest(),
                       upstream_declared_sha256="a"*64,include_private_text=True)

    def test_local_raw_db_view_matches_imported_digest_and_offset(self):
        records=extract_local_verse(self.path,self.lookup)
        self.assertTrue(records)
        for r in records:
            self.assertEqual(sha(HTML),r["source_sha256"])
            self.assertEqual(HTML[slice(*r["evidence_span"])],
                             r["interpretation_statement"])

    def test_default_cli_summary_is_content_free(self):
        out=io.StringIO()
        with patch("engines.tafsir.t02_cli.lookup_verse", return_value=self.lookup):
            with redirect_stdout(out):
                code=main(["2:43","--database",str(self.path)])
        self.assertEqual(0,code)
        data=json.loads(out.getvalue())
        self.assertFalse(data["text_included"])
        self.assertEqual("OK",data["status"])
        self.assertNotIn("اصطناعي",out.getvalue())
        self.assertNotIn("interpretation_statement",out.getvalue())

    def test_private_text_requires_explicit_flag(self):
        out=io.StringIO()
        with patch("engines.tafsir.t02_cli.lookup_verse",return_value=self.lookup):
            with redirect_stdout(out):
                code=main(["2:43","--database",str(self.path),"--include-text"])
        self.assertEqual(0,code)
        data=json.loads(out.getvalue())
        self.assertTrue(data["text_included"])
        self.assertIn("<b>",data["records"][0]["interpretation_statement"])

    def test_changed_db_refused_after_t01_receipt(self):
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute("UPDATE tafsirs SET text='المصدر تغير' WHERE source='tabary'")
        with self.assertRaisesRegex(TafsirT02Error,"T02_DATABASE_PIN_MISMATCH"):
            extract_local_verse(self.path,self.lookup)

    def test_sqlite_wal_sidecar_refused(self):
        wal=self.path.with_name(self.path.name+"-wal")
        wal.write_bytes(b"synthetic sidecar")
        with self.assertRaisesRegex(TafsirError,"T01_UNPINNED_SQLITE_SIDECAR"):
            extract_local_verse(self.path,self.lookup)
