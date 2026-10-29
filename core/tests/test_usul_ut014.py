"""UT-01.4 metadata-only bundle, source replay and display contract tests."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from engines.usul.ut014 import (
    load_usul_evidence, usul_research_section, UsulPresentationError,
    EVIDENCE_LEVELS, USUL_LINK_MAX_LEVEL,
)
from engines.usul.ut012 import TRUSTED_CATALOG_SHA256, TRUSTED_GRAPH_SHA256


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class UsulPresentationTests(unittest.TestCase):
    def setUp(self):
        self.td=tempfile.TemporaryDirectory()
        self.addCleanup(self.td.cleanup)
        self.root=Path(self.td.name)
        self.section=b"synthetic not a book section"
        (self.root/"section.bin").write_bytes(self.section)
        self.bundle={
            "usul_rule_candidate_id":"candidate:amr-structural-hypothesis",
            "usul_research_pointer_id":"pilot:amr-rule-research-pointer",
            "catalog_sha256":TRUSTED_CATALOG_SHA256,
            "graph_sha256":TRUSTED_GRAPH_SHA256,
            "usul_source_id":"pilot:waraqat-primary",
            "usul_work_id":"0276Juwayni.Waraqat",
            "usul_section_path":str(self.root/"section.bin"),
            "usul_section_sha256":sha(self.section),
            "query_terms":["الأمر"],
        }
        for key in ("waraqat_primary_html","waraqat_primary_export",
                    "waraqat_primary_manifest","waraqat_primary_section",
                    "waraqat_secondary_html","waraqat_secondary_section"):
            p=self.root/(key+".txt")
            p.write_text("synthetic only",encoding="utf-8")
            self.bundle[key]=str(p)
        self.path=self.root/"bundle.json"
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.bundle,ensure_ascii=False),
                             encoding="utf-8")

    def test_frozen_pins_and_numeric_historical_work_id(self):
        self.assertEqual(self.bundle,load_usul_evidence(self.path))

    def test_forbidden_text_and_authority_flags_rejected(self):
        for key in ("text","passage_text","scholarly_verified",
                    "public_fatwa_authorized","candidacy_reason",
                    "new_untrusted_field"):
            with self.subTest(key=key):
                self.bundle[key]="SECRET SOURCE TEXT"
                self.save()
                with self.assertRaises(UsulPresentationError):
                    load_usul_evidence(self.path)
                self.bundle.pop(key)
        self.save()

    def test_missing_pin_and_mismatched_digest_rejected(self):
        del self.bundle["catalog_sha256"]
        self.save()
        with self.assertRaises(UsulPresentationError):
            load_usul_evidence(self.path)
        self.bundle["catalog_sha256"]="a"*64
        self.save()
        with self.assertRaises(UsulPresentationError):
            load_usul_evidence(self.path)

    def test_symlink_and_missing_private_file_rejected(self):
        self.bundle["waraqat_primary_section"]=str(
            self.root/"not_existing_private_source")
        self.save()
        with self.assertRaises(UsulPresentationError):
            load_usul_evidence(self.path)

    def test_duplicate_json_field_rejected(self):
        self.path.write_text('{"catalog_sha256":"a","catalog_sha256":"b"}',
                             encoding="utf-8")
        with self.assertRaises(UsulPresentationError):
            load_usul_evidence(self.path)

    def test_query_term_array_is_bounded(self):
        self.bundle["query_terms"]=["الأمر","القرينة"]
        self.save()
        with self.assertRaises(UsulPresentationError):
            load_usul_evidence(self.path)

    def test_five_levels_with_non_normative_cap(self):
        self.assertEqual(len(EVIDENCE_LEVELS),5)
        self.assertEqual(USUL_LINK_MAX_LEVEL,"AUTOMATED_CANDIDATE")
        self.assertEqual(EVIDENCE_LEVELS[-2:],
                         ("TEXTUALLY_ATTRIBUTED","SCHOLARLY_VERIFIED"))

    def test_every_candidate_preserved_and_nested_link_display_correct(self):
        graph={
            "graph_sha256":TRUSTED_GRAPH_SHA256,
            "nodes":[{"kind":"PINNED_SECTION","source_id":"pilot:waraqat-primary",
                      "section_sha256":sha(self.section),
                      "byte_length":len(self.section)}],
        }
        catalog={"catalog_sha256":TRUSTED_CATALOG_SHA256}
        def fake(candidate, **kwargs):
            identity=candidate["candidate_id"]
            return {
                "link_id":"utl:"+identity,
                "link_status":"UNDETERMINED",
                "link":{
                    "link_id":"utl:"+identity,
                    "link_status":"UNDETERMINED",
                    "tafsir_candidate_id":identity,
                    "tafsir_passage_id":"interp:synthetic",
                    "tafsir_work_id":"tafsir_tabari",
                    "usul_rule_candidate_id":"candidate:amr-structural-hypothesis",
                    "usul_research_pointer_id":"pilot:amr-rule-research-pointer",
                    "verification_status":"UNVERIFIED",
                    "link_method":"EVIDENCE_CHAIN_VERIFICATION_ONLY",
                },
                "matching":{
                    "tie_level":"NONE",
                    "tafsir_raw_source_span":None,
                    "tafsir_tie":{"digest":None},
                    "usul_section_relative_byte_span":None,
                    "usul_tie_utf8":{"digest":None},
                    "tafsir_span_unit":"UNICODE_CODEPOINT_OFFSETS_IN_IMPORTED_RAW_TEXT",
                    "usul_span_unit":"UTF8_BYTES",
                },
                "qarinah":{"status":"NOT_OBSERVED_IN_SCOPE"},
                "scholarly_verified":False,
                "rule_application_verified":False,
                "text_included":False,
            }
        items=[{"candidate":{"candidate_id":f"cand:{i}"},
                "passage":{"passage_id":"same-source"},
                "original_raw_text":"PRIVATE SOURCE"} for i in range(7)]
        with patch("engines.usul.pilots.waraqat_stage08.replay_and_graph",
                   return_value=graph), \
             patch("engines.usul.ut014.build_catalog",
                   return_value=catalog), \
             patch("engines.usul.ut014.match_candidate",
                   side_effect=fake):
            result=usul_research_section(self.path,tafsir_items=items)
        self.assertEqual(7,result["counts"]["matches_total"])
        self.assertEqual(7,len(result["links_redacted"]))
        self.assertEqual("cand:6",result["links_redacted"][-1]["tafsir_candidate_id"])
        self.assertEqual("NONE",result["links_redacted"][0]["tie_level"])
        self.assertEqual("AUTOMATED_CANDIDATE",
                         result["links_redacted"][0]["evidence_level"])
        self.assertEqual("EVIDENCE_CHAIN_VERIFICATION_ONLY",
                         result["links_redacted"][0]["link_method"])
        self.assertFalse(result["scholarly_verified"])
        dumped=json.dumps(result,ensure_ascii=False)
        self.assertNotIn("PRIVATE SOURCE",dumped)
        self.assertNotIn(str(self.root),dumped)

    def test_mutated_raw_source_rejected_before_matching(self):
        self.bundle["usul_section_sha256"]="a"*64
        self.save()
        graph={"graph_sha256":TRUSTED_GRAPH_SHA256,
               "nodes":[{"kind":"PINNED_SECTION",
                         "source_id":"pilot:waraqat-primary",
                         "section_sha256":"a"*64,
                         "byte_length":len(self.section)}]}
        with patch("engines.usul.pilots.waraqat_stage08.replay_and_graph",
                   return_value=graph), \
             patch("engines.usul.ut014.build_catalog",
                   return_value={"catalog_sha256":TRUSTED_CATALOG_SHA256}):
            with self.assertRaisesRegex(UsulPresentationError,
                                        "US014_USUL_SECTION_BYTES_CHANGED"):
                usul_research_section(self.path,tafsir_items=[])

    def test_one_bad_candidate_aborts_full_section(self):
        graph={"graph_sha256":TRUSTED_GRAPH_SHA256,
               "nodes":[{"kind":"PINNED_SECTION",
                         "source_id":"pilot:waraqat-primary",
                         "section_sha256":sha(self.section),
                         "byte_length":len(self.section)}]}
        def fail(**kwargs):
            raise RuntimeError("PRIVATE ERROR TEXT")
        with patch("engines.usul.pilots.waraqat_stage08.replay_and_graph",
                   return_value=graph), \
             patch("engines.usul.ut014.build_catalog",
                   return_value={"catalog_sha256":TRUSTED_CATALOG_SHA256}), \
             patch("engines.usul.ut014.match_candidate",side_effect=fail):
            with self.assertRaises(RuntimeError):
                usul_research_section(self.path,tafsir_items=[
                    {"candidate":{},"passage":{},"original_raw_text":"private"}])


if __name__=="__main__":
    unittest.main()
