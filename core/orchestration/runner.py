"""Execute independent DAG nodes concurrently with bounded concurrency and truthful failure states."""
from __future__ import annotations
import asyncio
from concurrent.futures import ThreadPoolExecutor
import inspect
import threading
import time
import hashlib
from core.contracts import CONTRACT_VERSION, ContractError, validate_request, validate_result
from .plan import CasePlan


def _result(request, status, code):
    return {
        "contract_version": CONTRACT_VERSION, "request_id": request["request_id"],
        "engine": request["engine"], "engine_version": "kernel/0.1",
        "status": status, "findings": [], "evidence_refs": [],
        "uncertainties": [code], "errors": [],
        "provenance": {"snapshot_ids": list(request["source_snapshot_ids"])},
        "trace_id": request["request_id"],
    }


# One process-wide admission budget, not one budget per request or event loop.
# A sync handler cannot be forcibly cancelled by asyncio.wait_for. Its permit is
# retained by the *worker thread*, even after the waiting request times out.
_SYNC_WORKER_LIMIT = 8
_SYNC_WORKER_PERMITS = threading.BoundedSemaphore(_SYNC_WORKER_LIMIT)
_SYNC_EXECUTOR = ThreadPoolExecutor(
    max_workers=_SYNC_WORKER_LIMIT, thread_name_prefix="mubin-engine")


def _observe_completion(future):
    """Consume late adapter exceptions without logging potentially private data."""
    if not future.cancelled():
        try:
            future.exception()
        except BaseException:
            pass


async def _run_sync_handler(handler, request, lifecycle):
    """Bound synchronous adapter work across cases; timeout never implies a kill.

    No executor work is queued before a permit is available. The surrounding
    wait_for also bounds time spent waiting for a worker permit.
    """
    permit = _SYNC_WORKER_PERMITS
    while not permit.acquire(blocking=False):
        await asyncio.sleep(0.01)
    def invoke():
        try:
            return handler(request)
        finally:
            lifecycle["finished"] = True
            permit.release()
    try:
        future = asyncio.get_running_loop().run_in_executor(_SYNC_EXECUTOR, invoke)
    except BaseException:
        permit.release()
        raise
    lifecycle["submitted"] = True
    future.add_done_callback(_observe_completion)
    # Shield only protects worker bookkeeping. It does NOT let the timed-out
    # request wait for, cancel, or publish the late worker's eventual result.
    return await asyncio.shield(future)


async def run_case(plan, registry, store=None):
    """The five adapters are contracts, not MVE claims; each case has its own semaphore."""
    if not isinstance(plan, CasePlan):
        raise TypeError("PLAN_REQUIRED")
    ordered = plan.ordered()
    sem = asyncio.Semaphore(plan.max_parallel)
    tasks = {}

    async def run_node(node):
        began = time.perf_counter()
        if "_upstream" in node["inputs"]:
            raise ContractError("PLAN_UPSTREAM_SPOOFING")
        dependent = [await tasks[d] for d in node["depends_on"]]
        digest = hashlib.sha256((plan.case_id + ":" + node["id"]).encode("utf-8")).hexdigest()
        upstream = []
        for item in dependent:
            result = item["result"]
            upstream.append({
                "engine": result["engine"], "status": result["status"],
                "evidence_refs": list(result["evidence_refs"]),
                "synthetic": any(x.get("synthetic_fixture") is True or x.get("synthetic") is True
                                 for x in result["findings"]),
                "references": sorted({x["reference"] for x in result["findings"]
                                      if type(x.get("reference")) is str}),
            })
        inputs = dict(node["inputs"])
        if dependent:
            inputs["_upstream"] = upstream
        request = {
            "contract_version": CONTRACT_VERSION, "request_id": node["id"],
            "case_id": plan.case_id, "engine": node["engine"], "operation": node["operation"],
            "inputs": inputs, "methodology_profile_id": plan.methodology_profile_id,
            "source_snapshot_ids": list(plan.source_snapshot_ids),
            "limits": {"timeout_ms": node["timeout_ms"], "max_results": node["max_results"]},
            "idempotency_key": "idem." + digest,
        }
        validate_request(request)
        if any(x["result"]["status"] not in {"OK", "NO_MATCH"} for x in dependent):
            result = _result(request, "UNDETERMINED", "DEPENDENCY_NOT_OK")
        else:
            try:
                handler = registry.resolve(node["engine"], node["operation"])
                sync_lifecycle = {"submitted": False, "finished": False}
                async def dispatch():
                    async with sem:
                        if inspect.iscoroutinefunction(handler):
                            return await handler(request)
                        output = await _run_sync_handler(handler, request, sync_lifecycle)
                        if inspect.isawaitable(output):
                            return await output
                        return output
                try:
                    # Deadline includes admission to the per-case concurrency budget.
                    result = await asyncio.wait_for(dispatch(), node["timeout_ms"] / 1000)
                    validate_result(request, result)
                except asyncio.TimeoutError:
                    result = _result(request, "UNAVAILABLE", "ENGINE_TIMEOUT")
                    if sync_lifecycle["submitted"] and not sync_lifecycle["finished"]:
                        result["uncertainties"].append("SYNC_WORKER_TERMINATION_NOT_CONFIRMED")
                except ContractError:
                    result = _result(request, "REJECTED", "ENGINE_CONTRACT_REJECTED")
                except Exception:
                    result = _result(request, "ERROR", "ENGINE_EXECUTION_FAILED")
            except ContractError as exc:
                is_invalid_operation = str(exc) == "OPERATION_UNSUPPORTED"
                result = _result(request, "REJECTED" if is_invalid_operation else "UNAVAILABLE",
                                 "OPERATION_UNSUPPORTED" if is_invalid_operation else "ENGINE_NOT_REGISTERED")
        return {"node_id": node["id"], "result": result,
                "duration_ms": round((time.perf_counter() - began) * 1000, 3)}

    for node in ordered:
        tasks[node["id"]] = asyncio.create_task(run_node(node))
    try:
        entries = await asyncio.gather(*(tasks[node["id"]] for node in ordered))
    except BaseException:
        for task in tasks.values():
            task.cancel()
        await asyncio.gather(*tasks.values(), return_exceptions=True)
        raise
    statuses = {x["result"]["status"] for x in entries}
    # PARTIAL is not an OK, and unavailable must never be misreported as NO_MATCH.
    if len(statuses) == 1 and next(iter(statuses)) in {"OK", "NO_MATCH", "UNAVAILABLE", "REJECTED", "ERROR"}:
        status = next(iter(statuses))
    elif "OK" in statuses or "PARTIAL" in statuses:
        status = "PARTIAL"
    else:
        status = "UNDETERMINED"
    receipt = {"case_id": plan.case_id, "contract_version": CONTRACT_VERSION,
               "methodology_profile_id": plan.methodology_profile_id,
               "source_snapshot_ids": list(plan.source_snapshot_ids),
               "status": status, "nodes": entries, "synthetic_acceptance": False}
    if store is not None:
        store.save(plan.case_id, receipt)
    return receipt
