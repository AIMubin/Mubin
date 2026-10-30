"""B02-C.5: bind a CasePlan to its result *within the same trusted run*.

This is not source attestation, an independent runtime witness, P0 inference
validation, scholarly analysis, or a replacement for the Evidence Graph.
No raw node inputs, source text or paths are placed in the exported audit.
"""
from __future__ import annotations

import hashlib
import hmac
import json

from core.orchestration.plan import CasePlan
from core.orchestration.runner import run_case
from core.orchestration.cross_engine_chain import _node_index

CONTRACT = "mubin-plan-bound-execution/1.0"
MAX_AUDIT_NODES = 64


class PlanBindingError(ValueError):
    """Safe fixed diagnostic code only."""


def _key(value):
    if type(value) is not bytes or len(value) < 32:
        raise PlanBindingError("PLAN_BOUND_OPERATOR_KEY_REQUIRED")
    return value


def _canonical(value):
    try:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, RecursionError, UnicodeError) as exc:
        raise PlanBindingError("PLAN_BOUND_JSON_INVALID") from exc
    if len(raw) > 4 * 1024 * 1024:
        raise PlanBindingError("PLAN_BOUND_INPUT_TOO_LARGE")
    return raw


def _mac(key, purpose, payload):
    return hmac.new(key, purpose.encode("ascii") + b"\0" + _canonical(payload),
                    hashlib.sha256).hexdigest()


def _plan_canonical(plan):
    if not isinstance(plan, CasePlan):
        raise PlanBindingError("PLAN_BOUND_PLAN_REQUIRED")
    try:
        ordered = plan.ordered()
    except (ValueError, TypeError, KeyError) as exc:
        raise PlanBindingError("PLAN_BOUND_PLAN_INVALID") from exc
    return ordered, {
        "case_id": plan.case_id,
        "methodology_profile_id": plan.methodology_profile_id,
        "source_snapshot_ids": list(plan.source_snapshot_ids),
        "max_parallel": plan.max_parallel,
        "nodes": ordered,
    }


def _build(plan, receipt, audit_key):
    """Compute operator-keyed commitments, never expose plain private inputs."""
    k = _key(audit_key)
    ordered, canonical = _plan_canonical(plan)
    if type(receipt) is not dict:
        raise PlanBindingError("PLAN_BOUND_RECEIPT_INVALID")
    try:
        received = _node_index(receipt)
    except (ValueError, KeyError, TypeError, RecursionError) as exc:
        raise PlanBindingError("PLAN_BOUND_RECEIPT_INVALID") from exc
    if (receipt.get("case_id") != plan.case_id
            or receipt.get("methodology_profile_id") != plan.methodology_profile_id
            or receipt.get("source_snapshot_ids") != list(plan.source_snapshot_ids)
            or len(received) != len(ordered)
            or any(n["id"] not in received for n in ordered)):
        raise PlanBindingError("PLAN_BOUND_PLAN_RESULT_MISMATCH")

    summaries = []
    dag = []
    for node in ordered:
        result = received[node["id"]]
        if result["engine"] != node["engine"]:
            raise PlanBindingError("PLAN_BOUND_ENGINE_MISMATCH")
        for dep in node["depends_on"]:
            dag.append({"from_node": dep, "to_node": node["id"],
                        "relation": "DECLARED_DIRECT_DEPENDENCY_ONLY"})
        summaries.append({
            "node_id": node["id"],
            "engine": node["engine"],
            "operation": node["operation"],
            "depends_on": list(node["depends_on"]),
            "result_status": result["status"],
            "evidence_ref_count": len(result["evidence_refs"]),
            "input_hmac_sha256": _mac(k, "plan-node-input-v1", {
                "case_id": plan.case_id, "node_id": node["id"],
                "operation": node["operation"], "inputs": node["inputs"],
            }),
            "result_hmac_sha256": _mac(k, "engine-result-v1", result),
        })
    dag.sort(key=lambda x: (x["from_node"], x["to_node"]))
    summaries.sort(key=lambda x: x["node_id"])
    output = {
        "contract": CONTRACT,
        "case_id": plan.case_id,
        "status": "PLAN_AND_RESULT_BOUND_OPERATOR_LOCAL_ONLY",
        "plan_hmac_sha256": _mac(k, "case-plan-v1", canonical),
        "receipt_hmac_sha256": _mac(k, "case-result-v1", receipt),
        "node_count": len(summaries),
        "dependency_edge_count": len(dag),
        "nodes": summaries,
        "dependencies": dag,
        "original_operations_from_supplied_plan": True,
        "dependency_ids_from_supplied_plan": True,
        "operator_local_execution_attested": False,
        "external_runtime_authenticated": False,
        "upstream_payload_delivery_verified": False,
        "private_source_authenticated": False,
        "hadith_identity_verified": False,
        "scholarly_verified": False,
        "scientific_chain_established": False,
        "juristic_inference_allowed": False,
        "source_text_included": False,
    }
    return output


async def run_case_plan_bound(plan, registry, *, audit_key, store=None):
    """Run an actual plan and produce an attached, privacy-preserving receipt.

    Keep `audit_key` in the private operator vault (at least 32 random bytes).
    HMAC prevents simple low-entropy source-input hash guessing, but possession
    of a key alone is not external source authenticity or a signed attestation.
    """
    _key(audit_key)
    _plan_canonical(plan)
    receipt = await run_case(plan, registry, store=store)
    return {"runtime_receipt": receipt,
            "plan_bound_audit": _build(plan, receipt, audit_key)}


def verify_plan_bound_replay(plan, receipt, public_audit, *, audit_key):
    """Verify the exact submitted plan + receipt using trusted local key.

    Externally fabricated plan and result with a different key could also
    produce a internally consistent report; authenticity is not implied.
    """
    if type(public_audit) is not dict:
        return False
    try:
        expected = _build(plan, receipt, audit_key)
        if set(public_audit) != set(expected):
            return False
        if any(public_audit[k] != expected[k] for k in expected
               if k not in {"plan_hmac_sha256", "receipt_hmac_sha256"}):
            return False
        return (hmac.compare_digest(
                    public_audit["plan_hmac_sha256"], expected["plan_hmac_sha256"])
                and hmac.compare_digest(
                    public_audit["receipt_hmac_sha256"], expected["receipt_hmac_sha256"]))
    except (PlanBindingError, TypeError, ValueError, KeyError):
        return False
