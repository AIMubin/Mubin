"""B02-A: private P0 structural validation -> explicitly non-authoritative, redacted graph.

The full P0 bundle MUST remain inside the operator vault. This module does not
replace P0, independently authenticate sources, or treat a digest as a signature.
Its public projection intentionally is NOT a P0 input: the P0 schema requires
verbatim excerpts, while this export contains only opaque handles and topology.
"""
from __future__ import annotations

import hashlib
import json

from core.contracts.types import CONTRACT_VERSION, ENGINE_NAMES
from core.inference.validator import COLLECTIONS, validate_bundle

PROJECTION_CONTRACT = "mubin-b02a-p0-projection/1.0"
_MAX_LINKS = 128
_MAX_PROJECTED_EDGES = 70000
_BASE_FIELDS = {"contract", "status", "p0_contract_version", "p0_structural_passed",
                "external_source_authenticated", "scholarly_verified",
                "projection_is_p0_bundle", "source_text_included",
                "private_bundle_sha256", "counts", "nodes", "edges",
                "engine_bindings", "graph_sha256", "diagnostics"}
_COLLECTION_TYPES = frozenset(COLLECTIONS)
_EDGE_TYPES = frozenset({
    "SOURCE_WITNESS", "SOURCES_METHODOLOGY", "SOURCES_RULE",
    "SOURCES_CLAIM", "METHOD_RULE", "METHOD_INFERENCE",
    "RULE_INFERENCE", "PREMISE_INFERENCE", "INFERENCE_CONCLUSION",
    "OBJECTION_TO_INFERENCE", "SOURCES_OBJECTION",
    "INFERENCE_PROOF", "CONCLUSION_PROOF", "METHOD_PROOF",
    "HISTORICAL_EVIDENCE", "HISTORICAL_BASIS",
    "COUNTERFACTUAL_CONTEXT",
})


class ProjectionError(ValueError):
    """Stable error code only; never echo source texts or local paths."""


def _digest(value):
    return hashlib.sha256(value).hexdigest()


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8", "strict")


def _hash_graph(nodes, edges, bindings):
    return _digest(_canonical({"nodes": nodes, "edges": edges,
                               "engine_bindings": bindings}))


def _rejected(count):
    return {
        "contract": PROJECTION_CONTRACT, "status": "P0_REJECTED",
        "p0_contract_version": "0.1.0", "p0_structural_passed": False,
        "external_source_authenticated": False, "scholarly_verified": False,
        "projection_is_p0_bundle": False, "source_text_included": False,
        "private_bundle_sha256": None,
        "counts": {k: 0 for k in COLLECTIONS}, "nodes": [], "edges": [],
        "engine_bindings": [], "graph_sha256": None,
        "diagnostics": {"error_count": min(count, 5001), "code": "P0_STRUCTURAL_REJECTED"},
    }


def _check_bindings(links, case_receipt, evidence_handles, bundle_hash):
    """Bind ONLY explicit references already in supplied engine runtime receipts.

    This checks submission-consistency, not external custody, source truth,
    identity of reports, or provenance of the supplied receipt itself.
    """
    if links is None:
        links = ()
    if type(links) not in (tuple, list) or len(links) > _MAX_LINKS:
        raise ProjectionError("LINKS_INVALID")
    if not links:
        return []
    if type(case_receipt) is not dict:
        raise ProjectionError("CASE_RECEIPT_REQUIRED")
    if (case_receipt.get("contract_version") != CONTRACT_VERSION
            or type(case_receipt.get("nodes")) is not list
            or len(case_receipt["nodes"]) > 64
            or type(case_receipt.get("source_snapshot_ids")) is not list):
        raise ProjectionError("CASE_RECEIPT_INVALID")
    node_receipts = {}
    for entry in case_receipt["nodes"]:
        if type(entry) is not dict or type(entry.get("node_id")) is not str:
            raise ProjectionError("CASE_RECEIPT_INVALID")
        result = entry.get("result")
        if (type(result) is not dict
                or result.get("request_id") != entry["node_id"]
                or result.get("contract_version") != CONTRACT_VERSION
                or result.get("engine") not in ENGINE_NAMES
                or result.get("status") not in ("OK", "PARTIAL")
                or type(result.get("evidence_refs")) is not list
                or type(result.get("provenance")) is not dict
                or result["provenance"].get("snapshot_ids") != case_receipt["source_snapshot_ids"]
                or entry["node_id"] in node_receipts):
            raise ProjectionError("CASE_RECEIPT_INVALID")
        node_receipts[entry["node_id"]] = result
    used = set()
    bindings = []
    for link in links:
        if type(link) is not dict or set(link) != {
                "node_id", "engine_evidence_ref", "p0_evidence_id"}:
            raise ProjectionError("LINK_SHAPE_INVALID")
        node_id, engine_ref, p0_id = (
            link["node_id"], link["engine_evidence_ref"], link["p0_evidence_id"])
        if (type(node_id) is not str or type(engine_ref) is not str
                or type(p0_id) is not str
                or node_id not in node_receipts
                or engine_ref not in node_receipts[node_id]["evidence_refs"]
                or p0_id not in evidence_handles):
            raise ProjectionError("LINK_NOT_ATTESTED_BY_SUPPLIED_DATA")
        key = (node_id, engine_ref, p0_id)
        if key in used:
            raise ProjectionError("LINK_DUPLICATE")
        used.add(key)
        bindings.append({
            "engine": node_receipts[node_id]["engine"],
            "receipt_handle": _digest((bundle_hash + "\0node\0" + node_id).encode()),
            "engine_evidence_handle": _digest((bundle_hash + "\0engine-ref\0" + engine_ref).encode()),
            "p0_evidence_handle": evidence_handles[p0_id],
            "scope": "MATCHED_SUBMITTED_RECEIPT_ONLY",
        })
    return sorted(bindings, key=lambda b: (
        b["receipt_handle"], b["engine_evidence_handle"], b["p0_evidence_handle"]))


def project_p0_bundle(bundle, *, case_receipt=None, links=()):
    """Check full private P0 in memory, then return a *metadata-only* projection.

    A P0-invalid input returns a redacted refusal. Bad or forged link mapping
    raises a stable ProjectionError so an operator cannot accidentally export
    a misleading receipt.
    """
    problems = validate_bundle(bundle)
    if problems:
        return _rejected(len(problems))
    # validate_bundle bounds cardinality, byte length and UTF-8 JSON encoding.
    raw = _canonical(bundle)
    bundle_hash = _digest(raw)
    handles = {
        kind: {
            entry["id"]: _digest((
                bundle_hash + "\0" + kind + "\0" + entry["id"]).encode("utf-8"))
            for entry in bundle[kind]
        }
        for kind in COLLECTIONS
    }
    nodes = sorted(
        ({"handle": handle, "kind": kind}
         for kind, items in handles.items() for handle in items.values()),
        key=lambda n: (n["kind"], n["handle"]),
    )
    edges = set()

    def link(source_kind, source, target_kind, target, relation):
        # P0 validator has already verified every source/target reference.
        edges.add((
            handles[source_kind][source], handles[target_kind][target], relation))

    for item in bundle["evidence"]:
        link("sources", item["source_id"], "evidence", item["id"], "SOURCE_WITNESS")
    for item in bundle["methodologies"]:
        for ev in item["source_evidence_ids"]:
            link("evidence", ev, "methodologies", item["id"], "SOURCES_METHODOLOGY")
    for item in bundle["rules"]:
        link("methodologies", item["methodology_id"], "rules", item["id"], "METHOD_RULE")
        for ev in item["source_evidence_ids"]:
            link("evidence", ev, "rules", item["id"], "SOURCES_RULE")
    for item in bundle["claims"]:
        for ev in item["evidence_ids"]:
            link("evidence", ev, "claims", item["id"], "SOURCES_CLAIM")
        if item.get("counterfactual_context"):
            hist = item["counterfactual_context"]["historical_availability_id"]
            link("historical_availability", hist, "claims", item["id"],
                 "COUNTERFACTUAL_CONTEXT")
    for item in bundle["inferences"]:
        link("methodologies", item["methodology_id"], "inferences", item["id"],
             "METHOD_INFERENCE")
        for rule in item["rule_ids"]:
            link("rules", rule, "inferences", item["id"], "RULE_INFERENCE")
        for premise in item["premise_claim_ids"]:
            link("claims", premise, "inferences", item["id"], "PREMISE_INFERENCE")
        link("inferences", item["id"], "claims", item["conclusion_claim_id"],
             "INFERENCE_CONCLUSION")
    for item in bundle["objections"]:
        link("objections", item["id"], "inferences", item["target_inference_id"],
             "OBJECTION_TO_INFERENCE")
        for ev in item["evidence_ids"]:
            link("evidence", ev, "objections", item["id"], "SOURCES_OBJECTION")
    for item in bundle["proofs"]:
        for inf in item["inference_ids"]:
            link("inferences", inf, "proofs", item["id"], "INFERENCE_PROOF")
        link("claims", item["conclusion_claim_id"], "proofs", item["id"],
             "CONCLUSION_PROOF")
        link("methodologies", item["methodology_id"], "proofs", item["id"],
             "METHOD_PROOF")
    for item in bundle["historical_availability"]:
        link("evidence", item["evidence_id"], "historical_availability", item["id"],
             "HISTORICAL_EVIDENCE")
        for ev in item["basis_evidence_ids"]:
            link("evidence", ev, "historical_availability", item["id"], "HISTORICAL_BASIS")
    if len(edges) > _MAX_PROJECTED_EDGES:
        raise ProjectionError("PROJECTION_EDGE_LIMIT_EXCEEDED")
    redacted_edges = [
        {"from": a, "to": b, "relation": relation}
        for a, b, relation in sorted(edges)
    ]
    bindings = _check_bindings(links, case_receipt, handles["evidence"], bundle_hash)
    return {
        "contract": PROJECTION_CONTRACT, "status": "P0_STRUCTURALLY_VALID",
        "p0_contract_version": bundle["contract_version"], "p0_structural_passed": True,
        "external_source_authenticated": False, "scholarly_verified": False,
        "projection_is_p0_bundle": False, "source_text_included": False,
        "private_bundle_sha256": bundle_hash,
        "counts": {kind: len(bundle[kind]) for kind in COLLECTIONS},
        "nodes": nodes, "edges": redacted_edges, "engine_bindings": bindings,
        "graph_sha256": _hash_graph(nodes, redacted_edges, bindings),
        "diagnostics": {"error_count": 0, "code": "STRUCTURE_ONLY"},
    }


def verify_redacted_projection(view):
    """Check redacted graph integrity, NOT whether it came from an actual vault.

    A malicious party can forge both projection and hash. A trusted local
    verifier must recompute against the held-private bundle before attestation.
    """
    if type(view) is not dict or set(view) != _BASE_FIELDS:
        return False
    if (view.get("contract") != PROJECTION_CONTRACT or
            view.get("p0_contract_version") != "0.1.0" or
            view.get("external_source_authenticated") is not False or
            view.get("scholarly_verified") is not False or
            view.get("projection_is_p0_bundle") is not False or
            view.get("source_text_included") is not False):
        return False
    if view.get("status") == "P0_REJECTED":
        return (view.get("p0_structural_passed") is False
                and view.get("private_bundle_sha256") is None
                and view.get("graph_sha256") is None
                and view.get("nodes") == [] and view.get("edges") == []
                and view.get("engine_bindings") == []
                and type(view.get("counts")) is dict
                and set(view["counts"]) == _COLLECTION_TYPES
                and all(v == 0 for v in view["counts"].values())
                and type(view.get("diagnostics")) is dict
                and view["diagnostics"].get("code") == "P0_STRUCTURAL_REJECTED"
                and type(view["diagnostics"].get("error_count")) is int
                and view["diagnostics"]["error_count"] >= 1)
    if (view.get("status") != "P0_STRUCTURALLY_VALID" or
            view.get("p0_structural_passed") is not True or
            type(view.get("private_bundle_sha256")) is not str or
            len(view["private_bundle_sha256"]) != 64 or
            type(view.get("graph_sha256")) is not str or
            len(view["graph_sha256"]) != 64):
        return False
    counts, nodes, edges, bindings = (
        view.get("counts"), view.get("nodes"), view.get("edges"),
        view.get("engine_bindings"))
    if (type(counts) is not dict or set(counts) != _COLLECTION_TYPES
            or any(type(v) is not int or v < 0 for v in counts.values())
            or type(nodes) is not list or len(nodes) > 5000
            or type(edges) is not list or len(edges) > 70000
            or type(bindings) is not list or len(bindings) > _MAX_LINKS):
        return False
    node_ids = {}
    for item in nodes:
        if (type(item) is not dict or set(item) != {"handle", "kind"}
                or item["kind"] not in _COLLECTION_TYPES
                or type(item["handle"]) is not str or len(item["handle"]) != 64
                or item["handle"] in node_ids):
            return False
        node_ids[item["handle"]] = item["kind"]
    if len(nodes) != sum(counts.values()):
        return False
    if any(sum(n["kind"] == kind for n in nodes) != number
           for kind, number in counts.items()):
        return False
    seen_edges = set()
    for item in edges:
        if (type(item) is not dict or set(item) != {"from", "to", "relation"}
                or type(item["from"]) is not str or type(item["to"]) is not str
                or item["from"] not in node_ids or item["to"] not in node_ids
                or item["relation"] not in _EDGE_TYPES):
            return False
        key = (item["from"], item["to"], item["relation"])
        if key in seen_edges:
            return False
        seen_edges.add(key)
    for item in bindings:
        if (type(item) is not dict or set(item) != {
                "engine", "receipt_handle", "engine_evidence_handle",
                "p0_evidence_handle", "scope"}
                or item["engine"] not in ENGINE_NAMES
                or item["scope"] != "MATCHED_SUBMITTED_RECEIPT_ONLY"
                or item["p0_evidence_handle"] not in node_ids
                or node_ids[item["p0_evidence_handle"]] != "evidence"
                or any(type(item[k]) is not str or len(item[k]) != 64
                       for k in ("receipt_handle", "engine_evidence_handle"))):
            return False
    return (_hash_graph(nodes, edges, bindings) == view["graph_sha256"]
            and view.get("diagnostics") == {"error_count": 0, "code": "STRUCTURE_ONLY"})


def verify_private_projection(bundle, public_view, *, case_receipt=None, links=()):
    """Vault-side replay: compare a redacted receipt against the exact private P0.

    This is meaningful only when the caller already trusts its local input
    bundle and custody. It is neither scholarly approval nor source authentication.
    """
    if not verify_redacted_projection(public_view) or public_view["status"] != "P0_STRUCTURALLY_VALID":
        return False
    try:
        rebuilt = project_p0_bundle(bundle, case_receipt=case_receipt, links=links)
    except (ProjectionError, TypeError, ValueError, UnicodeError, RecursionError):
        return False
    return rebuilt == public_view
