"""Q0.1e: fixed Tanzil HTTPS export for PRIVATE local-only Quran reader.

The test's artificial Arabic sentences are not Quranic text. No test promotes
publisher authenticity, permissions or religious ruling eligibility.
"""
from __future__ import annotations
from hashlib import sha256
import json
import unittest
from unittest.mock import patch

from engines.quran.q01.engine import _VERSE_COUNTS
from engines.quran.q01e import official


def synthetic_full_export():
    lines = [f"{s}|{a}|مِثَالٌ اصْطِنَاعِيٌّ لِلِاخْتِبَارِ\n"
             for s, count in enumerate(_VERSE_COUNTS, 1)
             for a in range(1, count+1)]
    lines += ["\n", "# PLEASE DO NOT REMOVE OR CHANGE THIS COPYRIGHT BLOCK\n",
              "# Test-only invented text; no Quran source rights asserted\n"]
    return "".join(lines).encode("utf-8")


class OfficialLocalReaderTests(unittest.TestCase):
    def setUp(self):
        self.data = synthetic_full_export()
        self.hash = sha256(self.data).hexdigest()

    def load_test_source(self, source=None):
        with patch.object(official, "PINNED_OFFICIAL_DOMAIN_SHA256", self.hash):
            return official.load_official_candidate(self.data if source is None else source)

    def test_metadata_is_not_authentication(self):
        index = self.load_test_source()
        report = index.report()
        self.assertEqual(6236, report["verse_count"])
        self.assertEqual(self.hash, report["raw_sha256"])
        self.assertEqual("tanzil_domain_unattested_export", report["source_kind"])
        self.assertFalse(report["source_authenticated"])
        self.assertFalse(report["rights_verified"])
        self.assertFalse(report["eligible_for_religious_ruling"])
        self.assertFalse(report["official_tanzil_bytes_independently_verified"])
        with self.assertRaises(TypeError):
            index.manifest["rights_status"] = "approved"

    def test_observation_metadata_points_to_existing_transport_report(self):
        from pathlib import Path
        with patch.object(official, "PINNED_OFFICIAL_DOMAIN_SHA256", self.hash):
            idx=official.load_official_candidate(self.data)
        rel=idx.manifest["source_observation"]
        self.assertEqual("docs/research/QURAN-Q01E-DOMAIN-PROBE.md",rel)
        root=Path(__file__).resolve().parents[2]
        self.assertTrue((root/rel).is_file())

    def test_byte_drift_rejected_even_if_verses_are_plausible(self):
        altered = self.data.replace("مِثَالٌ".encode(), "حَقِيقِيٌّ".encode(), 1)
        with patch.object(official, "PINNED_OFFICIAL_DOMAIN_SHA256", self.hash):
            with self.assertRaises(official.OfficialSourceError):
                official.load_official_candidate(altered)

    def test_official_raw_must_contain_preserved_copyright_anchor(self):
        modified = self.data.replace(b"# PLEASE DO NOT REMOVE OR CHANGE THIS COPYRIGHT BLOCK",
                                     b"# generic notice")
        with patch.object(official, "PINNED_OFFICIAL_DOMAIN_SHA256", sha256(modified).hexdigest()):
            with self.assertRaises(official.OfficialSourceError):
                official.load_official_candidate(modified)

    def test_incomplete_and_reordered_sources_rejected(self):
        text=self.data.decode("utf-8")
        partial=text.replace("1|2|", "1|3|", 1)
        for raw in (partial.encode("utf-8"), self.data.split(b"\n",1)[1], b"<html>ERROR</html>"):
            with self.subTest(length=len(raw)):
                with patch.object(official, "PINNED_OFFICIAL_DOMAIN_SHA256", sha256(raw).hexdigest()):
                    with self.assertRaises(official.OfficialSourceError):
                        official.load_official_candidate(raw)

    def test_index_can_serve_from_exact_preloaded_raw_only(self):
        from engines.quran.q01c.reader import build_http_server
        with patch.object(official, "PINNED_OFFICIAL_DOMAIN_SHA256", self.hash):
            index=official.load_official_candidate(self.data)
            server=build_http_server(index,self.data,port=0)
            try:
                self.assertEqual("مِثَالٌ اصْطِنَاعِيٌّ لِلِاخْتِبَارِ",index.get("2:1")["text"])
                self.assertEqual(6236,len(index.verses))
            finally:
                server.server_close()

    def test_unsupported_official_index_constructor_forgery_rejected(self):
        from engines.quran.q01c.reader import build_http_server
        from engines.quran.q01b.tanzil import SourceIndex
        from types import MappingProxyType
        with patch.object(official, "PINNED_OFFICIAL_DOMAIN_SHA256", self.hash):
            idx=official.load_official_candidate(self.data)
            evil=SourceIndex(MappingProxyType({**idx.manifest,"source_id":"attacker"}),idx.verses,idx.raw_sha256)
            with self.assertRaises(Exception):
                build_http_server(evil,self.data,port=0)

    def test_full_pinned_candidate_http_retrieval_and_tafsir_metadata(self):
        """Synthetic FULL fixture exercises runtime with no external Quran texts."""
        import http.client
        import threading
        from engines.quran.q01c.reader import build_http_server
        with patch.object(official, "PINNED_OFFICIAL_DOMAIN_SHA256", self.hash):
            index=self.load_test_source()
            server=build_http_server(index,self.data,port=0)
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            try:
                def query(path, headers=None):
                    conn=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=5)
                    try:
                        conn.request("GET",path,headers=headers or {})
                        resp=conn.getresponse()
                        return resp.status,dict(resp.getheaders()),resp.read()
                    finally:
                        conn.close()
                self.assertEqual("127.0.0.1",server.server_address[0])
                status,headers,body=query("/api/status")
                self.assertEqual(200,status)
                data=json.loads(body)
                self.assertEqual("observed_tanzil_domain_unattested",data["display_provenance"])
                self.assertFalse(data["official_tanzil_bytes_independently_verified"])
                self.assertFalse(data["source_authenticated"])
                self.assertFalse(data["rights_verified"])
                self.assertEqual(6236,data["verse_count"])
                status,headers,body=query("/api/get?ref=2%3A1")
                self.assertEqual(200,status)
                self.assertEqual("مِثَالٌ اصْطِنَاعِيٌّ لِلِاخْتِبَارِ",
                                 json.loads(body)["result"]["text"])
                self.assertEqual("no-store",headers["Cache-Control"])
                self.assertEqual("no-referrer",headers["Referrer-Policy"])
                status,_,body=query("/api/tafsir-catalog?ref=2%3A1")
                self.assertEqual(200,status)
                catalog=json.loads(body)
                self.assertEqual(6,len(catalog["sources"]))
                for field in ("rights_verified","source_authenticated",
                              "redistribution_approved","juristic_inference_allowed",
                              "scholarly_verified","public_fatwa_authorized",
                              "text_import_allowed","p1_admitted"):
                    self.assertFalse(catalog[field],field)
                self.assertEqual(
                    "https://quran.ksu.edu.sa/index.php#aya=2_1&m=hafs",
                    catalog["links"]["choose_tafsir"])
                status,_,body=query("/api/notice")
                self.assertEqual(200,status)
                self.assertIn("PLEASE DO NOT REMOVE",
                              json.loads(body)["notice"])
                status,_,body=query("/api/status",headers={"Host":"evil.example"})
                self.assertEqual(403,status)
                status,_,body=query("/api/tafsir-catalog?ref=1%3A99")
                self.assertEqual(400,status)
                status,_,body=query("/api/tafsir-catalog?ref=2%3A1%0a")
                self.assertEqual(400,status)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_forged_direct_source_manifest_cannot_self_attest(self):
        from engines.quran.q01b.tanzil import SourceIndex, RawSourceError
        from engines.quran.q01c.reader import build_http_server
        from types import MappingProxyType
        with patch.object(official, "PINNED_OFFICIAL_DOMAIN_SHA256", self.hash):
            good=self.load_test_source()
            impostor=SourceIndex(
                MappingProxyType({**good.manifest,"rights_status":"approved"}),
                good.verses, good.raw_sha256)
            with self.assertRaises(RawSourceError):
                build_http_server(impostor,self.data,port=0)
            impostor2=SourceIndex(
                good.manifest,
                ((1,1,"نص غير مستمد من البايتات المثبتة"),),
                good.raw_sha256)
            with self.assertRaises(RawSourceError):
                build_http_server(impostor2,self.data,port=0)

    def test_direct_reader_cannot_serve_wrong_bytes_even_with_forged_index(self):
        from engines.quran.q01c.reader import build_http_server
        from engines.quran.q01b.tanzil import RawSourceError
        with patch.object(official, "PINNED_OFFICIAL_DOMAIN_SHA256", self.hash):
            index=self.load_test_source()
            altered=self.data.replace("مِثَالٌ".encode(),"مُفْتَرًى".encode(),1)
            with self.assertRaises(RawSourceError):
                build_http_server(index,altered,port=0)

    def test_q01f_navigation_is_only_for_prevalidated_sources(self):
        from engines.quran.tafsir.catalog import catalog_for_ref,CatalogError
        output=catalog_for_ref("2:1","tanzil_domain_unattested_export")
        self.assertEqual(6,len(output["sources"]))
        self.assertFalse(output["edition_verified"])
        self.assertFalse(output["scholarly_verification"])
        with self.assertRaises(CatalogError):
            catalog_for_ref("2:1","synthetic_fixture")

    def test_download_failure_and_mismatch_do_not_start_server(self):
        for fetcher in (lambda method: b"bad", lambda method: (_ for _ in ()).throw(OSError("down"))):
            with self.subTest(fetcher=fetcher):
                with self.assertRaises(official.OfficialSourceError):
                    official.obtain_official_index(fetcher=fetcher)

    def test_download_exact_pinned_official_does_not_write_file(self):
        with patch.object(official, "PINNED_OFFICIAL_DOMAIN_SHA256", self.hash):
            idx, raw = official.obtain_official_index(fetcher=lambda method:self.data)
            self.assertIs(raw, self.data)
            self.assertEqual(6236, idx.report()["verse_count"])
            self.assertFalse(idx.report()["source_authenticated"])
            self.assertEqual("unverified_tanzil_domain_response", idx.manifest["authority_status"])


if __name__=="__main__":
    unittest.main()
