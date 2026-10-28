"""UT-01.2 UsulTafsirLink acceptance tests (synthetic CI data only)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from engines.tafsir.t023 import identify_candidates
from engines.tafsir.t02 import CONTEXT as PASSAGE_CONTEXT
from engines.usul.ut012 import (
    LINK_CANDIDATE, LINK_REJECTED, LINK_UNDETERMINED,
    OFFSET_UNICODE_CHARS, OFFSET_UTF8_BYTES, UsulTafsirLinkError,
    build_link, reject_link, validate_link,
)

STATEMENT = ("قال المفسرون في قوله تعالى: وأقيموا الصلاة. "
             "ودلت الآية على أمر فعل الصلاة بيانا للمعنى. "
             "وقيل في القرينة قول الآخر.")


def passage():
    from engines.tafsir.t02 import make_record
    rec = make_record(quran_reference="2:43", work_id="tafsir_tabari",
                      author_id="محمد بن جرير الطبري",
                      source_record_id="tafsir:tafsir_tabari:2:43:"
                      + hashlib.sha256(STATEMENT.encode("utf-8")).hexdigest(),
                      source_sha256=hashlib.sha256(STATEMENT.encode("utf-8")).hexdigest(),
                      original_text=STATEMENT,
                      span=(0, 87), interpretation_type=None,
                      context_scope=PASSAGE_CONTEXT)
    return rec


def candidate(passage_rec):
    out = identify_candidates(passage_rec)
    return out[0]


def catalog(rule_id="candidate:amr-structural-hypothesis",
            pointer_id="pilot:amr-rule-research-pointer"):
    return {
        "engine": "usul-concept-rule-catalog/0.2.0",
        "schema_version": "u0.2.0",
        "status": "U02_CANDIDATE_CATALOG_PASS",
        "stage08_graph_sha256": "set-by-graph",
        "concepts": [
            {"id": "concept:amr-term", "concept_kind": "TERM",
             "review_status": "UNASSESSED"},
            {"id": "concept:qarinah-candidate", "concept_kind": "EXCEPTION",
             "review_status": "UNASSESSED"},
            {"id": "concept:wujub-candidate", "concept_kind": "OUTCOME",
             "review_status": "UNASSESSED"},
        ],
        "rule_candidates": [
            {"id": rule_id, "pointer_id": pointer_id,
             "if_concepts": ["concept:amr-term"],
             "unless_concepts": ["concept:qarinah-candidate"],
             "then_concept": "concept:wujub-candidate",
             "review_status": "UNASSESSED"},
        ],
        "relations": [],
    }


def graph(pointer_id="pointer:pilot-amr-structural",
          section_sha="9" * 64):
    g = {
        "engine": "usul-evidence-context-graph/0.1.0",
        "status": "EVIDENCE_CONTEXT_GRAPH_PASS",
        "scope": "pilot:waraqat-bab-amr",
        "stage07_engine": "waraqat-two-witness-stage07/0.1.0",
        "stage07_witness_count": 1, "context_radius_lines": 1,
        "nodes": [
            {"id": "witness:pilot-primary", "kind": "SOURCE_WITNESS",
             "source_id": "pilot:waraqat-primary", "source_url": "u",
             "work_title": "الورقات", "author": "الجويني",
             "printed_edition_verified": False},
            {"id": "section:pilot-bab-amr", "kind": "PINNED_SECTION",
             "source_id": "pilot:waraqat-primary",
             "section_sha256": section_sha, "section_locator": "باب الأمر",
             "offset_basis": "utf8_export", "source_byte_base": 3735,
             "source_line_base": 86, "byte_length": 1232, "line_count": 22},
            {"id": "query:pilot-amr-term", "kind": "SEARCH_QUERY",
             "witness_id": "pilot:waraqat-primary", "query_id": "pilot:amr-term",
             "query_utf8_sha256": "b" * 64,
             "interpretation": "LEXICAL_NAVIGATION_ONLY",
             "source_text_included": False},
            {"id": "pointer:pilot-amr-structural",
             "kind": "RULE_RESEARCH_POINTER",
             "pointer_id": "pilot:amr-rule-research-pointer",
             "reference_id": rule_id_default(), "review_status": "UNASSESSED",
             "rule_application_verified": False,
             "objection_presence_verified": False},
            {"id": "occurrence:pilot-1", "kind": "TEXT_OCCURRENCE",
             "query_id": "pilot:amr-term", "offset_basis": OFFSET_UTF8_BYTES,
             "byte_span": [100, 140]},
        ],
        "edges": [
            {"id": "edge:w-s", "kind": "WITNESS_HAS_PINNED_SECTION",
             "from": "witness:pilot-primary", "to": "section:pilot-bab-amr"},
            {"id": "edge:q-s", "kind": "QUERY_SCOPED_TO_SECTION",
             "from": "query:pilot-amr-term", "to": "section:pilot-bab-amr"},
            {"id": "edge:p-q", "kind": "RESEARCH_NAVIGATION_ONLY",
             "from": "pointer:pilot-amr-structural",
             "to": "query:pilot-amr-term",
             "no_claim_of_support": True, "no_claim_of_exception": True},
        ],
        "nodes_by_kind": {}, "edges_by_kind": {},
        "all_edge_references_valid": True, "source_text_included": False,
        "lexical_matches_promoted_to_rules": False,
        "rule_support_attested": False,
        "objection_presence_attested": False,
        "semantic_qarinah_verified": False,
        "juristic_inference_allowed": False, "scholarly_verified": False,
        "redistribution_approved": False,
    }
    from engines.usul.concept_rule_catalog import GRAPH_FIELDS, canonical
    payload = {k: g[k] for k in GRAPH_FIELDS}
    payload["status"] = "EVIDENCE_CONTEXT_GRAPH_PASS"
    g["graph_sha256"] = hashlib.sha256(canonical(payload)).hexdigest()
    return g


def rule_id_default():
    return "candidate:amr-structural-hypothesis"


class UT012Tests(unittest.TestCase):
    def build(self, **overrides):
        p = passage()
        c = candidate(p)
        g = graph()
        cat = catalog()
        cat["stage08_graph_sha256"] = g["graph_sha256"]
        kw = dict(quran_reference="2:43", tafsir_candidate=c,
                  tafsir_passage=p, usul_catalog=cat, usul_graph=g,
                  rule_candidate_id="candidate:amr-structural-hypothesis",
                  research_pointer_id="pilot:amr-rule-research-pointer")
        kw.update(overrides)
        return build_link(**kw)

    def test_1_candidate_related_with_reason(self):
        r = self.build(candidacy_reason="both texts discuss amr form",
                       candidacy_scope="LEXICAL_OVERLAP_ONLY")
        self.assertEqual(r["link_status"], LINK_CANDIDATE)
        self.assertFalse(r["cross_source_semantic_equivalence_verified"])

    def test_undetermined_without_reason(self):
        r = self.build()
        self.assertEqual(r["link_status"], LINK_UNDETERMINED)

    def test_2_chain_verified_both_sides(self):
        r = self.build()
        self.assertTrue(r["tafsir_source_binding_verified"])
        self.assertTrue(r["usul_source_binding_verified"])
        self.assertEqual(r["tafsir_raw_source_span_unit"], OFFSET_UNICODE_CHARS)
        self.assertEqual(r["usul_occurrence_span_unit"], OFFSET_UTF8_BYTES)

    def test_3_link_id_stable(self):
        self.assertEqual(self.build()["link_id"], self.build()["link_id"])

    def test_4_forged_evidence_digest_refused(self):
        p = passage()
        c = candidate(p)
        c["evidence_sha256"] = "f" * 64
        with self.assertRaises(UsulTafsirLinkError):
            self.build(tafsir_candidate=c, tafsir_passage=p)

    def test_4b_forged_passage_link_refused(self):
        p = passage()
        c = candidate(p)
        other = passage()
        other["interpretation_id"] = "interp:" + "e" * 40
        with self.assertRaises(UsulTafsirLinkError):
            self.build(tafsir_candidate=c,
                       tafsir_passage={**other, "interpretation_statement": STATEMENT})

    def test_4c_different_verse_refused(self):
        p = passage()
        c = candidate(p)
        with self.assertRaises(UsulTafsirLinkError):
            self.build(tafsir_candidate=c, tafsir_passage=p,
                       quran_reference="3:1")

    def test_5_ghost_rule_refused(self):
        with self.assertRaises(UsulTafsirLinkError):
            self.build(rule_candidate_id="candidate:ghost")

    def test_5b_ghost_pointer_refused(self):
        with self.assertRaises(UsulTafsirLinkError):
            self.build(research_pointer_id="pointer:ghost")

    def test_5c_catalog_digest_mismatch_refused(self):
        with self.assertRaises(UsulTafsirLinkError):
            self.build(expected_catalog_sha256="0" * 64)  # never pinned

    def test_5d_graph_digest_mismatch_refused(self):
        with self.assertRaises(UsulTafsirLinkError):
            self.build(expected_graph_sha256="0" * 64)

    def test_5e_bad_occurrence_refused(self):
        with self.assertRaises(UsulTafsirLinkError):
            self.build(occurrence_ids=["occurrence:ghost"])

    def test_6_promotion_refused(self):
        r = self.build()
        with self.assertRaises(UsulTafsirLinkError):
            validate_link({**r, "scholarly_verified": True},
                          tafsir_candidate=self.build()["__x"] if False else
                          candidate(passage()), tafsir_passage=passage(),
                          usul_catalog=catalog(), usul_graph=graph())

    def test_7_no_text_leakage(self):
        raw = json.dumps(self.build(), ensure_ascii=False)
        self.assertNotIn("قال المفسرون", raw)
        self.assertNotIn(STATEMENT, raw)

    def test_9_rejection_record(self):
        r = reject_link(quran_reference="2:43",
                        rejection_reason="evidence digest mismatch")
        self.assertEqual(r["link_status"], LINK_REJECTED)
        self.assertFalse(r["scholarly_verified"])

    def test_10_deterministic(self):
        a = json.dumps(self.build(), sort_keys=True, ensure_ascii=False)
        b = json.dumps(self.build(), sort_keys=True, ensure_ascii=False)
        self.assertEqual(a, b)

    def test_offset_units_never_merged(self):
        r = self.build()
        self.assertNotEqual(r["tafsir_raw_source_span_unit"],
                            r["usul_occurrence_span_unit"])


import json

if __name__ == "__main__":
    unittest.main()
