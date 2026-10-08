"""P0 contracts: positive example and adversarial failure-on-uncertainty checks."""
from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from core.inference import validate_bundle

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "schemas/inference-foundation.schema.json").read_text(encoding="utf-8"))


def fixture():
    excerpt = "Scholar-published source statement; hypothetical test data, not a fatwa."
    digest = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
    claims = ["clm.asl", "clm.far", "clm.hukm", "clm.illah"]
    return {
        "contract_version": "0.1.0",
        "sources": [{
            "id": "src.001", "kind": "usul", "work_title": "Hypothetical sample",
            "edition": "test-only", "locator": "folio-1", "content_sha256": "0" * 64
        }],
        "evidence": [{
            "id": "ev.001", "source_id": "src.001", "locator": "folio-1",
            "excerpt": excerpt, "excerpt_sha256": digest,
            "verification_status": "verified", "verification_method": "exact_source_match"
        }],
        "methodologies": [{
            "id": "met.001", "label": "Hypothetical scoped method",
            "version": "1", "source_evidence_ids": ["ev.001"]
        }],
        "claims": [{
            "id": name, "statement": "Hypothetical premise " + name,
            "claim_type": "source_attributed", "conclusion_kind": "source_derived",
            "evidence_ids": ["ev.001"]
        } for name in claims] + [{
            "id": "clm.conclusion", "statement": "Hypothetical qiyas conclusion",
            "claim_type": "inferred", "conclusion_kind": "qiyas_derived",
            "evidence_ids": [], "inference_id": "inf.001"
        }],
        "rules": [{
            "id": "rule.001", "methodology_id": "met.001",
            "rule_type": "qiyas", "expression": "Test qiyas pattern",
            "preconditions": ["asl has hukm", "illah is shared", "no blocker"],
            "exceptions": [], "source_evidence_ids": ["ev.001"],
            "formalization_status": "draft"
        }],
        "inferences": [{
            "id": "inf.001", "inference_kind": "qiyas", "methodology_id": "met.001",
            "rule_ids": ["rule.001"], "premise_claim_ids": claims,
            "conclusion_claim_id": "clm.conclusion", "exception_checks": [],
            "qiyas_elements": {
                "asl": "clm.asl", "far": "clm.far",
                "hukm_al_asl": "clm.hukm", "illah": "clm.illah"
            }
        }],
        "objections": [],
        "proofs": [{
            "id": "prf.001", "conclusion_claim_id": "clm.conclusion",
            "inference_ids": ["inf.001"], "methodology_id": "met.001",
            "verification_scope": "structural_only",
            "verification_status": "structurally_checked"
        }],
        "historical_availability": [{
            "id": "hist.001", "scholar_id": "sch.001", "evidence_id": "ev.001",
            "knowledge_state": "unknown", "basis_type": "none",
            "basis_evidence_ids": [], "statement": "No supported historical attestation"
        }]
    }


class TestP0InferenceFoundation(unittest.TestCase):
    def assert_blocked(self, bundle, fragment):
        failures = validate_bundle(bundle)
        self.assertTrue(any(fragment in item for item in failures), failures)

    def test_schema_validity_and_fixture(self):
        Draft202012Validator.check_schema(SCHEMA)
        data = fixture()
        self.assertEqual([], list(Draft202012Validator(SCHEMA).iter_errors(data)))
        self.assertEqual([], validate_bundle(data))

    def test_missing_source_evidence(self):
        data = fixture()
        data["claims"][0]["evidence_ids"] = []
        self.assert_blocked(data, "no source evidence")

    def test_digest_tamper(self):
        data = fixture()
        data["evidence"][0]["excerpt"] += " altered"
        self.assert_blocked(data, "digest mismatch")

    def test_missing_cited_source(self):
        data = fixture()
        data["evidence"][0]["source_id"] = "src.missing"
        self.assert_blocked(data, "unknown sources reference")

    def test_reject_mixed_methodologies(self):
        data = fixture()
        data["methodologies"].append({
            "id": "met.002", "label": "Another method", "version": "1",
            "source_evidence_ids": ["ev.001"]
        })
        data["inferences"][0]["methodology_id"] = "met.002"
        self.assert_blocked(data, "incompatible methodology")

    def test_qiyas_without_illah_slot(self):
        data = fixture()
        data["inferences"][0]["premise_claim_ids"].remove("clm.illah")
        self.assert_blocked(data, "missing illah")

    def test_source_claim_must_not_impersonate_inferred_result(self):
        data = fixture()
        data["claims"][0]["conclusion_kind"] = "qiyas_derived"
        self.assert_blocked(data, "source claim has non-source origin label")

    def test_premise_cycle(self):
        data = fixture()
        data["claims"][0]["claim_type"] = "inferred"
        data["claims"][0]["conclusion_kind"] = "qiyas_derived"
        data["claims"][0]["inference_id"] = "inf.001"
        self.assert_blocked(data, "cycle:")

    def test_open_objection_blocks_checked_proof(self):
        data = fixture()
        data["objections"].append({
            "id": "obj.001", "target_inference_id": "inf.001",
            "objection_kind": "invalid_analogy",
            "statement": "Hypothetical material objection",
            "evidence_ids": ["ev.001"], "status": "open"
        })
        self.assert_blocked(data, "outstanding objection")

    def test_unknown_exception_blocks_checked_proof(self):
        data = fixture()
        data["inferences"][0]["exception_checks"].append({
            "exception": "potential mani", "outcome": "unknown", "evidence_ids": []
        })
        self.assert_blocked(data, "unresolved or triggered exception")

    def test_historical_silence_cannot_prove_non_reachability(self):
        data = fixture()
        data["historical_availability"][0].update(
            knowledge_state="attested_not_reached", basis_type="none",
            basis_evidence_ids=[]
        )
        self.assert_blocked(data, "non-reachability cannot be inferred from silence")

    def test_attested_non_reachability_requires_source_evidence(self):
        data = fixture()
        data["historical_availability"][0].update(
            knowledge_state="attested_not_reached",
            basis_type="documented_chronological_impossibility", basis_evidence_ids=[]
        )
        self.assert_blocked(data, "no source evidence")

    def test_mixed_methodology_through_derived_premise(self):
        data = fixture()
        data["methodologies"].append({
            "id": "met.002", "label": "Other method", "version": "1",
            "source_evidence_ids": ["ev.001"]
        })
        data["rules"].append({
            "id": "rule.002", "methodology_id": "met.002",
            "rule_type": "deduction", "expression": "Hypothetical",
            "preconditions": ["one premise"], "exceptions": [],
            "source_evidence_ids": ["ev.001"], "formalization_status": "draft"
        })
        data["claims"].append({
            "id": "clm.intermediate", "statement": "Intermediate conclusion",
            "claim_type": "inferred", "conclusion_kind": "rule_derived",
            "evidence_ids": [], "inference_id": "inf.002"
        })
        data["inferences"].append({
            "id": "inf.002", "inference_kind": "deduction",
            "methodology_id": "met.002", "rule_ids": ["rule.002"],
            "premise_claim_ids": ["clm.asl"],
            "conclusion_claim_id": "clm.intermediate", "exception_checks": []
        })
        data["inferences"][0]["premise_claim_ids"].append("clm.intermediate")
        self.assert_blocked(data, "incompatible methodology in derived premise")

    def test_unchecked_rule_exception_blocks_proof(self):
        data = fixture()
        data["rules"][0]["exceptions"] = ["mani exists"]
        self.assert_blocked(data, "unchecked declared rule exceptions")

    def test_contested_conclusion_cannot_claim_checked_proof(self):
        data = fixture()
        data["claims"][-1]["conclusion_kind"] = "contested"
        self.assert_blocked(data, "contested or undetermined")

    def test_attested_reachability_cannot_use_impossibility_basis(self):
        data = fixture()
        data["historical_availability"][0].update(
            knowledge_state="attested_reached",
            basis_type="documented_chronological_impossibility",
            basis_evidence_ids=["ev.001"]
        )
        self.assert_blocked(data, "reachability requires explicit historical testimony")

    def test_cross_entity_duplicate_id(self):
        data = fixture()
        data["rules"][0]["id"] = "ev.001"
        self.assert_blocked(data, "duplicate entity id")

    def test_extra_human_attestation_field_is_rejected(self):
        data = fixture()
        data["claims"][0]["human_reviewed"] = True
        self.assert_blocked(data, "Additional properties are not allowed")

    def test_no_version_bump_or_h392_mutation(self):
        version = (ROOT / "VERSION.yaml").read_text(encoding="utf-8")
        self.assertIn("version: 0.1.0-alpha", version)
        status_path = ROOT / "engines/hadith/qualification/H3.9.2/artifacts/H3.9.2-STATUS.json"
        status = json.loads(status_path.read_text(encoding="utf-8"))
        self.assertFalse(status["benchmark_gate_passed"])
        self.assertFalse(status["architecture_gate_passed"])
        self.assertFalse(status["adjudication_review_surface"]["decision_ingestion_authorized"])
        self.assertEqual(158, status["adjudication_review_surface"]["combined_pending_case_count"])


if __name__ == "__main__":
    unittest.main()
