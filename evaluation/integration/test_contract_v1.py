"""MUBIN-SYS-A01 contract, DAG, isolation and honest Fiqh-scaffold regressions."""
from __future__ import annotations
import asyncio
import json
import threading
import unittest
from unittest.mock import patch
from pathlib import Path
from core.contracts import CONTRACT_VERSION, ContractError, EngineRegistry, validate_request, validate_result
from core.orchestration import CasePlan, PlanError, run_case, InMemoryCaseStore
from core.orchestration import runner as kernel_runner
from core.orchestration.mock_adapters import synthetic_registry
from engines.fiqh.models import FiqhCase, JuristicOpinion
from engines.fiqh.contracts import prepare_research

ROOT = Path(__file__).resolve().parents[2]


def node(id, engine, deps=None, timeout=500, inputs=None):
    return {"id": id, "engine": engine, "operation": "test_lookup", "inputs": inputs or {},
            "depends_on": deps or [], "timeout_ms": timeout, "max_results": 3}


def plan(*nodes, case="case.001", parallel=4):
    return CasePlan(case, "profile.research", ("snap.001",), tuple(nodes), parallel)


class ContractTests(unittest.TestCase):
    def test_schema_and_runtime_agree(self):
        from jsonschema import Draft202012Validator
        q = node("req.001", "quran")
        req = {"contract_version": CONTRACT_VERSION, "request_id": q["id"],
               "case_id": "case.001", "engine": "quran", "operation": q["operation"],
               "inputs": {}, "methodology_profile_id": "profile.research",
               "source_snapshot_ids": ["snap.001"], "limits": {"timeout_ms": 500, "max_results": 3},
               "idempotency_key": "case.001:req.001"}
        schema = json.loads((ROOT / "schemas/engine-request-v1.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        self.assertFalse(list(Draft202012Validator(schema).iter_errors(req)))
        self.assertIs(validate_request(req), req)
        result = {"contract_version": CONTRACT_VERSION, "request_id": "req.001",
                  "engine": "quran", "engine_version": "synthetic/0.1", "status": "OK",
                  "findings": [{"kind": "SYNTHETIC_FIXTURE"}], "evidence_refs": [],
                  "uncertainties": [], "errors": [], "provenance": {"snapshot_ids": ["snap.001"]},
                  "trace_id": "req.001"}
        result_schema = json.loads((ROOT / "schemas/engine-result-v1.schema.json").read_text())
        Draft202012Validator.check_schema(result_schema)
        self.assertFalse(list(Draft202012Validator(result_schema).iter_errors(result)))
        validate_result(req, result)
        result["provenance"]["snapshot_ids"] = ["snap.wrong"]
        with self.assertRaises(ContractError):
            validate_result(req, result)

    def test_bool_limits_rejected(self):
        req = {"contract_version": CONTRACT_VERSION, "request_id": "req.001", "case_id": "case.001",
               "engine": "fiqh", "operation": "test_lookup", "inputs": {},
               "methodology_profile_id": "profile.research", "source_snapshot_ids": [],
               "limits": {"timeout_ms": True, "max_results": 3}, "idempotency_key": "case.001:req.001"}
        with self.assertRaises(ContractError):
            validate_request(req)

    def test_input_normalization_rejects_duplicates(self):
        with self.assertRaises(PlanError):
            plan(node("req.001", "quran", inputs={"a": 1, "b": 2}),
                 node("req.002", "quran", inputs={"b": 2, "a": 1})).ordered()

    def test_non_json_inputs_refused(self):
        with self.assertRaises(PlanError):
            plan(node("req.001", "quran", inputs={"bad": object()})).ordered()

    def test_malformed_plan_fields_fail_closed(self):
        with self.assertRaisesRegex(PlanError, "PLAN_SNAPSHOTS_INVALID"):
            CasePlan("case.001", "profile.research", ("snap.001", []),
                     (node("req.001", "quran"),)).ordered()
        with self.assertRaisesRegex(PlanError, "PLAN_NODE_IDENTITY_INVALID"):
            plan(node("req.001", [])).ordered()
        with self.assertRaisesRegex(PlanError, "PLAN_DEPENDENCIES_INVALID"):
            plan(node("req.001", "quran", deps=[["req.002"]])).ordered()

    def test_unpaired_unicode_surrogates_are_rejected(self):
        with self.assertRaisesRegex(PlanError, "PLAN_INPUT_NOT_JSON"):
            plan(node("req.001", "quran", inputs={"text": "\ud800"})).ordered()
        req = {"contract_version": CONTRACT_VERSION, "request_id": "req.001",
               "case_id": "case.001", "engine": "quran", "operation": "test_lookup",
               "inputs": {"text": "\ud800"}, "methodology_profile_id": "profile.research",
               "source_snapshot_ids": ["snap.001"],
               "limits": {"timeout_ms": 500, "max_results": 3},
               "idempotency_key": "idem.001"}
        with self.assertRaisesRegex(ContractError, "REQUEST_INPUT_INVALID"):
            validate_request(req)

    def test_bad_envelope_types_raise_contract_errors(self):
        req = {"contract_version": CONTRACT_VERSION, "request_id": "req.001",
               "case_id": "case.001", "engine": "quran", "operation": "test_lookup",
               "inputs": {}, "methodology_profile_id": "profile.research",
               "source_snapshot_ids": ["snap.001"],
               "limits": {"timeout_ms": 500, "max_results": 3},
               "idempotency_key": "idem.001"}
        for bad in ([], {}, None):
            with self.subTest(engine=bad), self.assertRaisesRegex(ContractError, "ENGINE_UNKNOWN"):
                validate_request({**req, "engine": bad})
            with self.subTest(limits=bad), self.assertRaisesRegex(ContractError, "LIMITS_INVALID"):
                validate_request({**req, "limits": bad})
        result = {"contract_version": CONTRACT_VERSION, "request_id": "req.001",
                  "engine": "quran", "engine_version": "synthetic/0.1", "status": [],
                  "findings": [], "evidence_refs": [], "uncertainties": [], "errors": [],
                  "provenance": {"snapshot_ids": ["snap.001"]}, "trace_id": "req.001"}
        with self.assertRaisesRegex(ContractError, "RESULT_STATUS_INVALID"):
            validate_result(req, result)

    def test_upstream_override_rejected(self):
        with self.assertRaises(PlanError):
            plan(node("req.001", "fiqh", inputs={"_upstream": []})).ordered()

    def test_cycles_and_missing_dependencies(self):
        with self.assertRaises(PlanError):
            plan(node("req.001", "quran", ["req.002"]),
                 node("req.002", "tafsir", ["req.001"])).ordered()
        with self.assertRaises(PlanError):
            plan(node("req.001", "quran", ["req.404"])).ordered()

    def test_duplicate_nodes_rejected(self):
        with self.assertRaises(PlanError):
            plan(node("req.001", "quran"), node("req.001", "quran")).ordered()

    def test_mixed_fiqh_methodology_rejected(self):
        case = FiqhCase("case.001", "Synthetic legal research question", "method.001")
        opinion = JuristicOpinion("op.001", "source.001", "method.002")
        with self.assertRaises(ContractError):
            prepare_research(case, (opinion,), ("ev.001",))

    def test_fiqh_never_invents_authority(self):
        case = FiqhCase("case.001", "Synthetic legal research question", "method.001")
        self.assertEqual(prepare_research(case, ()).status, "UNDETERMINED")
        opinion = JuristicOpinion("op.001", "source.001", "method.001")
        finding = prepare_research(case, (opinion,), ("ev.001",))
        self.assertEqual(finding.status, "PARTIAL")
        self.assertEqual(finding.authority, "RESEARCH_ONLY")


class ExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_parallel_fanout(self):
        tracker = {}
        r = synthetic_registry(delay_ms=25, tracker=tracker)
        receipt = await run_case(plan(node("req.001", "quran"),
                                      node("req.002", "tafsir"),
                                      node("req.003", "hadith")), r)
        self.assertEqual(receipt["status"], "OK")
        self.assertGreaterEqual(tracker["peak"], 2)

    async def test_two_cases_without_global_lock(self):
        tracker = {}
        r = synthetic_registry(delay_ms=25, tracker=tracker)
        await asyncio.gather(
            run_case(plan(node("req.001", "quran"), case="case.001", parallel=1), r),
            run_case(plan(node("req.002", "quran"), case="case.002", parallel=1), r))
        self.assertGreaterEqual(tracker["peak"], 2)

    async def test_timeout_isolated(self):
        r = synthetic_registry(delay_ms=35)
        receipt = await run_case(plan(node("req.001", "quran", timeout=3),
                                      node("req.002", "hadith", timeout=120)), r)
        self.assertEqual(receipt["status"], "PARTIAL")
        byid = {x["node_id"]: x["result"]["status"] for x in receipt["nodes"]}
        self.assertEqual(byid["req.001"], "UNAVAILABLE")
        self.assertEqual(byid["req.002"], "OK")

    async def test_sync_timeout_does_not_claim_worker_was_killed(self):
        started, release, finished = (threading.Event() for _ in range(3))
        registry = EngineRegistry()
        def stalled(req):
            started.set()
            try:
                release.wait(3)
            finally:
                finished.set()
            raise RuntimeError("PRIVATE_LATE_FAILURE_MUST_NOT_LEAK")
        registry.register("quran", ["test_lookup"], stalled)
        try:
            case_task = asyncio.create_task(
                run_case(plan(node("req.001", "quran", timeout=150)), registry))
            self.assertTrue(await asyncio.to_thread(started.wait, 2))
            receipt = await case_task
            self.assertEqual(receipt["status"], "UNAVAILABLE")
            result = receipt["nodes"][0]["result"]
            self.assertEqual(result["status"], "UNAVAILABLE")
            self.assertIn("ENGINE_TIMEOUT", result["uncertainties"])
            self.assertIn("SYNC_WORKER_TERMINATION_NOT_CONFIRMED",
                          result["uncertainties"])
            self.assertFalse(finished.is_set())
            self.assertNotIn("PRIVATE_LATE_FAILURE", str(receipt))
        finally:
            release.set()
            self.assertTrue(await asyncio.to_thread(finished.wait, 2))
            await asyncio.sleep(0.03)

    async def test_timed_out_sync_worker_keeps_admission_permit(self):
        started, release, finished, invoked = (threading.Event() for _ in range(4))
        blocked = EngineRegistry()
        quick = EngineRegistry()
        def stalled(req):
            started.set()
            try:
                release.wait(3)
            finally:
                finished.set()
            return None
        def would_run(req):
            invoked.set()
            return None
        blocked.register("quran", ["test_lookup"], stalled)
        quick.register("hadith", ["test_lookup"], would_run)
        # Only for this test: cap the process-wide worker budget to one.
        # The worker captures its permit, so teardown cannot leak a lease.
        with patch.object(kernel_runner, "_SYNC_WORKER_PERMITS",
                          threading.BoundedSemaphore(1)):
            try:
                task = asyncio.create_task(run_case(
                    plan(node("req.001", "quran", timeout=150)), blocked))
                self.assertTrue(await asyncio.to_thread(started.wait, 2))
                first = await task
                self.assertEqual(first["status"], "UNAVAILABLE")
                denied = await run_case(
                    plan(node("req.002", "hadith", timeout=40),
                         case="case.002"), quick)
                self.assertEqual(denied["status"], "UNAVAILABLE")
                self.assertEqual(denied["nodes"][0]["result"]["uncertainties"],
                                 ["ENGINE_TIMEOUT"])
                self.assertFalse(invoked.is_set())
            finally:
                release.set()
                self.assertTrue(await asyncio.to_thread(finished.wait, 2))
                await asyncio.sleep(0.03)
            # The old worker has now released its admission slot; the same
            # handler may be invoked, proving that permits are not leaked.
            resumed = await run_case(
                plan(node("req.003", "hadith", timeout=300),
                     case="case.003"), quick)
            self.assertTrue(invoked.is_set())
            self.assertEqual(resumed["status"], "REJECTED")

    async def test_failure_blocks_only_dependents(self):
        r = synthetic_registry(statuses={"quran": "UNAVAILABLE"})
        receipt = await run_case(plan(node("req.001", "quran"),
                                      node("req.002", "tafsir", ["req.001"]),
                                      node("req.003", "hadith")), r)
        byid = {x["node_id"]: x["result"]["status"] for x in receipt["nodes"]}
        self.assertEqual(byid, {"req.001": "UNAVAILABLE", "req.002": "UNDETERMINED", "req.003": "OK"})

    async def test_no_match_is_not_unavailable(self):
        r = synthetic_registry(statuses={"quran": "NO_MATCH", "hadith": "UNAVAILABLE"})
        receipt = await run_case(plan(node("req.001", "quran"), node("req.002", "hadith")), r)
        self.assertEqual([x["result"]["status"] for x in receipt["nodes"]], ["NO_MATCH", "UNAVAILABLE"])

    async def test_queue_waiting_counts_against_deadline(self):
        r = synthetic_registry(delay_ms=40)
        receipt = await run_case(plan(node("req.001", "quran", timeout=100),
                                      node("req.002", "tafsir", timeout=5), parallel=1), r)
        byid = {x["node_id"]: x["result"]["status"] for x in receipt["nodes"]}
        self.assertEqual(byid, {"req.001": "OK", "req.002": "UNAVAILABLE"})

    async def test_all_unavailable_not_false_partial(self):
        r = synthetic_registry(statuses={"quran": "UNAVAILABLE"})
        receipt = await run_case(plan(node("req.001", "quran")), r)
        self.assertEqual(receipt["status"], "UNAVAILABLE")

    async def test_unsupported_operation_not_absent_engine(self):
        registry = synthetic_registry()
        n = node("req.001", "quran")
        n["operation"] = "unsupported"
        receipt = await run_case(plan(n), registry)
        self.assertEqual(receipt["nodes"][0]["result"]["status"], "REJECTED")

    async def test_exception_does_not_expose_text(self):
        reg = EngineRegistry()
        async def broken(req):
            raise RuntimeError("PRIVATE_SOURCE_CONTENT_SHOULD_NEVER_LEAK")
        reg.register("quran", ["test_lookup"], broken)
        receipt = await run_case(plan(node("req.001", "quran")), reg)
        self.assertEqual(receipt["status"], "ERROR")
        self.assertNotIn("PRIVATE_SOURCE_CONTENT", str(receipt))

    async def test_store_defensive_copy(self):
        store = InMemoryCaseStore()
        await run_case(plan(node("req.001", "quran")), synthetic_registry(), store)
        first = store.get("case.001")
        first["status"] = "UNAUTHORIZED"
        self.assertEqual(store.get("case.001")["status"], "OK")

    async def test_unregistered_adapter_is_explicit(self):
        receipt = await run_case(plan(node("req.001", "usul")), EngineRegistry())
        self.assertEqual(receipt["nodes"][0]["result"]["status"], "UNAVAILABLE")

    async def test_adapter_wrong_snapshots_rejected(self):
        reg = EngineRegistry()
        async def bad(req):
            result = {"contract_version": CONTRACT_VERSION, "request_id": req["request_id"],
                      "engine": "quran", "engine_version": "bad/0.1", "status": "OK",
                      "findings": [{"kind": "candidate"}], "evidence_refs": [],
                      "uncertainties": [], "errors": [], "provenance": {"snapshot_ids": ["snap.fake"]},
                      "trace_id": req["request_id"]}
            return result
        reg.register("quran", ["test_lookup"], bad)
        receipt = await run_case(plan(node("req.001", "quran")), reg)
        self.assertEqual(receipt["nodes"][0]["result"]["status"], "REJECTED")


if __name__ == "__main__":
    unittest.main()
