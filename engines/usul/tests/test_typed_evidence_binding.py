"""Stage09 non-promoting P0 citation proposals: synthetic graph/P0 contracts only."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from engines.usul.arabic_evidence_retrieval import FOLD_MARKS, retrieve
from engines.usul.evidence_context_graph import build_context_graph
from engines.usul.typed_evidence_binding import (
    BindingProposalError, bind_exact_observations,
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


MISSING = object()


class TypedBindingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        p = Path(temp.name) / "section.txt"
        p.write_bytes("الأمر فقط\n".encode("utf-8"))
        self.witness = {
            "source_id": "pilot:w1", "section_path": p,
            "section_sha256": sha(p.read_bytes()),
            "source_url": "https://example.invalid/synthetic",
            "section_locator": "synthetic location",
            "offset_basis": "extracted_section",
            "source_byte_base": 0,
            "source_line_base": 1,
        }
        self.queries = [{
            "id": "pilot:amr", "literal": "الأمر",
            "candidate_profiles": [FOLD_MARKS],
        }]
        self.graph = build_context_graph(
            retrieve([self.witness], self.queries),
            [self.witness], self.queries, [],
            work_title="synthetic usul workbook", author="synthetic author",
        )
        self.occ = next(n for n in self.graph["nodes"]
                        if n["kind"] == "TEXT_OCCURRENCE")
        root = Path(__file__).resolve().parents[3]
        self.bundle = json.loads((root/"engines/usul/examples/p0-bridge-demo-bundle.json")
                                 .read_text(encoding="utf-8"))
        self.bundle["sources"][0]["content_sha256"] = self.witness["section_sha256"]
        self.bundle["evidence"][0]["excerpt"] = "الأمر"
        self.bundle["evidence"][0]["excerpt_sha256"] = sha("الأمر".encode("utf-8"))
        self.proposals = [{
            "id": "pilot:proposed-citation",
            "occurrence_id": self.occ["id"],
            "p0_source_id": "demo:src",
            "p0_evidence_id": "demo:ev-premise-source",
            "relationship": "EXACT_BYTE_CITATION_PROPOSAL",
            "review_status": "UNASSESSED",
        }]

    def bind(self, graph=None, bundle=None, proposals=MISSING, pin=None):
        return bind_exact_observations(
            self.graph if graph is None else graph,
            self.graph["graph_sha256"] if pin is None else pin,
            self.bundle if bundle is None else bundle,
            self.proposals if proposals is MISSING else proposals,
        )

    def test_positive_exact_byte_binding_has_zero_promotion(self):
        p0_original = copy.deepcopy(self.bundle)
        a = self.bind()
        self.assertEqual(a, self.bind())
        self.assertEqual(a["status"], "STAGE09_TYPED_REFERENCE_PROPOSALS_PASS")
        self.assertEqual(a["proposal_count"], 1)
        self.assertEqual(len(a["proposal_report_sha256"]), 64)
        self.assertTrue(a["proposals"][0]["byte_correspondence_verified"])
        for name in ("scholarly_verified", "juristic_inference_allowed",
                     "public_fatwa_authorized", "source_text_included",
                     "p0_bundle_mutated", "p0_rule_execution_performed"):
            self.assertIs(a[name], False)
        self.assertFalse(a["proposals"][0]["p0_verification_status_upgraded"])
        self.assertFalse(a["proposals"][0]["rule_support_attested"])
        self.assertEqual(self.bundle, p0_original)
        self.assertNotIn("synthetic excerpt", json.dumps(a))

    def test_p0_excerpt_digest_does_not_match_source_occurrence(self):
        bad = copy.deepcopy(self.bundle)
        bad["evidence"][0]["excerpt"] = "الندب"
        bad["evidence"][0]["excerpt_sha256"] = sha("الندب".encode())
        with self.assertRaisesRegex(BindingProposalError, "byte-identical"):
            self.bind(bundle=bad)

    def test_p0_pretends_different_work_or_source_section(self):
        for field, value in (
            ("content_sha256", "0"*64), ("work_title", "unrelated work")
        ):
            bad = copy.deepcopy(self.bundle)
            bad["sources"][0][field] = value
            with self.subTest(field=field), self.assertRaises(BindingProposalError):
                self.bind(bundle=bad)

    def test_existing_P0_verified_label_is_not_elevated(self):
        self.assertEqual(self.bundle["evidence"][0]["verification_status"], "verified")
        result = self.bind()
        self.assertIs(result["proposals"][0]["semantic_equivalence_verified"], False)
        self.assertFalse(result["scholarly_verified"])

    def test_modified_graph_and_stale_pins_fail(self):
        with self.assertRaisesRegex(BindingProposalError, "pin"):
            self.bind(pin="0"*64)
        bad = copy.deepcopy(self.graph)
        bad["nodes"][0]["id"] = "tampered:id"
        with self.assertRaisesRegex(BindingProposalError, "canonical"):
            self.bind(graph=bad)

    def test_target_must_be_exact_not_orthographic_candidate(self):
        candidate = copy.deepcopy(self.proposals)
        candidate[0]["occurrence_id"] = "occurrence:" + "0"*32
        with self.assertRaisesRegex(BindingProposalError, "candidate-only"):
            self.bind(proposals=candidate)

    def test_invalid_proposal_or_duplicate_fails_closed(self):
        changes = [
            {"relationship": "SUPPORTS_RULE"},
            {"review_status": "VERIFIED"},
            {"p0_source_id": "demo:unknown"},
            {"p0_evidence_id": "demo:unknown"},
            {"id": "bad\nid"},
            {"extra": "undocumented"},
        ]
        for edit in changes:
            proposal = copy.deepcopy(self.proposals)
            proposal[0].update(edit)
            with self.subTest(edit=edit), self.assertRaises(BindingProposalError):
                self.bind(proposals=proposal)
        with self.assertRaises(BindingProposalError):
            self.bind(proposals=self.proposals * 2)

    def test_structurally_invalid_p0_bundle_rejected(self):
        bad = copy.deepcopy(self.bundle)
        bad["evidence"][0]["verification_method"] = "unverified"
        with self.assertRaisesRegex(BindingProposalError, "P0 bundle"):
            self.bind(bundle=bad)

    def test_none_or_unbounded_proposals_rejected(self):
        for value in (None, [], self.proposals * 17):
            with self.assertRaises(BindingProposalError):
                self.bind(proposals=value)

    def test_no_graph_links_to_fiqh_conclusion_are_created(self):
        result = self.bind()
        self.assertEqual(result["proposals"][0]["binding_status"],
                         "PROPOSED_EXACT_BYTE_LINK_UNASSESSED")
        self.assertNotIn("P0_EVIDENCE_VERIFIED", json.dumps(result))
        self.assertNotIn("DERIVES_RULING", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
