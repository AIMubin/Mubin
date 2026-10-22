"""Stage09: typed, NON-PROMOTING source-occurrence → P0 Evidence bindings.

A successful binding proves a narrow byte/digest correspondence between an
EXACT literal occurrence and an existing P0 excerpt/source record, once
the graph hash is independently pinned. It does NOT certify textual edition,
authorial attribution, interpretive equivalence or jurisdictional authority.
No modified P0 bundle is emitted; P0 rule inference is never executed.
"""
from __future__ import annotations

import hashlib
import json
import re

from core.inference.validator import validate_bundle

VERSION = "usul-typed-evidence-binding/0.1.0"
ID = re.compile(r"^[a-z][a-z0-9_.:-]{2,127}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
MAX_PROPOSALS = 16
CORE_GRAPH_FIELDS = (
    "engine", "status", "scope", "stage07_engine", "stage07_witness_count",
    "context_radius_lines", "nodes", "edges", "nodes_by_kind",
    "edges_by_kind", "all_edge_references_valid", "source_text_included",
    "lexical_matches_promoted_to_rules", "rule_support_attested",
    "objection_presence_attested", "semantic_qarinah_verified",
    "juristic_inference_allowed", "scholarly_verified",
    "redistribution_approved",
)


class BindingProposalError(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise BindingProposalError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def bind_exact_observations(graph, trusted_graph_sha256, p0_bundle, proposals):
    """Validate *existing* graph/P0 references; no write/promotion to P0.

    The caller pins trusted_graph_sha256 outside the candidate graph. The
    source graph itself must have been built by the Stage08 trusted runner.
    """
    need(type(graph) is dict and type(trusted_graph_sha256) is str and
         SHA.fullmatch(trusted_graph_sha256) is not None,
         "independently frozen graph digest required")
    need(graph.get("status") in ("EVIDENCE_CONTEXT_GRAPH_PASS",
                                "STAGE08_DUAL_SOURCE_CONTEXT_GRAPH_PASS"),
         "unsupported context graph status")
    need(graph.get("graph_sha256") == trusted_graph_sha256,
         "graph digest does not match frozen review pin")
    need(all(k in graph for k in CORE_GRAPH_FIELDS),
         "missing Stage08 canonical graph fields")
    payload = {k: graph[k] for k in CORE_GRAPH_FIELDS}
    payload["status"] = "EVIDENCE_CONTEXT_GRAPH_PASS"
    need(sha(canonical(payload)) == trusted_graph_sha256,
         "graph canonical payload differs from pinned digest")
    need(graph.get("source_text_included") is False
         and graph.get("rule_support_attested") is False
         and graph.get("objection_presence_attested") is False
         and graph.get("juristic_inference_allowed") is False,
         "graph must be pure non-juristic metadata")
    need(type(proposals) is list and 0 < len(proposals) <= MAX_PROPOSALS,
         "bounded nonempty proposal list required")
    need(type(p0_bundle) is dict, "P0 bundle must be a contract object")
    # Fail before touching P0 inference: validate the *existing* contract, not
    # an automatically created/synthetic substitute.
    try:
        errors = validate_bundle(p0_bundle)
    except (TypeError, ValueError, KeyError) as exc:
        raise BindingProposalError("malformed P0 contract") from exc
    need(not errors, "P0 bundle failed independent structural validation")

    nodes = graph["nodes"]
    edges = graph["edges"]
    need(type(nodes) is list and type(edges) is list
         and len(nodes) <= 6000 and len(edges) <= 12000,
         "invalid Stage08 graph size")
    need(all(type(n) is dict and type(n.get("id")) is str for n in nodes),
         "malformed graph nodes")
    lookup = {n["id"]: n for n in nodes}
    need(len(lookup) == len(nodes), "duplicate graph node IDs")
    need(all(type(e) is dict and e.get("from") in lookup
             and e.get("to") in lookup for e in edges),
         "dangling graph edge")
    sections = {i: n for i, n in lookup.items()
                if n.get("kind") == "PINNED_SECTION"}
    occurrences = {i: n for i, n in lookup.items()
                   if n.get("kind") == "TEXT_OCCURRENCE"}
    witnesses = {n["source_id"]: n for n in nodes
                 if n.get("kind") == "SOURCE_WITNESS"}
    exact_occurrences = {
        e["to"] for e in edges
        if e.get("kind") == "QUERY_LOCATES_OCCURRENCE"
        and e.get("classification") == "EXACT_LITERAL_ONLY"
        and lookup[e["from"]].get("kind") == "SEARCH_QUERY"
        and lookup[e["to"]].get("kind") == "TEXT_OCCURRENCE"
    }
    p0sources = {x["id"]: x for x in p0_bundle["sources"]}
    p0evidence = {x["id"]: x for x in p0_bundle["evidence"]}

    proposals_out = []
    seen = set()
    for row in proposals:
        need(type(row) is dict and set(row) == {
            "id", "occurrence_id", "p0_source_id", "p0_evidence_id",
            "relationship", "review_status"
        }, "invalid typed proposal schema")
        need(all(type(row[k]) is str and ID.fullmatch(row[k]) is not None
                 for k in ("id", "occurrence_id", "p0_source_id",
                           "p0_evidence_id")), "invalid typed reference ID")
        need(row["id"] not in seen, "repeated proposal ID")
        seen.add(row["id"])
        need(row["relationship"] == "EXACT_BYTE_CITATION_PROPOSAL"
             and row["review_status"] == "UNASSESSED",
             "only explicitly unassessed exact-byte proposals permitted")
        need(row["occurrence_id"] in exact_occurrences,
             "candidate-only or missing occurrence cannot bind P0 evidence")
        occurrence = occurrences[row["occurrence_id"]]
        section = sections.get(occurrence.get("section_id"))
        need(section is not None, "occurrence has no pinned section")
        witness = witnesses.get(section.get("source_id"))
        need(witness is not None, "section has no witness source")
        source = p0sources.get(row["p0_source_id"])
        evidence = p0evidence.get(row["p0_evidence_id"])
        need(source is not None and evidence is not None
             and evidence["source_id"] == source["id"],
             "P0 source/evidence reference unresolved or mismatched")
        need(source["kind"] == "usul"
             and source["content_sha256"] == section["section_sha256"],
             "P0 source digest not anchored to exactly the same pinned section")
        need(source["work_title"] == witness["work_title"],
             "P0 source work title differs from graph attribution")
        need(evidence["excerpt_sha256"] == occurrence["original_span_sha256"],
             "P0 excerpt is not byte-identical to pinned exact occurrence")
        # P0's internal verification_status is an INPUT claim only. Never copy
        # it into the binding decision or change it to verified.
        proposals_out.append({
            "proposal_id": row["id"],
            "occurrence_id": row["occurrence_id"],
            "p0_source_id": source["id"],
            "p0_evidence_id": evidence["id"],
            "source_section_sha256": section["section_sha256"],
            "excerpt_sha256": occurrence["original_span_sha256"],
            "binding_status": "PROPOSED_EXACT_BYTE_LINK_UNASSESSED",
            "byte_correspondence_verified": True,
            "p0_verification_status_upgraded": False,
            "source_edition_authenticated": False,
            "semantic_equivalence_verified": False,
            "rule_support_attested": False,
            "source_text_included": False,
        })
    out = {
        "engine": VERSION,
        "status": "STAGE09_TYPED_REFERENCE_PROPOSALS_PASS",
        "stage08_graph_sha256": trusted_graph_sha256,
        "proposals": proposals_out,
        "proposal_count": len(proposals_out),
        "witness_provenance_independently_replayed_here": False,
        "p0_bundle_mutated": False,
        "p0_rule_execution_performed": False,
        "scholarly_verified": False,
        "semantic_qarinah_verified": False,
        "redistribution_approved": False,
        "juristic_inference_allowed": False,
        "public_fatwa_authorized": False,
        "source_text_included": False,
    }
    return {**out, "proposal_report_sha256": sha(canonical(out))}
