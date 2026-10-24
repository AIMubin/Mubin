"""Separate verified SQLite sidecar for Tafsir Center: schema not claimed publishing approval."""
from __future__ import annotations
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from qa.tafsircenter_sidecar_v01 import (verify_sidecar, SidecarError,
    EXPECTED_SHA256, TABLES_AR, 
    SOURCE_ID)
from engines.quran.q01.engine import _VERSE_COUNTS


def make_sample(path):
    db=sqlite3.connect(path)
    try:
        for table in TABLES_AR:
            db.execute(f'CREATE TABLE "{table}" (sura INTEGER, aya INTEGER, tafsir TEXT)')
            db.executemany(f'INSERT INTO "{table}" VALUES (?,?,?)',(
                (s,a,'نص تفسير اصطناعي وليس حقيقيًا') for s,count in enumerate(_VERSE_COUNTS,1)
                for a in range(1,count+1)))
        db.execute('CREATE TABLE "QuranTafseer" (surahNo INTEGER, ayahNo INTEGER, Mukhtasarar TEXT, Mukhtasaren TEXT, Mukhtasarbn TEXT)')
        db.executemany('INSERT INTO "QuranTafseer" VALUES (?,?,?,?,?)',((s,a,'اختبار','test','test') for s,count in enumerate(_VERSE_COUNTS,1) for a in range(1,count+1)))
        db.execute('CREATE TABLE "word_content_rasm"(surahNo INTEGER,ayahNo INTEGER,wordNo INTEGER,word TEXT)')
        db.execute('CREATE TABLE "qeraat_info"(surahNo INTEGER,ayahNo INTEGER,wordNo INTEGER,content TEXT,note TEXT)')
        db.execute('CREATE TABLE "ayah_content_nozool"(surahNo INTEGER,ayahNo INTEGER,nozoolInfo TEXT)')
        db.execute('CREATE TABLE "surah_stats"(surahNo INTEGER,surahName TEXT)')
        db.executemany('INSERT INTO surah_stats VALUES (?,?)',((n,'سورة اصطناعية') for n in range(1,115)))
        db.commit()
    finally:db.close()


class SidecarTests(unittest.TestCase):
    def test_pinned_digest_and_exact_five_arabic_sources(self):
        self.assertEqual(64,len(EXPECTED_SHA256))
        self.assertEqual('tafsircenter_quran_db_sidecar_v01',SOURCE_ID)
        self.assertEqual({'tafsir_tabary','tafsir_katheer','tafsir_baghawy','tafsir_saadi','tafsir_moyassar'},set(TABLES_AR))

    def test_verification_does_not_pretend_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'private-quran.db'
            make_sample(path)
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            with patch('qa.tafsircenter_sidecar_v01.EXPECTED_SHA256',digest):
                receipt=verify_sidecar(path,deep=False)
            self.assertEqual(5,len(receipt['tafsir_sources']))
            self.assertEqual(6236,receipt['multi_tafsir_coordinates'])
            self.assertEqual(114,receipt['surah_count'])
            self.assertFalse(receipt['publication_allowed'])
            self.assertFalse(receipt['p1_admitted'])
            self.assertFalse(receipt['rights_verified'])
            self.assertEqual('legal_review_pending',receipt['rights_status'])
            self.assertNotIn('نص تفسير',str(receipt))

    def test_sqlite_uri_encodes_private_filename_with_spaces(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"private tafsir source.db"
            make_sample(path)
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            with patch("qa.tafsircenter_sidecar_v01.EXPECTED_SHA256",digest):
                report=verify_sidecar(path,deep=False)
            self.assertEqual(6236,report["multi_tafsir_coordinates"])
            self.assertFalse(report["rights_verified"])

    def test_modify_db_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'private.db'
            make_sample(path)
            with self.assertRaises(SidecarError):verify_sidecar(path,deep=False)

    def test_reject_wrong_table_schema_even_when_hash_pinned(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'private.db'
            make_sample(path)
            con=sqlite3.connect(path)
            con.execute('DROP TABLE tafsir_tabary')
            con.commit();con.close()
            with patch('qa.tafsircenter_sidecar_v01.EXPECTED_SHA256',hashlib.sha256(path.read_bytes()).hexdigest()):
                with self.assertRaises(SidecarError):verify_sidecar(path,deep=False)

    def test_existing_public_repo_db_path_is_blocked(self):
        from qa.tafsircenter_sidecar_v01 import SOURCE_ROOT
        with self.assertRaises(SidecarError):verify_sidecar(SOURCE_ROOT/'quran.db',deep=False)

if __name__=='__main__':unittest.main()