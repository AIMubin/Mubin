"""E2E-01.2: BOUNDED, operator-supplied verse-to-Usul research proposal.

Does NOT read or attest Quran/tafsir bytes, identify Arabic morphology, or
discover the presence/absence of a diverting indicator automatically.
Use E2E-01.1's signed operator lookup to bind this declaration to the
actual evidence head and Quran coordinate; there is no independent
scholarly, publication, legal or juristic authority in this record.
"""
from __future__ import annotations

import re
from typing import Any

from engines.quran.research.qualification import _valid_reference, QualificationError
from engines.usul.pilots.amr_default import example_bundle

CONTRACT = "mubin-semantic-linkage-v0.1"
VERSION = "semantic-linkage/0.1.1"
INDICATOR_CASES = frozenset(("PRESENT", "NOT_OBSERVED_IN_SCOPE", "NOT_EXAMINED"))
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ARABIC_WORD = re.compile(r"[\u0621-\u064A\u064B-\u065F\u0670\u0671-\u06D3\u0640]{1,40}\Z")
MAX_SCOPE = 64


class LinkageError(ValueError):
    """Only stable refusal codes; no private text, credentials or file paths."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _need(ok: bool, code: str):
    if not ok:
        raise LinkageError(code)


def _label(v, *, code: str, max_len: int = 160, empty: bool = False):
    _need(type(v) is str and (empty or bool(v.strip()))
          and len(v) <= max_len and "\x00" not in v
          and "\n" not in v and "\r" not in v, code)
    return v


def _ids(items, code: str):
    _need(type(items) is list and len(items) <= MAX_SCOPE, code)
    for item in items:
        _label(item, code=code, max_len=128)
    _need(len(items) == len(set(items)), code)
    return items


def assess_indicator_scope(*, sources_examined: list,
                           indicators_found: list,
                           sources_not_examined: list) -> dict[str, Any]:
    """Check OPERATOR-DECLARED review scope; no automatic text examination."""
    checked = _ids(sources_examined, "SCOPE_SOURCES_INVALID")
    found = _ids(indicators_found, "SCOPE_INDICATORS_INVALID")
    unexamined = _ids(sources_not_examined, "SCOPE_UNEXAMINED_INVALID")
    _need(not (set(checked) & set(unexamined)), "SCOPE_OVERLAP_INVALID")
    _need(bool(checked) or not found, "INDICATOR_WITHOUT_EXAMINATION")
    if found:
        case = "PRESENT"
    elif checked:
        case = "NOT_OBSERVED_IN_SCOPE"
    else:
        case = "NOT_EXAMINED"
    return {
        "case": case,
        "detail": ("operator reported an indicator" if found else
                   (f"operator examined {len(checked)} source(s) without reporting an indicator"
                    if checked else "no sources examined")),
        "scope": {
            "sources_examined": list(checked),
            "indicators_found": list(found),
            "sources_not_examined": list(unexamined),
            "sources_examined_count": len(checked),
            "sources_not_examined_count": len(unexamined),
            # None of the cases attests universal absence; even PRESENT
            # tells us only that an operator REPORTED a positive finding.
            "absence_not_confirmed": True,
            "examination_evidence_independently_verified": False,
        },
    }


def build_linkage(*, verse_ref: str, verse_text_source: str,
                  verse_text_sha256: str, imperative_word: str,
                  imperative_position: str, rule_id: str,
                  rule_expression: str, rule_source: str,
                  evidence_head_sha256: str, indicator_case: str,
                  indicator_detail: str = "",
                  indicator_scope: dict | None = None,
                  supporting_notes: str = "",
                  opposing_notes: str = "") -> dict[str, Any]:
    """Make an *unassessed source-scoped proposal*, NOT a verified linkage.

    Hash/source IDs are operator assertions until a trusted E2E-01.1
    retrieval binds the evidence head and coordinates. Exact verse-word
    byte correspondence remains NOT_VERIFIED even after that binding.
    """
    try:
        _valid_reference(verse_ref)
    except QualificationError as exc:
        raise LinkageError("VERSE_REF_INVALID") from exc
    _label(verse_text_source, code="TEXT_SOURCE_INVALID", max_len=128)
    _need(type(verse_text_sha256) is str
          and _SHA.fullmatch(verse_text_sha256) is not None,
          "TEXT_SHA_INVALID")
    _need(type(imperative_word) is str
          and _ARABIC_WORD.fullmatch(imperative_word) is not None,
          "IMPERATIVE_WORD_INVALID")
    _label(imperative_position, code="IMPERATIVE_POSITION_INVALID", max_len=120)
    _label(rule_source, code="RULE_SOURCE_INVALID", max_len=120)
    _need(type(evidence_head_sha256) is str
          and _SHA.fullmatch(evidence_head_sha256) is not None,
          "EVIDENCE_HEAD_INVALID")

    # Restrict to the ONE actually implemented al-Waraqat pilot. An
    # arbitrary caller-provided rule string must not impersonate that rule.
    canonical = example_bundle()["rules"][0]
    _need(rule_id == canonical["id"]
          and rule_expression == canonical["expression"]
          and rule_source == "الورقات", "USUL_RULE_OUT_OF_SCOPE")

    _need(type(indicator_case) is str and indicator_case in INDICATOR_CASES,
          "INDICATOR_CASE_INVALID")
    _need(type(indicator_scope) is dict
          and set(indicator_scope) == {
              "sources_examined", "indicators_found", "sources_not_examined"},
          "INDICATOR_SCOPE_INVALID")
    assessed = assess_indicator_scope(**indicator_scope)
    _need(indicator_case == assessed["case"],
          "INDICATOR_SCOPE_CASE_MISMATCH")
    _label(indicator_detail, code="INDICATOR_DETAIL_INVALID",
           max_len=240, empty=True)
    _label(supporting_notes, code="SUPPORTING_NOTES_INVALID",
           max_len=240, empty=True)
    _label(opposing_notes, code="OPPOSING_NOTES_INVALID",
           max_len=240, empty=True)
    states = {"PRESENT": "INDICATOR_PRESENT_REQUIRES_ASSESSMENT",
              "NOT_OBSERVED_IN_SCOPE": "INDICATOR_NOT_OBSERVED_IN_CHECKED_SCOPE",
              "NOT_EXAMINED": "INDICATOR_NOT_EXAMINED"}
    return {
        "contract": CONTRACT, "version": VERSION,
        "linkage_state": states[indicator_case],
        "verse": {
            "reference": verse_ref, "text_source": verse_text_source,
            "text_sha256": verse_text_sha256,
            "text_sha256_verified_against_verse": False,
            "imperative_word": imperative_word,
            "imperative_word_origin": "OPERATOR_SUPPLIED_NOT_BYTE_VERIFIED",
            "imperative_position": imperative_position,
        },
        "usul_rule": {
            "rule_id": canonical["id"], "expression": canonical["expression"],
            "source_work": "الورقات", "formalization_status": "RESEARCH_PILOT",
        },
        "evidence_head_sha256": evidence_head_sha256,
        "evidence_head_independently_verified_here": False,
        "diverting_indicator": {
            "case": assessed["case"],
            "detail": indicator_detail or assessed["detail"],
            "scope": assessed["scope"],
            "not_observed_does_not_mean_absent": True,
            "automatic_detection_performed": False,
        },
        "supporting_evidence": supporting_notes,
        "opposing_evidence": opposing_notes,
        "operator_notes_independently_verified": False,
        "semantic_relationship": "PROPOSED_NOT_CERTIFIED",
        "semantic_equivalence_verified": False,
        "text_included": False, "source_authenticated": False,
        "scholarly_verified": False, "edition_verified": False,
        "rights_status": "legal_review_pending", "rights_verified": False,
        "publication_allowed": False, "redistribution_approved": False,
        "juristic_inference_allowed": False,
        "public_fatwa_authorized": False, "p1_admitted": False,
    }
