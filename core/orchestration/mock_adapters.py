"""Explicitly synthetic test adapters; NEVER count as a real engine/MVE."""
from __future__ import annotations
import asyncio
from core.contracts import CONTRACT_VERSION, ENGINE_NAMES, EngineRegistry


def synthetic_registry(*, delay_ms=0, statuses=None, tracker=None):
    registry = EngineRegistry()
    statuses = statuses or {}
    for engine in sorted(ENGINE_NAMES):
        async def handler(req, _engine=engine):
            if tracker is not None:
                tracker["active"] = tracker.get("active", 0) + 1
                tracker["peak"] = max(tracker.get("peak", 0), tracker["active"])
            try:
                await asyncio.sleep(delay_ms / 1000)
                status = statuses.get(_engine, "OK")
                return {
                    "contract_version": CONTRACT_VERSION, "request_id": req["request_id"],
                    "engine": req["engine"], "engine_version": "synthetic/0.1",
                    "status": status,
                    "findings": ([{"kind": "SYNTHETIC_FIXTURE", "ref": "test." + _engine, "synthetic": True}]
                                 if status in {"OK", "PARTIAL"} else []),
                    "evidence_refs": [], "uncertainties": (["SYNTHETIC_PARTIAL"] if status == "PARTIAL" else []),
                    "errors": [], "provenance": {"snapshot_ids": list(req["source_snapshot_ids"])},
                    "trace_id": req["request_id"],
                }
            finally:
                if tracker is not None:
                    tracker["active"] -= 1
        registry.register(engine, {"test_lookup"}, handler)
    return registry
