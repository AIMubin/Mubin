"""B02-C.5: plan/result binding doesn't confer source or scholarly authority."""
from __future__ import annotations

import copy
import json
import unittest

from core.orchestration.plan import CasePlan
from core.orchestration.mock_adapters import synthetic_registry
from core.orchestration.plan_bound_provenance import (
    PlanBindingError, run_case_plan_bound, verify_plan_bound_replay,
)

KEY = b"private_local_operator_audit_key_len_64_bytes_simulated_only"
OTHER_KEY = b"other_local_operator_key_has_sufficient_entropy_for_test"


def task(id, engine, *, inputs=None, depends_on=None):
    return {"id": id, "engine": engine, "operation": "test_lookup",
            "inputs": inputs or {}, "depends_on": depends_on or [],
            "timeout_ms": 2000, "max_results": 10}


def plan(*, secret=None, dependency=True, operation="test_lookup"):
    left = task("node.q.001", "quran", inputs={
        "private_note": secret or "private_value_does_not_appear_in_audit"})
    right = task("node.f.001", "fiqh",
                 depends_on=["node.q.001"] if dependency else [])
    right["operation"] = operation
    return CasePlan("case.synthetic.001", "method.synthetic.001",
                    ("snap.synthetic.001",), (left, right))


class PlanBoundTests(unittest.IsolatedAsyncioTestCase):
    async def _run(self, p=None, registry=None):
        p = p or plan()
        return p, await run_case_plan_bound(
            p, registry or synthetic_registry(), audit_key=KEY)

    async def test_live_execution_yields_precise_DAG_but_not_scholarship(self):
        p, out = await self._run()
        audit, receipt = out["plan_bound_audit"], out["runtime_receipt"]
        self.assertEqual(receipt["status"], "OK")
        self.assertEqual(audit["node_count"], 2)
        self.assertEqual(audit["dependency_edge_count"], 1)
        self.assertEqual(audit["dependencies"], [{
            "from_node":"node.q.001", "to_node":"node.f.001",
            "relation":"DECLARED_DIRECT_DEPENDENCY_ONLY"}])
        self.assertEqual(audit["status"], "PLAN_AND_RESULT_BOUND_OPERATOR_LOCAL_ONLY")
        self.assertTrue(verify_plan_bound_replay(
            p, receipt, audit, audit_key=KEY))
        self.assertFalse(audit["operator_local_execution_attested"])
        self.assertFalse(audit["scientific_chain_established"])
        self.assertFalse(audit["scholarly_verified"])
        self.assertFalse(audit["juristic_inference_allowed"])

    async def test_plain_private_node_input_not_in_public_audit(self):
        secret = "PRIVATE_C:/DEVELOPMENT/LOCAL_VAULT_hadith_text"
        p, out = await self._run(plan(secret=secret))
        public = json.dumps(out["plan_bound_audit"], ensure_ascii=False)
        self.assertNotIn(secret, public)
        self.assertNotIn("private_value_does_not_appear_in_audit", public)
        self.assertIn("input_hmac_sha256", public)
        self.assertTrue(verify_plan_bound_replay(
            p, out["runtime_receipt"], out["plan_bound_audit"], audit_key=KEY))

    async def test_changed_node_inputs_invalidate_exact_replay(self):
        p, out = await self._run()
        changed = plan(secret="mutated")
        self.assertFalse(verify_plan_bound_replay(
            changed, out["runtime_receipt"], out["plan_bound_audit"],
            audit_key=KEY))

    async def test_removed_dependency_invalidates_replay(self):
        p, out = await self._run()
        self.assertFalse(verify_plan_bound_replay(
            plan(dependency=False), out["runtime_receipt"],
            out["plan_bound_audit"], audit_key=KEY))

    async def test_spoofed_operation_invalidates_replay(self):
        p, out = await self._run()
        changed = plan(operation="fake_operation")
        self.assertFalse(verify_plan_bound_replay(
            changed, out["runtime_receipt"], out["plan_bound_audit"], audit_key=KEY))

    async def test_tampered_result_cannot_replay(self):
        p, out = await self._run()
        tampered = copy.deepcopy(out["runtime_receipt"])
        tampered["nodes"][0]["result"]["status"] = "PARTIAL"
        self.assertFalse(verify_plan_bound_replay(
            p, tampered, out["plan_bound_audit"], audit_key=KEY))

    async def test_changed_plan_commitment_rejected(self):
        p, out = await self._run()
        changed = copy.deepcopy(out["plan_bound_audit"])
        changed["plan_hmac_sha256"] = "0"*64
        self.assertFalse(verify_plan_bound_replay(
            p, out["runtime_receipt"], changed, audit_key=KEY))

    async def test_wrong_key_never_verifies(self):
        p, out = await self._run()
        self.assertFalse(verify_plan_bound_replay(
            p, out["runtime_receipt"], out["plan_bound_audit"],
            audit_key=OTHER_KEY))

    async def test_missing_operator_key_refused(self):
        with self.assertRaisesRegex(PlanBindingError,
                                    "PLAN_BOUND_OPERATOR_KEY_REQUIRED"):
            await run_case_plan_bound(plan(), synthetic_registry(),
                                      audit_key=b"short")

    async def test_invalid_legacy_plan_or_cycle_refused(self):
        a=task("node.q.001","quran",depends_on=["node.f.001"])
        b=task("node.f.001","fiqh",depends_on=["node.q.001"])
        cyclic=CasePlan("case.synthetic.001","method.synthetic.001",
                        ("snap.synthetic.001",),(a,b))
        with self.assertRaisesRegex(PlanBindingError,"PLAN_BOUND_PLAN_INVALID"):
            await run_case_plan_bound(cyclic, synthetic_registry(), audit_key=KEY)

    async def test_dependency_partial_does_not_qualify(self):
        registry=synthetic_registry(statuses={"quran":"PARTIAL"})
        p, out=await self._run(registry=registry)
        self.assertEqual(out["runtime_receipt"]["status"], "PARTIAL")
        self.assertFalse(out["plan_bound_audit"]["scientific_chain_established"])
        self.assertEqual(
            next(x for x in out["plan_bound_audit"]["nodes"]
                 if x["engine"]=="fiqh")["result_status"],"UNDETERMINED")

    async def test_published_audit_cannot_accept_extra_scholarly_flag(self):
        p, out=await self._run()
        audit=copy.deepcopy(out["plan_bound_audit"])
        audit["scholarly_verified"]=True
        self.assertFalse(verify_plan_bound_replay(
            p,out["runtime_receipt"],audit,audit_key=KEY))

    async def test_provenance_result_identity_is_not_source_authenticity(self):
        p, out=await self._run()
        audit=out["plan_bound_audit"]
        for field in ("external_runtime_authenticated",
                      "upstream_payload_delivery_verified",
                      "private_source_authenticated",
                      "hadith_identity_verified",
                      "scholarly_verified","scientific_chain_established"):
            self.assertFalse(audit[field])

    async def test_output_cannot_include_unexpected_data_without_failure(self):
        p, out=await self._run()
        audit=copy.deepcopy(out["plan_bound_audit"])
        audit["local_raw_excerpt"]="should never be exported"
        self.assertFalse(verify_plan_bound_replay(
            p,out["runtime_receipt"],audit,audit_key=KEY))


if __name__ == "__main__":
    unittest.main()
