"""B02-C.3 read-only cross-engine evidence transfer audit.

P0 remains the only inference graph validator. This is NOT a new Evidence
Graph, a DAG attestation, source-authenticity verifier, or a scholarly engine.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from jsonschema import Draft202012Validator
from core.contracts.types import CONTRACT_VERSION, ENGINE_NAMES, identifier

VERSION = "mubin-cross-engine-chain-audit/1.0"
RELATIONS = {"EXACT_REF_RELAY", "CONTEXT_PROPOSAL", "SEMANTIC_PROPOSAL"}
RELAY = "OBSERVED_REFERENCE_RELAY_ONLY"
PROPOSAL = "UNVERIFIED_RESEARCH_PROPOSAL"


class ChainAuditError(ValueError):
    """Safe code, never private source data."""


def _encoded(obj):
    try:
        data = json.dumps(obj, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ChainAuditError("CHAIN_JSON_INVALID") from exc
    if len(data) > 2 * 1024 * 1024:
        raise ChainAuditError("CHAIN_TOO_LARGE")
    return data


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _hex(s):
    return type(s) is str and len(s) == 64 and all(c in "0123456789abcdef" for c in s)


def _node_index(receipt):
    if (type(receipt) is not dict
            or receipt.get("contract_version") != CONTRACT_VERSION
            or not identifier(receipt.get("case_id"))
            or receipt.get("synthetic_acceptance") is not False
            or type(receipt.get("source_snapshot_ids")) is not list
            or len(receipt["source_snapshot_ids"]) > 128
            or not all(identifier(s) for s in receipt["source_snapshot_ids"])
            or len(set(receipt["source_snapshot_ids"])) != len(receipt["source_snapshot_ids"])
            or type(receipt.get("nodes")) is not list
            or not 1 <= len(receipt["nodes"]) <= 64):
        raise ChainAuditError("CHAIN_CASE_INVALID")
    schema = json.loads((Path(__file__).resolve().parents[2] /
                         "schemas/engine-result-v1.schema.json").read_text(encoding="utf-8"))
    verifier = Draft202012Validator(schema)
    nodes = {}
    for entry in receipt["nodes"]:
        if (type(entry) is not dict or set(entry) != {"node_id", "result", "duration_ms"}
                or not identifier(entry["node_id"]) or entry["node_id"] in nodes
                or type(entry["result"]) is not dict):
            raise ChainAuditError("CHAIN_NODE_INVALID")
        result = entry["result"]
        if (list(verifier.iter_errors(result))
                or result["request_id"] != entry["node_id"]
                or result["trace_id"] != entry["node_id"]
                or result["provenance"]["snapshot_ids"] != receipt["source_snapshot_ids"]):
            raise ChainAuditError("CHAIN_NODE_CONTRACT_INVALID")
        nodes[entry["node_id"]] = result
    return nodes


def audit_cross_engine_chain(receipt, links):
    """Validate submitted reference topology; never promote proposed semantics.

    Every link is an explicit dict containing from_node, from_ref, to_node,
    to_ref, relation, assessment_sha256. SHA review references are only
    operator declarations; this module does not trust their content.
    """
    raw = _encoded(receipt)
    nodes = _node_index(receipt)
    if type(links) not in (list, tuple) or len(links) > 128:
        raise ChainAuditError("CHAIN_LINK_COUNT_INVALID")
    receipt_sha = _digest(raw)
    edges, used = [], set()
    for x in links:
        if (type(x) is not dict
                or set(x) != {"from_node", "from_ref", "to_node", "to_ref",
                              "relation", "assessment_sha256"}
                or not all(identifier(x[k]) for k in (
                    "from_node", "from_ref", "to_node", "to_ref"))
                or type(x["relation"]) is not str or x["relation"] not in RELATIONS
                or (x["assessment_sha256"] is not None and not _hex(x["assessment_sha256"]))):
            raise ChainAuditError("CHAIN_LINK_INVALID")
        if x["relation"] == "EXACT_REF_RELAY" and (
                x["from_ref"] != x["to_ref"] or x["assessment_sha256"] is not None):
            raise ChainAuditError("CHAIN_RELAY_NOT_EXACT")
        if x["relation"] == "SEMANTIC_PROPOSAL" and not _hex(x["assessment_sha256"]):
            raise ChainAuditError("CHAIN_REVIEW_DIGEST_REQUIRED")
        if x["relation"] == "CONTEXT_PROPOSAL" and x["assessment_sha256"] is not None:
            raise ChainAuditError("CHAIN_CONTEXT_HAS_ATTESTATION")
        key = (x["from_node"], x["to_node"], x["from_ref"], x["to_ref"], x["relation"])
        if key in used:
            raise ChainAuditError("CHAIN_DUPLICATE_LINK")
        used.add(key)
        a, b = nodes.get(x["from_node"]), nodes.get(x["to_node"])
        if (a is None or b is None or x["from_node"] == x["to_node"]
                or a["engine"] == b["engine"] or a["status"] != "OK"
                or b["status"] not in ("OK", "PARTIAL")
                or x["from_ref"] not in a["evidence_refs"]
                or x["to_ref"] not in b["evidence_refs"]):
            raise ChainAuditError("CHAIN_ENDPOINT_UNVERIFIED")
        handle = lambda s: _digest((receipt_sha + "\0ref\0" + s).encode("utf-8"))
        edges.append({
            "from_node": x["from_node"], "from_engine": a["engine"],
            "from_handle": handle(x["from_ref"]), "to_node": x["to_node"],
            "to_engine": b["engine"], "to_handle": handle(x["to_ref"]),
            "relation": x["relation"], "assessment_digest_declared": x["assessment_sha256"],
            "status": RELAY if x["relation"] == "EXACT_REF_RELAY" else PROPOSAL,
        })
    edges.sort(key=lambda e: (e["from_node"], e["to_node"], e["relation"],
                              e["from_handle"], e["to_handle"]))
    exact = sum(e["status"] == RELAY for e in edges)
    output = {
        "contract": VERSION, "case_id": receipt["case_id"],
        "receipt_sha256": receipt_sha, "status": "TRANSPORT_ONLY_INCOMPLETE",
        "node_count": len(nodes),
        "engine_count": len({r["engine"] for r in nodes.values()}),
        "links": edges,
        "counts": {"observed_reference_relays": exact,
                   "unverified_proposals": len(edges) - exact,
                   "qualified_semantic_links": 0},
        "source_text_included": False, "source_authenticated": False,
        "strict_selection_verified": False, "plan_dependencies_verified": False,
        "semantic_links_verified": False, "hadith_identity_verified": False,
        "opinion_attribution_verified": False, "juristic_inference_allowed": False,
        "scholarly_verified": False,
    }
    output["audit_sha256"] = _digest(_encoded(output))
    return output


def verify_redacted_chain_audit(view):
    """Metadata self-check, NOT an authenticity signature."""
    if type(view) is not dict:
        return False
    try:
        fields = {"contract", "case_id", "receipt_sha256", "status",
                  "node_count", "engine_count", "links", "counts", "audit_sha256"}
        flags = {"source_text_included", "source_authenticated",
                 "strict_selection_verified", "plan_dependencies_verified",
                 "semantic_links_verified", "hadith_identity_verified",
                 "opinion_attribution_verified", "juristic_inference_allowed",
                 "scholarly_verified"}
        if (set(view) != fields | flags or view["contract"] != VERSION
                or view["status"] != "TRANSPORT_ONLY_INCOMPLETE"
                or not identifier(view["case_id"]) or not _hex(view["receipt_sha256"])
                or type(view["node_count"]) is not int or not 1 <= view["node_count"] <= 64
                or type(view["engine_count"]) is not int or not 1 <= view["engine_count"] <= 5
                or any(view[f] is not False for f in flags)
                or type(view["links"]) is not list or len(view["links"]) > 128
                or type(view["counts"]) is not dict
                or set(view["counts"]) != {"observed_reference_relays",
                                          "unverified_proposals", "qualified_semantic_links"}
                or any(type(v) is not int or v < 0 for v in view["counts"].values())
                or view["counts"]["qualified_semantic_links"] != 0):
            return False
        for edge in view["links"]:
            if (type(edge) is not dict or set(edge) != {
                    "from_node", "from_engine", "from_handle", "to_node",
                    "to_engine", "to_handle", "relation", "assessment_digest_declared",
                    "status"} or not identifier(edge["from_node"])
                    or not identifier(edge["to_node"])
                    or type(edge["from_engine"]) is not str
                    or type(edge["to_engine"]) is not str
                    or edge["from_engine"] not in ENGINE_NAMES
                    or edge["to_engine"] not in ENGINE_NAMES
                    or edge["from_engine"] == edge["to_engine"]
                    or not _hex(edge["from_handle"]) or not _hex(edge["to_handle"])
                    or type(edge["relation"]) is not str or edge["relation"] not in RELATIONS
                    or edge["status"] != (RELAY if edge["relation"] == "EXACT_REF_RELAY" else PROPOSAL)
                    or (edge["relation"] == "EXACT_REF_RELAY" and (
                        edge["from_handle"] != edge["to_handle"]
                        or edge["assessment_digest_declared"] is not None))
                    or (edge["relation"] == "CONTEXT_PROPOSAL"
                        and edge["assessment_digest_declared"] is not None)
                    or (edge["relation"] == "SEMANTIC_PROPOSAL"
                        and not _hex(edge["assessment_digest_declared"]))):
                return False
        c = view["counts"]
        if (c["observed_reference_relays"] !=
                sum(x["status"] == RELAY for x in view["links"])
                or c["unverified_proposals"] !=
                sum(x["status"] == PROPOSAL for x in view["links"])):
            return False
        unsigned = {k: v for k, v in view.items() if k != "audit_sha256"}
        return _hex(view["audit_sha256"]) and _digest(_encoded(unsigned)) == view["audit_sha256"]
    except (TypeError, KeyError, ValueError, UnicodeError, RecursionError):
        return False


def verify_private_chain_replay(receipt, links, view):
    """Trusted local receipt replay, not private source corpus verification."""
    if not verify_redacted_chain_audit(view):
        return False
    try:
        return audit_cross_engine_chain(receipt, links) == view
    except (ChainAuditError, KeyError, TypeError, ValueError, RecursionError):
        return False
