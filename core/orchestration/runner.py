"""Execute independent DAG nodes concurrently with bounded concurrency and truthful failure states."""
from __future__ import annotations
import asyncio
import inspect
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
                async def dispatch():
                    async with sem:
                        if inspect.iscoroutinefunction(handler):
                            return await handler(request)
                        output = await asyncio.to_thread(handler, request)
                        if inspect.isawaitable(output):
                            return await output
                        return output
                try:
                    # Deadline includes admission to the per-case concurrency budget.
                    result = await asyncio.wait_for(dispatch(), node["timeout_ms"] / 1000)
                    validate_result(request, result)
                except asyncio.TimeoutError:
                    result = _result(request, "UNAVAILABLE", "ENGINE_TIMEOUT")
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
