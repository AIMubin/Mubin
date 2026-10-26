"""E2E-01.4b.3: transport + independence tests, all data synthetic.

No true LLM or external network in CI; mock HTTP transport is confined to
testing the behavior of the real, opt-in local model runner.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from engines.e2e.scientific_benchmark import load_casebook
from engines.e2e.frozen_preflight import preflight_frozen_packet
from engines.e2e.witness_science import _canonical
from engines.e2e.local_model_trial import (
    TrialError, _endpoint, execute_local_dual_model, _model_decision,
)

E = "http://127.0.0.1:8181/v1/chat/completions"
C = "http://127.0.0.1:8282/v1/chat/completions"


class FakeResponse:
    def __init__(self, payload, code=200):
        self.status = code
        self._body = json.dumps(payload, ensure_ascii=False).encode()

    def read(self, n):
        return self._body[:n]


class FakeConnection:
    calls = []
    behavior = {}
    def __init__(self, host, port, timeout):
        self.host, self.port = host, port
        self.closed = False
        self.request_json = None
        self.assert_timeout = timeout

    def request(self, method, path, body, headers):
        self.request_json = json.loads(body)
        self.calls.append((self.host, self.port, method, path,
                           self.request_json, headers))

    def getresponse(self):
        requested = self.request_json["model"]
        info = self.behavior.get(requested, {})
        decision = info.get("decision", "SUPPORTED")
        evidence_ids = info.get("evidence_ids", ["v", "t", "u"])
        result = {
            "id": info.get("id", "response-" + requested),
            "model": info.get("model", requested),
            "choices": [{"message": {
                "content": json.dumps({
                    "decision": decision,
                    "evidence_ids": evidence_ids,
                })}}],
        }
        if "override" in info:
            result = info["override"]
        return FakeResponse(result, info.get("code", 200))

    def close(self):
        self.closed = True


def w(role, rid, url, family, content):
    return dict(id=rid, role=role, url=url, family=family,
                text=content,
                sha256=hashlib.sha256(content.encode()).hexdigest())


def synthetic_pin(packet):
    """Invented receipt for CI only, never a real 2:43 textual witness."""
    return {
        "contract": "mubin-e2e-014b3-cited-excerpt-digests-v0.1",
        "case_id": "AMR-01-P", "reference": "2:43",
        "candidate_word": "أَقِيمُوا",
        "packet_canonical_sha256":
            hashlib.sha256(_canonical(packet)).hexdigest(),
        "witness_records": [
            {key: (row["sha256"] if key == "local_excerpt_sha256"
                   else row[key])
             for key in ("id", "role", "url", "family",
                         "local_excerpt_sha256")}
            for row in packet["witnesses"]
        ],
        "upstream_source_byte_attested": False,
        "original_quran_edition_authenticated": False,
        "original_tafsir_edition_authenticated": False,
        "independent_model_pair_executed": False,
        "source_authenticated": False,
        "scholarly_verified": False,
        "publication_allowed": False,
        "juristic_inference_allowed": False,
        "public_fatwa_authorized": False,
        "p1_admitted": False,
        "scientific_gold_label": None,
        "rights_status": "legal_review_pending",
    }


class LocalDualTrialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book, _ = load_casebook()
        cls.case = next(c for c in cls.book["cases"]
                        if c["id"] == "AMR-01-P")

    def setUp(self):
        self.packet = {
            "case_id": "AMR-01-P",
            "reference": "2:43",
            "witnesses": [
                w("verse", "v", self.case["quran_witness_url"],
                  "quran-digital",
                  "نص اختبار اصطناعي فقط: أَقِيمُوا"),
                w("tafsir", "t", "https://example.org/tafsir/2:43",
                  "tafsir-digital",
                  "تفسير اصطناعي مخصص للاختبار البرمجي"),
                w("usul", "u", self.case["usul_rule"]["url"],
                  "usul-digital",
                  "قاعدة اصطناعية مخصصة للاختبار البرمجي"),
            ],
        }
        self.manifest = synthetic_pin(self.packet)
        FakeConnection.calls = []
        FakeConnection.behavior = {}

    def run_fake(self, **kwargs):
        defaults = dict(casebook=self.book, packet=self.packet,
                        case_id="AMR-01-P",
                        evaluator_url=E, evaluator_model="model-A",
                        critic_url=C, critic_model="model-B")
        defaults.update(kwargs)
        with patch("engines.e2e.local_model_trial.http.client.HTTPConnection",
                   FakeConnection), patch(
                       "engines.e2e.frozen_preflight._load_manifest",
                       return_value=self.manifest):
            return execute_local_dual_model(**defaults)

    def test_two_local_calls_with_isolated_prompts(self):
        FakeConnection.behavior = {
            "model-A": {"decision": "SUPPORTED"},
            "model-B": {"decision": "REFUTED"},
        }
        result = self.run_fake()
        self.assertEqual(result["research_state"], "AI_DISAGREEMENT")
        self.assertTrue(result["runtime"]["two_local_chat_completion_responses_received"])
        self.assertFalse(result["independent_model_execution_proven"])
        self.assertFalse(result["runtime"]["actual_distinct_model_weights_independently_attested"])
        self.assertTrue(result["runtime"]["immediate_network_destination_loopback_only"])
        self.assertTrue(result["runtime"]["frozen_repository_excerpt_manifest_matched_before_dispatch"])
        self.assertFalse(result["runtime"]["local_server_forwarding_independently_excluded"])
        self.assertNotIn("source_text_sent_to_external_host", result["runtime"])
        self.assertEqual(len(FakeConnection.calls), 2)
        a, b = FakeConnection.calls
        self.assertEqual((a[1], b[1]), (8181, 8282))
        self.assertEqual(a[2:4], ("POST", "/v1/chat/completions"))
        self.assertEqual(b[2:4], ("POST", "/v1/chat/completions"))
        self.assertEqual(a[4]["temperature"], 0)
        self.assertFalse(a[4]["stream"])
        self.assertIn("أَقِيمُوا", a[4]["messages"][1]["content"])
        self.assertIn("أَقِيمُوا", b[4]["messages"][1]["content"])
        self.assertNotIn("response-model-A", b[4]["messages"][1]["content"])
        self.assertNotIn("SUPPORTED", b[4]["messages"][1]["content"])
        encoded = json.dumps(result, ensure_ascii=False)
        for source in self.packet["witnesses"]:
            self.assertNotIn(source["text"], encoded)

    def test_preflight_is_offline_and_pinned(self):
        with patch("engines.e2e.frozen_preflight._load_manifest",
                   return_value=self.manifest):
            result = preflight_frozen_packet(
                casebook=self.book, packet=self.packet,
                case_id="AMR-01-P")
        self.assertEqual(result["status"],
                         "LOCAL_FROZEN_EXCERPT_BYTE_PIN_MATCH")
        self.assertTrue(result["frozen_repository_excerpt_manifest_matched"])
        self.assertFalse(result["independent_model_pair_executed"])
        self.assertFalse(result["source_authenticated"])
        self.assertFalse(result["source_text_included"])
        self.assertEqual(FakeConnection.calls, [])

    def test_rehashed_changed_witness_is_rejected_before_http(self):
        packet = copy.deepcopy(self.packet)
        packet["witnesses"][1]["text"] += " تغيير اصطناعي"
        packet["witnesses"][1]["sha256"] = hashlib.sha256(
            packet["witnesses"][1]["text"].encode("utf-8")).hexdigest()
        with self.assertRaisesRegex(
                TrialError, "LOCAL_WITNESS_PIN_MISMATCH"):
            self.run_fake(packet=packet)
        self.assertEqual(FakeConnection.calls, [])

    def test_changed_canonical_packet_pin_is_rejected_before_http(self):
        self.manifest["packet_canonical_sha256"] = "0" * 64
        with self.assertRaisesRegex(
                TrialError, "LOCAL_PACKET_PIN_MISMATCH"):
            self.run_fake()
        self.assertEqual(FakeConnection.calls, [])

    def test_relabelled_source_family_is_rejected_before_http(self):
        packet = copy.deepcopy(self.packet)
        packet["witnesses"][1]["family"] = "impostor-tafsir-source"
        with self.assertRaisesRegex(
                TrialError, "LOCAL_WITNESS_PIN_MISMATCH"):
            self.run_fake(packet=packet)
        self.assertEqual(FakeConnection.calls, [])

    def test_manifest_with_text_or_authority_promotion_fails(self):
        self.manifest["witness_records"][1]["text"] = "private excerpt"
        with self.assertRaisesRegex(
                TrialError, "LOCAL_PIN_MANIFEST_INVALID"):
            self.run_fake()
        self.assertEqual(FakeConnection.calls, [])
        self.manifest = synthetic_pin(self.packet)
        self.manifest["source_authenticated"] = True
        with self.assertRaisesRegex(
                TrialError, "LOCAL_PIN_MANIFEST_INVALID"):
            self.run_fake()
        self.assertEqual(FakeConnection.calls, [])

    def test_agreement_is_uncertified(self):
        result = self.run_fake()
        self.assertEqual(result["research_state"], "AI_AGREEMENT_UNCERTIFIED")
        self.assertFalse(result["scholarly_verified"])
        self.assertFalse(result["public_fatwa_authorized"])

    def test_remote_and_dns_endpoints_rejected(self):
        invalid = (
            "https://api.openai.com/v1/chat/completions",
            "http://localhost:8181/v1/chat/completions",
            "http://192.168.1.2:8181/v1/chat/completions",
            "http://127.0.0.1:8181/admin",
            "http://127.0.0.1:8181/v1/chat/completions?redirect=x",
            "http://user:pass@127.0.0.1:8181/v1/chat/completions",
            "http://127.0.0.1:0/v1/chat/completions",
            "http://[::1]/v1/chat/completions",
            "http://[malformed",
        )
        for url in invalid:
            with self.subTest(url=url), self.assertRaises(TrialError):
                _endpoint(url)
        self.assertEqual(_endpoint("http://[::1]:8282/v1/chat/completions"),
                         ("::1", 8282))

    def test_same_socket_or_same_model_refused_before_call(self):
        for kw in ({"critic_url": E},
                   {"critic_model": "model-A"}):
            with self.subTest(kw=kw), self.assertRaises(TrialError):
                self.run_fake(**kw)
            self.assertEqual(FakeConnection.calls, [])

    def test_insufficient_packet_refused_before_exposing_text(self):
        bad = copy.deepcopy(self.packet)
        bad["witnesses"] = bad["witnesses"][:2]
        with self.assertRaisesRegex(TrialError, "LOCAL_EVIDENCE_INSUFFICIENT"):
            self.run_fake(packet=bad)
        self.assertEqual(FakeConnection.calls, [])

    def test_model_identity_mismatch_refused(self):
        FakeConnection.behavior["model-A"] = {
            "model": "a-different-actual-model"}
        with self.assertRaisesRegex(TrialError, "LOCAL_RESPONSE_MODEL_MISMATCH"):
            self.run_fake()
        self.assertEqual(len(FakeConnection.calls), 1)

    def test_hallucinated_witness_id_refused(self):
        FakeConnection.behavior["model-B"] = {
            "evidence_ids": ["verse-that-is-not-there"]}
        with self.assertRaisesRegex(TrialError, "TRIAL_AGENT_CITATION_INVALID"):
            self.run_fake()

    def test_non_200_and_invalid_json_and_extra_decision_fields(self):
        for info, error in (
            ({"code": 403}, "LOCAL_MODEL_RESPONSE_REFUSED"),
            ({"override": {"malformed": True}}, "LOCAL_RESPONSE_MODEL_MISMATCH"),
            ({"override": {
                "id": "id", "model": "model-A",
                "choices": [{"message": {"content":
                    '{"decision":"SUPPORTED","evidence_ids":[],"approved":true}'}}]
                }}, "LOCAL_DECISION_SHAPE_INVALID"),
        ):
            FakeConnection.calls = []
            FakeConnection.behavior = {"model-A": info}
            with self.subTest(info=info), self.assertRaisesRegex(
                    TrialError, error):
                self.run_fake()

    def test_duplicate_server_response_ids_refused(self):
        FakeConnection.behavior = {
            "model-A": {"id": "same"},
            "model-B": {"id": "same"},
        }
        with self.assertRaisesRegex(
                TrialError, "TRIAL_AGENT_INDEPENDENCE_UNESTABLISHED"):
            self.run_fake()

    def test_real_cited_excerpt_manifest_is_pinned_metadata_not_gold(self):
        path = (Path(__file__).resolve().parents[2]
                / "evaluation/evidence/amr_2_43_local_excerpt_digests_v01.json")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["case_id"], "AMR-01-P")
        self.assertEqual(manifest["reference"], "2:43")
        self.assertEqual(len(manifest["witness_records"]), 3)
        self.assertEqual({r["role"] for r in manifest["witness_records"]},
                         {"verse", "tafsir", "usul"})
        self.assertEqual(len(manifest["packet_canonical_sha256"]), 64)
        for source in manifest["witness_records"]:
            self.assertEqual(len(source["local_excerpt_sha256"]), 64)
            self.assertNotIn("text", source)
        self.assertFalse(manifest["independent_model_pair_executed"])
        self.assertFalse(manifest["upstream_source_byte_attested"])
        self.assertIsNone(manifest["scientific_gold_label"])
        for key in ("scholarly_verified", "source_authenticated",
                    "publication_allowed", "juristic_inference_allowed",
                    "public_fatwa_authorized", "p1_admitted"):
            self.assertIs(manifest[key], False)

    def test_only_first_scoped_case_runs(self):
        with self.assertRaisesRegex(TrialError, "LOCAL_CASE_NOT_ADMITTED"):
            self.run_fake(case_id="AMR-02-P")
        self.assertEqual(FakeConnection.calls, [])


if __name__ == "__main__":
    unittest.main()
