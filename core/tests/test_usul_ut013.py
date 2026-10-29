"""UT-01.3 conservative matching acceptance tests (synthetic CI data)."""
from __future__ import annotations

import hashlib
import json
import unittest

from engines.tafsir.t02 import make_record, CONTEXT as PASSAGE_CONTEXT
from engines.tafsir.t023 import identify_candidates
import engines.usul.ut012 as ut012
from engines.usul.ut013 import (
    match_candidate, summarize, locate_term, locate_term_utf8_bytes,
    TIE_EXACT, TIE_FOLDED, TIE_NONE, LINK_CANDIDATE, LINK_UNDETERMINED,
)

TERM = "الأمر"
HADITH_TEXT = ("وأما دلالة صيغة الأمر على الوجوب فإن الأمر في الشرع "
               "يفيد الطلب، ومحاذير القرائن معروفة في بابها.")
NO_TIE_TEXT = ("الكلام في تسمية هذا الباب وتعريف الغرض منه، وما يتبع "
               "للباحث في مراتب الكلام.")


def passage(text):
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return make_record(
        quran_reference="2:43", work_id="tafsir_tabari",
        author_id="محمد بن جرير الطبري",
        source_record_id="tafsir:tafsir_tabari:2:43:" + digest,
        source_sha256=digest, original_text=text,
        span=(0, len(text)), context_scope=PASSAGE_CONTEXT)


def cand(text):
    p = passage(text)
    return p, identify_candidates(p)[0]


class TieTests(unittest.TestCase):
    def test_exact(self):
        r = locate_term(HADITH_TEXT, "صيغة الأمر")
        self.assertEqual(r["tie"], TIE_EXACT)

    def test_folded(self):
        r = locate_term(HADITH_TEXT, "صيغة الأمر")
        self.assertEqual(r["tie"], TIE_EXACT)
        # folded-only: diacritic-carrying term against plain text
        r2 = locate_term("صيغة الامر في الشرع", "صِيغَةُ الأمرِ")
        self.assertEqual(r2["tie"], TIE_FOLDED)

    def test_utf8_byte_spans(self):
        raw = ("يجب الأمر".encode("utf-8") + b"\x00padding\x00"
               + "الأمر الاصطناعي".encode("utf-8"))
        r = locate_term_utf8_bytes(raw, "الأمر")
        self.assertEqual(r["tie"], TIE_EXACT)
        b0, b1 = r["span"]
        self.assertEqual(raw[b0:b1].decode("utf-8"), "الأمر")


class MatchingTests(unittest.TestCase):
    def setUp(self):
        from unittest.mock import patch
        import engines.usul.ut012 as ut012
        self.patches = []
        self._graph_obj = None
        self._catalog_obj = None

    def _pins(self):
        # sanctioned synthetic-CI pattern (mirrors main's UT-01.2 tests):
        # point the trusted pins at THIS test's synthetic graph/catalog.
        from unittest.mock import patch
        g = self._graph()
        c = self._catalog()
        c["stage08_graph_sha256"] = g["graph_sha256"]
        self._patches = [
            patch.object(ut012, "TRUSTED_GRAPH_SHA256", g["graph_sha256"]),
            patch.object(ut012, "TRUSTED_CATALOG_SHA256",
                         c["catalog_sha256"]),
        ]
        for p in self._patches:
            p.start()
        self.addCleanup(self._unpins)

    def _unpins(self):
        for p in getattr(self, "_patches", []):
            p.stop()

    def build(self, text=HADITH_TEXT, reason=None, term=TERM):
        self._pins()
        p, c = cand(text)
        usul_raw = HADITH_TEXT.encode("utf-8")
        return match_candidate(
            candidate=c, passage=p, tafsir_raw_text=text,
            usul_catalog=self._catalog(), usul_graph=self._graph(),
            usul_raw_text=usul_raw,
            rule_candidate_id="candidate:amr-structural-hypothesis",
            research_pointer_id="pilot:amr-rule-research-pointer",
            rule_query_terms=[term],
            candidacy_reason=reason,
            candidacy_scope="BAB_AL_AMR_LEXICAL_SCOPE")

    _cat = None
    _g = None
    def _catalog(self):
        if self._cat is None:
            self._cat = self._mk_cat_graph()[0]
        return self._cat
    def _graph(self):
        if self._g is None:
            self._g = self._mk_cat_graph()[1]
        return self._g
    def _cat_digest(self):
        return self._graph()["graph_sha256"] and self._catalog_digest
    def _graph_digest(self):
        return self._g["graph_sha256"]
    def _mk_cat_graph(self):
        from engines.usul.ut012 import OFFSET_UTF8_BYTES
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
                 "section_sha256": "9" * 64, "section_locator": "باب الأمر",
                 "offset_basis": "utf8_export", "source_byte_base": 3735,
                 "source_line_base": 86, "byte_length": len(HADITH_TEXT.encode("utf-8")),
                 "line_count": 3},
                {"id": "query:pilot-amr-term", "kind": "SEARCH_QUERY",
                 "witness_id": "pilot:waraqat-primary",
                 "query_id": "pilot:amr-term",
                 "query_utf8_sha256": "b" * 64,
                 "interpretation": "LEXICAL_NAVIGATION_ONLY",
                 "source_text_included": False},
                {"id": "pointer:pilot-amr-structural",
                 "kind": "RULE_RESEARCH_POINTER",
                 "pointer_id": "pilot:amr-rule-research-pointer",
                 "reference_id": "candidate:amr-structural-hypothesis",
                 "review_status": "UNASSESSED",
                 "rule_application_verified": False,
                 "objection_presence_verified": False},
                {"id": "occurrence:pilot-1", "kind": "TEXT_OCCURRENCE",
                 "query_id": "pilot:amr-term",
                 "offset_basis": OFFSET_UTF8_BYTES,
                 "byte_span": [0, 10]},
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
            "juristic_inference_allowed": False,
            "scholarly_verified": False,
            "redistribution_approved": False,
        }
        from engines.usul.concept_rule_catalog import (
            GRAPH_FIELDS, canonical)
        payload = {k: g[k] for k in GRAPH_FIELDS}
        payload["status"] = "EVIDENCE_CONTEXT_GRAPH_PASS"
        g["graph_sha256"] = hashlib.sha256(canonical(payload)).hexdigest()
        from engines.usul.concept_rule_catalog import build_catalog
        import json as _json
        from pathlib import Path as _P
        DATA = _P("engines/usul/pilots/data")
        cat = build_catalog(
            g, g["graph_sha256"],
            _json.loads((DATA / "waraqat-u02-catalog-candidates.json").read_text(encoding="utf-8")))
        return cat, g
    def _catalog_digest(self):
        return self._catalog_digest_holder
    def _graph_digest(self):
        return self._g["graph_sha256"]

    def test_exact_both_sides_with_reason_is_candidate(self):
        r = self.build(reason="exact literal tie on both pinned sides")
        self.assertEqual(r["link_status"], LINK_CANDIDATE)
        self.assertEqual(r["matching"]["tie_level"], TIE_EXACT)
        self.assertFalse(r["rule_application_verified"])

    def test_folded_only_is_undetermined(self):
        r = self.build(text="في المسألة أمرٌ من الأمر المهم هنا للنظر.")
        self.assertEqual(r["link_status"], LINK_UNDETERMINED)
        self.assertNotEqual(r["matching"]["tie_level"], TIE_EXACT)

    def test_misleading_similarity_not_promoted(self):
        # words like (الأهم/الأمور) share letters but not the exact term
        r = self.build(text="الأمور فيها متشابهة والأهم النظر فيها بعينه.")
        self.assertEqual(r["link_status"], LINK_UNDETERMINED)

    def test_no_tie_is_undetermined(self):
        # no lexical tie => UNDETERMINED; a reason without ties is refused
        with self.assertRaises(Exception):
            self.build(text=NO_TIE_TEXT, reason="x")
        r = self.build(text=NO_TIE_TEXT)
        self.assertEqual(r["link_status"], LINK_UNDETERMINED)

    def test_qarinah_not_observed_is_not_absent(self):
        r = self.build()
        self.assertEqual(r["qarinah"]["status"], "NOT_OBSERVED_IN_SCOPE")
        self.assertIn("not evidence", r["qarinah"]["note"])

    def test_qarinah_present_as_text_only(self):
        r = self.build(text=HADITH_TEXT + " والقرينة هنا معروفة في سياقها.")
        self.assertEqual(r["qarinah"]["status"], "PRESENT_AS_TEXT")
        self.assertFalse(r["rule_application_verified"])

    def test_forged_candidate_digest_refused(self):
        p, c = cand(HADITH_TEXT)
        c["evidence_sha256"] = "f" * 64
        with self.assertRaises(Exception):
            usul_raw = HADITH_TEXT.encode("utf-8")
            match_candidate(
                candidate=c, passage=p, tafsir_raw_text=HADITH_TEXT,
                usul_catalog=self._catalog(), usul_graph=self._graph(),
                usul_raw_text=usul_raw,
                rule_candidate_id="candidate:amr-structural-hypothesis",
                research_pointer_id="pilot:amr-rule-research-pointer",
                rule_query_terms=[TERM])

    def test_summary_never_claims_scholarship(self):
        p, c = cand(HADITH_TEXT)
        r = self.build(reason="tie")
        s = summarize([r])
        raw = json.dumps(s, ensure_ascii=False)
        self.assertNotIn("صحيح", raw)
        self.assertNotIn("وجوب", raw.replace("wujub", ""))
        self.assertFalse(s["scholarly_verified"])
        self.assertFalse(s["rule_application_verified"])

    def test_deterministic(self):
        a = json.dumps(self.build(reason="tie"), sort_keys=True,
                       ensure_ascii=False)
        b = json.dumps(self.build(reason="tie"), sort_keys=True,
                       ensure_ascii=False)
        self.assertEqual(a, b)


import json

if __name__ == "__main__":
    unittest.main()
