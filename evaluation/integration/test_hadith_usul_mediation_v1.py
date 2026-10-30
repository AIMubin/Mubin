"""B02-C.4: no witness, model vote or source match becomes scholarly proof."""
from __future__ import annotations
from hashlib import sha256
import copy
import json
import unittest

from core.orchestration.hadith_usul_mediation import (
    MediationError, assess_hadith_usul_hop,
)

PREFIX = b"PINNED_CONTEXT_BEFORE_"
SUFFIX = b"_PINNED_CONTEXT_AFTER"
DOCUMENTS = {
    "source.hadith": PREFIX + "مصدر حديث تجريبي لا يمثل حديثاً صحيحاً".encode("utf-8") + SUFFIX,
    "source.usul": PREFIX + "قاعدة أصولية تجريبية للاختبارات البرمجية فقط".encode("utf-8") + SUFFIX,
}
PINS = {k: sha256(v).hexdigest() for k, v in DOCUMENTS.items()}
STORAGE = {}


def sha(raw):
    return sha256(raw).hexdigest()


def canon(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def source_read(src, start, end):
    return DOCUMENTS[src][start:end]


def anchor(src):
    raw = DOCUMENTS[src]
    start, end = len(PREFIX), len(raw) - len(SUFFIX)
    return {
        "source_id": src, "source_sha256": sha(raw),
        "start_byte": start, "end_byte": end,
        "context_start_byte": 0, "context_end_byte": len(raw),
        "span_sha256": sha(raw[start:end]), "context_sha256": sha(raw),
    }


def sample(relation="RULE_SUPPORT_PROPOSAL", coverage="COMPLETE"):
    inp = {
        "contract": "mubin-hadith-usul-mediation/1.0",
        "case_id": "case.synthetic.001",
        "verse_reference": "6:145",
        "hypothesis": {"methodology_profile_id": "profile.synthetic",
                       "relation_type": relation},
        "witness": {
            "link_id": "hl.synthetic.001",
            "classification": "NARRATION_FRAGMENT_CANDIDATE",
            "source_span": anchor("source.hadith"),
            "hsearch_receipt_sha256": "0"*64,
            "coverage_state": coverage,
            "narration_identity_verified": False,
            "grade_assigned": False,
        },
        "usul": {"rule_id": "rule.example.001",
                 "source_span": anchor("source.usul")},
        "reviews": [], "open_defeater_ids": [],
    }
    bridge = {
        "contract": "mubin-hsearch-witness-bridge/1.0",
        "link_id": "hl.synthetic.001",
        "classification": "NARRATION_FRAGMENT_CANDIDATE",
        "witness_source_sha256": inp["witness"]["source_span"]["source_sha256"],
        "witness_span_sha256": inp["witness"]["source_span"]["span_sha256"],
        "pinned_source_count": 4 if coverage == "COMPLETE" else 3,
        "source_unavailable": [] if coverage == "COMPLETE" else ["book.four"],
        "candidate_only": True,
        "narration_identity_verified": False, "grade_assigned": False,
    }
    bridge_bytes = canon(bridge)
    inp["witness"]["hsearch_receipt_sha256"] = sha(bridge_bytes)
    STORAGE.clear()
    STORAGE["bridge"] = bridge_bytes

    core = {k: inp[k] for k in (
        "contract", "case_id", "verse_reference", "hypothesis", "witness",
        "usul", "open_defeater_ids")}
    input_sha = sha(canon(core))
    for index, (role, verdict) in enumerate([
        ("supporter", "SUPPORTS_HYPOTHESIS"),
        ("supporter", "SUPPORTS_HYPOTHESIS"),
        ("critic", "NO_OPEN_DEFEATER"),
    ], 1):
        run = f"run.synthetic.{index}"
        review = {"run_id": run, "model_id": f"model.{index}",
                  "role": role, "verdict": verdict}
        receipt = {
            "contract": "mubin-hadith-usul-review/1.0",
            "input_sha256": input_sha, **review,
            "anchor_roles": ["hadith", "usul"],
            "rationale": "Synthetic source-grounded critical assessment for negative contract testing only.",
        }
        raw = canon(receipt)
        STORAGE[run] = raw
        inp["reviews"].append({**review, "receipt_sha256": sha(raw)})
    return inp


def rebind_reviews(inp):
    core = {k: inp[k] for k in (
        "contract", "case_id", "verse_reference", "hypothesis", "witness",
        "usul", "open_defeater_ids")}
    digest = sha(canon(core))
    for review in inp["reviews"]:
        payload = json.loads(STORAGE[review["run_id"]])
        payload["input_sha256"] = digest
        raw = canon(payload)
        STORAGE[review["run_id"]] = raw
        review["receipt_sha256"] = sha(raw)


def run(x, **kwargs):
    return assess_hadith_usul_hop(
        x, source_pins=kwargs.get("pins", PINS),
        read_span=kwargs.get("span_reader", source_read),
        read_witness=kwargs.get("witness_reader", lambda link: STORAGE["bridge"]),
        read_assessment=kwargs.get("review_reader", lambda run_id: STORAGE[run_id]),
    )


class MediationTests(unittest.TestCase):
    def test_machine_candidate_never_becomes_scholarly_assessment(self):
        result = run(sample())
        self.assertEqual(result["status"], "MACHINE_RESEARCH_CANDIDATE_ONLY")
        for flag in (
            "scientifically_established_hop", "narration_identity_verified",
            "hadith_grade_assigned", "source_authenticity_verified",
            "semantic_truth_verified", "independent_model_families_verified",
            "juristic_inference_allowed", "scholarly_verified",
            "source_text_included",
        ):
            self.assertFalse(result[flag])
        self.assertNotIn("مصدر حديث", json.dumps(result, ensure_ascii=False))

    def test_lexical_candidate_never_upgrades_with_supporter_votes(self):
        self.assertEqual(run(sample("LEXICAL_PARALLEL"))["status"],
                         "LEXICAL_CANDIDATE_ONLY")

    def test_incomplete_hsearch_coverage_blocks_positive_status(self):
        self.assertEqual(run(sample(coverage="INCOMPLETE"))["status"],
                         "INCOMPLETE_SOURCE_COVERAGE")

    def test_open_defeater_veto(self):
        x = sample()
        x["open_defeater_ids"] = ["objection.001"]
        rebind_reviews(x)
        self.assertEqual(run(x)["status"], "CONTESTED")

    def test_removing_open_defeater_cannot_replay_positive_reviews(self):
        x = sample()
        x["open_defeater_ids"] = ["objection.001"]
        rebind_reviews(x)
        x["open_defeater_ids"] = []
        with self.assertRaisesRegex(MediationError, "REVIEW_NOT_SOURCE_BOUND"):
            run(x)

    def test_supporters_missing_means_undetermined(self):
        x = sample()
        x["reviews"] = x["reviews"][2:]
        self.assertEqual(run(x)["status"], "UNDETERMINED")

    def test_context_cannot_be_only_the_quoted_fragment(self):
        x = sample()
        for role in ("witness", "usul"):
            a = x[role]["source_span"]
            a["context_start_byte"] = a["start_byte"]
            a["context_end_byte"] = a["end_byte"]
            a["context_sha256"] = a["span_sha256"]
        with self.assertRaisesRegex(MediationError, "MEDIATION_SPAN_INVALID"):
            run(x)

    def test_replay_different_source_pin_refused(self):
        x = sample()
        x["witness"]["source_span"]["source_sha256"] = "0"*64
        with self.assertRaisesRegex(MediationError, "SOURCE_PIN_MISMATCH"):
            run(x)

    def test_span_checksum_change_refused(self):
        x = sample()
        x["usul"]["source_span"]["span_sha256"] = "f"*64
        with self.assertRaisesRegex(MediationError, "SOURCE_BYTES_DIFFER"):
            run(x)

    def test_witness_and_usul_cannot_be_same_source(self):
        x = sample()
        x["usul"]["source_span"] = copy.deepcopy(x["witness"]["source_span"])
        with self.assertRaisesRegex(MediationError, "SOURCE_DOMAINS_COLLAPSED"):
            run(x)

    def test_hsearch_bridge_digest_forgery_refused(self):
        x = sample()
        x["witness"]["hsearch_receipt_sha256"] = "f"*64
        with self.assertRaisesRegex(MediationError, "HSEARCH_RECEIPT_DIGEST_MISMATCH"):
            run(x)

    def test_hsearch_declared_coverage_mismatch_refused(self):
        x = sample()
        x["witness"]["coverage_state"] = "INCOMPLETE"
        with self.assertRaisesRegex(MediationError, "HSEARCH_COVERAGE_MISMATCH"):
            run(x)

    def test_review_digest_forgery_refused(self):
        x = sample()
        x["reviews"][0]["receipt_sha256"] = "0"*64
        with self.assertRaisesRegex(MediationError, "REVIEW_DIGEST_MISMATCH"):
            run(x)

    def test_review_bound_to_old_question_refused(self):
        x = sample()
        x["verse_reference"] = "49:6"
        with self.assertRaisesRegex(MediationError, "REVIEW_NOT_SOURCE_BOUND"):
            run(x)

    def test_duplicate_review_run_rejected(self):
        x = sample()
        x["reviews"][1]["run_id"] = x["reviews"][0]["run_id"]
        with self.assertRaisesRegex(MediationError, "DUPLICATE_REVIEW_RUN"):
            run(x)

    def test_model_role_duplicate_rejected(self):
        x = sample()
        x["reviews"][1]["model_id"] = x["reviews"][0]["model_id"]
        with self.assertRaisesRegex(MediationError, "REVIEW_NOT_SOURCE_BOUND"):
            run(x)

    def test_critic_can_veto_when_receipt_unchanged_sources(self):
        x = sample()
        x["reviews"][2]["verdict"] = "OPEN_DEFEATER"
        receipt = json.loads(STORAGE["run.synthetic.3"])
        receipt["verdict"] = "OPEN_DEFEATER"
        raw = canon(receipt)
        STORAGE["run.synthetic.3"] = raw
        x["reviews"][2]["receipt_sha256"] = sha(raw)
        self.assertEqual(run(x)["status"], "CONTESTED")

    def test_review_reader_exception_sanitized(self):
        x = sample()
        def private_error(_):
            raise RuntimeError("D:\\Sensitive\\SourceFile.txt")
        with self.assertRaisesRegex(MediationError, "^MEDIATION_REVIEW_RECEIPT_MISSING$"):
            run(x, review_reader=private_error)

    def test_unconfigured_local_reader_fails_closed(self):
        with self.assertRaisesRegex(MediationError, "TRUSTED_READERS_REQUIRED"):
            run(sample(), span_reader=None)

    def test_invalid_shape_refused_before_reading_sources(self):
        x = sample()
        x["witness"]["grade_assigned"] = True
        with self.assertRaisesRegex(MediationError, "MEDIATION_SCHEMA_INVALID"):
            run(x)

    def test_private_text_never_allowed_in_request(self):
        x = sample()
        x["hadith_excerpt"] = "private source quote"
        with self.assertRaisesRegex(MediationError, "MEDIATION_SCHEMA_INVALID"):
            run(x)


if __name__ == "__main__":
    unittest.main()
