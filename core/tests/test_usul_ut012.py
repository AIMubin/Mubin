"""UT-01.2 strictly synthetic source-chain tests + historical receipt consistency."""
from __future__ import annotations

import copy
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
import unittest

from engines.tafsir.t02 import make_record, _catalog_authors
from engines.tafsir.t023 import identify_candidates
from engines.usul import ut012
from engines.usul.concept_rule_catalog import (
    GRAPH_FIELDS, build_catalog, canonical,
)

ROOT = Path(__file__).resolve().parents[2]
RULE = "candidate:amr-structural-hypothesis"
POINTER = "pilot:amr-rule-research-pointer"
STATEMENT = (
    "قال المفسرون في قوله تعالى: وأقيموا الصلاة. "
    "ودلت الآية على أمر فعل الصلاة بيانا للمعنى. "
    "وقيل في القرينة قول الآخر."
)
PREFIX = "<html>بداية اصطناعية</html> \n"


def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def tafsir_pair():
    full = PREFIX + STATEMENT
    digest = sha(full)
    passage = make_record(
        quran_reference="2:43", work_id="tafsir_tabari",
        author_id=_catalog_authors()["tafsir_tabari"],
        source_record_id="tafsir:tafsir_tabari:2:43:" + digest,
        source_sha256=digest, original_text=full,
        span=(len(PREFIX),len(full)))
    return full, passage, identify_candidates(passage)[0]


def usul_pair():
    sid="section:w1"
    qid="query:amr"
    pointer_node="pointer:amr"
    witness="witness:w1"
    occurrence="occurrence:w1"
    other_query="query:other"
    other_occ="occurrence:other"
    g={
        "engine":"usul-evidence-context-graph/0.1.0",
        "status":"EVIDENCE_CONTEXT_GRAPH_PASS",
        "scope":"PINNED_TEXT_OBSERVATION_AND_RESEARCH_NAVIGATION_ONLY",
        "stage07_engine":"synthetic-stage07",
        "stage07_witness_count":1, "context_radius_lines":1,
        "nodes":[
            {"id":witness, "kind":"SOURCE_WITNESS",
             "source_id":"pilot:waraqat-primary"},
            {"id":sid, "kind":"PINNED_SECTION",
             "source_id":"pilot:waraqat-primary",
             "section_sha256":sha("synthetic source section"),
             "offset_basis":"utf8_export", "source_byte_base":3735,
             "byte_length":1232},
            {"id":qid, "kind":"SEARCH_QUERY",
             "query_id":"pilot:amr-term","witness_id":"pilot:waraqat-primary"},
            {"id":other_query,"kind":"SEARCH_QUERY",
             "query_id":"pilot:other","witness_id":"pilot:waraqat-primary"},
            {"id":pointer_node, "kind":"RULE_RESEARCH_POINTER",
             "pointer_id":POINTER,
             "reference_id":"pilot:rule-amr-default",
             "review_status":"UNASSESSED",
             "rule_application_verified":False},
            {"id":occurrence, "kind":"TEXT_OCCURRENCE",
             "section_id":sid, "section_byte_start":100,
             "section_byte_end_exclusive":140,
             "source_coordinate_basis":"utf8_export",
             "original_span_sha256":sha("شاهد اصطناعي"),
             "text_included":False,
             "semantic_classification":"NOT_EVALUATED"},
            {"id":other_occ,"kind":"TEXT_OCCURRENCE",
             "section_id":sid,"section_byte_start":150,
             "section_byte_end_exclusive":160,
             "source_coordinate_basis":"utf8_export",
             "original_span_sha256":sha("آخر"),
             "text_included":False,
             "semantic_classification":"NOT_EVALUATED"},
        ],
        "edges":[
            {"kind":"WITNESS_HAS_PINNED_SECTION","from":witness,"to":sid},
            {"kind":"QUERY_SCOPED_TO_SECTION","from":qid,"to":sid},
            {"kind":"QUERY_SCOPED_TO_SECTION","from":other_query,"to":sid},
            {"kind":"RESEARCH_NAVIGATION_ONLY","from":pointer_node,"to":qid,
             "no_claim_of_support":True, "no_claim_of_exception":True},
            {"kind":"QUERY_LOCATES_OCCURRENCE","from":qid,
             "to":occurrence,"classification":"EXACT_LITERAL_ONLY",
             "semantic_equivalence_verified":False},
            {"kind":"QUERY_LOCATES_OCCURRENCE","from":other_query,
             "to":other_occ,"classification":"EXACT_LITERAL_ONLY",
             "semantic_equivalence_verified":False},
        ],
        "nodes_by_kind":{}, "edges_by_kind":{},
        "all_edge_references_valid":True,
        "source_text_included":False,
        "lexical_matches_promoted_to_rules":False,
        "rule_support_attested":False,
        "objection_presence_attested":False,
        "semantic_qarinah_verified":False,
        "juristic_inference_allowed":False,
        "scholarly_verified":False,
        "redistribution_approved":False,
    }
    digest=hashlib.sha256(canonical({k:g[k] for k in GRAPH_FIELDS})).hexdigest()
    g["graph_sha256"]=digest
    manifest={
        "schema_version":"u0.2.0",
        "concepts":[
            {"id":"concept:amr-term","concept_kind":"TERM",
             "review_status":"UNASSESSED"},
            {"id":"concept:qarinah-candidate","concept_kind":"EXCEPTION",
             "review_status":"UNASSESSED"},
            {"id":"concept:wujub-candidate","concept_kind":"OUTCOME",
             "review_status":"UNASSESSED"},
        ],
        "rule_candidates":[
            {"id":RULE,"pointer_id":POINTER,
             "if_concepts":["concept:amr-term"],
             "unless_concepts":["concept:qarinah-candidate"],
             "then_concept":"concept:wujub-candidate",
             "review_status":"UNASSESSED"}
        ],
        "relations":[],
    }
    c=build_catalog(g,digest,manifest)
    return g,c,occurrence,other_occ


class UT012Tests(unittest.TestCase):
    def setUp(self):
        self.raw,self.p,self.c=tafsir_pair()
        self.g,self.catalog,self.occ,self.other=usul_pair()
        self.pc=patch.object(ut012,"TRUSTED_CATALOG_SHA256",
                             self.catalog["catalog_sha256"])
        self.pg=patch.object(ut012,"TRUSTED_GRAPH_SHA256",
                             self.g["graph_sha256"])
        self.pc.start()
        self.pg.start()
        self.addCleanup(self.pc.stop)
        self.addCleanup(self.pg.stop)

    def build(self,**change):
        args={
            "quran_reference":"2:43",
            "tafsir_candidate":self.c,
            "tafsir_passage":self.p,
            "tafsir_original_raw_text":self.raw,
            "usul_catalog":self.catalog,
            "usul_graph":self.g,
            "rule_candidate_id":RULE,
            "research_pointer_id":POINTER,
        }
        args.update(change)
        return ut012.build_link(**args)

    def check(self,record,**change):
        args={
            "tafsir_candidate":self.c,
            "tafsir_passage":self.p,
            "tafsir_original_raw_text":self.raw,
            "usul_catalog":self.catalog,
            "usul_graph":self.g,
        }
        args.update(change)
        return ut012.validate_link(record,**args)

    def assertRefused(self, **change):
        with self.assertRaises(ut012.UsulTafsirLinkError):
            self.build(**change)

    def test_undetermined_source_bound_metadata(self):
        x=self.build()
        self.assertEqual("UNDETERMINED",x["link_status"])
        self.assertEqual(ut012.TRUSTED_CATALOG_SHA256,x["usul_catalog_sha256"])
        self.assertEqual(ut012.TRUSTED_GRAPH_SHA256,x["usul_stage08_graph_sha256"])
        self.assertTrue(x["tafsir_source_binding_verified"])
        self.assertTrue(x["usul_source_binding_verified"])
        self.assertFalse(x["scholarly_verified"])
        self.check(x)

    def test_candidate_requires_both_reason_and_scope(self):
        x=self.build(candidacy_reason="lexical cue only",
                     candidacy_scope="RESEARCH_ONLY")
        self.assertEqual("CANDIDATE_RELATED",x["link_status"])
        self.check(x)
        self.assertRefused(candidacy_reason="bare assertion")
        self.assertRefused(candidacy_scope="RESEARCH_ONLY")

    def test_rejects_unsupported_grade(self):
        x=self.build()
        for flag in ("scholarly_verified","rule_application_verified",
                     "cross_source_semantic_equivalence_verified",
                     "juristic_inference_allowed","public_fatwa_authorized",
                     "text_included","p1_admitted"):
            with self.subTest(flag=flag):
                with self.assertRaises(ut012.UsulTafsirLinkError):
                    self.check({**x,flag:True})

    def test_candidate_raw_offsets_are_absolute_not_relative(self):
        x=self.build()
        self.assertEqual(self.c["raw_source_span"],
                         x["tafsir_raw_source_span"])
        self.assertGreater(x["tafsir_raw_source_span"][0],len(PREFIX)-1)
        self.assertEqual(["UNICODE_CODEPOINT_OFFSETS_IN_IMPORTED_RAW_TEXT",
                          "UTF8_BYTES"],x["offset_units_independent"])

    def test_source_byte_tamper_refused(self):
        self.assertRefused(tafsir_original_raw_text=self.raw+"corrupt")

    def test_tafsir_evidence_sha_tamper_refused(self):
        c=copy.deepcopy(self.c)
        c["evidence_sha256"]="f"*64
        self.assertRefused(tafsir_candidate=c)

    def test_tafsir_wrong_source_refused(self):
        c=copy.deepcopy(self.c)
        c["source_sha256"]="f"*64
        self.assertRefused(tafsir_candidate=c)

    def test_forged_passage_id_refused(self):
        p=copy.deepcopy(self.p)
        p["interpretation_id"]="interp:"+"a"*40
        self.assertRefused(tafsir_passage=p)

    def test_forged_classification_rejected_even_with_same_digest(self):
        c=copy.deepcopy(self.c)
        c["interpretation_type"]="LEGAL_INTERPRETATION"
        self.assertRefused(tafsir_candidate=c)

    def test_reject_different_reference(self):
        self.assertRefused(quran_reference="3:1")

    def test_graph_external_pin_refused(self):
        with patch.object(ut012,"TRUSTED_GRAPH_SHA256","0"*64):
            self.assertRefused()

    def test_catalog_external_pin_refused(self):
        with patch.object(ut012,"TRUSTED_CATALOG_SHA256","0"*64):
            self.assertRefused()

    def test_catalog_payload_mutation_refused_even_if_stamp_unchanged(self):
        modified=copy.deepcopy(self.catalog)
        modified["concepts"][0]["concept_kind"]="CONDITION"
        self.assertRefused(usul_catalog=modified)

    def test_rule_ghost_refused(self):
        self.assertRefused(rule_candidate_id="candidate:ghost")

    def test_pointer_ghost_refused(self):
        self.assertRefused(research_pointer_id="pointer:ghost")

    def test_occurrence_exact_query_valid(self):
        x=self.build(occurrence_ids=[self.occ])
        self.assertEqual([self.occ],x["usul_occurrence_ids"])
        self.check(x)

    def test_occurrence_wrong_query_refused(self):
        self.assertRefused(occurrence_ids=[self.other])

    def test_occurrence_ghost_refused(self):
        self.assertRefused(occurrence_ids=["occurrence:missing"])

    def test_occurrence_bad_byte_coordinate_refused(self):
        g=copy.deepcopy(self.g)
        n=next(z for z in g["nodes"] if z.get("id")==self.occ)
        n["section_byte_end_exclusive"]=3000
        # Broken graph digest is independently rejected; an adversary
        # cannot merely repair it and bypass the accepted historical pin.
        self.assertRefused(usul_graph=g)

    def test_record_field_tampering_detected(self):
        original=self.build()
        for changes in (
            {"tafsir_raw_source_span":[0,10]},
            {"usul_section_sha256":"0"*64},
            {"tafsir_evidence_sha256":"0"*64},
            {"verification_status":"VERIFIED"},
            {"usul_occurrence_span_unit":"UNICODE_CODEPOINTS"},
            {"link_id":"utl:"+"0"*40},
            {"extra":"hidden"},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(ut012.UsulTafsirLinkError):
                    self.check({**original,**changes})

    def test_empty_reason_and_bogus_scope_refused(self):
        self.assertRefused(candidacy_reason=" ",
                           candidacy_scope="RESEARCH_ONLY")
        self.assertRefused(candidacy_reason="text",candidacy_scope=" ")

    def test_rejection_record_distinct_and_valid(self):
        x=ut012.reject_link(quran_reference="2:43",
                            rejection_reason="source byte mismatch")
        self.assertEqual("REJECTED",x["link_status"])
        ut012.validate_link(x)
        with self.assertRaises(ut012.UsulTafsirLinkError):
            ut012.validate_link({**x,"rejection_reason":"other"})

    def test_determinism_and_pure_metadata(self):
        a=self.build(candidacy_reason="lexical only",candidacy_scope="UNASSESSED")
        b=self.build(candidacy_reason="lexical only",candidacy_scope="UNASSESSED")
        self.assertEqual(a,b)
        dumped=json.dumps(a,ensure_ascii=False)
        self.assertNotIn(STATEMENT,dumped)
        self.assertNotIn(PREFIX,dumped)
        self.assertFalse(a["text_included"])

    def test_historical_real_receipt_is_not_independent_ci_replay(self):
        report=json.loads((ROOT/"evaluation"/"evidence"/
                           "ut012_case_a_real_link.json").read_text(encoding="utf-8"))
        historical=json.loads((ROOT/"evaluation"/"evidence"/
                           "ut011_bab_amr_bridge_report.json").read_text(encoding="utf-8"))
        self.assertEqual("UNDETERMINED",report["link_status"])
        self.assertEqual(historical["catalog_sha256"],report["catalog_sha256"])
        self.assertEqual(historical["stage08_graph_sha256"],
                         report["stage08_graph_sha256"])
        self.assertEqual(historical["lexical_bindings"][0]["section_sha256"],
                         report["usul_section_sha256"])
        self.assertFalse(report["scholarly_verified"])
        self.assertNotIn(STATEMENT,json.dumps(report,ensure_ascii=False))


if __name__=="__main__":
    unittest.main()
