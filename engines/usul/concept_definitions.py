"""Research-only, metadata-only concept definitions rooted in U0.2.3.

No source text, verified scholarly attribution, licensed quotation,
normative rule execution or fiqh inference is accepted or emitted.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from engines.usul.concept_rule_catalog import (
    CatalogError, canonical, exact, need, sha, valid_id,
)

VERSION = "usul-concept-definitions/0.1.0"
SCHEMA = "u02-concept-definitions/0.1.0"
RECEIPT_STATUS = "U02_REAL_WARAQAT_PRIVATE_REPLAY_ACCEPTED"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
SEMVER = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")
COLLECTIONS = (
    "sources", "source_observations", "definition_candidates",
    "interpretation_candidates", "definition_comparisons",
)
TOP = ("schema_version", "basis_receipt_sha256", "previous_manifest_sha256") + COLLECTIONS
MAXIMUM = (16, 32, 64, 64, 64)
REQUIRED_FALSE = (
    "source_text_included", "private_paths_included", "source_support_attested",
    "scholarly_verified", "semantic_equivalence_verified",
    "redistribution_approved", "juristic_inference_allowed",
    "rule_execution_performed", "public_fatwa_authorized",
)


def _digest(value):
    return type(value) is str and SHA256.fullmatch(value) is not None


def _version(value):
    return type(value) is str and SEMVER.fullmatch(value) is not None


def _require_id(value, code):
    need(valid_id(value), code)


def normalize_manifest(manifest):
    exact(manifest, TOP, "DEFINITION_MANIFEST_FIELDS_INVALID")
    need(manifest["schema_version"] == SCHEMA,
         "DEFINITION_SCHEMA_UNSUPPORTED")
    need(_digest(manifest["basis_receipt_sha256"]),
         "DEFINITION_BASIS_PIN_MISSING")
    previous = manifest["previous_manifest_sha256"]
    need(previous is None or _digest(previous),
         "PREVIOUS_MANIFEST_PIN_INVALID")
    normalized = {k: manifest[k] for k in TOP[:3]}
    for name, maximum in zip(COLLECTIONS, MAXIMUM):
        records = manifest[name]
        need(type(records) is list and len(records) <= maximum,
             "DEFINITION_COLLECTION_BOUNDS_INVALID")
        need(all(type(r) is dict and valid_id(r.get("id")) for r in records),
             "DEFINITION_RECORD_ID_INVALID")
        ids = [r["id"] for r in records]
        need(len(ids) == len(set(ids)), "DEFINITION_DUPLICATE_ID")
        normalized[name] = sorted(records, key=lambda x: x["id"])
    return normalized


def _receipt_contract(receipt, trusted_receipt_sha256):
    need(type(receipt) is dict and _digest(trusted_receipt_sha256),
         "INDEPENDENT_RECEIPT_PIN_REQUIRED")
    need(receipt.get("acceptance_receipt_sha256") == trusted_receipt_sha256,
         "RECEIPT_PIN_MISMATCH")
    payload = {k: v for k, v in receipt.items()
               if k != "acceptance_receipt_sha256"}
    need(sha(canonical(payload)) == trusted_receipt_sha256,
         "RECEIPT_CANONICAL_DIGEST_MISMATCH")
    need(receipt.get("status") == RECEIPT_STATUS
         and receipt.get("full_private_inputs_matched_frozen_sha256") is True
         and receipt.get("identical_two_source_replays") is True
         and receipt.get("w1_mutated_html_rejected") is True
         and receipt.get("w2_mutated_html_rejected") is True
         and all(receipt.get(k) is False for k in REQUIRED_FALSE)
         and _digest(receipt.get("stage08_graph_sha256"))
         and _digest(receipt.get("catalog_sha256")),
         "RECEIPT_UNAUTHORIZED_OR_UNATTESTED")
    pins = receipt.get("original_private_witness_pins")
    need(type(pins) is dict and
         _digest(pins.get("w1_bab_amr_sha256")) and
         _digest(pins.get("w2_bab_amr_sha256")),
         "RECEIPT_SOURCE_SECTION_PIN_INVALID")
    entries = receipt.get("independent_original_byte_literal_counts")
    need(type(entries) is list and len(entries) == 3,
         "RECEIPT_CONCEPT_INVENTORY_INVALID")
    lookup = {}
    for row in entries:
        need(type(row) is dict and valid_id(row.get("concept_id"))
             and valid_id(row.get("query_id"))
             and type(row.get("independent_exact_count")) is int
             and row["independent_exact_count"] > 0
             and row.get("matches_reported_graph") is True
             and row["concept_id"] not in lookup,
             "RECEIPT_CONCEPT_LINK_INVALID")
        lookup[row["concept_id"]] = row
    return lookup, pins


def _validate_previous(manifest, previous, trusted_previous_sha256):
    normalized = normalize_manifest(manifest)
    if previous is None:
        need(normalized["previous_manifest_sha256"] is None
             and trusted_previous_sha256 is None,
             "INITIAL_MANIFEST_PARENT_MUST_BE_NULL")
        return normalized
    prior = normalize_manifest(previous)
    need(_digest(trusted_previous_sha256)
         and sha(canonical(prior)) == trusted_previous_sha256
         and normalized["previous_manifest_sha256"] == trusted_previous_sha256
         and normalized["basis_receipt_sha256"] == prior["basis_receipt_sha256"],
         "APPEND_ONLY_PARENT_PIN_MISMATCH")
    for name in COLLECTIONS:
        old = {x["id"]: x for x in prior[name]}
        new = {x["id"]: x for x in normalized[name]}
        need(all(key in new and new[key] == record
                 for key, record in old.items()),
             "APPEND_ONLY_RECORD_MUTATION_OR_DELETION")
    return normalized


def build_definitions(receipt, trusted_receipt_sha256, manifest,
                      previous_manifest=None, trusted_previous_sha256=None):
    """Return strictly unassessed metadata catalog linked to a pinned receipt."""
    lookup, pins = _receipt_contract(receipt, trusted_receipt_sha256)
    m = _validate_previous(manifest, previous_manifest, trusted_previous_sha256)
    need(m["basis_receipt_sha256"] == trusted_receipt_sha256,
         "DEFINITION_BASIS_PIN_MISMATCH")
    sources = {x["id"]: x for x in m["sources"]}
    observations = {x["id"]: x for x in m["source_observations"]}
    definitions = {x["id"]: x for x in m["definition_candidates"]}
    need(1 <= len(sources) and len(observations) == len(lookup),
         "SOURCE_OR_OBSERVATION_COVERAGE_INVALID")

    seen_source_witnesses = set()
    for source in sources.values():
        exact(source, ("id", "witness_id", "work_id", "claimed_author_id",
                       "edition_id", "locator_id", "section_sha256",
                       "rights_status", "attribution_review_status",
                       "edition_review_status", "version"),
              "SOURCE_REGISTRY_FIELDS_INVALID")
        for key in ("witness_id", "work_id", "claimed_author_id",
                    "edition_id", "locator_id"):
            _require_id(source[key], "SOURCE_REGISTRY_IDENTIFIER_INVALID")
        need(source["witness_id"] == "pilot:waraqat-primary"
             and source["section_sha256"] == pins["w1_bab_amr_sha256"]
             and source["rights_status"] in ("NOT_CLEARED", "RESTRICTED")
             and source["attribution_review_status"] == "UNASSESSED"
             and source["edition_review_status"] == "UNASSESSED"
             and _version(source["version"])
             and source["witness_id"] not in seen_source_witnesses,
             "SOURCE_REGISTRY_UNVERIFIED_OR_UNPINNED")
        seen_source_witnesses.add(source["witness_id"])
    need(len(sources) == 1, "SOURCE_REGISTRY_SCOPE_INVALID")
    seen_concepts = set()
    for obs in observations.values():
        exact(obs, ("id", "concept_id", "source_id", "query_id",
                    "version", "observation_status", "source_text_included"),
              "SOURCE_OBSERVATION_FIELDS_INVALID")
        c = obs["concept_id"]
        need(valid_id(c) and c in lookup and c not in seen_concepts
             and valid_id(obs["source_id"]) and obs["source_id"] in sources
             and valid_id(obs["query_id"])
             and obs["query_id"] == lookup[c]["query_id"]
             and _version(obs["version"])
             and obs["observation_status"] == "LEXICAL_ONLY"
             and obs["source_text_included"] is False,
             "SOURCE_OBSERVATION_UNANCHORED_OR_PROMOTED")
        seen_concepts.add(c)
    need(seen_concepts == set(lookup), "SOURCE_OBSERVATION_COVERAGE_INCOMPLETE")

    seen_definition_pairs = set()
    definitions_by_concept = {}
    for definition in definitions.values():
        exact(definition, ("id", "concept_id", "source_observation_id",
                           "version", "definition_sha256", "claimed_author_id",
                           "review_status", "source_text_included"),
              "DEFINITION_CANDIDATE_FIELDS_INVALID")
        oid = definition["source_observation_id"]
        need(valid_id(definition["concept_id"]) and valid_id(oid)
             and oid in observations
             and observations[oid]["concept_id"] == definition["concept_id"]
             and _version(definition["version"])
             and _digest(definition["definition_sha256"])
             and definition["claimed_author_id"] ==
             sources[observations[oid]["source_id"]]["claimed_author_id"]
             and definition["review_status"] == "UNASSESSED"
             and definition["source_text_included"] is False,
             "DEFINITION_ATTRIBUTION_OR_STATUS_INVALID")
        pair = (definition["concept_id"], definition["definition_sha256"])
        need(pair not in seen_definition_pairs, "DEFINITION_DUPLICATE_DIGEST")
        seen_definition_pairs.add(pair)
        definitions_by_concept.setdefault(definition["concept_id"], set()).add(
            definition["id"])

    for interp in m["interpretation_candidates"]:
        exact(interp, ("id", "concept_id", "definition_candidate_ids",
                       "version", "interpretation_sha256", "review_status",
                       "source_text_included"),
              "INTERPRETATION_FIELDS_INVALID")
        references = interp["definition_candidate_ids"]
        need(valid_id(interp["concept_id"])
             and interp["concept_id"] in lookup
             and type(references) is list and 1 <= len(references) <= 8
             and all(type(r) is str and r in definitions for r in references)
             and len(references) == len(set(references))
             and set(references) <= definitions_by_concept.get(
                 interp["concept_id"], set())
             and _version(interp["version"])
             and _digest(interp["interpretation_sha256"])
             and interp["review_status"] == "UNASSESSED"
             and interp["source_text_included"] is False,
             "INTERPRETATION_UNANCHORED_OR_PROMOTED")

    compared = set()
    for comparison in m["definition_comparisons"]:
        exact(comparison, ("id", "concept_id", "definition_candidate_ids",
                           "kind", "review_status"),
              "DEFINITION_COMPARISON_FIELDS_INVALID")
        refs = comparison["definition_candidate_ids"]
        need(valid_id(comparison["concept_id"])
             and comparison["concept_id"] in lookup and type(refs) is list
             and len(refs) == 2 and all(type(r) is str for r in refs)
             and len(set(refs)) == 2 and
             set(refs) <= definitions_by_concept.get(
                 comparison["concept_id"], set())
             and comparison["kind"] == "MULTIPLE_DEFINITIONS"
             and comparison["review_status"] == "UNASSESSED",
             "DEFINITION_COMPARISON_UNATTESTED")
        pair = (comparison["concept_id"],) + tuple(sorted(refs))
        need(pair not in compared, "DEFINITION_COMPARISON_DUPLICATE")
        compared.add(pair)

    result = {
        "engine": VERSION, "schema_version": SCHEMA,
        "status": "U02_DEFINITION_METADATA_CANDIDATES_PASS",
        "basis_receipt_sha256": trusted_receipt_sha256,
        "stage08_graph_sha256": receipt["stage08_graph_sha256"],
        "candidate_catalog_sha256": receipt["catalog_sha256"],
        "manifest_sha256": sha(canonical(m)),
        "previous_manifest_sha256": m["previous_manifest_sha256"],
        "source_count": len(sources), "observation_count": len(observations),
        "definition_candidate_count": len(definitions),
        "interpretation_candidate_count": len(m["interpretation_candidates"]),
        "multiple_definitions_comparison_count": len(m["definition_comparisons"]),
        "source_text_included": False, "private_paths_included": False,
        "scholarly_attribution_verified": False, "source_edition_authenticated": False,
        "scholarly_disagreement_attested": False,
        "source_support_attested": False, "scholarly_verified": False,
        "semantic_equivalence_verified": False, "redistribution_approved": False,
        "juristic_inference_allowed": False, "rule_execution_performed": False,
        "public_fatwa_authorized": False,
    }
    return {**result, "report_sha256": sha(canonical(result))}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--basis-receipt", type=Path, required=True)
    p.add_argument("--trusted-basis-sha256", required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--previous-manifest", type=Path)
    p.add_argument("--trusted-previous-sha256")
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    try:
        files = [a.basis_receipt, a.manifest]
        if a.previous_manifest:
            files.append(a.previous_manifest)
        data = []
        for f in files:
            raw = f.read_bytes()
            need(0 < len(raw) <= 131072, "DEFINITION_INPUT_BYTE_BUDGET_EXCEEDED")
            data.append(json.loads(raw.decode("utf-8")))
        report = build_definitions(data[0], a.trusted_basis_sha256, data[1],
                                   data[2] if len(data) > 2 else None,
                                   a.trusted_previous_sha256)
        code = 0
    except (CatalogError, OSError, ValueError, TypeError, UnicodeError,
            KeyError, RecursionError) as exc:
        report = {
            "engine": VERSION, "status": "U02_DEFINITION_METADATA_REJECTED",
            "reason_code": (str(exc) if type(exc) is CatalogError
                            else type(exc).__name__),
            "source_text_included": False, "scholarly_verified": False,
        }
        code = 2
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, sort_keys=True, indent=2,
                                ensure_ascii=False)+"\n", encoding="utf-8")
    print(json.dumps({"status": report["status"],
                      "source_text_included": False}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
