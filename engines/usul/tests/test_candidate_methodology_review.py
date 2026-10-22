"""Synthetic actual Stage07->Stage08->U0.2.0->U0.2.1 tests."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from engines.usul.arabic_evidence_retrieval import FOLD_MARKS, retrieve
from engines.usul.evidence_context_graph import build_context_graph
from engines.usul.concept_rule_catalog import CatalogError, build_catalog, sha
from engines.usul.candidate_methodology_review import build_methodology_review


class MethodologyCandidateReviewTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        f = Path(temp.name) / "synthetic.txt"
        f.write_text("مقدمة\nالأمر\nخاتمة\n", encoding="utf-8")
        witnesses = [{"source_id": "synthetic:w1", "section_path": f,
                      "section_sha256": sha(f.read_bytes()),
                      "source_url": "https://example.invalid/metadata-only",
                      "section_locator": "synthetic", "offset_basis": "utf8_export",
                      "source_byte_base": 0, "source_line_base": 1}]
        queries = [{"id": "query:amr", "literal": "الأمر",
                    "candidate_profiles": [FOLD_MARKS]}]
        pointers = [
            {"id": k, "kind": "RULE_RESEARCH_POINTER",
             "reference_id": "research:amr", "witness_id": "synthetic:w1",
             "query_id": "query:amr", "review_status": "UNASSESSED"}
            for k in ("pointer:first", "pointer:second")
        ]
        self.graph = build_context_graph(retrieve(witnesses, queries),
                                         witnesses, queries, pointers)
        self.pin = self.graph["graph_sha256"]
        self.catalog_manifest = {
            "schema_version": "u0.2.0",
            "concepts": [
                {"id": identifier, "concept_kind": kind,
                 "review_status": "UNASSESSED"}
                for identifier, kind in [
                    ("concept:premise", "TERM"), ("concept:exception", "EXCEPTION"),
                    ("concept:outcome", "OUTCOME"), ("concept:alternative", "OUTCOME")]
            ],
            "rule_candidates": [
                {"id": "candidate:first", "pointer_id": "pointer:first",
                 "if_concepts": ["concept:premise"],
                 "unless_concepts": ["concept:exception"],
                 "then_concept": "concept:outcome", "review_status": "UNASSESSED"},
                {"id": "candidate:second", "pointer_id": "pointer:second",
                 "if_concepts": ["concept:premise"],
                 "unless_concepts": ["concept:exception"],
                 "then_concept": "concept:alternative", "review_status": "UNASSESSED"},
            ],
            "relations": [],
        }
        self.catalog = build_catalog(self.graph, self.pin, self.catalog_manifest)
        self.overlay = {
            "schema_version": "u0.2.1",
            "catalog_sha256": self.catalog["catalog_sha256"],
            "methodology_profiles": [
                {"id": "methodology:alpha", "version": "0.1.0",
                 "research_pointer_ids": ["pointer:first"], "review_status": "UNASSESSED"},
                {"id": "methodology:beta", "version": "0.2.0",
                 "research_pointer_ids": ["pointer:second"], "review_status": "UNASSESSED"},
            ],
            "rule_profile_bindings": [
                {"rule_candidate_id": "candidate:first", "methodology_id": "methodology:alpha",
                 "methodology_version": "0.1.0", "review_status": "UNASSESSED"},
                {"rule_candidate_id": "candidate:second", "methodology_id": "methodology:beta",
                 "methodology_version": "0.2.0", "review_status": "UNASSESSED"},
            ],
            "ambiguities": [
                {"id": "ambiguity:exception", "subject_type": "CONCEPT",
                 "subject_id": "concept:exception",
                 "kind": "EXCEPTION_SCOPE_UNRESOLVED",
                 "research_pointer_id": "pointer:first",
                 "review_status": "UNRESOLVED"},
                {"id": "ambiguity:second", "subject_type": "RULE_CANDIDATE",
                 "subject_id": "candidate:second",
                 "kind": "FORMALIZATION_UNRESOLVED",
                 "research_pointer_id": "pointer:second",
                 "review_status": "UNRESOLVED"},
            ],
            "disagreements": [
                {"id": "difference:alpha-beta",
                 "left_rule_candidate_id": "candidate:first",
                 "right_rule_candidate_id": "candidate:second",
                 "kind": "PROFILE_DIVERGENCE", "review_status": "UNASSESSED"},
            ],
        }

    def run_review(self):
        return build_methodology_review(self.graph, self.pin,
                                        self.catalog_manifest, self.overlay)

    def test_complete_synthetic_integration_and_no_promotion(self):
        result = self.run_review()
        self.assertEqual(result["status"], "U02_METHODOLOGY_CANDIDATE_REVIEW_PASS")
        self.assertEqual((result["profile_count"], result["binding_count"],
                          result["ambiguity_count"],
                          result["disagreement_candidate_count"]), (2, 2, 2, 1))
        self.assertEqual(len(result["methodology_review_sha256"]), 64)
        self.assertEqual(result, self.run_review())
        for k in ("source_text_included", "rule_execution_performed",
                  "source_support_attested", "semantic_equivalence_verified",
                  "methodology_scholarly_authenticated",
                  "real_juristic_disagreement_attested", "scholarly_verified",
                  "redistribution_approved", "juristic_inference_allowed",
                  "public_fatwa_authorized"):
            self.assertFalse(result[k], k)
        self.assertNotIn("الأمر", json.dumps(result, ensure_ascii=False))

    def test_profile_and_bindings_order_independent(self):
        first = self.run_review()
        self.overlay["methodology_profiles"].reverse()
        self.overlay["rule_profile_bindings"].reverse()
        self.overlay["ambiguities"].reverse()
        self.assertEqual(first, self.run_review())

    def test_stale_catalog_fails_closed(self):
        self.overlay["catalog_sha256"] = "0"*64
        with self.assertRaisesRegex(CatalogError, "METHODOLOGY_STALE_CATALOG_PIN"):
            self.run_review()

    def test_forged_stage08_pin_fails_even_if_catalog_pin_remains_valid(self):
        self.graph["nodes"][0]["pointer_id"] = "pointer:fraud"
        with self.assertRaisesRegex(CatalogError, "STAGE08_DIGEST_MISMATCH"):
            self.run_review()

    def test_reject_unexpected_fields_and_methodology_authentication(self):
        self.overlay["methodology_profiles"][0]["scholarly_verified"] = True
        with self.assertRaisesRegex(CatalogError, "METHODOLOGY_PROFILE_FIELDS_INVALID"):
            self.run_review()

    def test_methodology_profile_cannot_claim_verified_status(self):
        self.overlay["methodology_profiles"][0]["review_status"] = "VERIFIED"
        with self.assertRaisesRegex(CatalogError, "METHODOLOGY_PROFILE_UNATTESTED"):
            self.run_review()

    def test_methodology_profile_must_be_versioned(self):
        self.overlay["methodology_profiles"][0]["version"] = "alpha-latest"
        with self.assertRaisesRegex(CatalogError, "METHODOLOGY_PROFILE_UNATTESTED"):
            self.run_review()

    def test_unanchored_profile_rejected(self):
        self.overlay["methodology_profiles"][0]["research_pointer_ids"] = ["pointer:missing"]
        with self.assertRaisesRegex(CatalogError, "METHODOLOGY_PROFILE_UNATTESTED"):
            self.run_review()

    def test_binding_cannot_cross_methodologies_or_pointer_scopes(self):
        self.overlay["rule_profile_bindings"][0]["methodology_id"] = "methodology:beta"
        self.overlay["rule_profile_bindings"][0]["methodology_version"] = "0.2.0"
        with self.assertRaisesRegex(CatalogError, "METHODOLOGY_RULE_BINDING_INVALID"):
            self.run_review()

    def test_binding_stale_version_refused(self):
        self.overlay["rule_profile_bindings"][0]["methodology_version"] = "0.0.1"
        with self.assertRaisesRegex(CatalogError, "METHODOLOGY_RULE_BINDING_INVALID"):
            self.run_review()

    def test_duplicate_rule_bindings_refused(self):
        self.overlay["rule_profile_bindings"][1]["rule_candidate_id"] = "candidate:first"
        with self.assertRaisesRegex(CatalogError, "METHODOLOGY_RULE_BINDING_INVALID"):
            self.run_review()

    def test_unknown_ambiguity_subject_refused(self):
        self.overlay["ambiguities"][0]["subject_id"] = "concept:missing"
        with self.assertRaisesRegex(CatalogError, "AMBIGUITY_UNANCHORED_OR_PROMOTED"):
            self.run_review()

    def test_ambiguity_must_use_a_pointer_of_its_subject(self):
        self.overlay["ambiguities"][1]["research_pointer_id"] = "pointer:first"
        with self.assertRaisesRegex(CatalogError, "AMBIGUITY_UNANCHORED_OR_PROMOTED"):
            self.run_review()

    def test_unresolved_ambiguity_cannot_be_marked_resolved(self):
        self.overlay["ambiguities"][0]["review_status"] = "RESOLVED"
        with self.assertRaisesRegex(CatalogError, "AMBIGUITY_UNANCHORED_OR_PROMOTED"):
            self.run_review()

    def test_no_invented_disagreement_semantics(self):
        self.overlay["disagreements"][0]["juristic_conclusion"] = "obligatory"
        with self.assertRaisesRegex(CatalogError, "DISAGREEMENT_FIELDS_INVALID"):
            self.run_review()

    def test_disagreement_requires_distinct_rule_candidates(self):
        self.overlay["disagreements"][0]["right_rule_candidate_id"] = "candidate:first"
        with self.assertRaisesRegex(CatalogError, "DISAGREEMENT_INVALID"):
            self.run_review()

    def test_profile_divergence_cannot_use_same_profile(self):
        self.overlay["rule_profile_bindings"][1]["methodology_id"] = "methodology:alpha"
        self.overlay["rule_profile_bindings"][1]["methodology_version"] = "0.1.0"
        self.overlay["methodology_profiles"][0]["research_pointer_ids"].append(
            "pointer:second")
        with self.assertRaisesRegex(CatalogError, "DISAGREEMENT_PROFILE_NOT_DISTINCT"):
            self.run_review()

    def test_structural_alternative_requires_actual_structural_difference(self):
        self.overlay["disagreements"][0]["kind"] = "STRUCTURAL_ALTERNATIVE"
        self.catalog_manifest["rule_candidates"][1]["then_concept"] = "concept:outcome"
        self.overlay["catalog_sha256"] = build_catalog(
            self.graph, self.pin, self.catalog_manifest)["catalog_sha256"]
        with self.assertRaisesRegex(CatalogError, "DISAGREEMENT_NO_STRUCTURAL_ALTERNATIVE"):
            self.run_review()

    def test_mirrored_disagreement_not_allowed(self):
        self.overlay["disagreements"].append({
            "id": "difference:reverse", "left_rule_candidate_id": "candidate:second",
            "right_rule_candidate_id": "candidate:first",
            "kind": "PROFILE_DIVERGENCE", "review_status": "UNASSESSED",
        })
        with self.assertRaisesRegex(CatalogError, "DISAGREEMENT_DUPLICATED"):
            self.run_review()

    def test_disagreement_requires_shared_comparison_concept(self):
        self.catalog_manifest["concepts"].extend([
            {"id": "concept:other-premise", "concept_kind": "TERM",
             "review_status": "UNASSESSED"},
            {"id": "concept:other-exception", "concept_kind": "EXCEPTION",
             "review_status": "UNASSESSED"},
        ])
        rule = self.catalog_manifest["rule_candidates"][1]
        rule["if_concepts"] = ["concept:other-premise"]
        rule["unless_concepts"] = ["concept:other-exception"]
        self.overlay["catalog_sha256"] = build_catalog(
            self.graph, self.pin, self.catalog_manifest)["catalog_sha256"]
        with self.assertRaisesRegex(CatalogError, "DISAGREEMENT_NO_COMMON_CONCEPT"):
            self.run_review()

    def test_malformed_ambiguity_kind_rejected_as_contract_error(self):
        self.overlay["ambiguities"][0]["kind"] = ["LEXICAL_SCOPE_UNRESOLVED"]
        with self.assertRaisesRegex(CatalogError, "AMBIGUITY_UNANCHORED_OR_PROMOTED"):
            self.run_review()

    def test_malformed_disagreement_kind_rejected_as_contract_error(self):
        self.overlay["disagreements"][0]["kind"] = ["PROFILE_DIVERGENCE"]
        with self.assertRaisesRegex(CatalogError, "DISAGREEMENT_INVALID"):
            self.run_review()

    def test_structural_alternative_does_not_imply_actual_disagreement(self):
        self.overlay["disagreements"][0]["kind"] = "STRUCTURAL_ALTERNATIVE"
        a = self.run_review()
        self.assertEqual(a["disagreement_candidate_count"], 1)
        self.assertFalse(a["real_juristic_disagreement_attested"])
        self.assertFalse(a["semantic_equivalence_verified"])

    def test_duplicate_ambiguity_id_not_allowed(self):
        self.overlay["ambiguities"].append(copy.deepcopy(self.overlay["ambiguities"][0]))
        with self.assertRaisesRegex(CatalogError, "AMBIGUITY_IDS_INVALID"):
            self.run_review()

    def test_malformed_bound_or_schema_version_rejected(self):
        self.overlay["schema_version"] = "u0.2.99"
        with self.assertRaisesRegex(CatalogError, "METHODOLOGY_STALE_CATALOG_PIN"):
            self.run_review()
        self.overlay["schema_version"] = "u0.2.1"
        self.overlay["methodology_profiles"] = []
        with self.assertRaisesRegex(CatalogError, "METHODOLOGY_REVIEW_BOUNDS_INVALID"):
            self.run_review()


if __name__ == "__main__":
    unittest.main()
