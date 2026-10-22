"""U0.2 metadata-only concept/rule research catalog on pinned Stage08 navigation.

No rule evaluation, semantic certification, scholarly judgment or fiqh.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

VERSION = "usul-concept-rule-catalog/0.2.0"
ID = re.compile(r"[a-z][a-z0-9_.:-]{2,127}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
GRAPH_FIELDS = (
    "engine", "status", "scope", "stage07_engine", "stage07_witness_count",
    "context_radius_lines", "nodes", "edges", "nodes_by_kind",
    "edges_by_kind", "all_edge_references_valid", "source_text_included",
    "lexical_matches_promoted_to_rules", "rule_support_attested",
    "objection_presence_attested", "semantic_qarinah_verified",
    "juristic_inference_allowed", "scholarly_verified", "redistribution_approved",
)
CONCEPT_KINDS = {"TERM", "CONDITION", "EXCEPTION", "OUTCOME"}
RELATION_KINDS = {"PROPOSED_RELATED_TO", "PROPOSED_BROADER_THAN",
                  "PROPOSED_DISTINGUISHED_FROM"}


class CatalogError(ValueError):
    pass


def need(condition, reason):
    if not condition:
        raise CatalogError(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(value):
    return hashlib.sha256(value).hexdigest()


def valid_id(value):
    return type(value) is str and ID.fullmatch(value) is not None


def exact(record, keys, reason):
    need(type(record) is dict and set(record) == set(keys), reason)


def index_research_pointers(graph, trusted_pin):
    need(type(graph) is dict and type(trusted_pin) is str and
         SHA.fullmatch(trusted_pin) is not None, "TRUSTED_GRAPH_PIN_REQUIRED")
    need(graph.get("status") in ("EVIDENCE_CONTEXT_GRAPH_PASS",
                                "STAGE08_DUAL_SOURCE_CONTEXT_GRAPH_PASS") and
         graph.get("graph_sha256") == trusted_pin and
         all(k in graph for k in GRAPH_FIELDS), "STAGE08_GRAPH_CONTRACT_INVALID")
    payload = {k: graph[k] for k in GRAPH_FIELDS}
    payload["status"] = "EVIDENCE_CONTEXT_GRAPH_PASS"
    need(sha(canonical(payload)) == trusted_pin, "STAGE08_DIGEST_MISMATCH")
    for flag in ("source_text_included", "lexical_matches_promoted_to_rules",
                 "rule_support_attested", "objection_presence_attested",
                 "semantic_qarinah_verified", "juristic_inference_allowed",
                 "scholarly_verified", "redistribution_approved"):
        need(graph[flag] is False, "STAGE08_NONPROMOTION_FLAG_INVALID")
    nodes, edges = graph["nodes"], graph["edges"]
    need(type(nodes) is list and len(nodes) <= 6000 and
         type(edges) is list and len(edges) <= 12000,
         "STAGE08_GRAPH_BOUNDS_INVALID")
    need(all(type(n) is dict and valid_id(n.get("id")) for n in nodes),
         "STAGE08_NODE_INVALID")
    lookup = {n["id"]: n for n in nodes}
    need(len(lookup) == len(nodes), "STAGE08_NODE_DUPLICATE")
    need(all(type(e) is dict and e.get("from") in lookup
             and e.get("to") in lookup for e in edges), "STAGE08_EDGE_INVALID")
    output = {}
    for n in nodes:
        if n.get("kind") != "RULE_RESEARCH_POINTER":
            continue
        pid = n.get("pointer_id")
        need(valid_id(pid) and pid not in output and
             valid_id(n.get("reference_id")) and
             n.get("review_status") == "UNASSESSED" and
             n.get("rule_application_verified") is False,
             "STAGE08_RULE_POINTER_INVALID")
        navigation = [e for e in edges
                      if e.get("kind") == "RESEARCH_NAVIGATION_ONLY"
                      and e["from"] == n["id"]
                      and e.get("no_claim_of_support") is True
                      and e.get("no_claim_of_exception") is True
                      and lookup[e["to"]].get("kind") == "SEARCH_QUERY"]
        need(len(navigation) == 1, "STAGE08_POINTER_NAVIGATION_INVALID")
        query = lookup[navigation[0]["to"]]
        scoped = [e for e in edges
                  if e.get("kind") == "QUERY_SCOPED_TO_SECTION"
                  and e["from"] == query["id"]
                  and lookup[e["to"]].get("kind") == "PINNED_SECTION"]
        need(len(scoped) == 1, "STAGE08_QUERY_SCOPE_INVALID")
        section = lookup[scoped[0]["to"]]
        need(type(section.get("section_sha256")) is str and
             SHA.fullmatch(section["section_sha256"]) is not None and
             query.get("witness_id") == section.get("source_id") and
             valid_id(query.get("query_id")), "STAGE08_POINTER_SECTION_INVALID")
        output[pid] = {"pointer_id": pid, "stage08_reference_id": n["reference_id"],
                       "query_id": query["query_id"],
                       "source_id": section["source_id"],
                       "section_sha256": section["section_sha256"],
                       "link_kind": "RESEARCH_NAVIGATION_ONLY",
                       "source_support_attested": False}
    return output


def _unique_ids(rows, label):
    keys = [r["id"] for r in rows]
    need(all(valid_id(k) for k in keys) and len(keys) == len(set(keys)),
         label + "_IDENTIFIER_INVALID")


def _check_broader_cycles(relations):
    graph = {}
    for row in relations:
        if row["kind"] == "PROPOSED_BROADER_THAN":
            graph.setdefault(row["from_concept_id"], set()).add(row["to_concept_id"])
    active, closed = set(), set()

    def walk(n):
        need(n not in active, "BROADER_THAN_PROPOSAL_CYCLE")
        if n in closed:
            return
        active.add(n)
        for nxt in sorted(graph.get(n, ())):
            walk(nxt)
        active.remove(n)
        closed.add(n)

    for node in sorted(graph):
        walk(node)


def build_catalog(stage08_graph, trusted_stage08_sha256, manifest):
    """Return candidate-only index; no lexical promotion, P0 mutation or execution."""
    pointers = index_research_pointers(stage08_graph, trusted_stage08_sha256)
    exact(manifest, ("schema_version", "concepts", "rule_candidates", "relations"),
          "CATALOG_MANIFEST_FIELDS_INVALID")
    need(manifest["schema_version"] == "u0.2.0", "CATALOG_SCHEMA_UNSUPPORTED")
    concepts, rules, relations = (manifest[k] for k in
                                  ("concepts", "rule_candidates", "relations"))
    need(type(concepts) is list and 1 <= len(concepts) <= 64
         and type(rules) is list and 1 <= len(rules) <= 32
         and type(relations) is list and len(relations) <= 128,
         "CATALOG_BOUND_VIOLATION")
    for c in concepts:
        exact(c, ("id", "concept_kind", "review_status"), "CONCEPT_FIELDS_INVALID")
        need(type(c["concept_kind"]) is str and
             c["concept_kind"] in CONCEPT_KINDS and
             c["review_status"] == "UNASSESSED", "CONCEPT_UNAUTHORIZED_STATUS")
    _unique_ids(concepts, "CONCEPT")
    ids = {c["id"] for c in concepts}
    for rule in rules:
        exact(rule, ("id", "pointer_id", "if_concepts", "unless_concepts",
                     "then_concept", "review_status"), "RULE_FIELDS_INVALID")
        need(valid_id(rule["pointer_id"]) and rule["pointer_id"] in pointers
             and rule["review_status"] == "UNASSESSED",
             "RULE_RESEARCH_POINTER_REQUIRED")
        pre, exc, out = (rule[k] for k in
                         ("if_concepts", "unless_concepts", "then_concept"))
        need(type(pre) is list and 1 <= len(pre) <= 8
             and type(exc) is list and len(exc) <= 8
             and all(valid_id(k) for k in pre + exc) and valid_id(out)
             and len(set(pre)) == len(pre) and len(set(exc)) == len(exc)
             and not set(pre).intersection(exc) and out not in set(pre + exc)
             and set(pre + exc + [out]) <= ids, "RULE_CONCEPT_REFERENCES_INVALID")
    _unique_ids(rules, "RULE")
    need(len({r["pointer_id"] for r in rules}) == len(rules),
         "RULE_POINTER_REUSED")
    seen = set()
    for rel in relations:
        exact(rel, ("from_concept_id", "to_concept_id", "kind", "review_status"),
              "RELATION_FIELDS_INVALID")
        src, dst = rel["from_concept_id"], rel["to_concept_id"]
        need(src in ids and dst in ids and src != dst
             and type(rel["kind"]) is str and rel["kind"] in RELATION_KINDS
             and rel["review_status"] == "UNASSESSED",
             "RELATION_UNAUTHORIZED_OR_UNRESOLVED")
        pair = (src, dst) if rel["kind"] == "PROPOSED_BROADER_THAN" else tuple(sorted((src, dst)))
        k = (rel["kind"],) + pair
        need(k not in seen, "RELATION_DUPLICATED")
        seen.add(k)
    _check_broader_cycles(relations)
    result = {
        "engine": VERSION, "schema_version": "u0.2.0",
        "status": "U02_CANDIDATE_CATALOG_PASS",
        "stage08_graph_sha256": trusted_stage08_sha256,
        "concepts": sorted(concepts, key=lambda c: c["id"]),
        "rule_candidates": [
            {**r, "research_anchor": pointers[r["pointer_id"]],
             "rule_execution_performed": False,
             "formalization_verified": False,
             "semantic_equivalence_verified": False}
            for r in sorted(rules, key=lambda r: r["id"])
        ],
        "relations": sorted(relations,
                            key=lambda x: (x["kind"], x["from_concept_id"],
                                           x["to_concept_id"])),
        "concept_count": len(concepts),
        "rule_candidate_count": len(rules), "relation_count": len(relations),
        "source_text_included": False, "research_navigation_only": True,
        "rule_execution_performed": False, "source_support_attested": False,
        "semantic_equivalence_verified": False, "scholarly_verified": False,
        "redistribution_approved": False, "public_fatwa_authorized": False,
        "juristic_inference_allowed": False,
    }
    return {**result, "catalog_sha256": sha(canonical(result))}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stage08-graph", type=Path, required=True)
    p.add_argument("--trusted-stage08-sha256", required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    try:
        a, b = args.stage08_graph.read_bytes(), args.manifest.read_bytes()
        need(len(a) <= 2_000_000 and len(b) <= 131_072,
             "INPUT_BYTE_BUDGET_EXCEEDED")
        graph, manifest = json.loads(a.decode("utf-8")), json.loads(b.decode("utf-8"))
        report = build_catalog(graph, args.trusted_stage08_sha256, manifest)
        exit_code = 0
    except (CatalogError, OSError, ValueError, KeyError, TypeError,
            UnicodeError, RecursionError) as exc:
        report = {
            "engine": VERSION, "status": "U02_CANDIDATE_CATALOG_REJECTED",
            "reason_code": str(exc) if type(exc) is CatalogError else type(exc).__name__,
            "source_text_included": False,
        }
        exit_code = 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True,
                                   indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "source_text_included": False}))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
