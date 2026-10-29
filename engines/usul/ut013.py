"""UT-01.3: conservative Usul-Tafsir candidate matching over pinned sources.

Separates literal EXACT ties from folded FOLDED_CANDIDATE ties, records
original offsets (Unicode codepoints for tafsir, UTF-8 bytes for usul) and
digests per side, and never treats a lexical marker as proof of a sharia
command form, nor an unobserved marker as proof of absence. Every accepted
candidate link passes through UT-01.2 build_link AND validate_link; the
contract is never bypassed.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from engines.usul.ut012 import (
    LINK_CANDIDATE, LINK_UNDETERMINED, OFFSET_UTF8_BYTES,
    UsulTafsirLinkError, build_link, validate_link,
)
from engines.tafsir.t02 import SPAN_UNIT as TAFSIR_SPAN_UNIT

CONTRACT = "mubin-usul-tafsir-matching-v1"
VERSION = "usul-tafsir-matching/0.1.0"
TIE_EXACT = "EXACT"
TIE_FOLDED = "FOLDED_CANDIDATE"
TIE_NONE = "NONE"
QARINAH_PRESENT = "PRESENT_AS_TEXT"
QARINAH_NOT_OBSERVED = "NOT_OBSERVED_IN_SCOPE"
QARINAH_NOTE = ("absence of the marker in the searched span is not evidence "
                "that no qarinah exists in the source")
_AR_MARKS = re.compile(r"[\u064B-\u065F\u0670\u0640]")


def _need(ok, code):
    if not ok:
        raise UsulTafsirLinkError(code)


def _fold(text: str) -> str:
    text = _AR_MARKS.sub("", text)
    text = re.sub(r"[\u0623\u0625\u0622]", "\u0627", text)
    text = text.replace("\u0649", "\u064a")
    return text


def _digest_text(text) -> str:
    data = text if isinstance(text, bytes) else text.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def locate_term(text: str, term: str) -> dict:
    """EXACT vs FOLDED_CANDIDATE location of term inside text (codepoints)."""
    _need(type(text) is str and type(term) is str, "UT013_LOCATE_INPUT_INVALID")
    exact = text.find(term)
    if exact >= 0:
        return {"tie": TIE_EXACT, "span": [exact, exact + len(term)],
                "digest": _digest_text(text[exact:exact + len(term)])}
    ftext, fterm = _fold(text), _fold(term)
    fpos = ftext.find(fterm)
    if fpos >= 0 and len(fterm) >= 3:
        return {"tie": TIE_FOLDED, "span": None,
                "folded_offset": fpos,
                "digest": _digest_text((str(fpos) + "|" + fterm).encode("utf-8"))}
    return {"tie": TIE_NONE, "span": None}


def locate_term_utf8_bytes(raw_bytes: bytes, term: str) -> dict:
    """Locate term in a UTF-8 byte source; spans are BYTE offsets."""
    _need(type(raw_bytes) is bytes, "UT013_BYTES_REQUIRED")
    text = raw_bytes.decode("utf-8", "strict")
    res = locate_term(text, term)
    if res["tie"] == TIE_EXACT:
        byte_start = len(text[:res["span"][0]].encode("utf-8"))
        byte_end = len(text[:res["span"][1]].encode("utf-8"))
        res["span"] = [byte_start, byte_end]
    return res


def _qarinah_status(candidate_text: str) -> dict:
    present = _fold(candidate_text).find(_fold("القرينة")) >= 0
    if present:
        return {"status": QARINAH_PRESENT,
                "note": "marker present as text; its juristic role is NOT assessed"}
    return {"status": QARINAH_NOT_OBSERVED, "note": QARINAH_NOTE}


def match_candidate(
    *, candidate: dict, passage: dict, tafsir_raw_text: str,
    usul_catalog: dict, usul_graph: dict, usul_raw_text: bytes,
    rule_candidate_id: str, research_pointer_id: str,
    rule_query_terms: list[str],
    candidacy_reason: str | None = None,
    candidacy_scope: str | None = None,
) -> dict:
    """Match one tafsir candidate against one usul rule candidate.

    Matching = lexical tie evidence on BOTH pinned sides (EXACT or folded),
    recorded with original offsets and digests. A tie is lexical navigation
    only: never proof of command form, never proof of qarinah absence.
    CANDIDATE_RELATED requires EXACT ties on both sides PLUS an explicit
    operator-supplied candidacy_reason; everything else is UNDETERMINED.
    The produced link always goes through ut012 build_link + validate_link.
    """
    _need(type(rule_query_terms) is list and rule_query_terms,
          "UT013_QUERY_TERMS_REQUIRED")
    _need(candidacy_reason is None
          or (type(candidacy_scope) is str
              and 1 <= len(candidacy_scope.strip()) <= 128),
          "UT013_CANDIDACY_SCOPE_REQUIRED_WITH_REASON")
    text = candidate["interpretation_statement"]
    _need(_digest_text(text) == candidate.get("evidence_sha256"),
          "UT013_CANDIDATE_DIGEST_MISMATCH")

    ties_tafsir = [locate_term(text, t) for t in rule_query_terms]
    t_exact = any(t["tie"] == TIE_EXACT for t in ties_tafsir)
    t_folded = any(t["tie"] == TIE_FOLDED for t in ties_tafsir)
    try:
        u_ties = [locate_term_utf8_bytes(usul_raw_text, t)
                  for t in rule_query_terms]
    except (UnicodeError, ValueError) as exc:
        raise UsulTafsirLinkError("UT013_USUL_SOURCE_UNREADABLE") from exc
    u_exact = any(t["tie"] == TIE_EXACT for t in u_ties)
    u_folded = any(t["tie"] == TIE_FOLDED for t in u_ties)

    if t_exact and u_exact and candidacy_reason:
        tie_level, link_status = TIE_EXACT, LINK_CANDIDATE
    else:
        tie_level = (TIE_FOLDED if (t_folded or t_exact or u_folded or u_exact)
                     else TIE_NONE)
        link_status = LINK_UNDETERMINED

    link = build_link(
        quran_reference=candidate["quran_reference"],
        tafsir_candidate=candidate,
        tafsir_passage=passage,
        tafsir_original_raw_text=tafsir_raw_text,
        usul_catalog=usul_catalog, usul_graph=usul_graph,
        rule_candidate_id=rule_candidate_id,
        research_pointer_id=research_pointer_id,
        candidacy_reason=(candidacy_reason if link_status == LINK_CANDIDATE
                          else None),
        candidacy_scope=(candidacy_scope if link_status == LINK_CANDIDATE
                         else None),
    )
    # the contract is never bypassed: re-verify the built link
    validate_link(link, tafsir_candidate=candidate, tafsir_passage=passage,
                  tafsir_original_raw_text=tafsir_raw_text,
                  usul_catalog=usul_catalog, usul_graph=usul_graph)
    _need(link["link_status"] == link_status,
          "UT013_MATCHER_CONTRACT_STATUS_MISMATCH")
    if link_status == LINK_UNDETERMINED:
        _need(candidacy_reason is None,
              "UT013_UNDETERMINED_WITH_REASON_FORBIDDEN")

    link["matching"] = {
        "tie_level": tie_level,
        "tafsir_ties": ties_tafsir,
        "usul_ties_utf8": u_ties,
        "tafsir_span_unit": TAFSIR_SPAN_UNIT,
        "usul_span_unit": OFFSET_UTF8_BYTES,
        "exact_requires_both_sides_and_explicit_reason": True,
        "lexical_marker_is_not_rule_form_evidence": True,
    }
    link["qarinah"] = _qarinah_status(text)
    return link


def summarize(matches: list[dict]) -> dict:
    _need(type(matches) is list, "UT013_MATCHES_NOT_LIST")
    by_status = {}
    by_tie = {}
    for m in matches:
        by_status[m["link_status"]] = by_status.get(m["link_status"], 0) + 1
        tie = m.get("matching", {}).get("tie_level", TIE_NONE)
        by_tie[tie] = by_tie.get(tie, 0) + 1
    return {
        "contract": CONTRACT, "version": VERSION,
        "matches_total": len(matches),
        "links_by_status": by_status, "ties_by_level": by_tie,
        "scholarly_verified": False, "rule_application_verified": False,
        "cross_source_semantic_equivalence_verified": False,
        "juristic_inference_allowed": False,
        "public_fatwa_authorized": False, "text_included": False,
        "p1_admitted": False, "consensus_claimed": False,
        "preference_by_system": False,
    }
