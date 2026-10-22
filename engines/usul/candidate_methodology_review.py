"""U0.2.1 research-only methodology bindings, ambiguities and alternatives.

All records are candidate metadata. This module does not execute rules,
certify source meaning, authenticate juristic methodologies or infer fatwa.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from engines.usul.concept_rule_catalog import (
    CatalogError, build_catalog, canonical, exact, need, sha, valid_id,
)

VERSION = "usul-candidate-methodology-review/0.2.1"
VERSION_PATTERN = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")
AMBIGUITIES = {"LEXICAL_SCOPE_UNRESOLVED", "EXCEPTION_SCOPE_UNRESOLVED",
               "CONDITION_SCOPE_UNRESOLVED", "FORMALIZATION_UNRESOLVED"}
DISAGREEMENTS = {"PROFILE_DIVERGENCE", "STRUCTURAL_ALTERNATIVE"}


def _version(v):
    return type(v) is str and VERSION_PATTERN.fullmatch(v) is not None


def _dedup_ids(rows, label):
    vals = [r["id"] for r in rows]
    need(all(valid_id(v) for v in vals) and len(vals) == len(set(vals)),
         label + "_IDS_INVALID")


def build_methodology_review(stage08_graph, trusted_stage08_sha256,
                             candidate_manifest, methodology_manifest):
    """Recompute the U0.2.0 catalog from trusted Stage08, then bind candidates.

    A caller-supplied stale candidate catalog or an invented methodology
    authorization never substitutes for a newly verified source graph.
    """
    catalog = build_catalog(stage08_graph, trusted_stage08_sha256,
                            candidate_manifest)
    exact(methodology_manifest,
          ("schema_version", "catalog_sha256", "methodology_profiles",
           "rule_profile_bindings", "ambiguities", "disagreements"),
          "METHODOLOGY_MANIFEST_FIELDS_INVALID")
    need(methodology_manifest["schema_version"] == "u0.2.1" and
         methodology_manifest["catalog_sha256"] == catalog["catalog_sha256"],
         "METHODOLOGY_STALE_CATALOG_PIN")
    profiles = methodology_manifest["methodology_profiles"]
    bindings = methodology_manifest["rule_profile_bindings"]
    ambiguities = methodology_manifest["ambiguities"]
    differences = methodology_manifest["disagreements"]
    need(type(profiles) is list and 1 <= len(profiles) <= 16 and
         type(bindings) is list and len(bindings) == catalog["rule_candidate_count"]
         and type(ambiguities) is list and len(ambiguities) <= 64 and
         type(differences) is list and len(differences) <= 32,
         "METHODOLOGY_REVIEW_BOUNDS_INVALID")
    rules = {r["id"]: r for r in catalog["rule_candidates"]}
    concepts = {c["id"] for c in catalog["concepts"]}
    pointers = {r["pointer_id"]: r["research_anchor"]
                for r in rules.values()}
    for p in profiles:
        exact(p, ("id", "version", "research_pointer_ids", "review_status"),
              "METHODOLOGY_PROFILE_FIELDS_INVALID")
        links = p["research_pointer_ids"]
        need(valid_id(p["id"]) and _version(p["version"])
             and p["review_status"] == "UNASSESSED"
             and type(links) is list and 1 <= len(links) <= 16
             and all(valid_id(link) for link in links)
             and len(set(links)) == len(links)
             and set(links) <= set(pointers),
             "METHODOLOGY_PROFILE_UNATTESTED")
    _dedup_ids(profiles, "METHODOLOGY_PROFILE")
    profile_map = {p["id"]: p for p in profiles}
    assignments = {}
    for b in bindings:
        exact(b, ("rule_candidate_id", "methodology_id",
                  "methodology_version", "review_status"),
              "METHODOLOGY_BINDING_FIELDS_INVALID")
        rid, mid = b["rule_candidate_id"], b["methodology_id"]
        need(valid_id(rid) and rid in rules and rid not in assignments
             and valid_id(mid) and mid in profile_map
             and b["methodology_version"] == profile_map[mid]["version"]
             and b["review_status"] == "UNASSESSED"
             and rules[rid]["pointer_id"] in profile_map[mid]["research_pointer_ids"],
             "METHODOLOGY_RULE_BINDING_INVALID")
        assignments[rid] = b
    need(set(assignments) == set(rules), "METHODOLOGY_INCOMPLETE_BINDINGS")

    def pointer_for_subject(subject_type, subject_id, pointer_id):
        if subject_type == "RULE_CANDIDATE":
            return subject_id in rules and rules[subject_id]["pointer_id"] == pointer_id
        if subject_type == "CONCEPT":
            return subject_id in concepts and any(
                pointer_id == r["pointer_id"] and
                subject_id in (r["if_concepts"] + r["unless_concepts"]
                               + [r["then_concept"]])
                for r in rules.values())
        return False

    for a in ambiguities:
        exact(a, ("id", "subject_type", "subject_id", "kind",
                  "research_pointer_id", "review_status"),
              "AMBIGUITY_FIELDS_INVALID")
        need(type(a["kind"]) is str and a["kind"] in AMBIGUITIES
             and a["review_status"] == "UNRESOLVED"
             and valid_id(a["research_pointer_id"])
             and pointer_for_subject(a["subject_type"], a["subject_id"],
                                     a["research_pointer_id"]),
             "AMBIGUITY_UNANCHORED_OR_PROMOTED")
    _dedup_ids(ambiguities, "AMBIGUITY")
    seen_pairs = set()
    for d in differences:
        exact(d, ("id", "left_rule_candidate_id", "right_rule_candidate_id",
                  "kind", "review_status"),
              "DISAGREEMENT_FIELDS_INVALID")
        left, right = d["left_rule_candidate_id"], d["right_rule_candidate_id"]
        need(type(d["kind"]) is str and d["kind"] in DISAGREEMENTS
             and d["review_status"] == "UNASSESSED"
             and valid_id(left) and valid_id(right)
             and left in rules and right in rules and left != right,
             "DISAGREEMENT_INVALID")
        shared = set(rules[left]["if_concepts"] +
                     rules[left]["unless_concepts"] +
                     [rules[left]["then_concept"]]) & set(
                         rules[right]["if_concepts"] +
                         rules[right]["unless_concepts"] +
                         [rules[right]["then_concept"]])
        need(bool(shared), "DISAGREEMENT_NO_COMMON_CONCEPT")
        signature = (d["kind"],) + tuple(sorted((left, right)))
        need(signature not in seen_pairs, "DISAGREEMENT_DUPLICATED")
        seen_pairs.add(signature)
        la, ra = assignments[left], assignments[right]
        if d["kind"] == "PROFILE_DIVERGENCE":
            need((la["methodology_id"], la["methodology_version"]) !=
                 (ra["methodology_id"], ra["methodology_version"]),
                 "DISAGREEMENT_PROFILE_NOT_DISTINCT")
        else:
            def structural(r):
                return (tuple(r["if_concepts"]), tuple(r["unless_concepts"]),
                        r["then_concept"])
            need(structural(rules[left]) != structural(rules[right]),
                 "DISAGREEMENT_NO_STRUCTURAL_ALTERNATIVE")
    _dedup_ids(differences, "DISAGREEMENT")
    # Zero published semantics; even two different profiles do not imply
    # a genuine jurisprudential disagreement without independent review.
    output = {
        "engine": VERSION, "schema_version": "u0.2.1",
        "status": "U02_METHODOLOGY_CANDIDATE_REVIEW_PASS",
        "stage08_graph_sha256": trusted_stage08_sha256,
        "catalog_sha256": catalog["catalog_sha256"],
        "methodology_profiles": sorted(profiles, key=lambda p: p["id"]),
        "rule_profile_bindings": sorted(bindings,
                                        key=lambda b: b["rule_candidate_id"]),
        "ambiguities": sorted(ambiguities, key=lambda a: a["id"]),
        "disagreements": sorted(differences, key=lambda d: d["id"]),
        "profile_count": len(profiles), "binding_count": len(bindings),
        "ambiguity_count": len(ambiguities),
        "disagreement_candidate_count": len(differences),
        "methodology_scholarly_authenticated": False,
        "real_juristic_disagreement_attested": False,
        "rule_execution_performed": False,
        "semantic_equivalence_verified": False,
        "source_support_attested": False,
        "scholarly_verified": False, "redistribution_approved": False,
        "public_fatwa_authorized": False, "juristic_inference_allowed": False,
        "source_text_included": False,
    }
    return {**output, "methodology_review_sha256": sha(canonical(output))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage08-graph", type=Path, required=True)
    parser.add_argument("--trusted-stage08-sha256", required=True)
    parser.add_argument("--catalog-manifest", type=Path, required=True)
    parser.add_argument("--methodology-manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        raw = [p.read_bytes() for p in
               (args.stage08_graph, args.catalog_manifest,
                args.methodology_manifest)]
        need(all(len(v) <= cap for v, cap in
                 zip(raw, (2_000_000, 131_072, 131_072))),
             "METHODOLOGY_INPUT_TOO_LARGE")
        graph, catalog, proposal = [json.loads(v.decode("utf-8")) for v in raw]
        report = build_methodology_review(graph, args.trusted_stage08_sha256,
                                          catalog, proposal)
        code = 0
    except (CatalogError, OSError, ValueError, KeyError, TypeError,
            UnicodeError, RecursionError) as exc:
        report = {"engine": VERSION,
                  "status": "U02_METHODOLOGY_CANDIDATE_REVIEW_REJECTED",
                  "reason_code": (str(exc) if type(exc) is CatalogError
                                  else type(exc).__name__),
                  "source_text_included": False}
        code = 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True,
                                    indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "source_text_included": False}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
