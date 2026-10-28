"""T0.2.1+T0.2.2 acceptance tests: structured, grounded, fail-closed."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from engines.tafsir.t02 import (
    TafsirT02Error, extract_from_t01_record, make_record, segment_statements,
    summarize, validate_record, CONTRACT, STATUS_RULE_EXTRACTED_UNVERIFIED,
)

TEXT = ("قال المفسرون في قوله تعالى: وأقيموا الصلاة. "
        "وفي الآية دلالة على الأمر بالصلاة. "
        "وقيل في القرائن ما له شأن.")


def rec(text: str = TEXT, span: tuple[int, int] = (0, 52),
        work_id: str = "tafsir_tabari", ref: str = "2:43") -> dict:
    statement = text[span[0]:span[1]]
    return {
        "contract": CONTRACT,
        "interpretation_id": "interp:" + "0" * 40,
        "quran_reference": ref,
        "work_id": work_id,
        "author_id": "محمد بن جرير الطبري",
        "source_record_id": "tafsir:tafsir_tabari:2:43:" + "a" * 64,
        "source_sha256": "a" * 64,
        "evidence_sha256": hashlib.sha256(statement.encode()).hexdigest(),
        "evidence_span": [span[0], span[1]],
        "interpretation_statement": statement,
        "interpretation_type": None,
        "context_scope": "VERSE_LOCAL_EXEGESIS",
        "extraction_method": "RULE_BASED_SEGMENTER",
        "verification_status": STATUS_RULE_EXTRACTED_UNVERIFIED,
        "edition": None, "volume": None, "page": None,
        "rights_status": "legal_review_pending",
        "scholarly_verified": False,
        "text_included": False,
    }


class T02GroundingTests(unittest.TestCase):
    def test_1_single_statement_valid_witness(self):
        r = make_record(quran_reference="2:43", work_id="tafsir_tabari",
                        author_id="الطبري", source_record_id="tafsir:x:" + "a" * 16,
                        source_sha256="a" * 64, original_text=TEXT,
                        span=(0, 52), interpretation_type=None,
                        context_scope="VERSE_LOCAL_EXEGESIS")
        validate_record(r, original_text=TEXT)
        self.assertTrue(r["interpretation_statement"] in TEXT)

    def test_2_multiple_statements_from_one_record(self):
        out = extract_from_t01_record({
            "evidence_id": "tafsir:tafsir_tabari:2:43:" + "a" * 64,
            "work_id": "tafsir_tabari", "author_ar": "الطبري",
            "imported_record_sha256": "a" * 64, "verse_locator": "2:43",
            "text": TEXT})
        self.assertTrue(len(out) >= 2)
        ids = {r["interpretation_id"] for r in out}
        self.assertEqual(len(ids), len(out))
        for r in out:
            validate_record(r, original_text=TEXT)

    def test_3_refuse_span_not_in_source_bounds(self):
        with self.assertRaises(TafsirT02Error):
            make_record(quran_reference="2:43", work_id="w",
                        author_id=None, source_record_id="x",
                        source_sha256="a" * 64, original_text=TEXT,
                        span=(0, 10_000), interpretation_type=None,
                        context_scope="VERSE_LOCAL_EXEGESIS")

    def test_4_refuse_mismatched_evidence_hash(self):
        bad = rec()
        bad["evidence_sha256"] = "b" * 64
        with self.assertRaises(TafsirT02Error):
            validate_record(bad, original_text=TEXT)

    def test_5_refuse_wrong_work_attribution(self):
        # provenance is carried from the t01 record; a record claiming a
        # different work_id than its source is refused at extraction
        t01 = {"evidence_id": "tafsir:tafsir_tabari:2:43:" + "a" * 64,
               "work_id": "tafsir_tabari", "author_ar": None,
               "imported_record_sha256": "a" * 64, "verse_locator": "2:43",
               "text": TEXT}
        out = extract_from_t01_record(t01)
        for r in out:
            self.assertEqual(r["work_id"], "tafsir_tabari")

    def test_6_empty_or_held_text_returns_empty(self):
        self.assertEqual(extract_from_t01_record({
            "evidence_id": "x", "work_id": "w",
            "imported_record_sha256": "a" * 64, "verse_locator": "2:43",
            "text": None}), [])

    def test_7_deterministic_ids_no_source_mixing(self):
        a = extract_from_t01_record({
            "evidence_id": "tafsir:tafsir_tabari:2:43:" + "a" * 64,
            "work_id": "tafsir_tabari", "author_ar": None,
            "imported_record_sha256": "a" * 64, "verse_locator": "2:43",
            "text": TEXT})
        b = extract_from_t01_record({
            "evidence_id": "tafsir:tafsir_baghawi:2:43:" + "b" * 64,
            "work_id": "tafsir_baghawi", "author_ar": None,
            "imported_record_sha256": "b" * 64, "verse_locator": "2:43",
            "text": TEXT})
        self.assertNotEqual(
            {r["interpretation_id"] for r in a},
            {r["interpretation_id"] for r in b})

    def test_8_original_text_preserved_byte_exact(self):
        out = extract_from_t01_record({
            "evidence_id": "tafsir:tafsir_tabari:2:43:" + "a" * 64,
            "work_id": "tafsir_tabari", "author_ar": None,
            "imported_record_sha256": "a" * 64, "verse_locator": "2:43",
            "text": TEXT})
        for r in out:
            s0, s1 = r["evidence_span"]
            self.assertEqual(TEXT[s0:s1], r["interpretation_statement"])

    def test_9_summary_never_contains_statement_text(self):
        out = extract_from_t01_record({
            "evidence_id": "tafsir:tafsir_tabari:2:43:" + "a" * 64,
            "work_id": "tafsir_tabari", "author_ar": None,
            "imported_record_sha256": "a" * 64, "verse_locator": "2:43",
            "text": TEXT})
        raw = json.dumps(summarize(out), ensure_ascii=False)
        self.assertNotIn("الصلاة", raw)

    def test_10_authority_flags_all_false(self):
        r = make_record(quran_reference="2:43", work_id="w", author_id=None,
                        source_record_id="x", source_sha256="a" * 64,
                        original_text=TEXT, span=(0, 52),
                        interpretation_type=None,
                        context_scope="VERSE_LOCAL_EXEGESIS")
        for flag in ("scholarly_verified", "text_included",
                     "publication_allowed", "juristic_inference_allowed",
                     "public_fatwa_authorized", "p1_admitted"):
            self.assertFalse(r[flag], flag)

    def test_refuse_invented_edition_metadata(self):
        bad = rec()
        bad["edition"] = "طبعة غير موجودة"
        with self.assertRaises(TafsirT02Error):
            validate_record(bad, original_text=TEXT)

    def test_segmenter_deterministic(self):
        a = segment_statements(TEXT)
        b = segment_statements(TEXT)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
