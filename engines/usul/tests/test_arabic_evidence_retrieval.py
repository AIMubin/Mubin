"""Stage07 Arabic evidence retrieval: byte fidelity and conservative candidates."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from engines.usul.arabic_evidence_retrieval import (
    ArabicRetrievalError, retrieve, FOLD_MARKS, FOLD_BRACKETS, FOLD_SPACES,
)

W1 = "الأمر\nو أما الوجوب فليس فرضًا\nهو الوجوب وليس الندب\n"
W2 = "الْأَمْر\nوأما الْوُجُوب فليس فرضًا\nهو [الوجوب] وليس الندب\n"
Q = [
    {"id": "pilot:amr", "literal": "الأمر",
     "candidate_profiles": [FOLD_MARKS, FOLD_BRACKETS, FOLD_SPACES]},
    {"id": "pilot:split", "literal": "و أما",
     "candidate_profiles": [FOLD_MARKS, FOLD_BRACKETS, FOLD_SPACES]},
    {"id": "pilot:editorial", "literal": "هو الوجوب",
     "candidate_profiles": [FOLD_MARKS, FOLD_BRACKETS]},
    {"id": "pilot:negation", "literal": "ليس",
     "candidate_profiles": [FOLD_MARKS]},
    {"id": "pilot:ghost", "literal": "غير_موجود",
     "candidate_profiles": [FOLD_MARKS, FOLD_BRACKETS, FOLD_SPACES]},
]


class ArabicRetrievalTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name)
        self.witnesses = []
        for i, (value, label, base, line_base) in enumerate([
            (W1, "pilot:primary", 3735, 86),
            (W2, "pilot:second", 0, 1),
        ]):
            p = self.path / f"witness{i}.txt"
            p.write_bytes(value.encode("utf-8"))
            self.witnesses.append({
                "source_id": label, "section_path": p,
                "section_sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                "source_url": f"https://example.invalid/witness{i}",
                "section_locator": f"synthetic section {i}",
                "offset_basis": "utf8_export" if i == 0 else "extracted_section",
                "source_byte_base": base, "source_line_base": line_base,
            })

    def search(self, queries=None, witnesses=None):
        return retrieve(self.witnesses if witnesses is None else witnesses,
                        Q if queries is None else queries)

    def test_two_source_proof_is_deterministic_and_metadata_only(self):
        out = self.search()
        self.assertEqual(out, self.search())
        self.assertEqual(out["status"], "ARABIC_SOURCE_RETRIEVAL_PASS")
        self.assertEqual(out["source_count"], 2)
        self.assertTrue(out["all_offsets_reference_original_section_bytes"])
        self.assertTrue(out["normalized_match_is_only_candidate"])
        self.assertFalse(out["scholarly_verified"])
        self.assertFalse(out["semantic_qarinah_verified"])
        self.assertFalse(out["redistribution_approved"])
        self.assertFalse(out["source_text_included"])
        plain = json.dumps(out, ensure_ascii=False)
        self.assertNotIn("هو [الوجوب]", plain)
        self.assertNotIn("فرضًا", plain)
        self.assertNotIn("غير_موجود", plain)
        self.assertEqual(out["witnesses"][0]["source_byte_base"], 3735)
        self.assertEqual(out["witnesses"][1]["source_byte_base"], 0)

    def test_all_original_byte_offsets_match_excerpts_without_copying_excerpts(self):
        out = self.search()
        for w, ref in zip(out["witnesses"], self.witnesses):
            raw = Path(ref["section_path"]).read_bytes()
            for report in w["queries"]:
                hits = list(report["strict_matches"])
                for profile in report["candidate_profiles"]:
                    hits.extend(profile["matches"])
                for hit in hits:
                    a, b = hit["section_byte_start"], hit["section_byte_end_exclusive"]
                    piece = raw[a:b]
                    self.assertTrue(piece)
                    self.assertEqual(hashlib.sha256(piece).hexdigest(),
                                     hit["original_bytes_sha256"])
                    self.assertEqual(hit["source_byte_start"],
                                     ref["source_byte_base"] + a)
                    self.assertEqual(hit["source_byte_end_exclusive"],
                                     ref["source_byte_base"] + b)
                    self.assertGreaterEqual(hit["section_line_number"], 1)
                    self.assertEqual(hit["source_line_number"],
                                     ref["source_line_base"] + hit["section_line_number"]-1)
                    self.assertTrue(hit["source_text_included"] is False)

    def test_diacritic_candidate_not_false_exact(self):
        data = self.search()
        primary = data["witnesses"][0]["queries"][0]
        second = data["witnesses"][1]["queries"][0]
        self.assertEqual(primary["strict_match_count"], 1)
        self.assertEqual(second["strict_match_count"], 0)
        folded = second["candidate_profiles"][0]
        self.assertEqual(folded["profile"], FOLD_MARKS)
        self.assertEqual(folded["match_count"], 1)
        self.assertEqual(folded["classification"], "ORTHOGRAPHIC_CANDIDATE_ONLY")
        self.assertFalse(second["semantic_equivalence_verified"])
        # W1 already exact: do not mislabel identical raw span as a candidate.
        self.assertEqual(primary["candidate_profiles"][0]["match_count"], 0)

    def test_joined_whitespace_is_candidate_only(self):
        result = self.search()
        w1, w2 = result["witnesses"]
        exact = w1["queries"][1]
        joined = w2["queries"][1]
        self.assertEqual(exact["strict_match_count"], 1)
        self.assertEqual(joined["strict_match_count"], 0)
        self.assertEqual(joined["candidate_profiles"][0]["match_count"], 0)
        self.assertEqual(joined["candidate_profiles"][2]["match_count"], 1)

    def test_bracket_contents_preserved_not_overwritten(self):
        result = self.search()
        w2 = result["witnesses"][1]
        row = w2["queries"][2]
        self.assertEqual(row["strict_match_count"], 0)
        self.assertEqual(row["candidate_profiles"][0]["match_count"], 0)
        self.assertEqual(row["candidate_profiles"][1]["match_count"], 1)
        original = self.witnesses[1]["section_path"].read_bytes()
        match = row["candidate_profiles"][1]["matches"][0]
        piece = original[match["section_byte_start"]:match["section_byte_end_exclusive"]]
        self.assertEqual(piece.decode("utf-8"), "هو [الوجوب")

    def test_negation_retained_and_miss_not_inferred(self):
        data = self.search()
        for w in data["witnesses"]:
            negation = w["queries"][3]
            self.assertEqual(negation["strict_match_count"], 2)
            miss = w["queries"][4]
            self.assertEqual(miss["strict_match_count"], 0)
            self.assertEqual(sum(p["match_count"] for p in miss["candidate_profiles"]), 0)
            self.assertTrue(miss["zero_exact_hits_does_not_prove_absence"])
            self.assertTrue(miss["zero_candidate_hits_does_not_prove_absence"])

    def test_no_hamza_fold_even_if_unicode_decomposed(self):
        self.witnesses[0]["section_path"].write_bytes(
            "ا\u0654مر ولا يجوز".encode("utf-8"))
        self.witnesses[0]["section_sha256"] = hashlib.sha256(
            self.witnesses[0]["section_path"].read_bytes()).hexdigest()
        variants = [{"id": "pilot:alef", "literal": "امر",
                     "candidate_profiles": [FOLD_MARKS, FOLD_BRACKETS, FOLD_SPACES]}]
        a = self.search(variants)["witnesses"][0]["queries"][0]
        self.assertEqual(a["strict_match_count"], 0)
        self.assertEqual(sum(p["match_count"] for p in a["candidate_profiles"]), 0)
        # No normalization ever deletes the lexical negation.
        b = self.search([{"id": "pilot:allowed", "literal": "يجوز",
                          "candidate_profiles": [FOLD_MARKS]}])
        self.assertEqual(b["witnesses"][0]["queries"][0]["strict_match_count"], 1)

    def test_edited_witness_rejected_even_if_two_files_would_normalize_equal(self):
        self.witnesses[0]["section_path"].write_bytes(
            self.witnesses[0]["section_path"].read_bytes().replace(
                "ليس".encode(), "ليـس".encode()))
        with self.assertRaisesRegex(ArabicRetrievalError, "digest"):
            self.search()

    def test_adversarial_schema_and_candidate_empty_fold(self):
        invalid = [
            [], [{"id": "pilot:a", "literal": "", "candidate_profiles": []}],
            [{"id": "pilot:a", "literal": "\n", "candidate_profiles": []}],
            [{"id": "pilot:a", "literal": "س\u2028ر", "candidate_profiles": []}],
            [{"id": "pilot:a", "literal": "س\u0085ر", "candidate_profiles": []}],
            [{"id": "pilot:a", "literal": "س"*130, "candidate_profiles": []}],
            [{"id": "pilot:a", "literal": "x", "candidate_profiles": ["aggressive"]}],
            [{"id": "pilot:a", "literal": "x", "candidate_profiles": [FOLD_MARKS,FOLD_MARKS]}],
            [{"id": "pilot:a", "literal": "x", "candidate_profiles": [FOLD_SPACES,FOLD_MARKS]}],
            [{"id": "pilot:a", "literal": "x", "candidate_profiles": [], "unknown": 1}],
            [Q[0],Q[0]],
        ]
        for queries in invalid:
            with self.subTest(queries=str(queries)[:80]), self.assertRaises(ArabicRetrievalError):
                self.search(queries)
        only_marks=[{"id": "pilot:marks", "literal": "\u064e",
                     "candidate_profiles": [FOLD_MARKS]}]
        with self.assertRaisesRegex(ArabicRetrievalError, "empty"):
            self.search(only_marks)

    def test_bad_witness_metadata_is_refused(self):
        for change in (
            {"section_sha256": "0"*64},
            {"offset_basis": "original_html"},
            {"source_id": "INVALID"},
            {"source_line_base": 0},
            {"source_byte_base": -1},
            {"another": "field"},
        ):
            witnesses = copy.deepcopy(self.witnesses)
            witnesses[1].update(change)
            with self.subTest(change=change), self.assertRaises(ArabicRetrievalError):
                self.search(witnesses=witnesses)

    def test_deletion_does_not_create_wrongly_certified_literal(self):
        w2_path=self.witnesses[1]["section_path"]
        w2_path.write_bytes("يجوز\n".encode("utf-8"))
        self.witnesses[1]["section_sha256"]=hashlib.sha256(w2_path.read_bytes()).hexdigest()
        out=self.search([{"id":"pilot:negated", "literal":"لا يجوز",
                          "candidate_profiles":[FOLD_MARKS,FOLD_BRACKETS,FOLD_SPACES]}])
        self.assertEqual(out["witnesses"][1]["queries"][0]["strict_match_count"],0)
        self.assertTrue(all(p["match_count"]==0 for p in
                            out["witnesses"][1]["queries"][0]["candidate_profiles"]))


if __name__ == "__main__":
    unittest.main()
