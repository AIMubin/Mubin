"""UT-01.3 adversarial synthetic matching tests; no private W1/Q0.3 bytes."""
from __future__ import annotations

import copy
import hashlib
import json
import unittest
from unittest.mock import patch

from engines.tafsir.t02 import make_record, _catalog_authors
from engines.tafsir.t023 import identify_candidates
from engines.usul import ut012
from engines.usul.ut013 import (
    TIE_EXACT, TIE_FOLDED, TIE_NONE,
    locate_term, locate_term_utf8_bytes, match_candidate,
    summarize, validate_match, REASON_PINNED_EXACT,
)
from engines.usul.concept_rule_catalog import (
    GRAPH_FIELDS, build_catalog, canonical,
)
from core.tests.test_usul_ut012 import usul_pair

TERM="الأمر"
PREFIX="بداية المصدر العربي الأصلي \n"
TAFSIR="قال المفسرون: الأمر يتعلق بدراسة نصوص التفسير لا بإصدار حكم."
TAFSIR_FOLDED="قال المفسرون: الأَمْرُ يتعلق بدراسة نصوص التفسير لا بإصدار حكم."
TAFSIR_NONE="قال المفسرون: النصوص المتعلقة بأمور البلاغة في هذا الباب."
TAFSIR_QARINAH=TAFSIR+" ويذكر النص القرينة من غير تحقق وظيفة فقهية."
USUL="هذا صدر الباب، الأمر يرد ضمن نص أصولي للاختبار التجريبي فقط."


def sha(data):
    return hashlib.sha256(data if type(data) is bytes
                           else data.encode("utf-8")).hexdigest()


def tafsir_pair(text=TAFSIR):
    raw=PREFIX+text
    digest=sha(raw)
    p=make_record(
        quran_reference="2:43",work_id="tafsir_tabari",
        author_id=_catalog_authors()["tafsir_tabari"],
        source_record_id="tafsir:tafsir_tabari:2:43:"+digest,
        source_sha256=digest, original_text=raw,
        span=(len(PREFIX),len(raw)))
    candidates=identify_candidates(p)
    assert candidates
    return raw,p,candidates[0]


def usul_sources(section_text=USUL):
    g,c,occ,other=usul_pair()
    raw=section_text.encode("utf-8")
    section=next(n for n in g["nodes"] if n.get("kind")=="PINNED_SECTION")
    section["section_sha256"]=sha(raw)
    section["byte_length"]=len(raw)
    query=next(n for n in g["nodes"] if n.get("kind")=="SEARCH_QUERY"
               and n.get("query_id")=="pilot:amr-term")
    query["query_utf8_sha256"]=sha(TERM)
    a=raw.find(TERM.encode("utf-8"))
    assert a>=0
    node=next(n for n in g["nodes"] if n.get("id")==occ)
    node.update({
        "section_byte_start":a,
        "section_byte_end_exclusive":a+len(TERM.encode("utf-8")),
        "source_coordinate_basis":"utf8_export",
        "original_span_sha256":sha(TERM),
        "text_included":False,
        "semantic_classification":"NOT_EVALUATED",
    })
    g["graph_sha256"]=sha(canonical({k:g[k] for k in GRAPH_FIELDS}))
    manifest={
        "schema_version":"u0.2.0",
        "concepts":c["concepts"],
        "rule_candidates":[
            {k:r[k] for k in ("id","pointer_id","if_concepts",
                               "unless_concepts","then_concept","review_status")}
            for r in c["rule_candidates"]
        ],
        "relations":c["relations"],
    }
    c=build_catalog(g,g["graph_sha256"],manifest)
    return raw,g,c,occ,other


class UnitLocationTests(unittest.TestCase):
    def test_exact_codepoints_and_original_sha(self):
        raw="مقدمة: " + TERM + " ختام"
        hit=locate_term(raw,TERM)
        self.assertEqual(TIE_EXACT,hit["tie"])
        a,b=hit["span"]
        self.assertEqual(TERM,raw[a:b])
        self.assertEqual(sha(raw[a:b]),hit["digest"])

    def test_folded_marks_are_mapped_to_raw_span_and_hash(self):
        raw="مقدمة: الأَمْرُ ختام"
        hit=locate_term(raw,TERM)
        self.assertEqual(TIE_FOLDED,hit["tie"])
        a,b=hit["span"]
        self.assertEqual("الأَمْر",raw[a:b])
        self.assertEqual(sha(raw[a:b]),hit["digest"])

    def test_original_utf8_byte_offset_both_profiles(self):
        for raw,kind in [("أول الباب: الأمر.",TIE_EXACT),
                         ("أول الباب: الأَمْرُ.",TIE_FOLDED)]:
            with self.subTest(raw=raw):
                encoded=raw.encode("utf-8")
                hit=locate_term_utf8_bytes(encoded,TERM)
                self.assertEqual(kind,hit["tie"])
                a,b=hit["span"]
                self.assertEqual(sha(encoded[a:b]),hit["digest"])
                self.assertGreater(a,len(raw[:raw.index("الأ")]))
                self.assertTrue(encoded[a:b].decode().startswith("الأ"))

    def test_rejects_subword_matches(self):
        self.assertEqual(TIE_NONE,locate_term("الأمرية ليست دليلًا",TERM)["tie"])
        self.assertEqual(TIE_NONE,locate_term("الأمور ليست الأمرية",TERM)["tie"])

    def test_conservative_fold_does_not_remove_hamza_or_normalize_alef(self):
        self.assertEqual(TIE_NONE,locate_term("الامر",TERM)["tie"])
        self.assertEqual(TIE_NONE,locate_term("ألأمر",TERM)["tie"])

    def test_malformed_utf8_rejected(self):
        with self.assertRaises(ut012.UsulTafsirLinkError):
            locate_term_utf8_bytes(b"\xff",TERM)

    def test_empty_term_refused(self):
        with self.assertRaises(ut012.UsulTafsirLinkError):
            locate_term("الأمر","")


class MatchingTests(unittest.TestCase):
    def setUp(self):
        self.raw,self.g,self.catalog,self.occ,self.other=usul_sources()
        self.pins=[
            patch.object(ut012,"TRUSTED_GRAPH_SHA256",self.g["graph_sha256"]),
            patch.object(ut012,"TRUSTED_CATALOG_SHA256",
                         self.catalog["catalog_sha256"]),
        ]
        for p in self.pins:
            p.start()
        self.addCleanup(lambda:[p.stop() for p in reversed(self.pins)])

    def build(self,text=TAFSIR,reason=None,scope=None,**changes):
        original,passage,candidate=tafsir_pair(text)
        params={
            "candidate":candidate,"passage":passage,
            "tafsir_raw_text":original,
            "usul_catalog":self.catalog,
            "usul_graph":self.g,
            "usul_raw_text":self.raw,
            "rule_candidate_id":"candidate:amr-structural-hypothesis",
            "research_pointer_id":"pilot:amr-rule-research-pointer",
            "rule_query_terms":[TERM],
            "candidacy_reason":reason,"candidacy_scope":scope,
        }
        params.update(changes)
        return match_candidate(**params),params

    def test_exact_tie_with_pinned_occurrence_and_reason(self):
        result,params=self.build(reason=REASON_PINNED_EXACT,
                                 scope="LEXICAL_NAVIGATION_ONLY")
        self.assertEqual("CANDIDATE_RELATED",result["link_status"])
        self.assertEqual(TIE_EXACT,result["matching"]["tie_level"])
        self.assertEqual([self.occ],result["link"]["usul_occurrence_ids"])
        self.assertEqual(self.occ,
                         result["matching"]["usul_exact_stage07_occurrence_id"])
        ut012.validate_link(result["link"],
            tafsir_candidate=params["candidate"],
            tafsir_passage=params["passage"],
            tafsir_original_raw_text=params["tafsir_raw_text"],
            usul_catalog=params["usul_catalog"],
            usul_graph=params["usul_graph"])
        validate_match(result,**params)

    def test_absent_reason_stays_undetermined_even_exact(self):
        result,_=self.build()
        self.assertEqual("UNDETERMINED",result["link_status"])
        self.assertEqual(TIE_EXACT,result["matching"]["tie_level"])
        self.assertIsNone(result["matching"]["usul_exact_stage07_occurrence_id"])

    def test_mark_folded_remains_undetermined_and_roundtrips(self):
        result,_=self.build(text=TAFSIR_FOLDED)
        self.assertEqual("UNDETERMINED",result["link_status"])
        self.assertEqual(TIE_FOLDED,result["matching"]["tie_level"])
        a,b=result["matching"]["tafsir_tie"]["span"]
        raw=TAFSIR_FOLDED[
            result["matching"]["tafsir_tie"]["span"][0]:
            result["matching"]["tafsir_tie"]["span"][1]]
        self.assertEqual(sha(raw),result["matching"]["tafsir_tie"]["digest"])
        self.assertIsNone(result["matching"]["usul_exact_stage07_occurrence_id"])

    def test_reason_without_both_pinned_exact_ties_refused(self):
        with self.assertRaises(ut012.UsulTafsirLinkError):
            self.build(text=TAFSIR_FOLDED,reason=REASON_PINNED_EXACT,
                       scope="LEXICAL_NAVIGATION_ONLY")
        with self.assertRaises(ut012.UsulTafsirLinkError):
            self.build(text=TAFSIR_NONE,reason=REASON_PINNED_EXACT,
                       scope="LEXICAL_NAVIGATION_ONLY")

    def test_no_tie_does_not_assert_relation(self):
        result,_=self.build(text=TAFSIR_NONE)
        self.assertEqual(TIE_NONE,result["matching"]["tie_level"])
        self.assertEqual("UNDETERMINED",result["link_status"])

    def test_unsupported_query_literal_refused_even_exact_in_both_sources(self):
        with self.assertRaisesRegex(ut012.UsulTafsirLinkError,
                                    "UT013_UNPINNED_STAGE07_QUERY_LITERAL"):
            self.build(changes_me="unused") if False else self.build(
                rule_query_terms=["هذا"])


    def test_free_text_candidacy_reason_refused_to_protect_private_text(self):
        with self.assertRaisesRegex(ut012.UsulTafsirLinkError,
                                    "UT013_REASON_SCOPE_INVALID"):
            self.build(reason="قال أهل التفسير: النص الخاص الكامل",
                       scope="SOURCE_LOCAL_LEXICAL_NAVIGATION")

    def test_summarize_rejects_post_validation_status_promotion(self):
        result,_=self.build(reason=REASON_PINNED_EXACT,scope="BOUNDED")
        tampered=copy.deepcopy(result)
        tampered["link"]["scholarly_verified"]=True
        with self.assertRaisesRegex(ut012.UsulTafsirLinkError,
                                    "UT013_MATCH_RECORD_INVALID"):
            summarize([tampered])

    def test_local_source_bytes_must_match_accepted_section_sha(self):
        with self.assertRaisesRegex(ut012.UsulTafsirLinkError,
                                    "UT013_WARAQAT_SECTION_RAW_SHA_MISMATCH"):
            self.build(usul_raw_text=self.raw+b"changed")

    def test_exact_search_requires_query_scoped_stage08_occurrence(self):
        g=copy.deepcopy(self.g)
        g["edges"]=[e for e in g["edges"]
                    if not (e.get("kind")=="QUERY_LOCATES_OCCURRENCE"
                            and e.get("to")==self.occ)]
        # Outside the already accepted pin, even graph rewrites are rejected.
        with self.assertRaises(ut012.UsulTafsirLinkError):
            self.build(usul_graph=g,reason=REASON_PINNED_EXACT,scope="LEXICAL_ONLY")


    def test_exact_unbound_to_stage07_occurrence_is_not_folded_evidence(self):
        # A synthetically self-consistent but *different* independently
        # pinned Stage08 graph can have the literal in the raw section and
        # no query-anchored exact occurrence. Such text is not a rule witness.
        raw,g,c,occ,other=usul_sources()
        g["edges"]=[edge for edge in g["edges"]
                    if not (edge.get("kind")=="QUERY_LOCATES_OCCURRENCE"
                            and edge.get("to")==occ)]
        g["graph_sha256"]=sha(canonical({k:g[k] for k in GRAPH_FIELDS}))
        manifest={
            "schema_version":"u0.2.0","concepts":c["concepts"],
            "rule_candidates":[
                {k:r[k] for k in ("id","pointer_id","if_concepts",
                                   "unless_concepts","then_concept",
                                   "review_status")}
                for r in c["rule_candidates"]],
            "relations":c["relations"],
        }
        cat=build_catalog(g,g["graph_sha256"],manifest)
        original,p,candidate=tafsir_pair()
        args=dict(
            candidate=candidate,passage=p,tafsir_raw_text=original,
            usul_catalog=cat,usul_graph=g,usul_raw_text=raw,
            rule_candidate_id="candidate:amr-structural-hypothesis",
            research_pointer_id="pilot:amr-rule-research-pointer",
            rule_query_terms=[TERM])
        with patch.object(ut012,"TRUSTED_GRAPH_SHA256",g["graph_sha256"]), \
             patch.object(ut012,"TRUSTED_CATALOG_SHA256",cat["catalog_sha256"]):
            result=match_candidate(**args)
            self.assertEqual("UNDETERMINED",result["link_status"])
            self.assertEqual(TIE_NONE,result["matching"]["tie_level"])
            with self.assertRaisesRegex(ut012.UsulTafsirLinkError,
                                        "UT013_REASON_WITHOUT_PINNED_EXACT_TIE"):
                match_candidate(**args,
                    candidacy_reason=REASON_PINNED_EXACT,
                    candidacy_scope="SOURCE_LOCAL_RESEARCH_ONLY")

    def test_no_mention_of_qarinah_cannot_be_evidence_of_absence(self):
        result,_=self.build()
        self.assertEqual("NOT_OBSERVED_IN_SCOPE",result["qarinah"]["status"])
        self.assertIn("not evidence",result["qarinah"]["note"])

    def test_qarinah_mentioned_without_legal_role(self):
        result,_=self.build(text=TAFSIR_QARINAH)
        self.assertEqual("PRESENT_AS_TEXT",result["qarinah"]["status"])
        self.assertFalse(result["rule_application_verified"])

    def test_envelope_rejects_mutation_and_does_not_pollute_ut012(self):
        result,inputs=self.build(reason=REASON_PINNED_EXACT,scope="BOUNDED")
        modified=copy.deepcopy(result)
        modified["matching"]["tafsir_tie"]["digest"]="0"*64
        with self.assertRaisesRegex(ut012.UsulTafsirLinkError,
                                    "UT013_ENVELOPE_TAMPERED"):
            validate_match(modified,**inputs)
        self.assertNotIn("matching",result["link"])
        self.assertNotIn("qarinah",result["link"])

    def test_no_text_or_authority_promotion_in_receipt(self):
        result,_=self.build(reason=REASON_PINNED_EXACT,scope="RESEARCH_ONLY")
        serialized=json.dumps(result,ensure_ascii=False)
        self.assertNotIn(TAFSIR,serialized)
        self.assertNotIn(USUL,serialized)
        self.assertFalse(result["scholarly_verified"])
        self.assertFalse(result["rule_application_verified"])
        self.assertFalse(result["text_included"])
        summary=summarize([result])
        self.assertEqual({"CANDIDATE_RELATED":1},
                         summary["links_by_status"])
        self.assertFalse(summary["juristic_inference_allowed"])

    def test_determinism(self):
        a,_=self.build(reason=REASON_PINNED_EXACT,scope="BOUNDED")
        b,_=self.build(reason=REASON_PINNED_EXACT,scope="BOUNDED")
        self.assertEqual(a,b)


if __name__=="__main__":
    unittest.main()
