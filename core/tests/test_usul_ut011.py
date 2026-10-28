"""UT-01.1 acceptance tests (synthetic CI data only)."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import unittest

from engines.usul.concept_rule_catalog import (
    CatalogError, build_catalog,
)

REPO = Path(__file__).resolve().parents[2]


GRAPH_FIELDS = (
    "engine", "status", "scope", "stage07_engine", "stage07_witness_count",
    "context_radius_lines", "nodes", "edges", "nodes_by_kind",
    "edges_by_kind", "all_edge_references_valid", "source_text_included",
    "lexical_matches_promoted_to_rules", "rule_support_attested",
    "objection_presence_attested", "semantic_qarinah_verified",
    "juristic_inference_allowed", "scholarly_verified", "redistribution_approved",
)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def graph():
    """Minimal valid Stage08-shaped graph with one real-shaped pointer."""
    return {
        "engine": "usul-evidence-context-graph/0.1.0",
        "status": "EVIDENCE_CONTEXT_GRAPH_PASS",
        "scope": "pilot:waraqat-bab-amr",
        "stage07_engine": "waraqat-two-witness-stage07/0.1.0",
        "stage07_witness_count": 1,
        "context_radius_lines": 1,
        "nodes": [
            {"id": "witness:waraqat-primary", "kind": "SOURCE_WITNESS", "source_id": "pilot:waraqat-primary",
             "source_url": "https://example", "work_title": "الورقات",
             "author": "الجويني", "printed_edition_verified": False},
            {"id": "section:bab-amr", "kind": "PINNED_SECTION", "source_id": "pilot:waraqat-primary",
             "section_sha256": "a" * 64, "section_locator": "باب الأمر",
             "offset_basis": "utf8_export", "source_byte_base": 3735,
             "source_line_base": 86, "byte_length": 1232, "line_count": 22},
            {"id": "query:pilot-amr-term", "kind": "SEARCH_QUERY", "witness_id": "pilot:waraqat-primary",
             "query_id": "pilot:amr-term", "query_utf8_sha256": "b" * 64,
             "interpretation": "LEXICAL_NAVIGATION_ONLY",
             "source_text_included": False},
            {"id": "pointer:pilot-amr", "kind": "RULE_RESEARCH_POINTER",
             "pointer_id": "pilot:amr-rule-research-pointer",
             "reference_id": "candidate:command", "review_status": "UNASSESSED",
             "rule_application_verified": False,
             "objection_presence_verified": False},
        ],
        "edges": [
            {"id": "edge:witness-section", "kind": "WITNESS_HAS_PINNED_SECTION", "from": "witness:waraqat-primary", "to": "section:bab-amr"},
            {"id": "edge:query-section", "kind": "QUERY_SCOPED_TO_SECTION", "from": "query:pilot-amr-term", "to": "section:bab-amr"},
            {"id": "edge:pointer-navigation", "kind": "RESEARCH_NAVIGATION_ONLY",
             "from": "pointer:pilot-amr", "to": "query:pilot-amr-term",
             "no_claim_of_support": True, "no_claim_of_exception": True},
        ],
        "nodes_by_kind": {}, "edges_by_kind": {},
        "scope": "pilot:waraqat-bab-amr",
        "stage07_engine": "waraqat-two-witness-stage07/0.1.0",
        "stage07_witness_count": 1, "context_radius_lines": 1,
        "all_edge_references_valid": True, "source_text_included": False,
        "lexical_matches_promoted_to_rules": False,
        "rule_support_attested": False,
        "objection_presence_attested": False,
        "semantic_qarinah_verified": False,
        "juristic_inference_allowed": False,
        "scholarly_verified": False,
        "redistribution_approved": False,
        "lexical_matches_promoted_to_rules": False,
        "rule_support_attested": False, "objection_presence_attested": False,
        "semantic_qarinah_verified": False, "juristic_inference_allowed": False,
        "scholarly_verified": False, "redistribution_approved": False,
    }


def manifest(pointer_id="pilot:amr-rule-research-pointer"):
    return {
        "schema_version": "u0.2.0",
        "concepts": [
            {"id": "concept:amr-term", "concept_kind": "TERM",
             "review_status": "UNASSESSED"},
            {"id": "concept:qarinah-candidate", "concept_kind": "CONDITION",
             "review_status": "UNASSESSED"},
            {"id": "concept:wujub-candidate", "concept_kind": "OUTCOME",
             "review_status": "UNASSESSED"},
        ],
        "rule_candidates": [
            {"id": "candidate:command", "pointer_id": pointer_id,
             "if_concepts": ["concept:amr-term"],
             "unless_concepts": ["concept:qarinah-candidate"],
             "then_concept": "concept:wujub-candidate",
             "review_status": "UNASSESSED"},
        ],
        "relations": [],
    }


def trusted(graph_obj):
    payload = {k: graph_obj[k] for k in GRAPH_FIELDS}
    payload["status"] = "EVIDENCE_CONTEXT_GRAPH_PASS"
    pin = hashlib.sha256(canonical(payload)).hexdigest()
    graph_obj["graph_sha256"] = pin  # contract: graph carries its own digest
    return pin


class UT011Tests(unittest.TestCase):
    def test_catalog_builds_with_real_pointer_chain(self):
        g = graph()
        out = build_catalog(g, trusted(g), manifest())
        self.assertEqual(out["status"], "U02_CANDIDATE_CATALOG_PASS")
        self.assertEqual(len(out["concepts"]), 3)
        self.assertEqual(len(out["rule_candidates"]), 1)
        anchor = out["rule_candidates"][0]["research_anchor"]
        self.assertEqual(anchor["pointer_id"], "pilot:amr-rule-research-pointer")

    def test_refuse_graph_digest_mismatch(self):
        g = graph()
        with self.assertRaises(CatalogError):
            build_catalog(g, "f" * 64, manifest())

    def test_refuse_pointer_without_query_or_witness(self):
        g = graph()
        g["nodes"] = [n for n in g["nodes"] if n["id"] != "query:pilot-amr-term"]
        with self.assertRaises(CatalogError):
            build_catalog(g, trusted(g), manifest())

    def test_refuse_rule_referencing_missing_concept(self):
        bad = manifest()
        bad["rule_candidates"][0]["if_concepts"] = ["concept:ghost"]
        g = graph()
        with self.assertRaises(CatalogError):
            build_catalog(g, trusted(g), bad)

    def test_refuse_unknown_pointer(self):
        g = graph()
        with self.assertRaises(CatalogError):
            build_catalog(g, trusted(g), manifest(pointer_id="pointer:ghost"))

    def test_refuse_promotion_statuses(self):
        bad = manifest()
        bad["rule_candidates"][0]["review_status"] = "ASSESSED_OK"
        g = graph()
        with self.assertRaises(CatalogError):
            build_catalog(g, trusted(g), bad)

    def test_deterministic(self):
        g = graph()
        a = json.dumps(build_catalog(g, trusted(g), manifest()),
                       sort_keys=True, ensure_ascii=False)
        b = json.dumps(build_catalog(g, trusted(g), manifest()),
                       sort_keys=True, ensure_ascii=False)
        self.assertEqual(a, b)

    def test_all_statuses_unassessed_and_flags_false(self):
        g = graph()
        out = build_catalog(g, trusted(g), manifest())
        for c in out["concepts"]:
            self.assertEqual(c["review_status"], "UNASSESSED")
        for r in out["rule_candidates"]:
            self.assertEqual(r["review_status"], "UNASSESSED")
            self.assertFalse(r["rule_execution_performed"])
            self.assertFalse(r["formalization_verified"])
            self.assertFalse(r["semantic_equivalence_verified"])
        self.assertFalse(out["scholarly_verified"])

    def test_real_evidence_receipt_flags_stay_false(self):
        p = REPO / "evaluation" / "evidence" / "ut011_bab_amr_bridge_report.json"
        self.assertTrue(p.is_file())
        rep = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(rep["status"], "U02_WARAQAT_PINNED_CATALOG_PASS")
        self.assertFalse(rep["source_text_included"])
        for flag in ("scholarly_verified", "juristic_inference_allowed",
                     "public_fatwa_authorized", "redistribution_approved",
                     "source_support_attested", "formalization_verified",
                     "semantic_equivalence_verified",
                     "source_edition_authenticated"):
            self.assertFalse(rep[flag], flag)
        self.assertEqual(rep["catalog_concept_count"], 3)
        self.assertEqual(rep["catalog_rule_candidates"], 1)

    def test_real_receipt_text_leak_scan(self):
        p = REPO / "evaluation" / "evidence" / "ut011_bab_amr_bridge_report.json"
        raw = p.read_text(encoding="utf-8")
        # no protected passage text and no local paths in the committed receipt
        self.assertNotIn("waraqat-bab-amr-private", raw)
        self.assertNotIn("D:\\MubinSources", raw)


if __name__ == "__main__":
    unittest.main()
