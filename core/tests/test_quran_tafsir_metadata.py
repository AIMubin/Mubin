"""Metadata-only Quran tafsir catalog tests; no tafsir text or legal approval."""
from __future__ import annotations
import copy
import json
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from hashlib import sha256

from engines.quran.tafsir.catalog import (load_catalog, validate_catalog,
    catalog_for_ref, CatalogError, ksu_links)
from engines.quran.q01b.tanzil import load_raw
from engines.quran.q01c.reader import build_http_server


DATA_PATH = Path(__file__).resolve().parents[2] / "engines/quran/tafsir/tafsir-catalog-v01.json"
SAMPLE = "1|1|مَثَالٌ اصطناعيٌّ للفحص\n".encode("utf-8")

def fixture_index():
    manifest = {
      "contract":"mubin-quran-q01b-verbatim-source-v1",
      "source_kind":"synthetic_fixture", "source_id":"synthetic:q01b",
      "source_url":None, "source_commit":None, "source_git_blob_sha1":None,
      "raw_sha256":sha256(SAMPLE).hexdigest(), "raw_byte_count":len(SAMPLE),
      "coverage":"partial", "reading":"hafs_an_asim_kufan",
      "rights_status":"requires_use_review", "authority_status":"not_authenticated"}
    return load_raw(json.dumps(manifest).encode(), SAMPLE)


class TafsirSourceCatalogTests(unittest.TestCase):
    def test_six_metadata_only_candidates(self):
        d = load_catalog()
        self.assertEqual("mubin-tafsir-metadata-v0.1", d["contract"])
        self.assertEqual(6, len(d["sources"]))
        self.assertEqual(6, len({x["id"] for x in d["sources"]}))
        for source in d["sources"]:
            self.assertTrue(source["title_ar"])
            self.assertIsNone(source["edition"])
            self.assertEqual("not_verified",source["rights_status"])
            self.assertEqual("metadata_only_unreviewed",source["source_status"])
            self.assertFalse(source["text_ingested"])
            self.assertFalse(source["allowed_for_local_quotation"])
            self.assertFalse(source["p1_eligible"])
            self.assertEqual("ksu_navigation_not_book_text",source["link_scope"])
            self.assertNotIn("text",source)
            self.assertNotIn("quote",source)
        self.assertEqual("https://quran.ksu.edu.sa/index.php",d["platform"]["navigation_base"])

    def test_unrecognized_authority_fields_fail_closed(self):
        d = copy.deepcopy(load_catalog())
        d["sources"][0]["rights_verified"] = True
        with self.assertRaises(CatalogError):
            validate_catalog(d)

    def test_cannot_turn_on_import_or_p1_admission(self):
        for prop in ("text_ingested","allowed_for_local_quotation","p1_eligible"):
            d = copy.deepcopy(load_catalog())
            d["sources"][1][prop] = True
            with self.subTest(prop=prop), self.assertRaises(CatalogError):
                validate_catalog(d)

    def test_editions_and_source_rights_must_not_be_invented(self):
        for prop,value in (("edition","2026 edition"),("rights_status","approved"),
                           ("source_status","qualified")):
            d = copy.deepcopy(load_catalog())
            d["sources"][1][prop] = value
            with self.subTest(prop=prop), self.assertRaises(CatalogError):
                validate_catalog(d)

    def test_url_allowlist_and_ids(self):
        d = copy.deepcopy(load_catalog())
        d["platform"]["navigation_base"]="https://attacker.example/"
        with self.assertRaises(CatalogError):
            validate_catalog(d)
        d=copy.deepcopy(load_catalog())
        d["sources"][1]["id"] = d["sources"][0]["id"]
        with self.assertRaises(CatalogError):
            validate_catalog(d)

    def test_extra_script_or_prose_fields_blocked(self):
        d=copy.deepcopy(load_catalog())
        d["sources"][0]["description_html"]="<iframe src='evil'>"
        with self.assertRaises(CatalogError):
            validate_catalog(d)

    def test_quran_reference_navigation_and_no_book_specific_fake_link(self):
        links=ksu_links("2:1")
        self.assertEqual("https://quran.ksu.edu.sa/index.php#aya=2_1&m=hafs&qaree=husary&trans=ar_mu",links["muyassar"])
        self.assertEqual("https://quran.ksu.edu.sa/index.php#aya=2_1&m=hafs",links["choose_tafsir"])
        self.assertFalse("tabari" in str(links).lower())
        for ref in ("00:1","1:99","115:1","2:0001","1:1#evil","<script>"):
            with self.subTest(ref=ref), self.assertRaises(CatalogError):
                ksu_links(ref)

    def test_only_real_record_sources_get_catalog(self):
        d=catalog_for_ref("2:1","unverified_github_mirror")
        self.assertEqual(6,len(d["sources"]))
        self.assertEqual("2:1",d["reference"])
        self.assertEqual("external_navigation_only",d["use_scope"])
        self.assertFalse(d["text_import_allowed"])
        self.assertFalse(d["scholarly_verification"])
        self.assertFalse(d["p1_admitted"])
        with self.assertRaises(CatalogError):
            catalog_for_ref("2:1","synthetic_fixture")
        with self.assertRaises(CatalogError):
            catalog_for_ref("2:1","mystery")
        with self.assertRaises(CatalogError):
            catalog_for_ref("1:8","unverified_github_mirror")

    def test_duplicate_json_key_is_rejected_without_rights_promotion(self):
        from unittest.mock import patch
        base=DATA_PATH.read_bytes()
        altered=base.replace(b'"sources": [',b'"sources": [], "sources": [',1)
        with patch("engines.quran.tafsir.catalog.Path.read_bytes",return_value=altered):
            with self.assertRaises(CatalogError):
                load_catalog()

    def test_korean_or_untrusted_html_labels_rejected(self):
        for label in ("<iframe>تفسير</iframe>", "x", "English only",
                      "تفسير\\nمزيف", "  تفسير", "تفسير{evil}", "تفسير\\u202eمقلوب"):
            bad=copy.deepcopy(load_catalog())
            bad["sources"][0]["title_ar"]=label
            with self.subTest(label=repr(label)), self.assertRaises(CatalogError):
                validate_catalog(bad)

    def test_frontend_external_link_trust_boundary(self):
        script=(DATA_PATH.parents[3]/"engines/quran/q01c/reader.js").read_text(encoding="utf-8")
        self.assertIn("/api/tafsir-catalog?ref=",script)
        self.assertIn("sourceType!==\"unverified_github_mirror\"",script)
        self.assertIn('a.rel="noopener noreferrer"',script)
        self.assertIn('a.referrerPolicy="no-referrer"',script)
        self.assertIn("panel.isConnected",script)
        self.assertIn("d.rights_verified!==false",script)
        self.assertIn("d.redistribution_approved!==false",script)
        self.assertIn("d.public_fatwa_authorized!==false",script)
        self.assertIn("d.text_import_allowed!==false",script)
        self.assertNotIn(".innerHTML",script)
        self.assertNotIn("fetch(KSU_BASE",script)
        self.assertNotIn("document.write(",script)

    def test_metadata_only_response_never_contains_tafsir_text(self):
        output=catalog_for_ref("114:6","unverified_github_mirror")
        self.assertEqual(6,len(output["sources"]))
        self.assertEqual("114:6",output["reference"])
        self.assertFalse(output["ai_tafsir_generated"])
        self.assertFalse(output["p1_admitted"])
        self.assertFalse(output["rights_verified"])
        for key in ("source_authenticated","scholarly_verified",
                    "redistribution_approved","juristic_inference_allowed",
                    "public_fatwa_authorized"):
            self.assertFalse(output[key],key)
        self.assertNotIn("text",json.dumps(output,ensure_ascii=False).split('"sources":')[0])

    def test_fixture_browser_cannot_access_tafsir_endpoint(self):
        server=build_http_server(fixture_index(),SAMPLE,port=0)
        thread=threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            uri=f"http://127.0.0.1:{server.server_port}/api/tafsir-catalog?ref=1%3A1"
            with self.assertRaises(urllib.error.HTTPError) as raised:
                urllib.request.urlopen(uri,timeout=5)
            self.assertEqual(403,raised.exception.code)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__=="__main__":
    unittest.main()
