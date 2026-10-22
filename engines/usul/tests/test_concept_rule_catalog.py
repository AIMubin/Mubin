"""Synthetic and real-Stage08-builder adversarial tests for U0.2 catalog."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from engines.usul.concept_rule_catalog import (
    CatalogError, GRAPH_FIELDS, build_catalog, canonical, sha,
)


class CandidateCatalogTests(unittest.TestCase):
    def setUp(self):
        self.pid = "pointer:" + "a"*32
        self.qid = "query:" + "b"*32
        self.sid = "section:" + "c"*32
        self.graph = {
            "engine": "usul-evidence-context-graph/0.1.0",
            "status": "EVIDENCE_CONTEXT_GRAPH_PASS",
            "scope": "PINNED_TEXT_OBSERVATION_AND_RESEARCH_NAVIGATION_ONLY",
            "stage07_engine": "synthetic", "stage07_witness_count": 1,
            "context_radius_lines": 1,
            "nodes": [
                {"id": self.pid, "kind": "RULE_RESEARCH_POINTER",
                 "pointer_id": "pointer:amr", "reference_id": "research:amr",
                 "review_status": "UNASSESSED", "rule_application_verified": False,
                 "objection_presence_verified": False},
                {"id": self.qid, "kind": "SEARCH_QUERY",
                 "query_id": "query:amr", "witness_id": "synthetic:w1"},
                {"id": self.sid, "kind": "PINNED_SECTION", "source_id": "synthetic:w1",
                 "section_sha256": sha(b"synthetic-only")},
            ],
            "edges": [
                {"kind": "RESEARCH_NAVIGATION_ONLY", "from": self.pid, "to": self.qid,
                 "no_claim_of_support": True, "no_claim_of_exception": True},
                {"kind": "QUERY_SCOPED_TO_SECTION", "from": self.qid, "to": self.sid},
            ],
            "nodes_by_kind": {"RULE_RESEARCH_POINTER": 1, "SEARCH_QUERY": 1,
                              "PINNED_SECTION": 1},
            "edges_by_kind": {"RESEARCH_NAVIGATION_ONLY": 1,
                              "QUERY_SCOPED_TO_SECTION": 1},
            "all_edge_references_valid": True, "source_text_included": False,
            "lexical_matches_promoted_to_rules": False,
            "rule_support_attested": False, "objection_presence_attested": False,
            "semantic_qarinah_verified": False, "juristic_inference_allowed": False,
            "scholarly_verified": False, "redistribution_approved": False,
        }
        self.repin()
        self.manifest = {
            "schema_version": "u0.2.0",
            "concepts": [
                {"id": "concept:command", "concept_kind": "TERM",
                 "review_status": "UNASSESSED"},
                {"id": "concept:context", "concept_kind": "EXCEPTION",
                 "review_status": "UNASSESSED"},
                {"id": "concept:outcome", "concept_kind": "OUTCOME",
                 "review_status": "UNASSESSED"},
            ],
            "rule_candidates": [
                {"id": "candidate:command", "pointer_id": "pointer:amr",
                 "if_concepts": ["concept:command"],
                 "unless_concepts": ["concept:context"],
                 "then_concept": "concept:outcome",
                 "review_status": "UNASSESSED"},
            ],
            "relations": [
                {"from_concept_id": "concept:command",
                 "to_concept_id": "concept:outcome",
                 "kind": "PROPOSED_RELATED_TO", "review_status": "UNASSESSED"},
            ],
        }

    def repin(self):
        self.pin = sha(canonical({k: self.graph[k] for k in GRAPH_FIELDS}))
        self.graph["graph_sha256"] = self.pin

    def result(self):
        return build_catalog(self.graph, self.pin, self.manifest)

    def test_deterministic_metadata_only_success(self):
        a = self.result()
        self.assertEqual(a, self.result())
        self.assertEqual(a["status"], "U02_CANDIDATE_CATALOG_PASS")
        self.assertEqual(a["rule_candidate_count"], 1)
        self.assertEqual(a["concept_count"], 3)
        self.assertEqual(len(a["catalog_sha256"]), 64)
        for flag in ("source_text_included", "rule_execution_performed",
                     "source_support_attested", "semantic_equivalence_verified",
                     "scholarly_verified", "redistribution_approved",
                     "public_fatwa_authorized", "juristic_inference_allowed"):
            self.assertFalse(a[flag])
        self.assertEqual(a["rule_candidates"][0]["research_anchor"]["section_sha256"],
                         sha(b"synthetic-only"))
        self.assertNotIn("synthetic-only", json.dumps(a))

    def test_order_invariant(self):
        first = self.result()
        self.manifest["concepts"].reverse()
        self.assertEqual(first, self.result())

    def test_external_graph_pin_required(self):
        with self.assertRaisesRegex(CatalogError, "TRUSTED_GRAPH_PIN_REQUIRED"):
            build_catalog(self.graph, "0"*63, self.manifest)

    def test_forged_section_detected_by_pinned_hash(self):
        self.graph["nodes"][2]["section_sha256"] = "0"*64
        with self.assertRaisesRegex(CatalogError, "STAGE08_DIGEST_MISMATCH"):
            self.result()

    def test_graph_support_promotion_refused(self):
        self.graph["rule_support_attested"] = True
        self.repin()
        with self.assertRaisesRegex(CatalogError, "STAGE08_NONPROMOTION_FLAG_INVALID"):
            self.result()

    def test_only_unassessed_pointer_allowed(self):
        self.graph["nodes"][0]["review_status"] = "VERIFIED"
        self.repin()
        with self.assertRaisesRegex(CatalogError, "STAGE08_RULE_POINTER_INVALID"):
            self.result()

    def test_no_normative_edge(self):
        self.graph["edges"][0]["kind"] = "SUPPORTS_RULE"
        self.repin()
        with self.assertRaisesRegex(CatalogError, "STAGE08_POINTER_NAVIGATION_INVALID"):
            self.result()

    def test_mismatched_query_source_refused(self):
        self.graph["nodes"][1]["witness_id"] = "synthetic:wrong"
        self.repin()
        with self.assertRaisesRegex(CatalogError, "STAGE08_POINTER_SECTION_INVALID"):
            self.result()

    def test_undeclared_rule_pointer_refused(self):
        self.manifest["rule_candidates"][0]["pointer_id"] = "pointer:missing"
        with self.assertRaisesRegex(CatalogError, "RULE_RESEARCH_POINTER_REQUIRED"):
            self.result()

    def test_prose_or_normative_rule_fields_refused(self):
        self.manifest["rule_candidates"][0]["rule_kind"] = "qiyas"
        with self.assertRaisesRegex(CatalogError, "RULE_FIELDS_INVALID"):
            self.result()
        del self.manifest["rule_candidates"][0]["rule_kind"]
        self.manifest["concepts"][0]["definition"] = "Arabic source excerpt"
        with self.assertRaisesRegex(CatalogError, "CONCEPT_FIELDS_INVALID"):
            self.result()

    def test_bad_concept_and_duplicate_ref_refused(self):
        self.manifest["rule_candidates"][0]["if_concepts"].append("concept:absent")
        with self.assertRaisesRegex(CatalogError, "RULE_CONCEPT_REFERENCES_INVALID"):
            self.result()
        self.manifest["rule_candidates"][0]["if_concepts"] = ["concept:command"]
        self.manifest["concepts"].append(copy.deepcopy(self.manifest["concepts"][0]))
        with self.assertRaisesRegex(CatalogError, "CONCEPT_IDENTIFIER_INVALID"):
            self.result()

    def test_cycle_in_proposed_broader_than_refused(self):
        self.manifest["relations"] = [
            {"from_concept_id": x, "to_concept_id": y,
             "kind": "PROPOSED_BROADER_THAN", "review_status": "UNASSESSED"}
            for x, y in (("concept:command", "concept:outcome"),
                         ("concept:outcome", "concept:command"))
        ]
        with self.assertRaisesRegex(CatalogError, "BROADER_THAN_PROPOSAL_CYCLE"):
            self.result()

    def test_undirected_relation_duplicate_refused(self):
        self.manifest["relations"].append({
            "from_concept_id": "concept:outcome", "to_concept_id": "concept:command",
            "kind": "PROPOSED_RELATED_TO", "review_status": "UNASSESSED"})
        with self.assertRaisesRegex(CatalogError, "RELATION_DUPLICATED"):
            self.result()

    def test_review_status_cannot_be_fabricated(self):
        self.manifest["rule_candidates"][0]["review_status"] = "VERIFIED"
        with self.assertRaisesRegex(CatalogError, "RULE_RESEARCH_POINTER_REQUIRED"):
            self.result()

    def test_real_stage08_builder_interoperability(self):
        # Stage07 + Stage08 are the actual implementations; source is synthetic.
        from engines.usul.arabic_evidence_retrieval import FOLD_MARKS, retrieve
        from engines.usul.evidence_context_graph import build_context_graph
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "witness.txt"
            f.write_text("بداية\nالأمر\nنهاية\n", encoding="utf-8")
            w = [{"source_id": "synthetic:w1", "section_path": f,
                  "section_sha256": sha(f.read_bytes()),
                  "source_url": "https://example.invalid/synthetic",
                  "section_locator": "synthetic", "offset_basis": "utf8_export",
                  "source_byte_base": 0, "source_line_base": 1}]
            queries = [{"id": "query:amr", "literal": "الأمر",
                        "candidate_profiles": [FOLD_MARKS]}]
            pointers = [{"id": "pointer:real", "kind": "RULE_RESEARCH_POINTER",
                         "reference_id": "research:amr", "witness_id": "synthetic:w1",
                         "query_id": "query:amr", "review_status": "UNASSESSED"}]
            stage07 = retrieve(w, queries)
            stage08 = build_context_graph(stage07, w, queries, pointers)
            self.manifest["rule_candidates"][0]["pointer_id"] = "pointer:real"
            a = build_catalog(stage08, stage08["graph_sha256"], self.manifest)
            self.assertEqual(a["status"], "U02_CANDIDATE_CATALOG_PASS")
            self.assertEqual(a["rule_candidates"][0]["research_anchor"]["section_sha256"],
                             sha(f.read_bytes()))
            self.assertFalse(a["source_support_attested"])


if __name__ == "__main__":
    unittest.main()
