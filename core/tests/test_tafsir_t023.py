"""T0.2.3 acceptance tests: identification, attribution, relationships."""
from __future__ import annotations
import json
import unittest

from engines.tafsir.t023 import (
    build_relationships, identify_candidates, summarize_analysis,
    ATTRIB_NAMED_REPORT, ATTRIB_AUTHOR_OWN, ATTRIB_UNKNOWN,
    IDENTITY_UNKNOWN, ENDORSE_EXPLICIT,
)

PASSAGE_REPORTED = ("وقال مجاهد: «أقيموا الصلاة أي أدها»، "
                    "وقيل: المراد أداء الصلاة في وقتها، "
                    "والصواب عندنا أنها واجبة في وقتها بلا خلاف فيه هنا.")
PASSAGE_PLAIN = ("دلت الآية على وجوب أداء الصلاة، ومعنى القول في تفسير "
                 "اللفظ ظاهر في سياق الكلام.")

def passage(text: str, pid_suffix: str = "a" * 40) -> dict:
    return {
        "interpretation_id": "interp:" + pid_suffix,
        "quran_reference": "2:43",
        "work_id": "tafsir_tabari",
        "source_record_id": "tafsir:tafsir_tabari:2:43:" + "a" * 64,
        "source_sha256": "a" * 64,
        "evidence_span": [0, len(text)],
        "interpretation_statement": text,
    }


class T023Tests(unittest.TestCase):
    def test_1_explicit_statement_identified(self):
        cands = identify_candidates(passage(PASSAGE_PLAIN))
        self.assertTrue(len(cands) >= 1)
        for c in cands:
            self.assertIn(c["interpretation_type"], (
                "VERSE_MEANING", "LEXICAL_EXPLANATION", "LEGAL_INTERPRETATION",
                "UNCLASSIFIED"))

    def test_2_multiple_candidates_from_one_passage(self):
        cands = identify_candidates(passage(PASSAGE_REPORTED))
        self.assertTrue(len(cands) >= 3)
        ids = {c["candidate_id"] for c in cands}
        self.assertEqual(len(ids), len(cands))

    def test_3_named_speaker_identified(self):
        cands = identify_candidates(passage(PASSAGE_REPORTED))
        named = [c for c in cands if c["speaker_name"] == "مجاهد"]
        self.assertTrue(named)
        self.assertEqual(named[0]["attribution_type"], ATTRIB_NAMED_REPORT)

    def test_4_reported_view_not_attributed_to_author(self):
        cands = identify_candidates(passage(PASSAGE_REPORTED))
        mujahid = [c for c in cands if c["speaker_name"] == "مجاهد"][0]
        self.assertNotEqual(mujahid["author_endorsement"], ENDORSE_EXPLICIT)
        self.assertFalse(mujahid["scholarly_verified"])

    def test_5_author_choice_extracted_with_witness(self):
        cands = identify_candidates(passage(PASSAGE_REPORTED))
        own = [c for c in cands if c["attribution_type"] == ATTRIB_AUTHOR_OWN]
        self.assertTrue(own)
        self.assertEqual(own[0]["author_endorsement"], ENDORSE_EXPLICIT)
        # the supporting phrase (والصواب) is inside the candidate text
        self.assertIn("الصواب", own[0]["interpretation_statement"])

    def test_6_no_agreement_from_word_similarity(self):
        cands_a = identify_candidates(passage(PASSAGE_REPORTED))
        cands_b = identify_candidates(passage(
            "وقال قتادة: «أقيموا الصلاة أي أدها».", pid_suffix="b" * 40))
        rels = build_relationships(cands_a + cands_b)
        # candidates from different passages never yield AGREEMENT
        cross = [r for r in rels if r["from_candidate_id"] in
                 {c["candidate_id"] for c in cands_b}]
        for r in cross:
            self.assertNotEqual(r["relation_type"], "AGREEMENT_CANDIDATE")

    def test_7_no_disagreement_from_different_wording(self):
        cands = identify_candidates(passage(PASSAGE_REPORTED))
        rels = build_relationships(cands)
        named = [c for c in cands if c["attribution_type"] == ATTRIB_NAMED_REPORT]
        if len(named) >= 2:
            for r in rels:
                self.assertNotEqual(r["relation_type"], "DISAGREEMENT_CANDIDATE")

    def test_8_relation_to_missing_record_refused(self):
        cands = identify_candidates(passage(PASSAGE_REPORTED))
        with self.assertRaises(Exception):
            build_relationships([cands[0], {"candidate_id": "ghost",
                "passage_id": "interp:" + "f" * 40}])

    def test_9_unsupported_relation_is_undetermined(self):
        cands = identify_candidates(passage(PASSAGE_REPORTED))
        rels = build_relationships(cands)
        supported = {"PREFERENCE", "OBJECTION", "ALTERNATIVE_INTERPRETATION"}
        for r in rels:
            if r["relation_type"] not in supported:
                self.assertEqual(r["relation_type"], "UNDETERMINED")

    def test_10_source_sha_and_spans_preserved(self):
        cands = identify_candidates(passage(PASSAGE_REPORTED))
        for c in cands:
            self.assertEqual(c["source_sha256"], "a" * 64)
            self.assertEqual(
                PASSAGE_REPORTED[c["statement_start"]:c["statement_end"]],
                c["interpretation_statement"])

    def test_11_undetermined_preserved(self):
        cands = identify_candidates(passage(PASSAGE_REPORTED))
        rels = build_relationships(cands)
        has_und = any(r["relation_type"] == "UNDETERMINED" for r in rels)
        self.assertTrue(has_und or len(rels) == 0)

    def test_12_summary_never_leaks_text(self):
        cands = identify_candidates(passage(PASSAGE_REPORTED))
        rels = build_relationships(cands)
        raw = json.dumps(summarize_analysis([1], cands, rels), ensure_ascii=False)
        self.assertNotIn("مجاهد", raw)
        self.assertNotIn("الصلاة", raw)

    def test_13_authority_flags_stay_false(self):
        cands = identify_candidates(passage(PASSAGE_REPORTED))
        rels = build_relationships(cands)
        for c in cands:
            for flag in ("scholarly_verified", "text_included",
                         "publication_allowed", "juristic_inference_allowed",
                         "public_fatwa_authorized", "p1_admitted"):
                self.assertFalse(c[flag], flag)
        for r in rels:
            self.assertFalse(r["scholarly_verified"])
            self.assertFalse(r["consensus_claimed"])
            self.assertFalse(r["preference_by_system"])

    def test_14_confidence_never_upgrades_verification(self):
        cands = identify_candidates(passage(PASSAGE_REPORTED))
        for c in cands:
            self.assertEqual(c["verification_status"], "UNVERIFIED")
            self.assertIn(c["attribution_confidence"], ("LOW", "MEDIUM"))


if __name__ == "__main__":
    unittest.main()
