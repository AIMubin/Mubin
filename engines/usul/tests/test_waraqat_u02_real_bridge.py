"""Adversarial U0.2.2 synthetic-only tests; private Waraqat sources never needed."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engines.usul.arabic_evidence_retrieval import FOLD_MARKS, retrieve
from engines.usul.evidence_context_graph import build_context_graph
from engines.usul.concept_rule_catalog import CatalogError, sha
from engines.usul.pilots import waraqat_u02_real_bridge as bridge


class WaraqatU02BridgeTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        root = Path(t.name)
        self.primary = root / "synthetic-w1.txt"
        self.secondary = root / "synthetic-w2.txt"
        self.primary.write_text("الأمر الأمر\nالقرينة الوجوب\n", encoding="utf-8")
        self.secondary.write_text("الْأَمْر\nوحدات اصطناعية\n", encoding="utf-8")
        self.w1_sha = sha(self.primary.read_bytes())
        self.w2_sha = sha(self.secondary.read_bytes())
        witnesses = [
            {"source_id": "pilot:waraqat-primary",
             "section_path": self.primary, "section_sha256": self.w1_sha,
             "source_url": "https://example.invalid/w1",
             "section_locator": "synthetic W1", "offset_basis": "utf8_export",
             "source_byte_base": 0, "source_line_base": 1},
            {"source_id": "pilot:waraqat-comparator",
             "section_path": self.secondary, "section_sha256": self.w2_sha,
             "source_url": "https://example.invalid/w2",
             "section_locator": "synthetic W2",
             "offset_basis": "extracted_section",
             "source_byte_base": 0, "source_line_base": 1},
        ]
        queries = [{"id": ident, "literal": word,
                    "candidate_profiles": [FOLD_MARKS]}
                   for ident, word in (
                       ("pilot:amr-term", "الأمر"),
                       ("pilot:qarinah-term", "القرينة"),
                       ("pilot:wujub-term", "الوجوب"))]
        pointers = [
            {"id": "pilot:amr-rule-research-pointer",
             "kind": "RULE_RESEARCH_POINTER",
             "reference_id": "pilot:rule-amr-default",
             "witness_id": "pilot:waraqat-primary",
             "query_id": "pilot:amr-term",
             "review_status": "UNASSESSED"},
            {"id": "pilot:qarinah-objection-research-pointer",
             "kind": "OBJECTION_RESEARCH_POINTER",
             "reference_id": "pilot:objection-candidate",
             "witness_id": "pilot:waraqat-comparator",
             "query_id": "pilot:qarinah-term",
             "review_status": "UNASSESSED"},
        ]
        graph = build_context_graph(retrieve(witnesses, queries),
                                    witnesses, queries, pointers)
        graph.update({
            "status": "STAGE08_DUAL_SOURCE_CONTEXT_GRAPH_PASS",
            "runner": bridge.stage08.VERSION,
            "source_replay_verified_by_runner": True,
            "source_replay_status": "STAGE07_DUAL_WITNESS_ARABIC_RETRIEVAL_PASS",
            "primary_section_sha256": self.w1_sha,
            "secondary_section_sha256": self.w2_sha,
        })
        self.graph = graph
        self.expected_nodes = len(graph["nodes"])
        self.expected_edges = len(graph["edges"])
        self.catalog = {
            "schema_version": "u0.2.0",
            "concepts": [
                {"id": k, "concept_kind": kind, "review_status": "UNASSESSED"}
                for k, kind in (
                    ("concept:amr-term", "TERM"),
                    ("concept:qarinah-candidate", "EXCEPTION"),
                    ("concept:wujub-candidate", "OUTCOME"))
            ],
            "rule_candidates": [{
                "id": "candidate:amr-structural-hypothesis",
                "pointer_id": "pilot:amr-rule-research-pointer",
                "if_concepts": ["concept:amr-term"],
                "unless_concepts": ["concept:qarinah-candidate"],
                "then_concept": "concept:wujub-candidate",
                "review_status": "UNASSESSED",
            }],
            "relations": [],
        }
        self.lexical = {
            "schema_version": "u0.2.2",
            "lexical_bindings": [
                {"concept_id": c, "witness_id": "pilot:waraqat-primary",
                 "query_id": q, "classification": "EXACT_LITERAL_ONLY",
                 "expected_unique_occurrences": cnt}
                for c, q, cnt in (
                    ("concept:amr-term", "pilot:amr-term", 2),
                    ("concept:qarinah-candidate", "pilot:qarinah-term", 1),
                    ("concept:wujub-candidate", "pilot:wujub-term", 1))
            ]
        }

    def result(self):
        with patch.object(bridge, "WARAQAT_STAGE08_GRAPH_SHA256",
                          self.graph["graph_sha256"]), \
             patch.object(bridge, "W1_SECTION_SHA", self.w1_sha), \
             patch.object(bridge, "W2_SECTION_SHA", self.w2_sha), \
             patch.object(bridge, "EXPECTED_WITNESSES", {
                 "pilot:waraqat-primary": self.w1_sha,
                 "pilot:waraqat-comparator": self.w2_sha,
             }), \
             patch.object(bridge, "EXPECTED_NODES", self.expected_nodes), \
             patch.object(bridge, "EXPECTED_EDGES", self.expected_edges):
            return bridge.bind_replayed_metadata(self.graph,
                                                  self.catalog, self.lexical)

    def test_actual_stage07_stage08_to_u02_catalog_synthetic_integration(self):
        result = self.result()
        self.assertEqual(result["status"], "U02_WARAQAT_PINNED_CATALOG_PASS")
        self.assertEqual(result, self.result())
        self.assertTrue(result["source_replay_executed_here"])
        self.assertEqual(result["lexical_binding_count"], 3)
        self.assertEqual(
            {r["concept_id"]: r["unique_occurrence_count"]
             for r in result["lexical_bindings"]},
            {"concept:amr-term": 2, "concept:qarinah-candidate": 1,
             "concept:wujub-candidate": 1})
        for key in ("source_text_included", "scholarly_verified",
                    "redistribution_approved", "semantic_equivalence_verified",
                    "public_fatwa_authorized", "juristic_inference_allowed",
                    "source_support_attested", "source_edition_authenticated",
                    "formalization_verified", "rule_execution_performed"):
            self.assertFalse(result[key])
        self.assertNotIn("القرينة الوجوب", json.dumps(result, ensure_ascii=False))

    def test_stale_graph_mutation_rejected_even_if_source_replay_flag_present(self):
        self.graph["nodes"][0]["kind"] = "FRAUD"
        with self.assertRaisesRegex(CatalogError, "STAGE08_DIGEST_MISMATCH"):
            self.result()

    def test_forged_runner_attestation_rejected(self):
        self.graph["source_replay_verified_by_runner"] = False
        with self.assertRaisesRegex(CatalogError, "WARAQAT_REAL_SOURCE_REPLAY_PIN_MISMATCH"):
            self.result()

    def test_forged_frozen_source_pin_rejected(self):
        self.graph["secondary_section_sha256"] = "0"*64
        with self.assertRaisesRegex(CatalogError, "WARAQAT_REAL_SOURCE_REPLAY_PIN_MISMATCH"):
            self.result()

    def test_unexpected_extra_stage08_nodes_fail_fixed_inventory(self):
        self.graph["nodes"].append({"id": "fake:node", "kind": "FAKE"})
        with self.assertRaisesRegex(CatalogError, "WARAQAT_REAL_SOURCE_REPLAY_PIN_MISMATCH"):
            self.result()

    def test_lexical_count_forgery_rejected(self):
        self.lexical["lexical_bindings"][0]["expected_unique_occurrences"] = 3
        with self.assertRaisesRegex(CatalogError, "LEXICAL_EXPECTED_COUNT_MISMATCH"):
            self.result()

    def test_unrelated_query_refused(self):
        self.lexical["lexical_bindings"][0]["query_id"] = "pilot:unrelated"
        with self.assertRaisesRegex(CatalogError, "LEXICAL_QUERY_UNRESOLVED"):
            self.result()

    def test_orthographic_candidates_cannot_impersonate_exact(self):
        self.lexical["lexical_bindings"][0]["classification"] = (
            "ORTHOGRAPHIC_CANDIDATE_ONLY")
        with self.assertRaisesRegex(CatalogError, "LEXICAL_EXPECTED_COUNT_MISMATCH"):
            self.result()

    def test_all_concept_ids_require_lexical_bindings(self):
        self.lexical["lexical_bindings"].pop()
        with self.assertRaisesRegex(CatalogError, "LEXICAL_CONCEPT_COVERAGE_INCOMPLETE"):
            self.result()

    def test_duplicate_concept_lexical_bindings_rejected(self):
        self.lexical["lexical_bindings"].append(
            copy.deepcopy(self.lexical["lexical_bindings"][0]))
        with self.assertRaisesRegex(CatalogError, "LEXICAL_BINDING_UNSUPPORTED_REFERENCE"):
            self.result()

    def test_unknown_lexical_field_rejected(self):
        self.lexical["lexical_bindings"][0]["source_support_attested"] = True
        with self.assertRaisesRegex(CatalogError, "LEXICAL_BINDING_FIELDS_INVALID"):
            self.result()

    def test_invalid_positive_count_rejected(self):
        self.lexical["lexical_bindings"][0]["expected_unique_occurrences"] = True
        with self.assertRaisesRegex(CatalogError, "LEXICAL_BINDING_UNSUPPORTED_REFERENCE"):
            self.result()

    def test_rule_promoting_catalog_rejected(self):
        self.catalog["rule_candidates"][0]["review_status"] = "VERIFIED"
        with self.assertRaisesRegex(CatalogError, "RULE_RESEARCH_POINTER_REQUIRED"):
            self.result()

    def test_actual_replay_gateway_invoked_before_binding(self):
        paths = tuple(str(self.primary) for _ in range(6))
        with patch.object(bridge.stage08, "replay_and_graph",
                          return_value=self.graph) as gateway, \
             patch.object(bridge, "WARAQAT_STAGE08_GRAPH_SHA256",
                          self.graph["graph_sha256"]), \
             patch.object(bridge, "W1_SECTION_SHA", self.w1_sha), \
             patch.object(bridge, "W2_SECTION_SHA", self.w2_sha), \
             patch.object(bridge, "EXPECTED_WITNESSES", {
                 "pilot:waraqat-primary": self.w1_sha,
                 "pilot:waraqat-comparator": self.w2_sha,
             }), \
             patch.object(bridge, "EXPECTED_NODES", self.expected_nodes), \
             patch.object(bridge, "EXPECTED_EDGES", self.expected_edges):
            report = bridge.replay_and_bind(paths, [], [], self.catalog, self.lexical)
        gateway.assert_called_once_with(*paths, [], [])
        self.assertEqual(report["status"], "U02_WARAQAT_PINNED_CATALOG_PASS")

    def test_cli_without_private_files_returns_pending_and_no_text(self):
        p = Path(self.primary.parent) / "result.json"
        paths = []
        for name in ("primary-html", "primary-export", "primary-manifest",
                     "primary-section", "secondary-html", "secondary-section"):
            paths.extend(["--"+name, str(self.primary.parent / (name+".missing"))])
        proc = subprocess.run(
            [sys.executable, "-m", "engines.usul.pilots.waraqat_u02_real_bridge",
             *paths, "--report", str(p)],
            cwd=Path(__file__).resolve().parents[3],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 3, proc.stderr)
        self.assertEqual(json.loads(p.read_text(encoding="utf-8"))["status"],
                         "PENDING_PRIVATE_WITNESS_FILES")
        self.assertNotIn("الأمر", p.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
