"""E2E-01.4: source-family independent oracle + signed-qualification evaluation.

Reuses production-like SYNTHETIC Quran/tafsir SQLite and an actually signed
qualification ledger from the already passing E2E-01.1 fixture.
No Quran/Tafsir text, source secrets or actual vault in Git.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from core.tests import test_e2e_research_slice as e2e_fixture
from core.tests import test_quran_operator_workspace_i01b as workspace_fixture
from engines.e2e import evaluation as eva
from engines.e2e.research_slice import QUESTION
from engines.quran.research.private_adapters import ResearchAdapterError
from engines.quran.research import qualification as qual


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        e2e_fixture.E2EResearchSliceTests.setUp(self)

    def run_eval(self, refs=None):
        return eva.run_full_evaluation(
            self.adapters, self.corpus, self.vault,
            self.qual_ledger, self.qual_anchor, self.qual_key,
            ["2:1", "2:43"] if refs is None else refs, QUESTION)

    def test_eight_groups_pass_actual_synthetic_sqlite_and_signed_ledger(self):
        report = self.run_eval()
        self.assertEqual(report["contract"], eva.CONTRACT)
        self.assertEqual(len(report["groups"]), 8)
        self.assertEqual(
            {g["group"] for g in report["groups"]},
            {"coordinate_accuracy", "source_completeness",
             "qualification_consistency", "gap_completeness", "abstention",
             "authority_flags", "determinism", "source_provenance"})
        self.assertTrue(report["all_passed"], report)
        self.assertEqual(report["failed"], 0)
        self.assertEqual(report["critical_failures"], 0)
        self.assertGreaterEqual(report["total"], 65)
        self.assertEqual(report["passed"], report["total"])
        for k in ("source_authenticated", "scholarly_verified",
                  "rights_verified", "publication_allowed",
                  "juristic_inference_allowed", "public_fatwa_authorized",
                  "p1_admitted", "text_included"):
            self.assertIs(report[k], False)
        self.assertGreaterEqual(len(report["cannot_automate"]), 6)

    def test_sidecar_six_and_corpus_five_are_two_independent_families(self):
        report = self.run_eval(["2:1"])
        completeness = next(g for g in report["groups"]
                            if g["group"] == "source_completeness")
        self.assertTrue(completeness["passed"])
        checks = {c["check"]: c for c in completeness["checks"]}
        self.assertTrue(checks["corpus_sources_complete"]["passed"])
        self.assertTrue(checks["sidecar_sources_complete"]["passed"])
        self.assertTrue(checks["unified_sources_unique_and_complete"]["passed"])
        provenance = next(g for g in report["groups"]
                          if g["group"] == "source_provenance")
        self.assertTrue(provenance["passed"])
        self.assertTrue(any(c["check"] == "provenance_QuranTafseer"
                            for c in provenance["checks"]))

    def test_coordinate_absent_in_both_dbs_correctly_passes(self):
        report = self.run_eval(["2:43"])
        group = next(g for g in report["groups"]
                     if g["group"] == "coordinate_accuracy")
        self.assertEqual(len(group["checks"]), 11)
        self.assertTrue(group["passed"])
        self.assertTrue(all(c["passed"] and "expected=False" in c["detail"]
                            for c in group["checks"]))

    def test_false_negative_in_one_adapter_detected_as_critical(self):
        real_lookup = self.adapters.lookup
        def false_missing(reference, source_id, **kwargs):
            if reference == "2:1" and source_id == "tafsir_tabary":
                raise ResearchAdapterError("REFERENCE_NOT_PRESENT")
            return real_lookup(reference, source_id, **kwargs)
        with patch.object(self.adapters, "lookup", side_effect=false_missing):
            report = self.run_eval(["2:1"])
        self.assertFalse(report["all_passed"])
        self.assertGreaterEqual(report["critical_failures"], 1)
        coordinate = next(g for g in report["groups"]
                          if g["group"] == "coordinate_accuracy")
        failed = [x["check"] for x in coordinate["checks"] if not x["passed"]]
        self.assertEqual(failed, ["coordinate_2:1_tafsir_tabary"])

    def test_missing_reported_corpus_source_is_not_green(self):
        real_sources = self.adapters.corpus_sources
        with patch.object(self.adapters, "corpus_sources",
                          side_effect=lambda: real_sources()[:-1]):
            report = self.run_eval(["2:1"])
        source = next(g for g in report["groups"]
                      if g["group"] == "source_completeness")
        self.assertFalse(source["passed"])
        self.assertFalse(report["all_passed"])

    def test_signed_rejection_is_consistent_not_turned_unreviewed(self):
        workspace_fixture.WorkspaceTests._record(self, "SOURCE_REJECTED")
        report = self.run_eval(["2:1"])
        self.assertTrue(report["all_passed"], report)
        qualified = next(g for g in report["groups"]
                         if g["group"] == "qualification_consistency")
        self.assertTrue(qualified["passed"])

    def test_corrupt_signed_ledger_refuses_entire_evaluation(self):
        self.qual_ledger.write_bytes(b"tampered")
        with self.assertRaises(qual.QualificationError):
            self.run_eval(["2:1"])

    def test_authority_flag_promotion_never_counts_as_success(self):
        original = eva.research_slice
        def forbidden_promotion(*args, **kwargs):
            result = original(*args, **kwargs)
            result["limits"]["publication_allowed"] = True
            return result
        with patch.object(eva, "research_slice",
                          side_effect=forbidden_promotion):
            report = self.run_eval(["2:1"])
        self.assertFalse(report["all_passed"])
        self.assertGreaterEqual(report["critical_failures"], 1)
        group = next(g for g in report["groups"]
                     if g["group"] == "authority_flags")
        self.assertFalse(group["passed"])

    def test_valid_refs_are_required_and_no_vacuous_pass(self):
        for refs in ([], ["2:1", "2:1"], ["bad"], "2:1",
                     ["2:1"] * 33):
            with self.subTest(refs=refs), self.assertRaises(eva.EvaluationError):
                self.run_eval(refs)

    def test_corpus_db_must_match_adapter_anchor(self):
        with self.assertRaisesRegex(
                eva.EvaluationError, "EVALUATION_CORPUS_PATH_MISMATCH"):
            eva.run_full_evaluation(
                self.adapters, self.sidecar, self.vault,
                self.qual_ledger, self.qual_anchor, self.qual_key,
                ["2:1"], QUESTION)

    def test_no_source_text_or_private_key_paths_in_report(self):
        raw = json.dumps(self.run_eval(["2:1"]), ensure_ascii=False)
        self.assertNotIn(workspace_fixture.PLACEHOLDER, raw)
        self.assertNotIn("synthetic-footnote-only", raw)
        self.assertNotIn(str(self.vault), raw)
        self.assertNotIn(str(self.evidence_key), raw)

    def test_same_reference_set_yields_deterministic_result(self):
        a = json.dumps(self.run_eval(["2:1"]), ensure_ascii=False, sort_keys=True)
        b = json.dumps(self.run_eval(["2:1"]), ensure_ascii=False, sort_keys=True)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
