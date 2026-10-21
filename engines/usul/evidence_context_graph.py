"""U0.1 Stage08: source-byte-anchored context and research citation navigation.

This is a metadata-only graph. It independently re-runs Stage07 retrieval
against pinned section bytes before accepting a hit or computing a context.
Rule and objection pointers navigate QUERIES, never endorse observations,
infer exceptions, or support legal conclusions.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engines.usul.arabic_evidence_retrieval import (
    EXACT, ArabicRetrievalError, retrieve,
)

VERSION = "usul-evidence-context-graph/0.1.0"
MAX_NODES = 6000
MAX_EDGES = 12000
MAX_POINTERS = 16
POINTER_TYPES = {"RULE_RESEARCH_POINTER", "OBJECTION_RESEARCH_POINTER"}


class ContextGraphError(ValueError):
    pass


def _need(ok, why):
    if not ok:
        raise ContextGraphError(why)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _id(category, *data):
    return category + ":" + _sha(_canonical(data))[:32]


def _index_lines(raw):
    parts = raw.splitlines(keepends=True)
    _need(b"".join(parts) == raw and bool(parts),
          "context source not reconstructable from lines")
    offsets, pos = [0], 0
    for line in parts:
        pos += len(line)
        offsets.append(pos)
    return parts, offsets


def _validate_pointers(pointers, witness_ids, query_ids):
    _need(type(pointers) is list and len(pointers) <= MAX_POINTERS,
          "research pointers must be a bounded array")
    seen = set()
    for row in pointers:
        _need(type(row) is dict and set(row) == {
            "id", "kind", "reference_id", "witness_id", "query_id",
            "review_status"
        }, "invalid research pointer contract")
        _need(type(row["id"]) is str and 3 <= len(row["id"]) <= 128
              and row["id"] not in seen, "invalid or duplicate pointer ID")
        seen.add(row["id"])
        _need(row["kind"] in POINTER_TYPES
              and row["review_status"] == "UNASSESSED",
              "only unassessed research navigation is allowed")
        _need(type(row["reference_id"]) is str and
              3 <= len(row["reference_id"]) <= 128,
              "invalid referenced rule/objection identifier")
        _need(row["witness_id"] in witness_ids and row["query_id"] in query_ids,
              "research pointer must cite a declared witness/query pair")


def build_context_graph(stage07_report, witnesses, queries, pointers=None, *,
                        context_radius_lines=1, work_title=None, author=None):
    """Require a recomputed identical Stage07 report, with frozen private bytes.

    Only the caller's Stage07 trusted gateway can attest HTML provenance;
    this generic builder attests *section* bytes and Stage07 search semantics.
    It refuses any report whose entire witness result differs from a replay.
    """
    _need(type(context_radius_lines) is int
          and 0 <= context_radius_lines <= 2,
          "context radius must be 0, 1 or 2 lines")
    _need(type(stage07_report) is dict and
          stage07_report.get("status") in (
              "ARABIC_SOURCE_RETRIEVAL_PASS",
              "STAGE07_DUAL_WITNESS_ARABIC_RETRIEVAL_PASS"),
          "Stage07 retrieval status not accepted")
    replay = retrieve(witnesses, queries)
    _need(stage07_report.get("witnesses") == replay["witnesses"]
          and stage07_report.get("source_count") == replay["source_count"]
          and stage07_report.get("all_offsets_reference_original_section_bytes") is True
          and stage07_report.get("normalized_match_is_only_candidate") is True,
          "provided Stage07 matches are not independently reproducible")
    if stage07_report["status"] == "STAGE07_DUAL_WITNESS_ARABIC_RETRIEVAL_PASS":
        p = stage07_report.get("stage06_strict_provenance")
        _need(type(p) is dict and
              p.get("status") == "STAGE06_DUAL_SOURCE_EXTRACTION_REPLAY_PASS"
              and p.get("both_html_to_section_replays_verified") is True,
              "dual-witness report lacks Stage06 strict replay metadata")
    _need((work_title is None or (type(work_title) is str and
                                  0 < len(work_title) <= 256))
          and (author is None or (type(author) is str and
                                 0 < len(author) <= 256)),
          "source attribution metadata invalid")
    witness_ids = {w["source_id"] for w in witnesses}
    query_ids = {q["id"] for q in queries}
    pointers = [] if pointers is None else pointers
    _validate_pointers(pointers, witness_ids, query_ids)

    nodes = {}
    edges = {}

    def node(kind, identifier, **fields):
        obj = {"id": identifier, "kind": kind, **fields}
        if identifier in nodes:
            _need(nodes[identifier] == obj, "node ID collision")
        else:
            _need(len(nodes) < MAX_NODES, "graph node budget exceeded")
            nodes[identifier] = obj
        return identifier

    def edge(kind, start, end, **fields):
        item = {"kind": kind, "from": start, "to": end, **fields}
        key = _id("edge", item)
        _need(len(edges) < MAX_EDGES or key in edges,
              "graph edge budget exceeded")
        edges[key] = {"id": key, **item}

    for w, record in zip(witnesses, replay["witnesses"]):
        raw = Path(w["section_path"]).read_bytes()
        _need(_sha(raw) == w["section_sha256"] and
              len(raw) == record["indexed_section_bytes"],
              "source changed while context graph was constructed")
        parts, starts = _index_lines(raw)
        wid = node("SOURCE_WITNESS", _id("witness", w["source_id"], w["section_sha256"]),
                   source_id=w["source_id"], source_url=w["source_url"],
                   work_title=work_title, author=author,
                   printed_edition_verified=False)
        sid = node("PINNED_SECTION", _id("section", w["source_id"], w["section_sha256"]),
                   source_id=w["source_id"],
                   section_sha256=w["section_sha256"],
                   section_locator=w["section_locator"],
                   offset_basis=w["offset_basis"],
                   source_byte_base=w["source_byte_base"],
                   source_line_base=w["source_line_base"],
                   byte_length=len(raw), line_count=len(parts))
        edge("WITNESS_HAS_PINNED_SECTION", wid, sid)
        for query_record in record["queries"]:
            qid = node("SEARCH_QUERY", _id("query", w["source_id"], query_record["query_id"],
                                           query_record["query_utf8_sha256"]),
                       witness_id=w["source_id"],
                       query_id=query_record["query_id"],
                       query_utf8_sha256=query_record["query_utf8_sha256"],
                       interpretation="LEXICAL_NAVIGATION_ONLY",
                       source_text_included=False)
            edge("QUERY_SCOPED_TO_SECTION", qid, sid)

            bundles = [("EXACT", EXACT, query_record["strict_matches"])]
            bundles.extend(
                ("FOLDED_CANDIDATE", c["profile"], c["matches"])
                for c in query_record["candidate_profiles"]
            )
            for classification, profile, hits in bundles:
                for hit in hits:
                    a, b = hit["section_byte_start"], hit["section_byte_end_exclusive"]
                    line_no = hit["section_line_number"]
                    _need(1 <= line_no <= len(parts)
                          and starts[line_no - 1] <= a < b <= starts[line_no]
                          and _sha(raw[a:b]) == hit["original_bytes_sha256"]
                          and _sha(parts[line_no-1]) == hit["original_line_sha256"],
                          "hit bytes/line not anchored in pinned source")
                    first = max(0, line_no-1-context_radius_lines)
                    last = min(len(parts), line_no+context_radius_lines)
                    start_byte, end_byte = starts[first], starts[last]
                    context = raw[start_byte:end_byte]
                    context_id = node(
                        "HASHED_CONTEXT", _id("context", w["source_id"], w["section_sha256"],
                                             start_byte, end_byte),
                        section_id=sid,
                        section_byte_start=start_byte,
                        section_byte_end_exclusive=end_byte,
                        section_line_start=first+1,
                        section_line_end_inclusive=last,
                        context_sha256=_sha(context),
                        byte_length=len(context),
                        text_included=False,
                    )
                    edge("SECTION_HAS_CONTEXT", sid, context_id)
                    observation_id = node(
                        "TEXT_OCCURRENCE", _id("occurrence", w["source_id"],
                                               w["section_sha256"], a, b,
                                               hit["original_bytes_sha256"]),
                        section_id=sid, section_byte_start=a,
                        section_byte_end_exclusive=b,
                        source_coordinate_basis=w["offset_basis"],
                        source_byte_start=w["source_byte_base"]+a,
                        source_byte_end_exclusive=w["source_byte_base"]+b,
                        section_line_number=line_no,
                        source_line_number=w["source_line_base"]+line_no-1,
                        original_span_sha256=hit["original_bytes_sha256"],
                        original_line_sha256=hit["original_line_sha256"],
                        text_included=False,
                        semantic_classification="NOT_EVALUATED",
                    )
                    edge("CONTEXT_INCLUDES_OCCURRENCE", context_id, observation_id)
                    edge("QUERY_LOCATES_OCCURRENCE", qid, observation_id,
                         profile=profile,
                         classification=("EXACT_LITERAL_ONLY" if classification == "EXACT"
                                         else "ORTHOGRAPHIC_CANDIDATE_ONLY"),
                         semantic_equivalence_verified=False)
    for p in pointers:
        qid = next(
            (_id("query", p["witness_id"], q["id"],
                 _sha(q["literal"].encode("utf-8")))
             for q in queries if q["id"] == p["query_id"]), None)
        _need(qid in nodes, "research pointer references absent query")
        pointer = node(p["kind"], _id("pointer", p["id"], p["reference_id"]),
                       pointer_id=p["id"], reference_id=p["reference_id"],
                       review_status="UNASSESSED",
                       rule_application_verified=False,
                       objection_presence_verified=False)
        edge("RESEARCH_NAVIGATION_ONLY", pointer, qid,
             no_claim_of_support=True, no_claim_of_exception=True)

    _need(all(e["from"] in nodes and e["to"] in nodes for e in edges.values()),
          "dangling graph edge")
    node_list = [nodes[k] for k in sorted(nodes)]
    edge_list = [edges[k] for k in sorted(edges)]
    payload = {
        "engine": VERSION,
        "status": "EVIDENCE_CONTEXT_GRAPH_PASS",
        "scope": "PINNED_TEXT_OBSERVATION_AND_RESEARCH_NAVIGATION_ONLY",
        "stage07_engine": replay["engine"],
        "stage07_witness_count": replay["source_count"],
        "context_radius_lines": context_radius_lines,
        "nodes": node_list,
        "edges": edge_list,
        "nodes_by_kind": {
            kind: sum(n["kind"] == kind for n in node_list)
            for kind in sorted({n["kind"] for n in node_list})
        },
        "edges_by_kind": {
            kind: sum(e["kind"] == kind for e in edge_list)
            for kind in sorted({e["kind"] for e in edge_list})
        },
        "all_edge_references_valid": True,
        "source_text_included": False,
        "lexical_matches_promoted_to_rules": False,
        "rule_support_attested": False,
        "objection_presence_attested": False,
        "semantic_qarinah_verified": False,
        "juristic_inference_allowed": False,
        "scholarly_verified": False,
        "redistribution_approved": False,
    }
    return {**payload, "graph_sha256": _sha(_canonical(payload))}
