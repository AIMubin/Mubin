"""E2E-01.2: semantic linkage between a verse observation and a Usul rule.

Records a researcher observation, links it to an al-Waraqat rule as PROPOSED,
and assesses the diverting indicator in three distinct cases:
  (a) PRESENT, (b) NOT_OBSERVED_IN_SCOPE, (c) NOT_EXAMINED
(b) does not mean the indicator is confirmed absent.
"""
from __future__ import annotations
from typing import Any

CONTRACT = "mubin-semantic-linkage-v0.1"
VERSION = "semantic-linkage/0.1.0"
INDICATOR_CASES = frozenset(("PRESENT", "NOT_OBSERVED_IN_SCOPE", "NOT_EXAMINED"))


class LinkageError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _need(ok, code):
    if not ok:
        raise LinkageError(code)


def build_linkage(*, verse_ref: str, verse_text_source: str,
    verse_text_sha256: str, imperative_word: str, imperative_position: str,
    rule_id: str, rule_expression: str, rule_source: str,
    evidence_head_sha256: str, indicator_case: str,
    indicator_detail: str = "", indicator_scope: dict | None = None,
    supporting_notes: str = "", opposing_notes: str = "") -> dict[str, Any]:
    _need(type(verse_ref) is str and ":" in verse_ref, "VERSE_REF_INVALID")
    _need(type(verse_text_source) is str, "TEXT_SOURCE_INVALID")
    _need(type(verse_text_sha256) is str and len(verse_text_sha256) == 64,
          "TEXT_SHA_INVALID")
    _need(type(imperative_word) is str and len(imperative_word) > 0,
          "IMPERATIVE_WORD_INVALID")
    _need(type(imperative_position) is str, "IMPERATIVE_POSITION_INVALID")
    _need(type(rule_id) is str and len(rule_id) > 0, "RULE_ID_INVALID")
    _need(type(rule_expression) is str, "RULE_EXPRESSION_INVALID")
    _need(type(rule_source) is str, "RULE_SOURCE_INVALID")
    _need(type(evidence_head_sha256) is str and len(evidence_head_sha256) == 64,
          "EVIDENCE_HEAD_INVALID")
    _need(indicator_case in INDICATOR_CASES, "INDICATOR_CASE_INVALID")
    states = {"PRESENT": "INDICATOR_PRESENT_REQUIRES_ASSESSMENT",
              "NOT_OBSERVED_IN_SCOPE": "INDICATOR_NOT_OBSERVED_IN_CHECKED_SCOPE",
              "NOT_EXAMINED": "INDICATOR_NOT_EXAMINED"}
    return {"contract": CONTRACT, "version": VERSION,
        "linkage_state": states[indicator_case],
        "verse": {"reference": verse_ref, "text_source": verse_text_source,
            "text_sha256": verse_text_sha256,
            "imperative_word": imperative_word,
            "imperative_position": imperative_position},
        "usul_rule": {"rule_id": rule_id, "expression": rule_expression,
            "source_work": rule_source},
        "evidence_head_sha256": evidence_head_sha256,
        "diverting_indicator": {"case": indicator_case,
            "detail": indicator_detail, "scope": indicator_scope or {},
            "not_observed_does_not_mean_absent": indicator_case == "NOT_OBSERVED_IN_SCOPE"},
        "supporting_evidence": supporting_notes,
        "opposing_evidence": opposing_notes,
        "semantic_relationship": "PROPOSED_NOT_CERTIFIED",
        "text_included": False, "scholarly_verified": False,
        "edition_verified": False, "rights_status": "legal_review_pending",
        "publication_allowed": False, "juristic_inference_allowed": False,
        "public_fatwa_authorized": False, "p1_admitted": False}


def assess_indicator_scope(*, sources_examined: list,
    indicators_found: list, sources_not_examined: list) -> dict[str, Any]:
    _need(type(sources_examined) is list, "SCOPE_SOURCES_INVALID")
    _need(type(indicators_found) is list, "SCOPE_INDICATORS_INVALID")
    _need(type(sources_not_examined) is list, "SCOPE_UNEXAMINED_INVALID")
    if indicators_found:
        case = "PRESENT"
        detail = "; ".join(indicators_found)
    elif sources_examined:
        case = "NOT_OBSERVED_IN_SCOPE"
        detail = f"examined {len(sources_examined)} source(s)"
    else:
        case = "NOT_EXAMINED"
        detail = "no diverting-indicator search has been performed"
    return {"case": case, "detail": detail,
        "scope": {"sources_examined": sources_examined,
            "indicators_found": indicators_found,
            "sources_not_examined": sources_not_examined,
            "absence_not_confirmed": case != "PRESENT"}}
