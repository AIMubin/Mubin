"""Private-corpus intake: provenance, integrity, atomic commit, no publication."""
from __future__ import annotations
import copy
from hashlib import sha256
import gzip
import json
from pathlib import Path
import sqlite3
import os
import threading
from concurrent.futures import ThreadPoolExecutor
import tempfile
import unittest
from unittest.mock import patch

from qa.corpus_ingest_v01 import (load_manifest, CorpusIngestError,
    _decompress, _validate_tafsir, _validate_source, ingest_corpus,
    PIN_QURAN_ID, _safepath, REPO_ROOT, VALID_IDS)
from engines.quran.q01.engine import _VERSE_COUNTS


def fake_quranenc(sid="ar_qe_arabic_moyassar"):
    data={"schemaVersion":1,"edition":{"id":sid,"source":"QuranEnc.com","version":"1.0.0"},
          "verses":{str(s):{str(a):{"text":f"شرح اصطناعي {s} {a}",
                                 "footnotes":"<b>حاشية اختبار</b>" if a==1 else ""}
                    for a in range(1,amount+1)}
                    for s,amount in enumerate(_VERSE_COUNTS,1)}}
    raw=json.dumps(data,ensure_ascii=False,separators=(",",":")).encode("utf-8")
    return gzip.compress(raw), len(raw)


class CorpusImportTests(unittest.TestCase):
    def test_catalog_has_five_pinned_sources_and_publication_off(self):
        d=load_manifest()
        self.assertEqual("internal_research_only_legal_pending",d["rights_policy"])
        self.assertEqual(VALID_IDS,{x["id"] for x in d["sources"]})
        for x in d["sources"]:
            self.assertFalse(x["publication_enabled"])
            self.assertEqual("legal_review_pending",x["rights_status"])
            self.assertGreater(len(x["attribution"]),10)
            self.assertTrue(x["source_license_url"].startswith("https://"))

    def test_cannot_turn_on_publication_through_manifest(self):
        d=load_manifest()
        d["sources"][0]["publication_enabled"]=True
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"bad.json"
            path.write_text(json.dumps(d,ensure_ascii=False))
            with self.assertRaises(CorpusIngestError):load_manifest(path)

    def test_reject_untrusted_download_host(self):
        d=load_manifest()
        d["sources"][1]["download_url"]="https://evil.example/source.gz"
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"bad.json"
            p.write_text(json.dumps(d,ensure_ascii=False))
            with self.assertRaises(CorpusIngestError):load_manifest(p)

    def test_reject_duplicate_manifest_keys(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"bad.json"
            p.write_text('{"contract":"x","contract":"x"}')
            with self.assertRaises(CorpusIngestError):load_manifest(p)

    def test_detect_corrupted_gzip_and_bomb(self):
        raw,gsize=fake_quranenc()
        self.assertEqual(gsize,len(_decompress(raw,gsize)))
        for bad in (raw[:-2], raw+b"TRAILING",raw[:100]):
            with self.subTest(n=len(bad)),self.assertRaises(CorpusIngestError):
                _decompress(bad,gsize)
        with self.assertRaises(CorpusIngestError): _decompress(raw,100)

    def test_full_synthetic_6236_metadata_and_footnotes_preserved(self):
        blob,uncompressed=fake_quranenc()
        entry={"version":"ar_qe_arabic_moyassar@1.0.0","uncompressed_bytes":uncompressed}
        rows=_validate_tafsir(blob,entry)
        self.assertEqual(6236,len(rows))
        self.assertEqual((1,1,"شرح اصطناعي 1 1","<b>حاشية اختبار</b>"),rows[0])

    def test_reject_missing_ayah_even_if_total_records_look_similar(self):
        blob,ln=fake_quranenc()
        data=json.loads(gzip.decompress(blob))
        del data["verses"]["1"]["1"]
        new=json.dumps(data,ensure_ascii=False).encode()
        with self.assertRaises(CorpusIngestError):_validate_tafsir(gzip.compress(new),{"version":"ar_qe_arabic_moyassar@1.0.0","uncompressed_bytes":len(new)})

    def test_reject_changed_edition_identity(self):
        blob,ln=fake_quranenc()
        with self.assertRaises(CorpusIngestError):_validate_tafsir(blob,{"version":"ar_qe_other@1.0","uncompressed_bytes":ln})

    def test_reject_html_with_executable_script_fields(self):
        blob,ln=fake_quranenc()
        data=json.loads(gzip.decompress(blob))
        data["verses"]["1"]["1"]["script"]="alert(1)"
        changed=json.dumps(data).encode()
        with self.assertRaises(CorpusIngestError):_validate_tafsir(gzip.compress(changed),{"version":"ar_qe_arabic_moyassar@1.0.0","uncompressed_bytes":len(changed)})

    def test_no_corpus_in_public_git(self):
        with self.assertRaises(CorpusIngestError):
            _safepath(REPO_ROOT/"research"/"corpora.sqlite3",output=True)
        with self.assertRaises(CorpusIngestError):
            _safepath(REPO_ROOT/"source_text",output=False)

    def test_private_file_paths_are_canonicalized_before_use(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)
            nested=base/"ordinary"/".."/"private-source"
            self.assertEqual((base/"private-source").resolve(),_safepath(nested))
            out=base/"ordinary"/".."/"private.sqlite3"
            self.assertEqual((base/"private.sqlite3").resolve(),_safepath(out,output=True))
            self.assertFalse(REPO_ROOT in _safepath(out,output=True).parents)

    def test_real_digest_of_package_required(self):
        blob,ln=fake_quranenc()
        item={"kind":"tafsir","compressed_bytes":len(blob),"sha256":"0"*64,"uncompressed_bytes":ln}
        with self.assertRaises(CorpusIngestError):_validate_source(item,blob)

    def test_atomic_private_ingest_zero_publication_and_no_text_logs(self):
        q=b"FAKE QURAN INPUT NOT SCRIPTURE"
        blob,ln=fake_quranenc()
        d=load_manifest()
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)
            for item in d["sources"]:
                if item["kind"]=="quran":
                    raw=q
                else:
                    edition_id=item["version"].split("@")[0]
                    raw,n=fake_quranenc(edition_id)
                    item["uncompressed_bytes"]=n
                item["sha256"]=sha256(raw).hexdigest()
                item["compressed_bytes"]=len(raw)
                (base/item["file_name"]).write_bytes(raw)
            # The fake Quran validator is mocked here; the authentic Quran
            # verification test remains separate in Q0.1e integration tests.
            with patch("qa.corpus_ingest_v01._validate_quran",
                       return_value=[(1,1,"عبارة اصطناعية غير قرآنية","")]):
                result=ingest_corpus(d,base,base/"private.sqlite3")
            self.assertEqual(4*6236+1,result["records"])
            self.assertFalse(result["publication_allowed"])
            self.assertFalse(result["p1_evidence_admitted"])
            self.assertFalse(result["scholarly_verified"])
            self.assertNotIn("شرح اصطناعي",str(result))
            conn=sqlite3.connect(base/"private.sqlite3")
            try:
                self.assertEqual(5,conn.execute("SELECT COUNT(*) FROM corpus_sources").fetchone()[0])
                self.assertEqual("<b>حاشية اختبار</b>",conn.execute("SELECT footnotes FROM corpus_entries WHERE source_kind='tafsir' LIMIT 1").fetchone()[0])
                self.assertEqual(0,conn.execute("SELECT SUM(publication_enabled) FROM corpus_sources").fetchone()[0])
            finally:conn.close()

    def test_fail_closed_output_not_partially_published(self):
        d=load_manifest()
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)
            with self.assertRaises(CorpusIngestError):
                ingest_corpus(d,base,base/"private.sqlite3")
            self.assertFalse((base/"private.sqlite3").exists())

    def test_concurrent_partial_imports_cannot_overwrite_one_snapshot(self):
        # Force both operators to reach publication together. The old
        # exists()-then-os.replace() path allowed TWO success receipts.
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            dbfile=root/"output"/"immutable.sqlite3"
            inputs=[]
            for n in (1,2):
                folder=root/f"private-{n}"
                folder.mkdir()
                d=load_manifest()
                item=d["sources"][n]
                blob,raw_length=fake_quranenc(item["version"].split("@")[0])
                item["sha256"]=sha256(blob).hexdigest()
                item["compressed_bytes"]=len(blob)
                item["uncompressed_bytes"]=raw_length
                (folder/item["file_name"]).write_bytes(blob)
                inputs.append((d,folder,item["id"]))
            barrier=threading.Barrier(2)
            original_link=os.link

            def compete(source,destination):
                barrier.wait(timeout=15)
                return original_link(source,destination)

            def attempt(task):
                catalog,folder,sid=task
                try:
                    receipt=ingest_corpus(catalog,folder,dbfile,allow_partial=True)
                    return ("ok",sid,receipt)
                except CorpusIngestError as exc:
                    return ("denied",sid,str(exc))

            with patch("qa.corpus_ingest_v01.os.link",side_effect=compete):
                with ThreadPoolExecutor(max_workers=2) as executor:
                    results=list(executor.map(attempt,inputs))
            passed=[x for x in results if x[0]=="ok"]
            denied=[x for x in results if x[0]=="denied"]
            self.assertEqual(1,len(passed),results)
            self.assertEqual(1,len(denied),results)
            self.assertEqual("output_already_exists_at_publish",denied[0][2])
            self.assertEqual(6236,passed[0][2]["records"])
            conn=sqlite3.connect(dbfile)
            try:
                ids=[x[0] for x in conn.execute(
                    "SELECT source_id FROM corpus_sources").fetchall()]
                self.assertEqual([passed[0][1]],ids)
                self.assertEqual("ok",conn.execute("PRAGMA quick_check").fetchone()[0])
            finally:
                # Connection context manager only commits/rolls back; it does
                # NOT close the Windows file handle before TempDir cleanup.
                conn.close()
            self.assertEqual([],list(dbfile.parent.glob(".mubin-private-*")))

    def test_missing_sources_can_be_skipped_with_truthful_partial_report(self):
        d=load_manifest()
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)
            item=d["sources"][1]
            blob,ln=fake_quranenc(item["version"].split("@")[0])
            item["sha256"]=sha256(blob).hexdigest()
            item["compressed_bytes"]=len(blob)
            item["uncompressed_bytes"]=ln
            (base/item["file_name"]).write_bytes(blob)
            r=ingest_corpus(d,base,base/"partial.sqlite3",allow_partial=True)
            self.assertEqual(1,len(r["imported_sources"]))
            self.assertEqual(4,len(r["skipped_sources"]))
            self.assertEqual(6236,r["records"])
            self.assertFalse(r["publication_allowed"])

if __name__=="__main__":unittest.main()