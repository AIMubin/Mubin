"""Pinned, non-authoritative observation from one live Tanzil GET comparison."""
from __future__ import annotations
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
PATH=ROOT/"research/quran/q01d-tanzil-domain-20261018.json"
OFFICIAL_SHA="7f30c647331a61100ebf24a80507dc0fcdd9f2df97f1312b5b2dfcb982a7f326"
MIRROR_SHA="f64fe7657dbe2e185e9995e14f7a67ee6cf1a30773f39184883d7a763d70fb19"

class OfficialDomainReceiptTests(unittest.TestCase):
    def test_exact_observation_not_authentication(self):
        o=json.loads(PATH.read_text(encoding="utf-8"))
        self.assertEqual("mubin-q01d-tanzil-domain-observation-v1",o["contract"])
        self.assertEqual("2026-10-18",o["observed_date"])
        self.assertEqual(39155112593,o["evidence_run_id"])
        self.assertEqual("GET",o["request_method"])
        self.assertEqual("https://tanzil.net/pub/download/index.php",o["url"])
        self.assertEqual("uthmani",o["preset"]["quranType"])
        self.assertEqual("txt-2",o["preset"]["outType"])
        self.assertEqual(OFFICIAL_SHA,o["official_domain_observed_sha256"])
        self.assertEqual(MIRROR_SHA,o["mirror_raw_sha256"])
        self.assertEqual("verse_equal_bytes_different",o["comparison"])
        self.assertEqual(6236,o["verse_count"])
        self.assertEqual(0,o["different_verse_count"])
        for k in ("authenticated_publisher_artifact","independently_signed_by_publisher",
                  "rights_verified","eligible_for_religious_ruling","source_text_stored_in_repo"):
            self.assertIs(o[k],False,k)
        self.assertEqual(set(o),{
          "contract","observed_date","evidence_run_id","request_method","url",
          "preset","official_domain_observed_sha256","mirror_raw_sha256",
          "comparison","verse_count","different_verse_count",
          "authenticated_publisher_artifact","independently_signed_by_publisher",
          "rights_verified","eligible_for_religious_ruling","source_text_stored_in_repo"
        })

if __name__=="__main__":unittest.main()
