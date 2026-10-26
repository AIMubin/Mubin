"""E2E-01.4b.1: audit the 24-case provenance and abstention-only baseline."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from engines.e2e.scientific_benchmark import (
    CASEBOOK_PATH, KINDS, CasebookError,
    evaluate_casebook, load_casebook, validate_casebook,
)


class AmrCasebookTests(unittest.TestCase):
    def setUp(self):
        self.book, self.sha = load_casebook()

    def test_exact_24_cases_8_each(self):
        self.assertEqual(len(self.book["cases"]), 24)
        self.assertEqual(self.book["categories"],
                         {k: 8 for k in KINDS})
        self.assertEqual(len({c["id"] for c in self.book["cases"]}), 24)

    def test_three_variants_do_not_leak_across_reference_splits(self):
        verses_by_split = {}
        for c in self.book["cases"]:
            verses_by_split.setdefault(c["split"], set()).add(c["reference"])
        self.assertEqual(len(verses_by_split["development"]), 4)
        self.assertEqual(len(verses_by_split["holdout"]), 4)
        self.assertFalse(verses_by_split["development"] &
                         verses_by_split["holdout"])
        self.assertFalse(self.book["split_plan"]["source_family_disjoint"])

    def test_dev_benchmark_abstains_on_semantics(self):
        report = evaluate_casebook()
        self.assertEqual(report["count"], 12)
        self.assertTrue(report["all_process_expectations_match"])
        self.assertFalse(report["scientific_accuracy_measured"])
        self.assertEqual(report["casebook_sha256"], self.sha)
        self.assertTrue(all(r["scientific_gold_label"] is None
                            and not r["usul_semantic_link_certified"]
                            for r in report["results"]))

    def test_frozen_holdout_is_separate_and_not_hidden_gold(self):
        report = evaluate_casebook(split="holdout")
        self.assertEqual(report["count"], 12)
        self.assertEqual(report["casebook_sha256"], self.sha)
        self.assertEqual(report["distribution"],
                         {k: 4 for k in sorted(KINDS)})
        self.assertFalse(report["scientific_accuracy_measured"])

    def test_wrong_source_attribution_is_refuted_not_relabelled(self):
        negative = [c for c in self.book["cases"]
                    if c["category"] == "CONSTRUCTED_NEGATIVE"]
        self.assertEqual(len(negative), 8)
        self.assertTrue(all(c["reference"] != c["asserted_word_reference"]
                            for c in negative))
        report = evaluate_casebook()
        self.assertTrue(all(r["process_outcome"]
                            == "REFUTED_REFERENCE_CONFLICT"
                            for r in report["results"]
                            if r["candidate_class"] == "CONSTRUCTED_NEGATIVE"))

    def test_positive_cases_never_auto_promote_to_supported(self):
        positives = [r for r in evaluate_casebook()["results"]
                     if r["candidate_class"] == "POSITIVE_CANDIDATE"]
        self.assertEqual(len(positives), 4)
        self.assertTrue(all(r["process_outcome"] == "CANDIDATE_UNVERIFIED"
                            and not r["source_witness_byte_verified"]
                            for r in positives))

    def test_split_leakage_is_refused(self):
        bad = copy.deepcopy(self.book)
        row = next(r for r in bad["cases"] if r["reference"] == "2:43")
        row["split"] = "holdout"
        with self.assertRaisesRegex(CasebookError, "CASEBOOK_SPLIT_INVALID"):
            validate_casebook(bad)

    def test_fabricated_rights_or_scholarly_promotion_refused(self):
        for name in ("scholarly_verified", "publication_allowed",
                     "juristic_inference_allowed", "source_authenticated"):
            bad = copy.deepcopy(self.book)
            bad["cases"][0][name] = True
            with self.subTest(name=name), self.assertRaisesRegex(
                    CasebookError, "CASEBOOK_AUTHORITY_INVALID"):
                validate_casebook(bad)

    def test_wrong_witness_or_rule_or_false_digest_refused(self):
        for change, reason in (
            ({"quran_witness_url": "https://example.com/verse"},
             "CASEBOOK_WITNESS_LOCATOR_INVALID"),
            ({"external_verse_digest": "f" * 64},
             "CASEBOOK_WITNESS_UNVERIFIED"),
            ({"scientific_gold_label": "SUPPORTED"},
             "CASEBOOK_AUTHORITY_INVALID"),
        ):
            bad = copy.deepcopy(self.book)
            bad["cases"][0].update(change)
            with self.subTest(change=change), self.assertRaisesRegex(
                    CasebookError, reason):
                validate_casebook(bad)

    def test_wrong_or_duplicate_claim_cannot_earn_a_green_case(self):
        for tweak in ("wrong_ref", "duplicate_id", "wrong_label", "wrong_word"):
            bad = copy.deepcopy(self.book)
            if tweak == "wrong_ref":
                bad["cases"][0]["asserted_word_reference"] = "2:110"
            if tweak == "duplicate_id":
                bad["cases"][0]["id"] = bad["cases"][1]["id"]
            if tweak == "wrong_label":
                bad["cases"][0]["expected_process_result"] = "SUPPORTED"
            if tweak == "wrong_word":
                bad["cases"][1]["observed_word"] = "وَاقْتُلُوا"
            with self.subTest(tweak=tweak), self.assertRaises(CasebookError):
                validate_casebook(bad)

    def test_codex_p2_malformed_alleged_reference_never_scores_conflict(self):
        # Prior P2: None / out-of-range refs / JSON objects used to pass
        # because "different from source ref" alone counted as a negative.
        for alleged in (None, "2:999", {"sura": 2, "aya": 44}, [], 0,
                        "random", "2:44"):
            bad = copy.deepcopy(self.book)
            target = next(row for row in bad["cases"]
                          if row["id"] == "AMR-01-N")
            target["asserted_word_reference"] = alleged
            with self.subTest(alleged=alleged), self.assertRaises(
                    CasebookError):
                validate_casebook(bad)

    def test_valid_but_swapped_negative_pair_is_not_frozen_baseline(self):
        bad = copy.deepcopy(self.book)
        target = next(row for row in bad["cases"]
                      if row["id"] == "AMR-05-N")
        self.assertEqual(target["asserted_word_reference"], "24:56")
        target["asserted_word_reference"] = "2:43"
        with self.assertRaisesRegex(
                CasebookError, "CASEBOOK_ASSERTED_REFERENCE_MISMATCH"):
            validate_casebook(bad)

    def test_missing_cases_fail_not_return_empty_scorecard(self):
        bad = copy.deepcopy(self.book)
        bad["cases"] = bad["cases"][:-1]
        with self.assertRaises(CasebookError):
            validate_casebook(bad)

    def test_json_digest_changes_after_tamper_and_invalid_case_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cases.json"
            path.write_text(json.dumps(self.book, ensure_ascii=False),
                            encoding="utf-8")
            loaded, digest = load_casebook(path)
            self.assertEqual(loaded["cases_total"], 24)
            self.assertNotEqual(digest, self.sha)
            bad = copy.deepcopy(self.book)
            bad["cases"][0]["reference"] = "2:999"
            path.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(CasebookError):
                load_casebook(path)


if __name__ == "__main__":
    unittest.main()
