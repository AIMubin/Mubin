"""Stage08 metadata graph tests using only synthetic Arabic witnesses."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from engines.usul.arabic_evidence_retrieval import (
    FOLD_BRACKETS, FOLD_MARKS, FOLD_SPACES, retrieve,
)
from engines.usul.evidence_context_graph import (
    ContextGraphError, build_context_graph,
)

SOURCES = (
    "المقدمة\nالأمر لا يعني الندب\nو أما القرينة فمذكورة\nالنهاية\n",
    "المقدمة\nالْأَمْر لا يعني [الندب]\nوأما القرينة فمذكورة\nالنهاية\n",
)
QUERIES = [
    {"id": "pilot:amr", "literal": "الأمر",
     "candidate_profiles": [FOLD_MARKS, FOLD_BRACKETS, FOLD_SPACES]},
    {"id": "pilot:split", "literal": "و أما",
     "candidate_profiles": [FOLD_MARKS, FOLD_BRACKETS, FOLD_SPACES]},
    {"id": "pilot:absent", "literal": "دليل غائب",
     "candidate_profiles": [FOLD_MARKS]},
]
POINTERS = [
    {"id": "pilot:rule-navigation", "kind": "RULE_RESEARCH_POINTER",
     "reference_id": "pilot:rule-amr-default", "witness_id": "pilot:w1",
     "query_id": "pilot:amr", "review_status": "UNASSESSED"},
    {"id": "pilot:objection-navigation", "kind": "OBJECTION_RESEARCH_POINTER",
     "reference_id": "pilot:objection-review", "witness_id": "pilot:w2",
     "query_id": "pilot:absent", "review_status": "UNASSESSED"},
]


def digest(data):
    return hashlib.sha256(data).hexdigest()


class ContextGraphTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.witnesses = []
        for i, text in enumerate(SOURCES):
            path = root / f"w{i}.txt"
            path.write_bytes(text.encode("utf-8"))
            self.witnesses.append({
                "source_id": f"pilot:w{i+1}", "section_path": path,
                "section_sha256": digest(path.read_bytes()),
                "source_url": f"https://example.invalid/witness-{i}",
                "section_locator": "synthetic باب الأمر",
                "offset_basis": "utf8_export" if i == 0 else "extracted_section",
                "source_byte_base": 50 if i == 0 else 0,
                "source_line_base": 7 if i == 0 else 1,
            })
        self.report = retrieve(self.witnesses, QUERIES)

    def build(self, report=None, pointers=None, **kwargs):
        return build_context_graph(
            self.report if report is None else report,
            self.witnesses, QUERIES,
            POINTERS if pointers is None else pointers,
            work_title="Synthetic only", author="Synthetic author", **kwargs)

    def test_replay_and_graph_determinism(self):
        a = self.build()
        self.assertEqual(a, self.build())
        self.assertEqual(a["status"], "EVIDENCE_CONTEXT_GRAPH_PASS")
        self.assertEqual(len(a["graph_sha256"]), 64)
        self.assertTrue(a["all_edge_references_valid"])
        self.assertFalse(a["source_text_included"])
        self.assertFalse(a["semantic_qarinah_verified"])
        self.assertFalse(a["juristic_inference_allowed"])
        self.assertFalse(a["lexical_matches_promoted_to_rules"])
        self.assertEqual(a["nodes_by_kind"]["SOURCE_WITNESS"], 2)
        self.assertEqual(a["nodes_by_kind"]["PINNED_SECTION"], 2)
        self.assertEqual(a["nodes_by_kind"]["RULE_RESEARCH_POINTER"], 1)
        self.assertEqual(a["nodes_by_kind"]["OBJECTION_RESEARCH_POINTER"], 1)
        self.assertNotIn("الأمر لا يعني الندب", json.dumps(a, ensure_ascii=False))

    def test_all_context_hashes_reconstruct_original_bytes(self):
        graph = self.build()
        witness_to_section = {
            w["source_id"]: w for w in self.witnesses
        }
        sections = {n["id"]: n for n in graph["nodes"]
                    if n["kind"] == "PINNED_SECTION"}
        for context in (n for n in graph["nodes"] if n["kind"] == "HASHED_CONTEXT"):
            sec = sections[context["section_id"]]
            raw = Path(witness_to_section[sec["source_id"]]["section_path"]).read_bytes()
            start, end = context["section_byte_start"], context["section_byte_end_exclusive"]
            self.assertEqual(digest(raw[start:end]), context["context_sha256"])
            self.assertTrue(0 <= start < end <= len(raw))
        for occurrence in (n for n in graph["nodes"] if n["kind"] == "TEXT_OCCURRENCE"):
            sec = sections[occurrence["section_id"]]
            origin = witness_to_section[sec["source_id"]]
            raw = Path(origin["section_path"]).read_bytes()
            a, b = occurrence["section_byte_start"], occurrence["section_byte_end_exclusive"]
            self.assertEqual(digest(raw[a:b]), occurrence["original_span_sha256"])
            self.assertEqual(occurrence["source_byte_start"], a+origin["source_byte_base"])
            self.assertEqual(occurrence["source_byte_end_exclusive"], b+origin["source_byte_base"])

    def test_candidate_edges_never_upgrade_occurrence_or_rule(self):
        graph = self.build()
        candidate = [e for e in graph["edges"] if e["kind"] == "QUERY_LOCATES_OCCURRENCE"
                     and e["classification"] == "ORTHOGRAPHIC_CANDIDATE_ONLY"]
        self.assertGreater(len(candidate), 0)
        self.assertTrue(all(e["semantic_equivalence_verified"] is False for e in candidate))
        self.assertTrue(all(n["semantic_classification"] == "NOT_EVALUATED"
                            for n in graph["nodes"] if n["kind"] == "TEXT_OCCURRENCE"))
        self.assertEqual(
            {e["kind"] for e in graph["edges"] if "POINTER" in e["from"]}, set())
        pointers = [e for e in graph["edges"] if e["kind"] == "RESEARCH_NAVIGATION_ONLY"]
        self.assertEqual(len(pointers), 2)
        self.assertTrue(all(e["no_claim_of_support"] and e["no_claim_of_exception"]
                            for e in pointers))
        self.assertTrue(all(
            n["review_status"] == "UNASSESSED"
            for n in graph["nodes"] if n["kind"] in
            ("RULE_RESEARCH_POINTER", "OBJECTION_RESEARCH_POINTER")
        ))

    def test_same_span_under_multiple_profiles_is_one_occurrence(self):
        graph = self.build(pointers=[])
        observations = [n for n in graph["nodes"] if n["kind"] == "TEXT_OCCURRENCE"]
        signatures = {
            (n["section_id"], n["section_byte_start"], n["section_byte_end_exclusive"])
            for n in observations
        }
        self.assertEqual(len(observations), len(signatures))
        self.assertGreater(graph["edges_by_kind"]["QUERY_LOCATES_OCCURRENCE"],
                           len(observations))

    def test_false_report_positive_or_candidate_hash_refused(self):
        forged = copy.deepcopy(self.report)
        forged["witnesses"][0]["queries"][0]["strict_matches"][0][
            "original_bytes_sha256"] = "0"*64
        with self.assertRaisesRegex(ContextGraphError, "not independently"):
            self.build(forged)
        forged = copy.deepcopy(self.report)
        forged["witnesses"][1]["queries"][0]["candidate_profiles"][0][
            "matches"][0]["profile"] = "literal_exact_v1"
        with self.assertRaisesRegex(ContextGraphError, "not independently"):
            self.build(forged)

    def test_tampered_private_bytes_fail_after_stage07_report(self):
        f = Path(self.witnesses[0]["section_path"])
        f.write_bytes(f.read_bytes().replace("لا".encode(), "ما".encode()))
        with self.assertRaises(ArabicRetrievalError):
            self.build()

    def test_stage07_strict_provenance_metadata_required_for_accepted_dual_status(self):
        with self.assertRaisesRegex(ContextGraphError, "status"):
            self.build({"status": "source_claim"})
        dual = {**copy.deepcopy(self.report),
                "status": "STAGE07_DUAL_WITNESS_ARABIC_RETRIEVAL_PASS"}
        with self.assertRaisesRegex(ContextGraphError, "Stage06"):
            self.build(dual)
        dual["stage06_strict_provenance"] = {
            "status": "STAGE06_DUAL_SOURCE_EXTRACTION_REPLAY_PASS",
            "both_html_to_section_replays_verified": True,
        }
        self.assertEqual(self.build(dual)["status"], "EVIDENCE_CONTEXT_GRAPH_PASS")

    def test_pointers_must_be_unassessed_and_reference_known_query(self):
        for change in (
            {"review_status": "VERIFIED"},
            {"query_id": "pilot:unknown"},
            {"witness_id": "pilot:unknown"},
            {"kind": "SUPPORTS_RULE"},
            {"reference_id": ""},
        ):
            ptrs = copy.deepcopy(POINTERS)
            ptrs[0].update(change)
            with self.subTest(change=change), self.assertRaises(ContextGraphError):
                self.build(pointers=ptrs)
        with self.assertRaisesRegex(ContextGraphError, "duplicate"):
            self.build(pointers=[POINTERS[0], POINTERS[0]])

    def test_zero_hit_objection_pointer_never_reports_presence(self):
        graph = self.build()
        objection = next(n for n in graph["nodes"]
                         if n["kind"] == "OBJECTION_RESEARCH_POINTER")
        self.assertFalse(objection["objection_presence_verified"])
        self.assertFalse(objection["rule_application_verified"])
        self.assertFalse(graph["objection_presence_attested"])

    def test_context_radius_restricted(self):
        with self.assertRaises(ContextGraphError):
            self.build(context_radius_lines=10)
        with self.assertRaises(ContextGraphError):
            self.build(context_radius_lines=-1)
        v = self.build(context_radius_lines=0)
        self.assertEqual(v["context_radius_lines"], 0)
        for c in (n for n in v["nodes"] if n["kind"] == "HASHED_CONTEXT"):
            self.assertEqual(c["section_line_start"], c["section_line_end_inclusive"])


if __name__ == "__main__":
    unittest.main()
