"""U0.2.2 al-Waraqat: private W1/W2 replay → metadata-only candidate lexical anchors.

Source bytes never leave the local operator machine. A frozen Stage08 graph
digest is checked after the COMPLETE Stage06→Stage07→Stage08 replay.
The result is research navigation and lexical observation ONLY.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from engines.usul.concept_rule_catalog import (
    CatalogError, build_catalog, canonical, exact, need, sha, valid_id,
)
from engines.usul.pilots import waraqat_stage08 as stage08
from engines.usul.pilots.waraqat_stage09 import WARAQAT_STAGE08_GRAPH_SHA256
from engines.usul.pilots.waraqat_stage07 import W1_SECTION_SHA, W2_SECTION_SHA

VERSION = "waraqat-u02-pinned-lexical-catalog/0.2.2"
EXPECTED_NODES = 53
EXPECTED_EDGES = 87
EXPECTED_WITNESSES = {
    "pilot:waraqat-primary": W1_SECTION_SHA,
    "pilot:waraqat-comparator": W2_SECTION_SHA,
}
CLASSIFICATIONS = {"EXACT_LITERAL_ONLY", "ORTHOGRAPHIC_CANDIDATE_ONLY"}
REPO_DATA = Path(__file__).resolve().parent / "data"


def lexical_links(graph, catalog, manifest):
    """Exact byte-observation *metadata* links; no semantic support claim.

    The caller must first validate the graph against an external pin using
    build_catalog(). The pinned Stage08 graph describes query-specific exact
    or diagnostic folded matches with no interpretation.
    """
    exact(manifest, ("schema_version", "lexical_bindings"),
          "LEXICAL_MANIFEST_FIELDS_INVALID")
    need(manifest["schema_version"] == "u0.2.2",
         "LEXICAL_MANIFEST_SCHEMA_INVALID")
    rows = manifest["lexical_bindings"]
    need(type(rows) is list and 1 <= len(rows) <= 16,
         "LEXICAL_BINDING_BOUNDS_INVALID")
    concepts = {r["id"] for r in catalog["concepts"]}
    nodes = {r["id"]: r for r in graph["nodes"]}
    edges = graph["edges"]
    ids = set()
    output = []
    for row in rows:
        exact(row, ("concept_id", "witness_id", "query_id",
                    "classification", "expected_unique_occurrences"),
              "LEXICAL_BINDING_FIELDS_INVALID")
        cid, witness, query_id, classification = (
            row["concept_id"], row["witness_id"], row["query_id"],
            row["classification"])
        count = row["expected_unique_occurrences"]
        need(valid_id(cid) and cid in concepts and cid not in ids
             and type(witness) is str and witness in EXPECTED_WITNESSES
             and valid_id(query_id)
             and type(classification) is str and
             classification in CLASSIFICATIONS
             and type(count) is int and 1 <= count <= 64,
             "LEXICAL_BINDING_UNSUPPORTED_REFERENCE")
        ids.add(cid)
        sections = [n for n in nodes.values()
                    if n.get("kind") == "PINNED_SECTION"
                    and n.get("source_id") == witness
                    and n.get("section_sha256") == EXPECTED_WITNESSES[witness]]
        need(len(sections) == 1, "LEXICAL_WITNESS_PIN_MISMATCH")
        section = sections[0]
        query_nodes = [n for n in nodes.values()
                       if n.get("kind") == "SEARCH_QUERY"
                       and n.get("query_id") == query_id
                       and n.get("witness_id") == witness]
        need(len(query_nodes) == 1, "LEXICAL_QUERY_UNRESOLVED")
        query = query_nodes[0]
        need(any(e.get("kind") == "QUERY_SCOPED_TO_SECTION"
                 and e.get("from") == query["id"]
                 and e.get("to") == section["id"] for e in edges),
             "LEXICAL_QUERY_WRONG_SECTION")
        occurrences = set()
        for edge in edges:
            if edge.get("kind") != "QUERY_LOCATES_OCCURRENCE" or (
                    edge.get("from") != query["id"] or
                    edge.get("classification") != classification):
                continue
            target = nodes.get(edge.get("to"))
            need(target is not None and target.get("kind") == "TEXT_OCCURRENCE"
                 and target.get("section_id") == section["id"]
                 and target.get("semantic_classification") == "NOT_EVALUATED"
                 and edge.get("semantic_equivalence_verified") is False,
                 "LEXICAL_OCCURRENCE_PROMOTION_OR_CROSS_SOURCE")
            occurrences.add(target["id"])
        need(len(occurrences) == count, "LEXICAL_EXPECTED_COUNT_MISMATCH")
        output.append({
            "concept_id": cid, "query_id": query_id,
            "source_id": witness,
            "section_sha256": section["section_sha256"],
            "classification": classification,
            "unique_occurrence_count": count,
            "occurrence_ids": sorted(occurrences),
            "lexical_presence_only": True,
            "source_support_attested": False,
            "semantic_equivalence_verified": False,
            "scholarly_verified": False,
        })
    need(ids == concepts, "LEXICAL_CONCEPT_COVERAGE_INCOMPLETE")
    return sorted(output, key=lambda x: x["concept_id"])


def bind_replayed_metadata(graph, catalog_manifest, lexical_manifest):
    """Require the exact historically attested graph, not just any self-hash."""
    need(type(graph) is dict and
         graph.get("status") == "STAGE08_DUAL_SOURCE_CONTEXT_GRAPH_PASS"
         and graph.get("runner") == stage08.VERSION
         and graph.get("source_replay_verified_by_runner") is True
         and graph.get("source_replay_status") ==
         "STAGE07_DUAL_WITNESS_ARABIC_RETRIEVAL_PASS"
         and graph.get("primary_section_sha256") == W1_SECTION_SHA
         and graph.get("secondary_section_sha256") == W2_SECTION_SHA
         and graph.get("graph_sha256") == WARAQAT_STAGE08_GRAPH_SHA256
         and len(graph.get("nodes", [])) == EXPECTED_NODES
         and len(graph.get("edges", [])) == EXPECTED_EDGES,
         "WARAQAT_REAL_SOURCE_REPLAY_PIN_MISMATCH")
    catalog = build_catalog(graph, WARAQAT_STAGE08_GRAPH_SHA256,
                            catalog_manifest)
    links = lexical_links(graph, catalog, lexical_manifest)
    result = {
        "engine": VERSION, "status": "U02_WARAQAT_PINNED_CATALOG_PASS",
        "stage08_graph_sha256": graph["graph_sha256"],
        "stage08_node_count": len(graph["nodes"]),
        "stage08_edge_count": len(graph["edges"]),
        "stage08_source_replay_status": graph["source_replay_status"],
        "source_replay_executed_here": True,
        "catalog_sha256": catalog["catalog_sha256"],
        "catalog_rule_candidates": catalog["rule_candidate_count"],
        "catalog_concept_count": catalog["concept_count"],
        "lexical_bindings": links,
        "lexical_binding_count": len(links),
        "textual_match_does_not_imply_rule_support": True,
        "source_text_included": False,
        "source_support_attested": False,
        "source_edition_authenticated": False,
        "semantic_equivalence_verified": False,
        "formalization_verified": False,
        "scholarly_verified": False,
        "redistribution_approved": False,
        "public_fatwa_authorized": False,
        "juristic_inference_allowed": False,
        "rule_execution_performed": False,
    }
    return {**result, "u02_real_replay_report_sha256": sha(canonical(result))}


def replay_and_bind(paths, queries, pointers, catalog_manifest,
                    lexical_manifest):
    """The ONLY real-source entry: replay the pinned local HTMLs first."""
    need(type(paths) in (tuple, list) and len(paths) == 6,
         "WARAQAT_PRIVATE_SOURCE_PATHS_INVALID")
    graph = stage08.replay_and_graph(*paths, queries, pointers)
    return bind_replayed_metadata(graph, catalog_manifest, lexical_manifest)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("primary-html", "primary-export", "primary-manifest",
                 "primary-section", "secondary-html", "secondary-section"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--queries", type=Path,
                   default=REPO_DATA / "waraqat-stage07-queries.json")
    p.add_argument("--pointers", type=Path,
                   default=REPO_DATA / "waraqat-stage08-research-pointers.json")
    p.add_argument("--catalog-manifest", type=Path,
                   default=REPO_DATA / "waraqat-u02-catalog-candidates.json")
    p.add_argument("--lexical-manifest", type=Path,
                   default=REPO_DATA / "waraqat-u02-lexical-bindings.json")
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()
    paths = tuple(getattr(args, name.replace("-", "_")) for name in (
        "primary-html", "primary-export", "primary-manifest",
        "primary-section", "secondary-html", "secondary-section"))
    try:
        if not all(path.is_file() for path in paths):
            report, code = {
                "engine": VERSION, "status": "PENDING_PRIVATE_WITNESS_FILES",
                "source_text_included": False, "scholarly_verified": False,
            }, 3
        else:
            data = []
            for path in (args.queries, args.pointers,
                         args.catalog_manifest, args.lexical_manifest):
                if not path.is_file() or not 0 < path.stat().st_size <= 131072:
                    raise CatalogError("RESEARCH_METADATA_INPUT_ABSENT_OR_OVERSIZED")
                data.append(json.loads(path.read_text(encoding="utf-8")))
            report = replay_and_bind(paths, *data)
            code = 0
    except (CatalogError, OSError, UnicodeError, ValueError, TypeError,
            KeyError, RecursionError) as exc:
        report, code = {
            "engine": VERSION, "status": "U02_WARAQAT_PINNED_CATALOG_FAILED",
            "reason_code": (str(exc) if type(exc) is CatalogError
                            else type(exc).__name__),
            "source_text_included": False, "scholarly_verified": False,
        }, 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True,
                                     indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"],
                      "source_text_included": False}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
