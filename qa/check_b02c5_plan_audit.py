"""B02-C.5 public metadata integrity gate (NOT HMAC or private source verification).

The local operator key, original CasePlan and re-executed runtime receipt
are deliberately unavailable to CI. Never claim their authenticity here.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

CONTRACT = "mubin-plan-bound-execution/1.0"
FILENAME = "b02c5-plan-bound-audit-6-145-v1.json"
SHA = re.compile(r"^[0-9a-f]{64}$")
EXPECTED = {
    "b02c2.us1": ("usul", "bind_source_spans"),
    "b02c2.q1": ("quran", "lookup_verse"),
    "b02c2.t1": ("tafsir", "research_verse"),
    "b02c2.h1": ("hadith", "detect_tafsir_mentions"),
    "b02c2.u2": ("usul", "evaluate_proposition"),
    "b02c2.f1": ("fiqh", "prepare_case"),
}
BLOCKED_CLAIMS = (
    "operator_local_execution_attested",
    "external_runtime_authenticated",
    "upstream_payload_delivery_verified",
    "private_source_authenticated",
    "hadith_identity_verified",
    "scholarly_verified",
    "scientific_chain_established",
    "juristic_inference_allowed",
    "source_text_included",
)
FIELDS = {
    "contract", "case_id", "status", "plan_hmac_sha256", "receipt_hmac_sha256",
    "node_count", "dependency_edge_count", "nodes", "dependencies",
    "original_operations_from_supplied_plan",
    "dependency_ids_from_supplied_plan",
    *BLOCKED_CLAIMS,
}
NODE_FIELDS = {
    "node_id", "engine", "operation", "depends_on", "result_status",
    "evidence_ref_count", "input_hmac_sha256", "result_hmac_sha256",
}
EDGE_FIELDS = {"from_node", "to_node", "relation"}


class AuditError(ValueError):
    """Fixed non-sensitive validation code."""


def need(condition, code):
    if not condition:
        raise AuditError(code)


def is_mac(value):
    return type(value) is str and SHA.fullmatch(value) is not None


def validate_view(audit, kernel, evidence):
    need(type(audit) is dict and set(audit) == FIELDS
         and audit.get("contract") == CONTRACT
         and audit.get("status") == "PLAN_AND_RESULT_BOUND_OPERATOR_LOCAL_ONLY",
         "PLAN_AUDIT_CONTRACT_INVALID")
    need(audit.get("case_id") == kernel.get("case_id")
         and audit.get("node_count") == 6
         and audit.get("dependency_edge_count") == 5
         and audit.get("original_operations_from_supplied_plan") is True
         and audit.get("dependency_ids_from_supplied_plan") is True,
         "PLAN_AUDIT_CASE_OR_COUNTS_INVALID")
    need(all(audit.get(flag) is False for flag in BLOCKED_CLAIMS),
         "PLAN_AUDIT_FALSE_AUTHORITY_CLAIM")
    need(is_mac(audit.get("plan_hmac_sha256"))
         and is_mac(audit.get("receipt_hmac_sha256")),
         "PLAN_AUDIT_HMAC_FORMAT_INVALID")

    nodes, edges = audit.get("nodes"), audit.get("dependencies")
    need(type(nodes) is list and len(nodes) == 6
         and type(edges) is list and len(edges) == 5,
         "PLAN_AUDIT_TOPOLOGY_INVALID")
    need(type(kernel.get("nodes")) is list and len(kernel["nodes"]) == 6,
         "PLAN_AUDIT_BASELINE_INVALID")
    baseline = {}
    for item in kernel["nodes"]:
        need(type(item) is dict and type(item.get("result")) is dict
             and type(item.get("node_id")) is str
             and item["node_id"] not in baseline,
             "PLAN_AUDIT_BASELINE_INVALID")
        baseline[item["node_id"]] = item["result"]
    need(set(baseline) == set(EXPECTED), "PLAN_AUDIT_BASELINE_NODE_SET_INVALID")

    observed = {}
    for node in nodes:
        need(type(node) is dict and set(node) == NODE_FIELDS
             and type(node.get("node_id")) is str
             and node["node_id"] in EXPECTED
             and node["node_id"] not in observed
             and (node["engine"], node["operation"]) == EXPECTED[node["node_id"]],
             "PLAN_AUDIT_NODE_SHAPE_INVALID")
        ident = node["node_id"]
        old = baseline[ident]
        need(node["result_status"] == old["status"]
             and node["evidence_ref_count"] == len(old["evidence_refs"])
             and type(node["evidence_ref_count"]) is int
             and type(node["depends_on"]) is list
             and all(type(d) is str for d in node["depends_on"])
             and len(set(node["depends_on"])) == len(node["depends_on"])
             and is_mac(node["input_hmac_sha256"])
             and is_mac(node["result_hmac_sha256"]),
             "PLAN_AUDIT_RESULT_OR_HMAC_MISMATCH")
        observed[ident] = node
    need(set(observed) == set(EXPECTED) and
         [node["node_id"] for node in nodes] == sorted(EXPECTED),
         "PLAN_AUDIT_NODE_SET_OR_ORDER_INVALID")

    root = "b02c2.f1"
    expected_deps = set(EXPECTED) - {root}
    need(set(observed[root]["depends_on"]) == expected_deps
         and len(observed[root]["depends_on"]) == 5
         and all(not observed[n]["depends_on"] for n in expected_deps),
         "PLAN_AUDIT_DAG_INVALID")
    expected_edges = {
        (n, root, "DECLARED_DIRECT_DEPENDENCY_ONLY") for n in expected_deps
    }
    actual_edges = []
    for edge in edges:
        need(type(edge) is dict and set(edge) == EDGE_FIELDS
             and all(type(edge.get(k)) is str for k in EDGE_FIELDS),
             "PLAN_AUDIT_EDGE_INVALID")
        actual_edges.append((edge["from_node"], edge["to_node"], edge["relation"]))
    need(set(actual_edges) == expected_edges
         and len(set(actual_edges)) == len(actual_edges)
         and actual_edges == sorted(actual_edges),
         "PLAN_AUDIT_DAG_EDGE_MISMATCH")

    need(type(evidence) is dict
         and evidence.get("preserved_candidate", {}).get("selected") is False
         and evidence.get("strict_gate_v3", {}).get("verdict")
             == "REJECTED_ALL_CANDIDATES_UNDER_FULL_BAR",
         "PLAN_AUDIT_SELECTION_NOT_REJECTED")
    claim = evidence.get("b02c5_plan_bound_replay", {})
    need(type(claim) is dict and claim.get("audit_file") == FILENAME
         and claim.get("contract") == CONTRACT
         and claim.get("status") == audit["status"]
         and claim.get("node_count") == audit["node_count"]
         and claim.get("dependency_edge_count") == audit["dependency_edge_count"]
         and claim.get("plan_hmac_sha256") == audit["plan_hmac_sha256"]
         and claim.get("receipt_hmac_sha256") == audit["receipt_hmac_sha256"]
         and type(claim.get("boundaries")) is dict
         and all(claim["boundaries"].get(k) is False for k in (
             "scientific_chain_established", "scholarly_verified",
             "juristic_inference_allowed", "hadith_identity_verified",
             "private_source_authenticated")),
         "PLAN_AUDIT_HANDOFF_MISMATCH")

    raw = json.dumps(audit, ensure_ascii=False, sort_keys=True)
    need(re.search(r"[\u0600-\u06ff]|(?:[A-Za-z]:\\|/home/|/Users/)", raw) is None
         and len(raw.encode("utf-8")) <= 30000,
         "PLAN_AUDIT_SENSITIVE_OR_OVERSIZED")
    return {
        "nodes": 6, "declared_dag_edges": 5, "result_counts_consistent": True,
        "hmac_format_valid": True, "hmac_recomputed": False,
        "operator_key_accessed": False, "scholarly_verified": False,
        "scope": "PUBLISHED_METADATA_ONLY_NOT_A_PRIVATE_PLAN_REPLAY",
    }


def validate(root):
    folder = Path(root) / "research/b02b"
    audit = json.loads((folder / FILENAME).read_text(encoding="utf-8-sig"))
    kernel = json.loads((folder / "b02c2-kernel-receipt-6-145-v1.json").read_text(encoding="utf-8-sig"))
    evidence = json.loads((folder / "evidence-receipt.json").read_text(encoding="utf-8-sig"))
    return validate_view(audit, kernel, evidence)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--if-present", action="store_true")
    args = parser.parse_args()
    if args.if_present and not (
        Path(args.root) / "research/b02b" / FILENAME
    ).is_file():
        print("B02-C.5 report absent; synthetic regression tests still execute.")
        return 0
    try:
        result = validate(args.root)
    except (AuditError, OSError, ValueError, TypeError, KeyError, IndexError) as exc:
        print("B02C5 METADATA FAIL " +
              (str(exc) if isinstance(exc, AuditError) else "INVALID_INPUT"))
        return 1
    print("B02C5 METADATA VALID " + json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
