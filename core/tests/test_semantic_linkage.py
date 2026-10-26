"""E2E-01.2 semantic linkage tests. Synthetic only, ASCII only."""
from __future__ import annotations
import unittest
from engines.e2e.semantic_linkage import build_linkage, assess_indicator_scope, LinkageError

def link(**kw):
    base = dict(verse_ref="2:43", verse_text_source="pinned_tanzil",
        verse_text_sha256="a"*64, imperative_word="aqimuu",
        imperative_position="word 2", rule_id="amr-default",
        rule_expression="imperative without diverting indicator => obligation candidate",
        rule_source="al-Waraqat", evidence_head_sha256="b"*64,
        indicator_case="NOT_OBSERVED_IN_SCOPE", indicator_detail="3 sources checked",
        indicator_scope={"sources": ["quran", "tafsir"]},
        supporting_notes="clear imperative form", opposing_notes="")
    base.update(kw)
    return build_linkage(**base)

class TestLinkage(unittest.TestCase):
    def test_metadata_only_all_flags_false(self):
        r = link()
        for k in ("scholarly_verified","edition_verified",
                  "publication_allowed","juristic_inference_allowed",
                  "public_fatwa_authorized","p1_admitted","text_included"):
            self.assertFalse(r[k], f"{k} must be False")
        self.assertEqual(r["rights_status"], "legal_review_pending")

    def test_proposed_not_certified(self):
        self.assertEqual(link()["semantic_relationship"], "PROPOSED_NOT_CERTIFIED")

    def test_not_observed_does_not_mean_absent(self):
        self.assertTrue(link()["diverting_indicator"]["not_observed_does_not_mean_absent"])

    def test_present_changes_state(self):
        r = link(indicator_case="PRESENT")
        self.assertEqual(r["linkage_state"], "INDICATOR_PRESENT_REQUIRES_ASSESSMENT")

    def test_invalid_case(self):
        with self.assertRaises(LinkageError):
            link(indicator_case="CONFIRMED_ABSENT")

    def test_scope_present(self):
        r = assess_indicator_scope(sources_examined=["quran"],indicators_found=["conditional"],sources_not_examined=["hadith"])
        self.assertEqual(r["case"], "PRESENT")
        self.assertFalse(r["scope"]["absence_not_confirmed"])

    def test_scope_not_observed(self):
        r = assess_indicator_scope(sources_examined=["quran","tafsir"],indicators_found=[],sources_not_examined=["hadith"])
        self.assertEqual(r["case"], "NOT_OBSERVED_IN_SCOPE")
        self.assertTrue(r["scope"]["absence_not_confirmed"])

    def test_scope_not_examined(self):
        r = assess_indicator_scope(sources_examined=[],indicators_found=[],sources_not_examined=[])
        self.assertEqual(r["case"], "NOT_EXAMINED")

if __name__ == "__main__":
    unittest.main()
