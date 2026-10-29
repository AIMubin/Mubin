"""T0.3 acceptance: unified contract + reader extension + security."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from unittest.mock import patch

from engines.quran.q01b.tanzil import load_raw
from engines.quran.q01c.reader import build_http_server
from engines.tafsir.t03 import unified_research_query

RAW = ('1|1|سَلَامٌ مختبر\n1|2|نَصٌّ تجريبي\n2|1|بَحْثٌ اصطناعي\n2|43|آية اصطناعية للاختبار فقط\n').encode('utf-8')
MANIFEST = {'contract': 'mubin-quran-q01b-verbatim-source-v1',
            'source_kind': 'synthetic_fixture', 'source_id': 'synthetic:q01b',
            'source_url': None, 'source_commit': None,
            'source_git_blob_sha1': None,
            'raw_sha256': hashlib.sha256(RAW).hexdigest(),
            'raw_byte_count': len(RAW), 'coverage': 'partial',
            'reading': 'hafs_an_asim_kufan',
            'rights_status': 'requires_use_review',
            'authority_status': 'not_authenticated'}

PASSAGE_TEXT = ("قال المفسرون: دلت الآية على الأمر بالصلاة. "
                "وقيل في المراد قول آخر.")


class T03Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / "quran_tafsir.db"
        conn = sqlite3.connect(self.db)
        conn.execute("CREATE TABLE tafsirs(source TEXT, sura INTEGER,"
                     " aya INTEGER, text TEXT)")
        conn.execute("INSERT INTO tafsirs VALUES(?,?,?,?)",
                     ("tabari", 2, 43, PASSAGE_TEXT))
        conn.commit()
        conn.close()
        self.db_digest = hashlib.sha256(self.db.read_bytes()).hexdigest()
        raw_digest = hashlib.sha256(PASSAGE_TEXT.encode("utf-8")).hexdigest()
        self.lookup = {
            "contract": "mubin-tafsir-t01-v1", "quran_reference": "2:43",
            "tafsir_count": 1,
            "corpus": {"linked_database_pin_matched": True,
                       "linked_sqlite_sha256": self.db_digest,
                       "original_upstream_sqlite_sha256_declared": "0" * 64,
                       "source_dataset": "synthetic"},
            "tafsirs": [{
                "work_id": "tafsir_tabari", "work_title_ar": "جامع البيان",
                "author_ar": "محمد بن جرير الطبري",
                "dataset_source_key": "tabari",
                "display_status": "SOURCE_TEXT_UNVERIFIED_EDITION",
                "edition_authenticated": False, "quality_flags": [],
                "evidence_id": f"tafsir:tafsir_tabari:2:43:{raw_digest}",
                "imported_record_sha256": raw_digest,
                "verse_locator": "2:43", "text": PASSAGE_TEXT,
                "text_access": "LOCAL_RESEARCH",
                "source_dataset": "synthetic"}]}
        def fake_lookup(db, ref, *, include_private_text=False):
            import re
            if not re.fullmatch(r"[1-9][0-9]{0,2}:[1-9][0-9]{0,2}", ref or ""):
                raise ValueError("T01_INVALID_REFERENCE")
            return dict(self.lookup, quran_reference=ref)
        self.lookup_patch = patch(
            "engines.tafsir.t03.lookup_verse", side_effect=fake_lookup)
        self.lookup_patch.start()
        self.addCleanup(self.lookup_patch.stop)

    # --- T0.3.1 ---
    def test_valid_query_metadata_only(self):
        r = unified_research_query(self.db, "2:43")
        self.assertEqual(r["status"], "OK")
        self.assertEqual(r["tafsir_count"], 1)
        self.assertFalse(r["text_included"])
        self.assertFalse(r["scholarly_verified"])
        self.assertFalse(r["consensus_claimed"])
        self.assertEqual(r["counts"]["passages_processed"], 1)
        self.assertTrue(r["tafsirs"][0]["candidate_count"] >= 1)
        for c in r["tafsirs"][0]["candidates_redacted"]:
            self.assertNotIn("interpretation_statement", c)

    def test_invalid_reference_refused(self):
        with self.assertRaises(ValueError):
            unified_research_query(self.db, "not-a-ref")

    def test_candidate_navigation_chain(self):
        r = unified_research_query(self.db, "2:43")
        c = r["tafsirs"][0]["candidates_redacted"][0]
        self.assertTrue(c["candidate_id"].startswith("cand:"))
        self.assertTrue(c["passage_id"].startswith("interp:"))
        self.assertTrue(c["source_record_id"].startswith("tafsir:"))
        self.assertEqual(c["quran_reference"], "2:43")
        work = r["tafsirs"][0]
        passage = next(p for p in work["passages_redacted"]
                       if p["passage_id"] == c["passage_id"])
        self.assertEqual(passage["source_record_id"], c["source_record_id"])
        self.assertEqual(passage["raw_source_span"][0] + c["statement_start"],
                         c["raw_source_span"][0])
        self.assertEqual(passage["raw_source_span"][0] + c["statement_end"],
                         c["raw_source_span"][1])
        self.assertIs(c["text_included"], False)
        self.assertNotIn("interpretation_statement", passage)

    def test_contract_refuses_fake_private_text_included_flag(self):
        with self.assertRaisesRegex(ValueError, "T03_PRIVATE_TEXT_NOT_SUPPORTED"):
            unified_research_query(self.db, "2:43", include_private_text=True)

    def test_undetermined_relation_not_agreement(self):
        r = unified_research_query(self.db, "2:43")
        for rel in r["relations"]:
            if rel["relation_type"] == "UNDETERMINED":
                self.assertFalse(rel["consensus_claimed"])
                self.assertFalse(rel["scholarly_verified"])

    # --- T0.3.2/3: reader extension ---
    def _server(self):
        idx = load_raw(json.dumps(MANIFEST).encode(), RAW)
        return build_http_server(idx, RAW, port=0,
                                 tafsir_db_path=self.db)

    def _get(self, path, extra=None):
        server = self._server()
        port = server.server_address[1]
        th = threading.Thread(target=server.serve_forever, daemon=True)
        th.start()
        self.addCleanup(server.shutdown)
        conn = HTTPConnection("127.0.0.1", port, timeout=30)
        headers = {"Host": f"127.0.0.1:{port}"}
        headers.update(extra or {})
        conn.request("GET", path, headers=headers)
        r = conn.getresponse()
        body = r.read()
        conn.close()
        return r, body

    def test_research_disabled_without_db(self):
        idx = load_raw(json.dumps(MANIFEST).encode(), RAW)
        server = build_http_server(idx, RAW, port=0, tafsir_db_path=None)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        conn = HTTPConnection("127.0.0.1", port, timeout=10)
        conn.request("GET", "/api/research?ref=2:43",
                     headers={"Host": f"127.0.0.1:{port}"})
        r = conn.getresponse()
        body = json.loads(r.read())
        conn.close()
        self.assertEqual(r.status, 403)
        self.assertEqual(body["error"], "tafsir_research_disabled")

    def test_research_route_metadata_only(self):
        r, body = self._get("/api/research?ref=2%3A43")
        self.assertEqual(r.status, 200)
        data = json.loads(body)
        self.assertFalse(data["text_included"])
        raw = json.dumps(data, ensure_ascii=False)
        self.assertNotIn("دلت الآية", raw)
        self.assertNotIn(PASSAGE_TEXT[:20], raw)

    def test_tafsir_row_does_not_bypass_missing_quran_anchor(self):
        r, body = self._get("/api/research?ref=2%3A44")
        self.assertEqual(r.status, 404)
        data = json.loads(body)
        self.assertEqual(data["error"], "verse_not_in_loaded_quran_source")

    def test_duplicate_or_malformed_query_refused_without_source_text(self):
        for target in ("/api/research?ref=2%3A43&ref=2%3A43",
                       "/api/research?ref=2%3A0"):
            with self.subTest(target=target):
                r, body = self._get(target)
                self.assertEqual(r.status, 400)
                self.assertNotIn("دلت الآية", body.decode("utf-8"))

    def test_reader_sanitizes_unexpected_local_source_errors(self):
        with patch("engines.tafsir.t03.unified_research_query",
                   side_effect=RuntimeError("SENSITIVE PRIVATE SOURCE TEXT")):
            r, body = self._get("/api/research?ref=2%3A43")
        self.assertEqual(r.status, 422)
        self.assertNotIn("SENSITIVE PRIVATE SOURCE TEXT",body.decode("utf-8"))

    def test_cross_origin_still_rejected(self):
        r, _ = self._get("/api/research?ref=2%3A43",
                         {"Origin": "http://evil.example"})
        self.assertEqual(r.status, 403)

    def test_research_page_served_rtl_no_text(self):
        r, body = self._get("/research")
        self.assertEqual(r.status, 200)
        text = body.decode("utf-8")
        self.assertIn('dir="rtl"', text)
        self.assertNotIn("دلت الآية", text)

    def test_existing_reader_routes_unaffected(self):
        r, _ = self._get("/api/status")
        self.assertEqual(r.status, 200)


    def test_hadith_api_explicit_opt_in_redacts_and_sanitizes(self):
        idx=load_raw(json.dumps(MANIFEST).encode(),RAW)
        server=build_http_server(idx,RAW,port=0,tafsir_db_path=self.db,
                                 hadith_cache_dir=self.root/"synthetic-cache")
        port=server.server_address[1]
        threading.Thread(target=server.serve_forever,daemon=True).start()
        self.addCleanup(server.shutdown)
        def fetch():
            conn=HTTPConnection("127.0.0.1",port,timeout=15)
            conn.request("GET","/api/research?ref=2%3A43",
                         headers={"Host":f"127.0.0.1:{port}"})
            res=conn.getresponse()
            status=res.status
            data=json.loads(res.read())
            conn.close()
            return status,data
        synthetic={"status":"OK","text_included":False,"mentions_total":1,
                   "witnesses_total":0,"links_total":1,"links_by_status":{
                       "SOURCE_UNAVAILABLE":1},"holdout_read":False}
        with patch("engines.tafsir.t01.lookup_verse",return_value=self.lookup), \
             patch("engines.hadith.hsearch.pipeline.run_hsearch",
                   return_value=synthetic):
            status,data=fetch()
        self.assertEqual(200,status)
        self.assertEqual(synthetic,data["hadith"])
        self.assertFalse(data["text_included"])
        self.assertNotIn(PASSAGE_TEXT,json.dumps(data,ensure_ascii=False))
        with patch("engines.tafsir.t01.lookup_verse",return_value=self.lookup), \
             patch("engines.hadith.hsearch.pipeline.run_hsearch",
                   side_effect=RuntimeError("SENSITIVE_PRIVATE_HADITH_TEXT")):
            status,data=fetch()
        self.assertEqual(422,status)
        self.assertNotIn("SENSITIVE_PRIVATE_HADITH_TEXT",json.dumps(data))


    def test_usul_opt_in_http_uses_all_candidates_and_redacts(self):
        from engines.tafsir.t02_cli import extract_local_verse
        from engines.tafsir.t023 import identify_candidates
        passages=extract_local_verse(self.db,self.lookup)
        self.assertTrue(passages)
        first=next(p for p in passages if identify_candidates(p))
        index=load_raw(json.dumps(MANIFEST).encode(),RAW)
        server=build_http_server(index,RAW,port=0,tafsir_db_path=self.db,
                                 usul_evidence_path=self.root/"usul_private.json")
        port=server.server_port
        threading.Thread(target=server.serve_forever,daemon=True).start()
        self.addCleanup(server.shutdown)
        observed=[]
        synthetic={
            "contract":"mubin-usul-tafsir-presentation-v1",
            "counts":{"matches_total":2,
                      "links_by_status":{"UNDETERMINED":2},
                      "ties_by_level":{"NONE":2}},
            "links_redacted":[{"link_status":"UNDETERMINED"},
                              {"link_status":"UNDETERMINED"}],
            "evidence_levels":["RETRIEVED_SOURCE_MATERIAL",
                               "GROUNDED_PASSAGE","AUTOMATED_CANDIDATE",
                               "TEXTUALLY_ATTRIBUTED","SCHOLARLY_VERIFIED"],
            "usul_link_level_cap":"AUTOMATED_CANDIDATE",
            "text_included":False,"scholarly_verified":False,
        }
        def fake_section(bundle_path, *, tafsir_items):
            self.assertEqual(self.root/"usul_private.json",bundle_path)
            observed.extend(tafsir_items)
            return synthetic
        def fetch():
            c=HTTPConnection("127.0.0.1",port,timeout=15)
            c.request("GET","/api/research?ref=2%3A43",
                      headers={"Host":f"127.0.0.1:{port}"})
            r=c.getresponse()
            status=r.status
            data=json.loads(r.read())
            c.close()
            return status,data
        with patch("engines.tafsir.t01.lookup_verse",return_value=self.lookup), \
             patch("engines.tafsir.t02_cli.extract_local_verse",
                   return_value=[first,first]), \
             patch("engines.usul.ut014.usul_research_section",
                   side_effect=fake_section):
            status,result=fetch()
        self.assertEqual(200,status)
        self.assertEqual(synthetic,result["usul"])
        self.assertEqual(2,len(observed))
        self.assertEqual(observed[0]["candidate"]["candidate_id"],
                         observed[1]["candidate"]["candidate_id"])
        self.assertNotIn(PASSAGE_TEXT,json.dumps(result,ensure_ascii=False))
        self.assertFalse(result["usul"]["scholarly_verified"])
        with patch("engines.tafsir.t01.lookup_verse",return_value=self.lookup), \
             patch("engines.usul.ut014.usul_research_section",
                   side_effect=RuntimeError("PRIVATE_WARAQAT_CONTENT")):
            status,result=fetch()
        self.assertEqual(422,status)
        self.assertNotIn("PRIVATE_WARAQAT_CONTENT",json.dumps(result))
        self.assertNotIn(str(self.root),json.dumps(result))


if __name__ == "__main__":
    unittest.main()
