"""Negative tests: ungrounded lexical matches cannot become semantic authority."""
from __future__ import annotations
import hashlib
import copy
import json
import unittest
from core.orchestration.semantic_link_research import (
    evaluate_research_link, SemanticLinkError,
)

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

DOCUMENTS = {
    "src.quran": "نص تجريبي للآية للاختبار فقط".encode("utf-8"),
    "src.tafsir": "يذكر النص التجريبي بيان المقصود والقرائن".encode("utf-8"),
    "src.usul": "قاعدة أصولية تجريبية وأمثلة افتراضية".encode("utf-8"),
}
PINS = {k: digest(v) for k, v in DOCUMENTS.items()}

def read_span(name, start, end):
    return DOCUMENTS[name][start:end]

RECEIPTS = {}

def sample(relation="TAFSIR_MEDIATED_APPLICATION"):
    anchors = []
    for idx, role in enumerate(("quran", "tafsir", "usul"), 1):
        src = "src." + role
        raw = DOCUMENTS[src]
        anchors.append({
            "id": "anchor.%03d" % idx, "role": role,
            "source_id": src, "source_sha256": digest(raw),
            "reference": "6:145" if role != "usul" else "rule.001",
            "start_byte": 0, "end_byte": len(raw),
            "context_start_byte": 0, "context_end_byte": len(raw),
            "excerpt_sha256": digest(raw), "context_sha256": digest(raw),
        })
    reviews = [
        {"run_id":"run.001", "model_id":"model.one", "role":"supporter",
         "verdict":"SUPPORTS_LINK", "anchor_ids":[a["id"] for a in anchors],
         "receipt_sha256":"a"*64},
        {"run_id":"run.002", "model_id":"model.two", "role":"supporter",
         "verdict":"SUPPORTS_LINK", "anchor_ids":[a["id"] for a in anchors],
         "receipt_sha256":"b"*64},
        {"run_id":"run.003", "model_id":"model.three", "role":"critic",
         "verdict":"NO_OPEN_DEFEATER", "anchor_ids":[a["id"] for a in anchors],
         "receipt_sha256":"c"*64},
    ]
    input_hash = digest(json.dumps({
        "case_id":"case.001", "verse_reference":"6:145", "rule_id":"rule.001",
        "methodology_profile_id":"method.001", "relation_type":relation,
        "anchors":anchors,
    }, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    RECEIPTS.clear()
    for review in reviews:
        doc = {**review, "contract":"mubin-machine-semantic-review/1.0",
               "input_sha256":input_hash,
               "rationale":"A synthetic reasoning receipt for byte-level contract validation only."}
        doc.pop("receipt_sha256")
        raw = json.dumps(doc, ensure_ascii=False, sort_keys=True).encode("utf-8")
        RECEIPTS[review["run_id"]] = raw
        review["receipt_sha256"] = digest(raw)
    return {
        "contract":"mubin-semantic-link-research/1.0", "case_id":"case.001",
        "verse_reference":"6:145", "rule_id":"rule.001",
        "methodology_profile_id":"method.001",
        "relation_type":relation, "anchors":anchors,
        "assessments":reviews, "open_defeater_ids":[],
    }

class SemanticResearchTests(unittest.TestCase):
    def evaluate(self, data, **kwargs):
        return evaluate_research_link(
            data, source_pins=kwargs.get("pins", PINS),
            read_span=kwargs.get("reader", read_span),
            read_assessment=kwargs.get("reviewer", lambda run_id: RECEIPTS[run_id]))

    def test_machine_research_support_is_not_scholarly_certification(self):
        x = self.evaluate(sample())
        self.assertEqual(x["status"], "MACHINE_SUPPORTED_RESEARCH_ONLY")
        self.assertTrue(x["machine_research_gate_passed"])
        self.assertFalse(x["scholarly_verified"])
        self.assertFalse(x["verified_source_authenticity"])
        self.assertFalse(x["model_independence_established"])
        self.assertFalse(x["juristic_inference_allowed"])

    def test_lexical_only_never_passes_even_with_three_reviews(self):
        x=self.evaluate(sample("LEXICAL_OVERLAP"))
        self.assertEqual(x["status"], "LEXICAL_ONLY")
        self.assertFalse(x["machine_research_gate_passed"])

    def test_contextual_hypothesis_never_gets_procedural_pass(self):
        result = self.evaluate(sample("CONTEXTUAL_HYPOTHESIS"))
        self.assertEqual(result["status"], "UNDETERMINED")
        self.assertFalse(result["machine_research_gate_passed"])

    def test_forged_review_digest_refused(self):
        x = sample()
        x["assessments"][0]["receipt_sha256"] = "0" * 64
        with self.assertRaises(SemanticLinkError):
            self.evaluate(x)

    def test_unavailable_review_receipt_does_not_count_as_vote(self):
        with self.assertRaises(SemanticLinkError) as cm:
            self.evaluate(sample(), reviewer=lambda run_id: (_ for _ in ()).throw(
                RuntimeError("PRIVATE_REVIEW_PATH")))
        self.assertEqual(str(cm.exception), "SEMANTIC_LINK_REVIEW_READ_FAILED")
        self.assertNotIn("PRIVATE", str(cm.exception))

    def test_reviewed_input_version_change_fails(self):
        x=sample()
        x["case_id"]="case.other"
        with self.assertRaises(SemanticLinkError):
            self.evaluate(x)

    def test_no_reviews_cannot_pass(self):
        x=sample()
        x["assessments"]=[]
        self.assertEqual(self.evaluate(x)["status"], "UNDETERMINED")

    def test_open_defeater_blocks(self):
        x=sample()
        x["open_defeater_ids"]=["defeater.001"]
        self.assertEqual(self.evaluate(x)["status"], "CONTESTED")

    def test_critic_veto_blocks(self):
        x=sample()
        x["assessments"][-1]["verdict"]="OPEN_DEFEATER"
        recorded=json.loads(RECEIPTS["run.003"])
        recorded["verdict"]="OPEN_DEFEATER"
        rewritten=json.dumps(recorded, ensure_ascii=False, sort_keys=True).encode("utf-8")
        RECEIPTS["run.003"]=rewritten
        x["assessments"][-1]["receipt_sha256"]=digest(rewritten)
        self.assertEqual(self.evaluate(x)["status"], "CONTESTED")

    def test_repeated_review_run_invalid(self):
        x=sample()
        x["assessments"][1]["run_id"]="run.001"
        with self.assertRaises(SemanticLinkError):
            self.evaluate(x)

    def test_corrupt_excerpt_refused(self):
        x=sample()
        x["anchors"][0]["excerpt_sha256"]="0"*64
        with self.assertRaises(SemanticLinkError):
            self.evaluate(x)

    def test_source_pin_wrong_refused(self):
        x=sample()
        x["anchors"][0]["source_sha256"]="0"*64
        with self.assertRaises(SemanticLinkError):
            self.evaluate(x)

    def test_verse_mismatch_refused(self):
        x=sample()
        x["anchors"][1]["reference"]="49:6"
        with self.assertRaises(SemanticLinkError):
            self.evaluate(x)

    def test_usul_rule_mismatch_refused(self):
        x=sample()
        x["anchors"][2]["reference"]="rule.other"
        with self.assertRaises(SemanticLinkError):
            self.evaluate(x)

    def test_missing_tafsir_anchor_refused(self):
        x=sample()
        x["anchors"]=x["anchors"][:1]+x["anchors"][2:]
        with self.assertRaises(SemanticLinkError):
            self.evaluate(x)

    def test_missing_context_in_support_review_refused(self):
        x=sample()
        x["assessments"][0]["anchor_ids"]=["anchor.001","anchor.002"]
        with self.assertRaises(SemanticLinkError):
            self.evaluate(x)

    def test_unbound_review_anchor_refused(self):
        x=sample()
        x["assessments"][0]["anchor_ids"]=["anchor.001","anchor.002","anchor.nonexistent"]
        with self.assertRaises(SemanticLinkError):
            self.evaluate(x)

    def test_source_reader_exception_redacted(self):
        def raise_secret(*args):
            raise RuntimeError("C:\\PRIVATE_VAULT\\secret")
        with self.assertRaises(SemanticLinkError) as cm:
            self.evaluate(sample(), reader=raise_secret)
        self.assertEqual(str(cm.exception), "SEMANTIC_LINK_SOURCE_READ_FAILED")
        self.assertNotIn("PRIVATE", str(cm.exception))

    def test_invalid_json_not_accepted(self):
        x=sample()
        x["assessment_forged"]=True
        with self.assertRaises(SemanticLinkError):
            self.evaluate(x)

    def test_stance_requires_actual_critic(self):
        x=sample()
        x["assessments"][-1]["role"]="supporter"
        with self.assertRaises(SemanticLinkError):
            self.evaluate(x)

    def test_non_utf8_response_never_contains_raw_text(self):
        x=sample()
        x["case_id"]="sensitive?\\nsource text"
        with self.assertRaises(SemanticLinkError) as cm:
            self.evaluate(x)
        self.assertNotIn("sensitive", str(cm.exception))

if __name__=="__main__":
    unittest.main()
