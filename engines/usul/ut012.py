"""UT-01.2: UsulTafsirLink — evidence-gated cross-engine contract.

Binds one T0.2.3 tafsir candidate to one U0.2 rule candidate ONLY when both
source-evidence chains verify independently. The two engines use different
offset systems (Unicode chars vs UTF-8 bytes); spans are recorded with their
own basis and are never compared or converted here. The link never asserts
meaning, rule application, or any scholarly/legal conclusion: authority
flags are structural constants (False), and attempts to raise them fail.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from engines.tafsir.t023 import TafsirT02Error
from engines.usul.concept_rule_catalog import (
    CatalogError, canonical, index_research_pointers, sha as _sha_of_canonical,
)

CONTRACT = "mubin-usul-tafsir-link-v1"
VERSION = "usul-tafsir-link/0.1.0"

LINK_CANDIDATE = "CANDIDATE_RELATED"
LINK_UNDETERMINED = "UNDETERMINED"
LINK_REJECTED = "REJECTED"
LINK_STATUSES = frozenset((LINK_CANDIDATE, LINK_UNDETERMINED, LINK_REJECTED))

# deliberately absent by design: SUPPORTED_RULE / APPLICABLE_RULE /
# OBLIGATION_DERIVED imply a juridical conclusion the contract cannot make.

# T0.2 uses codepoint offsets into imported raw text; Usul Stage07/08 uses
# UTF-8 byte offsets into original source files. Never compare or convert.
OFFSET_UNICODE_CHARS = "UNICODE_CODEPOINT_OFFSETS_IN_IMPORTED_RAW_TEXT"
OFFSET_UTF8_BYTES = "UTF8_BYTES"

_TAFSIR_STATUS_REQUIRED = "UNVERIFIED"


class UsulTafsirLinkError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _need(ok, code):
    if not ok:
        raise UsulTafsirLinkError(code)


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verify_tafsir_side(candidate: dict, passage: dict) -> dict:
    """Recompute the tafsir candidate's evidence chain inside its passage.

    Returns binding metadata. Raises on any forgery or mismatch.
    """
    _need(type(candidate) is dict and type(passage) is dict,
          "UT012_TAFSIR_INPUT_INVALID")
    _need(candidate.get("passage_id") == passage.get("interpretation_id"),
          "UT012_PASSAGE_ID_MISMATCH")
    _need(candidate.get("source_record_id") == passage.get("source_record_id"),
          "UT012_SOURCE_RECORD_MISMATCH")
    _need(candidate.get("source_sha256") == passage.get("source_sha256"),
          "UT012_SOURCE_SHA_MISMATCH")
    _need(candidate.get("quran_reference") == passage.get("quran_reference"),
          "UT012_REFERENCE_MISMATCH")
    statement = passage.get("interpretation_statement")
    _need(type(statement) is str and statement, "UT012_PASSAGE_TEXT_EMPTY")
    s0, s1 = candidate.get("statement_start"), candidate.get("statement_end")
    _need(type(s0) is int and type(s1) is int and 0 <= s0 < s1 <= len(statement),
          "UT012_SPAN_OUT_OF_BOUNDS")
    snippet = statement[s0:s1]
    _need(_sha_text(snippet) == candidate.get("evidence_sha256"),
          "UT012_EVIDENCE_DIGEST_MISMATCH")
    _need(candidate.get("interpretation_statement") == snippet,
          "UT012_STATEMENT_NOT_EXACT_SLICE")
    _need(candidate.get("verification_status") == _TAFSIR_STATUS_REQUIRED,
          "UT012_CANDIDATE_NOT_UNVERIFIED")
    passage_span = passage.get("evidence_span")
    _need(type(passage_span) is list and len(passage_span) == 2
          and 0 <= passage_span[0] < passage_span[1],
          "UT012_PASSAGE_SPAN_INVALID")
    _need(passage.get("evidence_span_unit") in (None, OFFSET_UNICODE_CHARS),
          "UT012_PASSAGE_OFFSET_UNIT_INVALID")
    return {
        "tafsir_candidate_id": candidate["candidate_id"],
        "tafsir_passage_id": passage["interpretation_id"],
        "tafsir_work_id": passage["work_id"],
        "tafsir_source_record_id": passage["source_record_id"],
        "tafsir_source_sha256": passage["source_sha256"],
        "tafsir_raw_source_span": [s0, s1],
        "tafsir_evidence_sha256": candidate["evidence_sha256"],
        "tafsir_raw_source_span_unit": OFFSET_UNICODE_CHARS,
        "tafsir_source_binding_verified": True,
    }


def _graph_self_digest(graph: dict) -> str:
    from engines.usul.concept_rule_catalog import GRAPH_FIELDS
    _need(type(graph) is dict and all(k in graph for k in GRAPH_FIELDS),
          "UT012_GRAPH_CONTRACT_INVALID")
    payload = {k: graph[k] for k in GRAPH_FIELDS}
    payload["status"] = "EVIDENCE_CONTEXT_GRAPH_PASS"
    return hashlib.sha256(canonical(payload)).hexdigest()


def verify_usul_side(catalog: dict, graph: dict, *,
                     rule_candidate_id: str, research_pointer_id: str,
                     occurrence_ids=None,
                     expected_catalog_sha256: str | None = None,
                     expected_graph_sha256: str | None = None) -> dict:
    """Verify the usul side: catalog/graph digests, rule candidate, pointer
    navigation chain, and pinned section. Raises on any failure."""
    _need(type(catalog) is dict and type(graph) is dict,
          "UT012_USUL_INPUT_INVALID")
    graph_digest = graph.get("graph_sha256")
    recomputed = _graph_self_digest(graph)
    _need(graph_digest == recomputed,
          "UT012_GRAPH_SELF_DIGEST_MISMATCH")
    if expected_graph_sha256 is not None:
        _need(graph_digest == expected_graph_sha256,
              "UT012_GRAPH_DIGEST_NOT_THE_ACCEPTED_ONE")
    if expected_catalog_sha256 is not None:
        # The catalog builder stamps its own digest; re-deriving it here would
        # duplicate builder logic. We require the builder's stamp to match the
        # accepted reference AND the stamp's graph binding to match the graph.
        cat_digest = catalog.get("catalog_sha256")
        _need(type(cat_digest) is str, "UT012_CATALOG_DIGEST_MISSING")
        _need(cat_digest == expected_catalog_sha256,
              "UT012_CATALOG_DIGEST_NOT_THE_ACCEPTED_ONE")
    _need(catalog.get("stage08_graph_sha256") == graph_digest,
          "UT012_CATALOG_GRAPH_BINDING_MISMATCH")
    rules = catalog.get("rule_candidates") or []
    rule = next((r for r in rules if r.get("id") == rule_candidate_id), None)
    _need(rule is not None, "UT012_RULE_CANDIDATE_NOT_IN_CATALOG")
    _need(rule.get("review_status") == "UNASSESSED",
          "UT012_RULE_CANDIDATE_NOT_UNASSESSED")
    _need(research_pointer_id == rule.get("pointer_id"),
          "UT012_RESEARCH_POINTER_MISMATCH")
    pointers = index_research_pointers(graph, graph_digest)
    _need(rule.get("pointer_id") in pointers,
          "UT012_RESEARCH_POINTER_NOT_IN_GRAPH")
    ptr = pointers[rule["pointer_id"]]
    _need(ptr.get("query_id") and ptr.get("source_id")
          and ptr.get("section_sha256"),
          "UT012_POINTER_CHAIN_INCOMPLETE")
    if occurrence_ids:
        nodes = graph.get("nodes")
        _need(type(nodes) is list, "UT012_GRAPH_NODES_INVALID")
        by_id = {n.get("id"): n for n in nodes}
        for oid in occurrence_ids:
            node = by_id.get(oid)
            _need(node is not None
                  and node.get("kind") == "TEXT_OCCURRENCE",
                  "UT012_OCCURRENCE_ID_INVALID")
    return {
        "usul_rule_candidate_id": rule_candidate_id,
        "usul_catalog_sha256": expected_catalog_sha256
        or "self-consistent-not-pinned",
        "usul_stage08_graph_sha256": graph_digest,
        "usul_research_pointer_id": rule["pointer_id"],
        "usul_source_id": ptr["source_id"],
        "usul_section_sha256": ptr["section_sha256"],
        "usul_occurrence_ids": list(occurrence_ids or []),
        "usul_occurrence_span_unit": OFFSET_UTF8_BYTES,
        "usul_source_binding_verified": True,
    }


def build_link(*, quran_reference: str,
               tafsir_candidate: dict, tafsir_passage: dict,
               usul_catalog: dict, usul_graph: dict,
               rule_candidate_id: str, research_pointer_id: str,
               occurrence_ids=None,
               expected_catalog_sha256: str | None = None,
               expected_graph_sha256: str | None = None,
               candidacy_reason: str | None = None,
               candidacy_scope: str | None = None) -> dict:
    """Build one UsulTafsirLink. Fail-closed on any forged side.

    CANDIDATE_RELATED requires an explicit operator-supplied candidacy_reason
    (recorded verbatim; the contract never infers one from text).
    Otherwise the link is UNDETERMINED when both chains verify.
    """
    _need(type(quran_reference) is str and ":" in quran_reference,
          "UT012_REFERENCE_INVALID")
    _need(tafsir_candidate.get("quran_reference") == quran_reference,
          "UT012_QURAN_REFERENCE_MISMATCH")
    _need(tafsir_passage.get("quran_reference") == quran_reference,
          "UT012_QURAN_REFERENCE_MISMATCH")
    t_side = verify_tafsir_side(tafsir_candidate, tafsir_passage)
    u_side = verify_usul_side(usul_catalog, usul_graph,
                              rule_candidate_id=rule_candidate_id,
                              research_pointer_id=research_pointer_id,
                              occurrence_ids=occurrence_ids,
                              expected_catalog_sha256=expected_catalog_sha256,
                              expected_graph_sha256=expected_graph_sha256)
    _need(t_side["tafsir_work_id"] and u_side["usul_source_id"],
          "UT012_SIDE_METADATA_INCOMPLETE")
    if candidacy_reason is not None:
        _need(type(candidacy_reason) is str
              and 0 < len(candidacy_reason) <= 512,
              "UT012_CANDIDACY_REASON_INVALID")
        link_status = LINK_CANDIDATE
    else:
        link_status = LINK_UNDETERMINED
    link_id = "utl:" + _sha_text("|".join((
        t_side["tafsir_candidate_id"], u_side["usul_rule_candidate_id"],
        u_side["usul_stage08_graph_sha256"],
        t_side["tafsir_evidence_sha256"],
        u_side["usul_section_sha256"], link_status)))[:40]
    return {
        "contract": CONTRACT, "version": VERSION,
        "link_id": link_id,
        "quran_reference": quran_reference,
        "link_status": link_status,
        "link_method": "EVIDENCE_CHAIN_VERIFICATION_ONLY",
        "verification_status": "UNVERIFIED",
        "candidacy_reason": candidacy_reason,
        "candidacy_scope": candidacy_scope,
        **t_side, **u_side,
        "offset_units_independent": (
            t_side["tafsir_raw_source_span_unit"],
            u_side["usul_occurrence_span_unit"]),
        "cross_source_semantic_equivalence_verified": False,
        "rule_application_verified": False,
        "scholarly_verified": False,
        "juristic_inference_allowed": False,
        "public_fatwa_authorized": False,
        "text_included": False,
        "p1_admitted": False,
        "rights_status": "legal_review_pending",
    }


def reject_link(*, quran_reference: str, rejection_reason: str) -> dict:
    """Record a deterministic rejection with its reason (no side data)."""
    _need(type(rejection_reason) is str and 0 < len(rejection_reason) <= 512,
          "UT012_REJECTION_REASON_INVALID")
    return {
        "contract": CONTRACT, "version": VERSION,
        "link_id": "utl-rejected:" + _sha_text(
            quran_reference + "|" + rejection_reason)[:40],
        "quran_reference": quran_reference,
        "link_status": LINK_REJECTED,
        "rejection_reason": rejection_reason,
        "verification_status": "UNVERIFIED",
        "cross_source_semantic_equivalence_verified": False,
        "rule_application_verified": False,
        "scholarly_verified": False,
        "juristic_inference_allowed": False,
        "public_fatwa_authorized": False,
        "text_included": False,
        "p1_admitted": False,
        "rights_status": "legal_review_pending",
    }


def validate_link(record: dict, *, tafsir_candidate: dict,
                  tafsir_passage: dict, usul_catalog: dict,
                  usul_graph: dict) -> None:
    """Re-verify a stored link against its sources; forgery raises."""
    _need(type(record) is dict and record.get("contract") == CONTRACT,
          "UT012_RECORD_CONTRACT_INVALID")
    _need(record.get("link_status") in LINK_STATUSES,
          "UT012_LINK_STATUS_INVALID")
    for flag in ("cross_source_semantic_equivalence_verified",
                 "rule_application_verified", "scholarly_verified",
                 "juristic_inference_allowed", "public_fatwa_authorized",
                 "text_included"):
        _need(record.get(flag) is False,
              f"UT012_FORBIDDEN_FLAG_TRUE_{flag}")
    t_side = verify_tafsir_side(tafsir_candidate, tafsir_passage)
    u_side = verify_usul_side(usul_catalog, usul_graph,
                              rule_candidate_id=record["usul_rule_candidate_id"],
                              research_pointer_id=record["usul_research_pointer_id"],
                              occurrence_ids=record.get("usul_occurrence_ids") or None)
    _need(record.get("link_id") == "utl:" + _sha_text("|".join((
        t_side["tafsir_candidate_id"], u_side["usul_rule_candidate_id"],
        u_side["usul_stage08_graph_sha256"], t_side["tafsir_evidence_sha256"],
        u_side["usul_section_sha256"], record["link_status"])))[:40],
        "UT012_LINK_ID_MISMATCH")
