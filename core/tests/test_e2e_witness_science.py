"""E2E-01.4b.2: actual local bytes + two distinct AI report contracts.

No remote source access or model is mocked as an independently executed LLM.
All witness strings are synthetic, never Quran text, for CI.
"""
from __future__ import annotations

import copy
import hashlib
import json
import unittest

from engines.e2e.scientific_benchmark import load_casebook
from engines.e2e.witness_science import (
    TrialError, _witness_packet, run_trial, _canonical,
)


def witness(role, rid, url, family, text):
    return {
        "id": rid, "role": role, "url": url, "family": family,
        "text": text, "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


class LocalWitnessTrialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book, _ = load_casebook()
        cls.case = next(x for x in cls.book["cases"] if x["id"] == "AMR-01-P")

    def setUp(self):
        self.packet = {
            "case_id": "AMR-01-P", "reference": "2:43",
            "witnesses": [
                witness("verse", "verse1", self.case["quran_witness_url"],
                        "quran-site", "اختبار بيانات اصطناعية: أَقِيمُوا"),
                witness("tafsir", "tafsir1",
                        "https://example.org/tafsir/2/43",
                        "tafsir-library", "شرح اصطناعي لا يُنسب إلى تفسير"),
                witness("usul", "usul1", self.case["usul_rule"]["url"],
                        "usul-digital", "قاعدة اصطناعية لا تعكس متن الورقات"),
            ],
        }
        self.digest = hashlib.sha256(_canonical(self.packet)).hexdigest()
        self.a = dict(role="evaluator", model_id="model-A", provider="A",
                      run_id="e-123", packet_sha256=self.digest,
                      decision="SUPPORTED",
                      evidence_ids=["verse1", "tafsir1", "usul1"])
        self.b = dict(role="critic", model_id="model-B", provider="B",
                      run_id="c-456", packet_sha256=self.digest,
                      decision="REFUTED", evidence_ids=["verse1", "usul1"])

    def score(self, packet=None, a=None, b=None):
        return run_trial(self.book, "AMR-01-P", self.packet if packet is None else packet,
                         self.a if a is None else a, self.b if b is None else b)

    def test_conflicting_independent_ai_reports_do_not_certify(self):
        result = self.score()
        self.assertEqual(result["research_state"], "AI_DISAGREEMENT")
        self.assertTrue(result["evidence"]["three_witness_roles_present"])
        self.assertTrue(result["evidence"]["exact_candidate_substring_in_verse_bytes"])
        self.assertFalse(result["scholarly_verified"])
        self.assertFalse(result["independently_assessed_scientific_accuracy"])
        self.assertFalse(result["independent_external_source_custody_proven"])

    def test_agreement_is_uncertified_not_supported(self):
        same = dict(self.b, decision="SUPPORTED")
        out = self.score(b=same)
        self.assertEqual(out["research_state"], "AI_AGREEMENT_UNCERTIFIED")
        self.assertFalse(out["scholarly_verified"])
        self.assertFalse(out["juristic_inference_allowed"])

    def test_missing_tafsir_forces_abstention_even_when_ai_agrees(self):
        packet = copy.deepcopy(self.packet)
        packet["witnesses"] = [w for w in packet["witnesses"]
                               if w["role"] != "tafsir"]
        digest = hashlib.sha256(_canonical(packet)).hexdigest()
        a = dict(self.a, packet_sha256=digest, evidence_ids=["verse1", "usul1"])
        b = dict(self.b, packet_sha256=digest, decision="SUPPORTED")
        out = self.score(packet=packet, a=a, b=b)
        self.assertEqual(out["research_state"], "UNDETERMINED")
        self.assertFalse(out["evidence"]["three_witness_roles_present"])

    def test_no_exact_verse_candidate_forces_abstention(self):
        packet = copy.deepcopy(self.packet)
        packet["witnesses"][0]["text"] = "كلمات اصطناعية أخرى"
        packet["witnesses"][0]["sha256"] = hashlib.sha256(
            packet["witnesses"][0]["text"].encode()).hexdigest()
        digest = hashlib.sha256(_canonical(packet)).hexdigest()
        a = dict(self.a, packet_sha256=digest)
        b = dict(self.b, packet_sha256=digest, decision="SUPPORTED")
        out = self.score(packet=packet, a=a, b=b)
        self.assertFalse(out["evidence"]["exact_candidate_substring_in_verse_bytes"])
        self.assertEqual(out["research_state"], "UNDETERMINED")

    def test_wrong_sha_is_refused_before_ai_assessment(self):
        packet = copy.deepcopy(self.packet)
        packet["witnesses"][0]["sha256"] = "f" * 64
        with self.assertRaisesRegex(TrialError, "TRIAL_WITNESS_HASH_MISMATCH"):
            self.score(packet=packet)

    def test_packet_replay_rejected(self):
        altered = copy.deepcopy(self.a)
        altered["packet_sha256"] = "f" * 64
        with self.assertRaisesRegex(TrialError, "TRIAL_AGENT_CONTRACT_INVALID"):
            self.score(a=altered)

    def test_citation_hallucination_refused(self):
        altered = dict(self.a, evidence_ids=["not-a-witness"])
        with self.assertRaisesRegex(TrialError, "TRIAL_AGENT_CITATION_INVALID"):
            self.score(a=altered)

    def test_same_model_or_provider_or_run_not_independent(self):
        for key, value in (("model_id", "model-A"), ("provider", "A"),
                           ("run_id", "e-123")):
            with self.subTest(field=key):
                altered = dict(self.b, **{key: value})
                with self.assertRaisesRegex(
                        TrialError, "TRIAL_AGENT_INDEPENDENCE_UNESTABLISHED"):
                    self.score(b=altered)

    def test_wrong_role_or_forged_input_shape_refused(self):
        altered = dict(self.a, role="critic")
        with self.assertRaisesRegex(TrialError, "TRIAL_AGENT_CONTRACT_INVALID"):
            self.score(a=altered)
        packet = copy.deepcopy(self.packet)
        packet["witnesses"][0]["extra"] = "untrusted"
        with self.assertRaisesRegex(TrialError, "TRIAL_WITNESS_SHAPE_INVALID"):
            self.score(packet=packet)

    def test_wrong_verse_and_usul_locators_refused(self):
        for role, expected in (("verse", "TRIAL_VERSE_LOCATOR_MISMATCH"),
                               ("usul", "TRIAL_USUL_LOCATOR_MISMATCH")):
            packet = copy.deepcopy(self.packet)
            row = next(r for r in packet["witnesses"] if r["role"] == role)
            row["url"] = "https://example.org/other"
            with self.subTest(role=role), self.assertRaisesRegex(
                    TrialError, expected):
                self.score(packet=packet)

    def test_negative_case_not_promoted_to_positive_scientific_trial(self):
        bad = copy.deepcopy(self.packet)
        bad["case_id"] = "AMR-01-N"
        with self.assertRaisesRegex(TrialError, "TRIAL_CASE_OUT_OF_SCOPE"):
            run_trial(self.book, "AMR-01-N", bad, self.a, self.b)

    def test_no_source_text_is_in_report(self):
        s = json.dumps(self.score(), ensure_ascii=False)
        for w in self.packet["witnesses"]:
            self.assertNotIn(w["text"], s)
        self.assertIn("source_text_included", s)

    def test_duplicate_role_and_source_ids_refused(self):
        packet = copy.deepcopy(self.packet)
        packet["witnesses"][1]["role"] = "verse"
        with self.assertRaisesRegex(TrialError, "TRIAL_WITNESS_ID_INVALID"):
            self.score(packet=packet)
        packet = copy.deepcopy(self.packet)
        packet["witnesses"][1]["id"] = "verse1"
        with self.assertRaisesRegex(TrialError, "TRIAL_WITNESS_ID_INVALID"):
            self.score(packet=packet)


if __name__ == "__main__":
    unittest.main()
