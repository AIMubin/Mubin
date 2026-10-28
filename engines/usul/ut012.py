"""UT-01.2 — conservative, pinned Usul–Tafsir *metadata* evidence links.

This module verifies two independent source chains. No similarity detection,
semantic interpretation, rule application, or religious judgment occurs here.
The only production Usul source pins are the independently accepted Waraqat
U0.2 receipts. Synthetic CI may override those pins by explicit test patching.
"""
from __future__ import annotations

import hashlib
import json
import re

from engines.tafsir.t02 import validate_record
from engines.tafsir.t023 import (
    _validate_candidate, identify_candidates, _validate_passage,
)
from engines.usul.concept_rule_catalog import (
    build_catalog, canonical, index_research_pointers,
)

CONTRACT = "mubin-usul-tafsir-link-v1"
VERSION = "usul-tafsir-link/0.1.1"
LINK_CANDIDATE = "CANDIDATE_RELATED"
LINK_UNDETERMINED = "UNDETERMINED"
LINK_REJECTED = "REJECTED"
OFFSET_UNICODE_CHARS = "UNICODE_CODEPOINT_OFFSETS_IN_IMPORTED_RAW_TEXT"
OFFSET_UTF8_BYTES = "UTF8_BYTES"

# Historical, independently operator-accepted real-source U0.2 pins.
TRUSTED_GRAPH_SHA256 = (
    "72ca6bd80c4e70378dd9d2f1cfc75841024b292d2335479d167add1a8ca6fdb2"
)
TRUSTED_CATALOG_SHA256 = (
    "ab77f297b0b6e4518bd7c8f0b00e13cf38df4c6372d642d76d494a7df1b75ca5"
)
_SHA = re.compile(r"^[a-f0-9]{64}$")
_AUTHORITY_FALSE = (
    "cross_source_semantic_equivalence_verified",
    "rule_application_verified", "scholarly_verified",
    "juristic_inference_allowed", "public_fatwa_authorized",
    "text_included", "p1_admitted",
)


class UsulTafsirLinkError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _need(ok, code):
    if not ok:
        raise UsulTafsirLinkError(code)


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _link_id(payload: dict) -> str:
    return "utl:" + _hash(canonical(payload))[:40]


def verify_tafsir_side(candidate: dict, passage: dict, *,
                       original_raw_text: str) -> dict:
    """Check the *original imported source bytes*, T0.2 and T0.2.3 contracts."""
    _need(type(original_raw_text) is str and bool(original_raw_text),
          "UT012_ORIGINAL_TAFSIR_TEXT_REQUIRED")
    try:
        validate_record(passage, original_text=original_raw_text)
        _validate_passage(passage)
        _validate_candidate(candidate)
    except (ValueError, KeyError, TypeError) as exc:
        raise UsulTafsirLinkError("UT012_TAFSIR_SOURCE_CONTRACT_INVALID") from exc
    _need(candidate.get("passage_id") == passage["interpretation_id"]
          and candidate.get("work_id") == passage["work_id"]
          and candidate.get("quran_reference") == passage["quran_reference"]
          and candidate.get("source_record_id") == passage["source_record_id"]
          and candidate.get("source_sha256") == passage["source_sha256"]
          and candidate.get("passage_span") == passage["evidence_span"],
          "UT012_TAFSIR_PARENT_MISMATCH")
    a, b = candidate["statement_start"], candidate["statement_end"]
    _need(candidate["interpretation_statement"]
          == passage["interpretation_statement"][a:b],
          "UT012_TAFSIR_CANDIDATE_NOT_SOURCE_SLICE")
    expected_raw = [passage["evidence_span"][0] + a,
                    passage["evidence_span"][0] + b]
    _need(candidate["raw_source_span"] == expected_raw
          and original_raw_text[expected_raw[0]:expected_raw[1]]
          == candidate["interpretation_statement"],
          "UT012_TAFSIR_RAW_SOURCE_SPAN_MISMATCH")
    # Self-consistency is not enough: ensure this was emitted by T0.2.3,
    # not an invented classification of a valid source paragraph.
    _need(any(c == candidate for c in identify_candidates(passage)),
          "UT012_TAFSIR_CANDIDATE_NOT_EMITTED")
    return {
        "tafsir_candidate_id": candidate["candidate_id"],
        "tafsir_passage_id": passage["interpretation_id"],
        "tafsir_work_id": passage["work_id"],
        "tafsir_source_record_id": passage["source_record_id"],
        "tafsir_source_sha256": passage["source_sha256"],
        "tafsir_raw_source_span": list(expected_raw),
        "tafsir_evidence_sha256": candidate["evidence_sha256"],
        "tafsir_raw_source_span_unit": OFFSET_UNICODE_CHARS,
        "tafsir_source_binding_verified": True,
    }


def verify_usul_side(catalog: dict, graph: dict, *,
                     rule_candidate_id: str, research_pointer_id: str,
                     occurrence_ids=None) -> dict:
    """Require an independently accepted graph and canonical catalog bytes."""
    _need(type(catalog) is dict and type(graph) is dict,
          "UT012_USUL_INPUT_INVALID")
    _need(graph.get("graph_sha256") == TRUSTED_GRAPH_SHA256,
          "UT012_GRAPH_EXTERNAL_PIN_MISMATCH")
    _need(catalog.get("catalog_sha256") == TRUSTED_CATALOG_SHA256,
          "UT012_CATALOG_EXTERNAL_PIN_MISMATCH")
    _need(catalog.get("stage08_graph_sha256") == TRUSTED_GRAPH_SHA256,
          "UT012_CATALOG_GRAPH_PIN_MISMATCH")
    try:
        pointers = index_research_pointers(graph, TRUSTED_GRAPH_SHA256)
        # Rebuild from the *actual* source-bound graph and all catalog
        # concepts/rules/relations; a self-chosen hash is not sufficient.
        manifest = {
            "schema_version": "u0.2.0",
            "concepts": catalog["concepts"],
            "rule_candidates": [
                {k: rule[k] for k in (
                    "id", "pointer_id", "if_concepts", "unless_concepts",
                    "then_concept", "review_status")}
                for rule in catalog["rule_candidates"]
            ],
            "relations": catalog["relations"],
        }
        rebuilt = build_catalog(graph, TRUSTED_GRAPH_SHA256, manifest)
    except (ValueError, KeyError, TypeError, RecursionError) as exc:
        raise UsulTafsirLinkError("UT012_USUL_CATALOG_OR_GRAPH_INVALID") from exc
    _need(catalog == rebuilt, "UT012_CATALOG_CANONICAL_DIGEST_INVALID")
    matches = [r for r in rebuilt["rule_candidates"]
               if r["id"] == rule_candidate_id]
    _need(len(matches) == 1, "UT012_RULE_CANDIDATE_NOT_IN_CATALOG")
    rule = matches[0]
    _need(rule.get("review_status") == "UNASSESSED"
          and research_pointer_id == rule["pointer_id"]
          and research_pointer_id in pointers,
          "UT012_RESEARCH_POINTER_INVALID")
    anchor = pointers[research_pointer_id]
    # The research pointer's reference_id can be the historical research
    # question (pilot:rule-amr-default), not the U0.2 candidate rule ID.
    _need(rule["research_anchor"] == anchor,
          "UT012_RULE_POINTER_REFERENCE_MISMATCH")
    _need(type(occurrence_ids) in (list, type(None)),
          "UT012_OCCURRENCE_ARRAY_INVALID")
    occurrence_ids = [] if occurrence_ids is None else occurrence_ids
    _need(len(occurrence_ids) <= 16
          and len(occurrence_ids) == len(set(
              x for x in occurrence_ids if type(x) is str))
          and all(type(x) is str for x in occurrence_ids),
          "UT012_OCCURRENCE_IDS_INVALID")
    query_nodes = [n for n in graph["nodes"]
                   if n.get("kind") == "SEARCH_QUERY"
                   and n.get("query_id") == anchor["query_id"]
                   and n.get("witness_id") == anchor["source_id"]]
    _need(len(query_nodes) == 1, "UT012_QUERY_BINDING_INVALID")
    query = query_nodes[0]
    section_nodes = [n for n in graph["nodes"]
                     if n.get("kind") == "PINNED_SECTION"
                     and n.get("source_id") == anchor["source_id"]
                     and n.get("section_sha256") == anchor["section_sha256"]]
    _need(len(section_nodes) == 1, "UT012_SECTION_BINDING_INVALID")
    section = section_nodes[0]
    _need(section.get("offset_basis") in ("utf8_export", "extracted_section")
          and type(section.get("byte_length")) is int,
          "UT012_SECTION_BYTE_COORDINATES_INVALID")
    _need(any(e.get("kind") == "QUERY_SCOPED_TO_SECTION"
              and e.get("from") == query["id"]
              and e.get("to") == section["id"] for e in graph["edges"]),
          "UT012_QUERY_SECTION_EDGE_MISSING")
    nodes = {n["id"]: n for n in graph["nodes"]}
    for oid in occurrence_ids:
        node = nodes.get(oid)
        _need(node is not None and node.get("kind") == "TEXT_OCCURRENCE"
              and node.get("section_id") == section["id"]
              and node.get("source_coordinate_basis") == section["offset_basis"]
              and type(node.get("section_byte_start")) is int
              and type(node.get("section_byte_end_exclusive")) is int
              and 0 <= node["section_byte_start"] <
                  node["section_byte_end_exclusive"] <= section["byte_length"]
              and type(node.get("original_span_sha256")) is str
              and _SHA.fullmatch(node["original_span_sha256"]) is not None
              and node.get("text_included") is False
              and node.get("semantic_classification") == "NOT_EVALUATED",
              "UT012_OCCURRENCE_SECTION_OR_SPAN_INVALID")
        _need(any(e.get("kind") == "QUERY_LOCATES_OCCURRENCE"
                  and e.get("from") == query["id"] and e.get("to") == oid
                  and e.get("classification") == "EXACT_LITERAL_ONLY"
                  and e.get("semantic_equivalence_verified") is False
                  for e in graph["edges"]),
              "UT012_OCCURRENCE_NOT_FROM_RULE_QUERY")
    return {
        "usul_rule_candidate_id": rule_candidate_id,
        "usul_catalog_sha256": TRUSTED_CATALOG_SHA256,
        "usul_stage08_graph_sha256": TRUSTED_GRAPH_SHA256,
        "usul_research_pointer_id": research_pointer_id,
        "usul_source_id": anchor["source_id"],
        "usul_section_sha256": anchor["section_sha256"],
        "usul_occurrence_ids": sorted(occurrence_ids),
        "usul_occurrence_span_unit": OFFSET_UTF8_BYTES,
        "usul_source_binding_verified": True,
    }


def build_link(*, quran_reference: str, tafsir_candidate: dict,
               tafsir_passage: dict, tafsir_original_raw_text: str,
               usul_catalog: dict, usul_graph: dict, rule_candidate_id: str,
               research_pointer_id: str, occurrence_ids=None,
               candidacy_reason: str | None = None,
               candidacy_scope: str | None = None) -> dict:
    """Produce a candidate or UNDETERMINED link, never a legal rule."""
    _need(type(quran_reference) is str
          and quran_reference == tafsir_candidate.get("quran_reference")
          and quran_reference == tafsir_passage.get("quran_reference"),
          "UT012_QURAN_REFERENCE_MISMATCH")
    t = verify_tafsir_side(tafsir_candidate, tafsir_passage,
                           original_raw_text=tafsir_original_raw_text)
    u = verify_usul_side(usul_catalog, usul_graph,
                         rule_candidate_id=rule_candidate_id,
                         research_pointer_id=research_pointer_id,
                         occurrence_ids=occurrence_ids)
    _need((candidacy_reason is None and candidacy_scope is None)
          or (type(candidacy_reason) is str
              and 1 <= len(candidacy_reason.strip()) <= 512
              and type(candidacy_scope) is str
              and 1 <= len(candidacy_scope.strip()) <= 128),
          "UT012_CANDIDACY_REASON_AND_SCOPE_REQUIRED")
    status = LINK_CANDIDATE if candidacy_reason is not None else LINK_UNDETERMINED
    content = {
        "contract": CONTRACT, "version": VERSION, "quran_reference": quran_reference,
        "link_status": status, "link_method": "EVIDENCE_CHAIN_VERIFICATION_ONLY",
        "verification_status": "UNVERIFIED",
        "candidacy_reason": candidacy_reason, "candidacy_scope": candidacy_scope,
        **t, **u,
        "offset_units_independent": [OFFSET_UNICODE_CHARS, OFFSET_UTF8_BYTES],
        **{flag: False for flag in _AUTHORITY_FALSE},
        "rights_status": "legal_review_pending",
    }
    return {**content, "link_id": _link_id(content)}


def reject_link(*, quran_reference: str, rejection_reason: str) -> dict:
    """Record a rejection, never an evidence-bound candidate."""
    _need(type(quran_reference) is str and bool(quran_reference)
          and type(rejection_reason) is str
          and 1 <= len(rejection_reason.strip()) <= 512,
          "UT012_REJECTION_INPUT_INVALID")
    fields = {
        "contract": CONTRACT, "version": VERSION,
        "quran_reference": quran_reference, "link_status": LINK_REJECTED,
        "rejection_reason": rejection_reason, "verification_status": "UNVERIFIED",
        **{flag: False for flag in _AUTHORITY_FALSE},
        "rights_status": "legal_review_pending",
    }
    return {**fields, "link_id": "utl-rejected:" + _hash(canonical(fields))[:40]}


def validate_link(record: dict, *, tafsir_candidate: dict | None = None,
                  tafsir_passage: dict | None = None,
                  tafsir_original_raw_text: str | None = None,
                  usul_catalog: dict | None = None,
                  usul_graph: dict | None = None) -> None:
    """Rebuild from *independent* sources and compare ALL fields exactly."""
    _need(type(record) is dict and record.get("contract") == CONTRACT
          and record.get("version") == VERSION,
          "UT012_LINK_CONTRACT_INVALID")
    _need(all(record.get(flag) is False for flag in _AUTHORITY_FALSE),
          "UT012_UNAUTHORIZED_STATUS_PROMOTION")
    if record.get("link_status") == LINK_REJECTED:
        rebuilt = reject_link(quran_reference=record.get("quran_reference"),
                              rejection_reason=record.get("rejection_reason"))
    else:
        _need(record.get("link_status") in
              (LINK_CANDIDATE, LINK_UNDETERMINED),
              "UT012_LINK_STATUS_INVALID")
        rebuilt = build_link(
            quran_reference=record.get("quran_reference"),
            tafsir_candidate=tafsir_candidate,
            tafsir_passage=tafsir_passage,
            tafsir_original_raw_text=tafsir_original_raw_text,
            usul_catalog=usul_catalog, usul_graph=usul_graph,
            rule_candidate_id=record.get("usul_rule_candidate_id"),
            research_pointer_id=record.get("usul_research_pointer_id"),
            occurrence_ids=record.get("usul_occurrence_ids"),
            candidacy_reason=record.get("candidacy_reason"),
            candidacy_scope=record.get("candidacy_scope"),
        )
    _need(record == rebuilt, "UT012_STORED_LINK_CHANGED")
