"""E2E-01.2: synthetic semantic observation, scope and actual E2E integration."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from engines.e2e.semantic_linkage import (
    CONTRACT, LinkageError, assess_indicator_scope, build_linkage,
)
from engines.e2e.research_slice import research_slice, ResearchSliceError, QUESTION
from engines.usul.pilots.amr_default import example_bundle
from core.tests import test_e2e_research_slice as e2e_fixtures


def example(**kwargs):
    canonical = example_bundle()["rules"][0]
    data = dict(
        verse_ref="2:43", verse_text_source="operator-reported-pinned-witness",
        verse_text_sha256="a" * 64, imperative_word="أَقِيمُوا",
        imperative_position="operator-report: word token",
        rule_id=canonical["id"], rule_expression=canonical["expression"],
        rule_source="الورقات", evidence_head_sha256="b" * 64,
        indicator_case="NOT_OBSERVED_IN_SCOPE",
        indicator_scope={
            "sources_examined": ["quran-witness", "tafsir-a"],
            "indicators_found": [],
            "sources_not_examined": ["hadith", "tafsir-b"],
        },
        supporting_notes="operator submitted candidate imperative",
        opposing_notes="",
    )
    data.update(kwargs)
    return data


class TestSemanticLinkage(unittest.TestCase):
    def test_metadata_only_all_flags_false(self):
        out = build_linkage(**example())
        for k in ("source_authenticated", "scholarly_verified",
                  "rights_verified", "edition_verified", "publication_allowed",
                  "redistribution_approved", "juristic_inference_allowed",
                  "public_fatwa_authorized", "p1_admitted", "text_included"):
            self.assertIs(out[k], False)
        self.assertEqual(out["rights_status"], "legal_review_pending")
        self.assertIs(out["verse"]["text_sha256_verified_against_verse"], False)

    def test_proposed_not_certified_even_with_sha_labels(self):
        out = build_linkage(**example())
        self.assertEqual(out["contract"], CONTRACT)
        self.assertEqual(out["semantic_relationship"], "PROPOSED_NOT_CERTIFIED")
        self.assertIs(out["semantic_equivalence_verified"], False)
        self.assertIs(out["evidence_head_independently_verified_here"], False)

    def test_not_observed_does_not_mean_absent(self):
        out = build_linkage(**example())
        self.assertEqual(out["linkage_state"],
                         "INDICATOR_NOT_OBSERVED_IN_CHECKED_SCOPE")
        self.assertTrue(
            out["diverting_indicator"]["not_observed_does_not_mean_absent"])
        self.assertEqual(
            out["diverting_indicator"]["scope"]["sources_examined_count"], 2)

    def test_present_requires_checked_scope_and_is_not_absolute(self):
        scope = dict(sources_examined=["tafsir-a"],
                     indicators_found=["potential-qarinah"],
                     sources_not_examined=["hadith"])
        out = build_linkage(**example(
            indicator_case="PRESENT", indicator_scope=scope))
        self.assertEqual(out["linkage_state"],
                         "INDICATOR_PRESENT_REQUIRES_ASSESSMENT")
        self.assertTrue(out["diverting_indicator"]["scope"]["absence_not_confirmed"])
        self.assertIs(out["diverting_indicator"]["automatic_detection_performed"], False)

    def test_invalid_case(self):
        with self.assertRaisesRegex(LinkageError, "INDICATOR_CASE_INVALID"):
            build_linkage(**example(indicator_case="CONFIRMED_ABSENT"))

    def test_scope_present(self):
        out = assess_indicator_scope(
            sources_examined=["quran"], indicators_found=["conditional"],
            sources_not_examined=["hadith"])
        self.assertEqual(out["case"], "PRESENT")

    def test_scope_not_observed(self):
        out = assess_indicator_scope(
            sources_examined=["quran", "tafsir"], indicators_found=[],
            sources_not_examined=["hadith"])
        self.assertEqual(out["case"], "NOT_OBSERVED_IN_SCOPE")
        self.assertTrue(out["scope"]["absence_not_confirmed"])

    def test_scope_not_examined(self):
        out = assess_indicator_scope(
            sources_examined=[], indicators_found=[],
            sources_not_examined=["quran", "hadith"])
        self.assertEqual(out["case"], "NOT_EXAMINED")

    def test_fake_positive_without_examined_source_rejected(self):
        with self.assertRaisesRegex(
                LinkageError, "INDICATOR_WITHOUT_EXAMINATION"):
            assess_indicator_scope(
                sources_examined=[], indicators_found=["found"],
                sources_not_examined=["quran"])

    def test_contradictory_source_scope_rejected(self):
        with self.assertRaisesRegex(LinkageError, "SCOPE_OVERLAP_INVALID"):
            assess_indicator_scope(
                sources_examined=["quran"], indicators_found=[],
                sources_not_examined=["quran"])

    def test_case_cannot_conflict_with_declared_observations(self):
        with self.assertRaisesRegex(
                LinkageError, "INDICATOR_SCOPE_CASE_MISMATCH"):
            build_linkage(**example(indicator_case="PRESENT"))

    def test_malformed_digest_or_verse_coordinate_rejected(self):
        for changed in (dict(verse_text_sha256="z" * 64),
                        dict(evidence_head_sha256="B" * 64),
                        dict(verse_ref="2:999"), dict(verse_ref="2:043")):
            with self.subTest(changed=changed):
                with self.assertRaises(LinkageError):
                    build_linkage(**example(**changed))

    def test_cannot_impersonate_another_usul_rule(self):
        with self.assertRaisesRegex(LinkageError, "USUL_RULE_OUT_OF_SCOPE"):
            build_linkage(**example(rule_id="some-other-rule"))
        with self.assertRaisesRegex(LinkageError, "USUL_RULE_OUT_OF_SCOPE"):
            build_linkage(**example(rule_expression="invented new ruling"))

    def test_non_arabic_word_or_unbounded_notes_refused(self):
        with self.assertRaisesRegex(LinkageError, "IMPERATIVE_WORD_INVALID"):
            build_linkage(**example(imperative_word="command"))
        with self.assertRaisesRegex(LinkageError, "SUPPORTING_NOTES_INVALID"):
            build_linkage(**example(supporting_notes="x" * 241))


class TestResearchSliceIntegration(unittest.TestCase):
    def setUp(self):
        # Reuse real synthetic corpus+sidecar SQLite and qualified operator
        # fixture without rediscovering its eight unrelated tests.
        e2e_fixtures.E2EResearchSliceTests.setUp(self)

    def _run(self, *, props=None, reference="2:43"):
        proposal = example(
            verse_ref=reference, evidence_head_sha256=self.adapters.evidence_head())
        if props:
            proposal.update(props)
        return research_slice(
            self.adapters, reference, QUESTION,
            ledger=self.qual_ledger,
            qualification_anchor_dir=self.qual_anchor,
            qualification_key=self.qual_key, vault=self.vault,
            linkage_observation=proposal)

    def test_proposal_bound_to_authenticated_head_but_word_not_verified(self):
        out = self._run()
        link = out["research_linkage"]
        self.assertEqual(link["status"], "PROPOSED_NOT_CERTIFIED")
        self.assertTrue(link["evidence_head_bound_to_qualified_retrieval"])
        self.assertFalse(link["verse_text_byte_match_independently_verified"])
        self.assertFalse(link["verse_is_evidence_for_usul_rule"])
        self.assertEqual(link["proposal"]["verse"]["reference"], "2:43")
        self.assertFalse(out["limits"]["juristic_inference_allowed"])

    def test_evidence_head_mismatch_refused(self):
        with self.assertRaisesRegex(
                ResearchSliceError, "E2E_LINKAGE_EVIDENCE_HEAD_MISMATCH"):
            self._run(props={"evidence_head_sha256": "a" * 64})

    def test_wrong_reference_refused(self):
        with self.assertRaisesRegex(
                ResearchSliceError, "E2E_LINKAGE_REFERENCE_MISMATCH"):
            self._run(props={"verse_ref": "2:44"})


if __name__ == "__main__":
    unittest.main()
