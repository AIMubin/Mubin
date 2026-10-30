"""B02-C.5: adversarial public-audit metadata integrity tests, no private key."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import unittest

from qa.check_b02c5_plan_audit import AuditError, validate, validate_view

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "research/b02b"


def published():
    return tuple(json.loads((DIR / name).read_text(encoding="utf-8-sig"))
                 for name in (
                     "b02c5-plan-bound-audit-6-145-v1.json",
                     "b02c2-kernel-receipt-6-145-v1.json",
                     "evidence-receipt.json"))


class PlanAuditMetadataTests(unittest.TestCase):
    def test_real_public_audit_consistent_no_private_hmac_claim(self):
        result = validate(ROOT)
        self.assertEqual(result["nodes"], 6)
        self.assertEqual(result["declared_dag_edges"], 5)
        self.assertFalse(result["hmac_recomputed"])
        self.assertFalse(result["operator_key_accessed"])
        self.assertFalse(result["scholarly_verified"])

    def check(self, modifier, label):
        data = [copy.deepcopy(x) for x in published()]
        modifier(*data)
        with self.assertRaisesRegex(AuditError, label):
            validate_view(*data)

    def test_one_missing_node_rejected(self):
        self.check(lambda a,k,e: a["nodes"].pop(), "PLAN_AUDIT_TOPOLOGY_INVALID")

    def test_changed_engine_operation_rejected(self):
        self.check(lambda a,k,e: a["nodes"][0].update(
            operation="issue_fatwa"), "PLAN_AUDIT_NODE_SHAPE_INVALID")

    def test_changed_fiqh_status_rejected(self):
        self.check(lambda a,k,e: a["nodes"][0].update(
            result_status="OK"), "PLAN_AUDIT_RESULT_OR_HMAC_MISMATCH")

    def test_one_forged_input_hmac_rejected(self):
        self.check(lambda a,k,e: a["nodes"][0].update(
            input_hmac_sha256="not-a-sha"), "PLAN_AUDIT_RESULT_OR_HMAC_MISMATCH")

    def test_replaced_dependent_hop_rejected(self):
        self.check(lambda a,k,e: a["dependencies"][0].update(
            from_node="b02c2.f1"), "PLAN_AUDIT_DAG_EDGE_MISMATCH")

    def test_hidden_upstream_dependency_rejected(self):
        def modify(a,k,e):
            for n in a["nodes"]:
                if n["node_id"]=="b02c2.q1":
                    n["depends_on"].append("b02c2.t1")
        self.check(modify, "PLAN_AUDIT_DAG_INVALID")

    def test_duplicate_dag_edge_rejected(self):
        self.check(lambda a,k,e: a["dependencies"][1].update(
            a["dependencies"][0]), "PLAN_AUDIT_DAG_EDGE_MISMATCH")

    def test_scholarly_claim_rejected(self):
        self.check(lambda a,k,e: a.update(scholarly_verified=True),
                   "PLAN_AUDIT_FALSE_AUTHORITY_CLAIM")

    def test_altered_operator_key_commitment_rejected(self):
        self.check(lambda a,k,e: a.update(plan_hmac_sha256="1"*64),
                   "PLAN_AUDIT_HANDOFF_MISMATCH")

    def test_synthetic_new_receipt_does_not_match_old_claim(self):
        self.check(lambda a,k,e: a.update(receipt_hmac_sha256="2"*64),
                   "PLAN_AUDIT_HANDOFF_MISMATCH")

    def test_selection_promotion_rejected(self):
        self.check(lambda a,k,e:
                   e["preserved_candidate"].update(selected=True),
                   "PLAN_AUDIT_SELECTION_NOT_REJECTED")

    def test_private_text_cannot_leak_in_metadata(self):
        self.check(lambda a,k,e:
                   a["nodes"][0].update(secret="مقتطف من المصدر"),
                   "PLAN_AUDIT_NODE_SHAPE_INVALID")

    def test_claim_missing_binding_refused(self):
        self.check(lambda a,k,e:
                   e["b02c5_plan_bound_replay"].update(audit_file="wrong.json"),
                   "PLAN_AUDIT_HANDOFF_MISMATCH")


if __name__ == "__main__":
    unittest.main()
