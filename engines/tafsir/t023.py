"""T0.2.3: evidence-bound *candidate* identification and cautious relations.

Rules identify linguistic cues inside already-pinned T0.2 source passages.
Neither a cue nor a sentence split establishes an exegetical opinion,
author endorsement, semantic agreement or contradiction.
"""
from __future__ import annotations

import re
from typing import Any

from engines.quran.tafsir.catalog import _reference, CatalogError
from engines.tafsir.t02 import (
    _sha, _id, _need, _catalog_authors, TafsirT02Error,
    CONTRACT as T02_CONTRACT, SPAN_UNIT, CONTEXT as T02_CONTEXT,
    METHOD_RULE_SEGMENTER, STATUS_RULE_EXTRACTED_UNVERIFIED,
)

CONTRACT = "mubin-tafsir-t023-identification-v1"
VERSION = "tafsir-t023/0.1.0"
TYPES = frozenset((
    "LEXICAL_EXPLANATION", "VERSE_MEANING", "REPORTED_OPINION",
    "NARRATIVE_EVIDENCE", "LEGAL_INTERPRETATION", "PREFERENCE_STATEMENT",
    "OBJECTION_OR_RESPONSE", "UNCLASSIFIED",
))
ATTRIB_AUTHOR_OWN = "AUTHOR_OWN_EXPLICIT"
ATTRIB_NAMED_REPORT = "NAMED_REPORT"
ATTRIB_ANONYMOUS_REPORT = "ANONYMOUS_REPORT"
ATTRIB_NARRATED = "NARRATED_WITH_CHAIN_OR_SOURCE"
ATTRIB_UNKNOWN = "UNKNOWN"
IDENTITY_NAMED = "NAMED_IN_TEXT"
IDENTITY_UNKNOWN = "UNKNOWN"
ENDORSE_NONE = "NONE"
ENDORSE_EXPLICIT = "AUTHOR_EXPLICIT_ENDORSEMENT_CUE_UNVERIFIED"
ENDORSE_AMBIGUOUS = "AMBIGUOUS"
RELATIONS = frozenset((
    "AGREEMENT_CANDIDATE", "DISAGREEMENT_CANDIDATE",
    "QUALIFICATION", "ELABORATION", "ALTERNATIVE_INTERPRETATION",
    "OBJECTION", "PREFERENCE", "UNDETERMINED",
))
_RE_NAMED = re.compile(
    r"(?:و)?قال[ \t]+([\u0621-\u064A\u0640]+(?:[ \t]+[\u0621-\u064A\u0640]+){0,3})"
    r"(?=[ \t]*(?::|،|\.|\u06d4|\u061f|في\b|عن\b))")
_RE_ANON = re.compile(r"(?:و)?قيل\b")
_RE_NARRATED = re.compile(r"(?:و)?(?:روى|أخبر|حدثنا|أنبأ)\b")
# First-person author preference *cues*: even these remain unverified, and
# quotations carrying the phrase must not become the author's own opinion.
_RE_AUTHOR = re.compile(
    r"(?:والصواب[ \t]+عندنا|والصواب[ \t]+في[ \t]+ذلك[ \t]+عندنا|"
    r"والأولى[ \t]+عندنا)")
_RE_OBJECTION = re.compile(
    r"(?:ولا[ \t]+يجوز|دفع[ \t]+هذا|اعتراض|والرد[ \t]+على|"
    r"هذا[ \t]+غير[ \t]+صحيح|بطل[ \t]+هذا)")
_RE_LEXICAL = re.compile(r"(?:معنى|لفظ|تسمية|وتسمى|وتعرف)\b")
_RE_LEGAL = re.compile(r"(?:يجب|وجوب|فرض|حكم|لا[ \t]+يجوز|كراهة|ندب)\b")
_MAX_CANDIDATES = 1024
_MAX_SOURCE_CHARS = 2000
_SHA_RE = re.compile(r"^[a-f0-9]{64}$")


def _in_quoted_span(text: str, index: int) -> bool:
    """Best-effort quote guard: never infer author ownership inside «...»."""
    return text[:index].count("«") > text[:index].count("»")


def _validate_passage(p: dict) -> None:
    """Verify T0.2 self-consistency; raw source bytes were checked upstream.

    A caller can forge a self-consistent T0.2 record; this function is not
    a substitute for the pinned local T0.1→T0.2 acquisition pipeline.
    """
    _need(type(p) is dict, "T023_PASSAGE_NOT_DICT")
    fields = (
        "contract", "interpretation_id", "quran_reference", "work_id",
        "source_record_id", "source_sha256", "evidence_sha256",
        "evidence_span", "evidence_span_unit", "interpretation_statement",
        "verification_status", "extraction_method", "candidate_kind",
        "context_scope",
    )
    _need(all(k in p for k in fields), "T023_PASSAGE_FIELDS_MISSING")
    _need(p["contract"] == T02_CONTRACT
          and p["verification_status"] == STATUS_RULE_EXTRACTED_UNVERIFIED
          and p["extraction_method"] == METHOD_RULE_SEGMENTER
          and p["candidate_kind"] == "UNCLASSIFIED_TEXT_SEGMENT"
          and p["context_scope"] == T02_CONTEXT,
          "T023_UNTRUSTED_PASSAGE_CONTRACT")
    try:
        _reference(p["quran_reference"])
    except (CatalogError, TypeError) as exc:
        raise TafsirT02Error("T023_INVALID_REFERENCE") from exc
    work, digest = p["work_id"], p["source_sha256"]
    _need(type(work) is str and work in _catalog_authors()
          and type(digest) is str and _SHA_RE.fullmatch(digest) is not None,
          "T023_INVALID_SOURCE_IDENTITY")
    _need(p["source_record_id"] ==
          f"tafsir:{work}:{p['quran_reference']}:{digest}",
          "T023_SOURCE_RECORD_MISMATCH")
    text = p["interpretation_statement"]
    _need(type(text) is str and 0 < len(text) <= _MAX_SOURCE_CHARS,
          "T023_INVALID_PASSAGE_TEXT")
    span = p["evidence_span"]
    _need(type(span) is list and len(span) == 2
          and all(type(v) is int for v in span)
          and 0 <= span[0] < span[1]
          and span[1]-span[0] == len(text)
          and p["evidence_span_unit"] == SPAN_UNIT,
          "T023_INVALID_PASSAGE_SPAN")
    ev = _sha(text.encode("utf-8"))
    _need(p["evidence_sha256"] == ev
          and p["interpretation_id"] ==
          _id(p["source_record_id"], (span[0], span[1]), ev),
          "T023_PASSAGE_EVIDENCE_MISMATCH")
    for f in ("scholarly_verified", "textual_interpretation_assessed",
              "publication_allowed", "juristic_inference_allowed",
              "public_fatwa_authorized", "p1_admitted"):
        _need(p.get(f) is False, "T023_UNAUTHORIZED_PASSAGE_PROMOTION")


def _validate_candidate(c: dict) -> None:
    _need(type(c) is dict
          and c.get("contract") == CONTRACT
          and c.get("verification_status") == "UNVERIFIED"
          and c.get("candidate_kind") == "LEXICAL_CUE_CANDIDATE",
          "T023_CANDIDATE_INVALID")
    _need(c.get("interpretation_type") in TYPES
          and c.get("attribution_type") in (
              ATTRIB_AUTHOR_OWN, ATTRIB_NAMED_REPORT,
              ATTRIB_ANONYMOUS_REPORT, ATTRIB_NARRATED, ATTRIB_UNKNOWN),
          "T023_CANDIDATE_CLASS_INVALID")
    _need(type(c.get("passage_id")) is str
          and type(c.get("statement_start")) is int
          and type(c.get("statement_end")) is int
          and 0 <= c["statement_start"] < c["statement_end"]
          and c["statement_end"]-c["statement_start"] <= _MAX_SOURCE_CHARS,
          "T023_CANDIDATE_OFFSETS_INVALID")
    text = c.get("interpretation_statement")
    _need(type(text) is str and len(text) ==
          c["statement_end"]-c["statement_start"],
          "T023_CANDIDATE_TEXT_INVALID")
    absolute = c.get("raw_source_span")
    passage = c.get("passage_span")
    _need(type(passage) is list and len(passage) == 2
          and all(type(n) is int for n in passage)
          and type(absolute) is list and len(absolute) == 2
          and all(type(n) is int for n in absolute)
          and absolute == [
              passage[0]+c["statement_start"], passage[0]+c["statement_end"]],
          "T023_CANDIDATE_RAW_SPAN_INVALID")
    _need(c.get("evidence_sha256") == _sha(text.encode("utf-8"))
          and c.get("candidate_id") ==
          "cand:" + _sha((
              c["passage_id"] + "|" + str(c["statement_start"])
              + "|" + str(c["statement_end"])).encode("utf-8"))[:40],
          "T023_CANDIDATE_EVIDENCE_INVALID")
    _need(type(c.get("work_id")) is str
          and c["work_id"] in _catalog_authors()
          and c.get("source_record_id") ==
          f"tafsir:{c['work_id']}:{c['quran_reference']}:{c['source_sha256']}",
          "T023_CANDIDATE_SOURCE_INVALID")
    _need(c.get("speaker_identity_status") in (IDENTITY_NAMED, IDENTITY_UNKNOWN)
          and (c.get("speaker_identity_status") != IDENTITY_NAMED
               or (c.get("attribution_type") == ATTRIB_NAMED_REPORT
                   and type(c.get("speaker_name")) is str
                   and len(c["speaker_name"]) > 0)),
          "T023_SPEAKER_INVALID")
    _need(c.get("scholarly_verified") is False
          and c.get("publication_allowed") is False
          and c.get("juristic_inference_allowed") is False
          and c.get("public_fatwa_authorized") is False
          and c.get("p1_admitted") is False,
          "T023_AUTHORITY_PROMOTION_FORBIDDEN")


def identify_candidates(passage: dict) -> list[dict]:
    """Extract unverified lexical candidates from one T0.2-pinned passage."""
    _validate_passage(passage)
    text = passage["interpretation_statement"]
    starts: dict[int, dict] = {}
    for pattern, kind in (
        (_RE_NAMED, "NAMED"), (_RE_ANON, "ANON"),
        (_RE_NARRATED, "NARRATED"), (_RE_AUTHOR, "AUTHOR"),
    ):
        for m in pattern.finditer(text):
            if kind == "AUTHOR" and _in_quoted_span(text, m.start()):
                continue
            if m.start() not in starts:
                starts[m.start()] = {
                    "start": m.start(), "end_cue": m.end(),
                    "kind": kind, "speaker": m.group(1).strip()
                    if kind == "NAMED" else None,
                }
    markers = sorted(starts.values(), key=lambda z: z["start"])
    pieces = []
    if not markers:
        pieces.append((0, len(text), "PLAIN", None, None))
    else:
        if markers[0]["start"] > 0:
            pieces.append((0, markers[0]["start"], "PLAIN", None, None))
        for idx, marker in enumerate(markers):
            end = (markers[idx+1]["start"] if idx+1 < len(markers)
                   else len(text))
            pieces.append((marker["start"], end, marker["kind"],
                           marker["speaker"], marker["end_cue"]))
    _need(len(pieces) <= _MAX_CANDIDATES, "T023_TOO_MANY_CANDIDATES")
    result: list[dict] = []
    for start, end, kind, speaker, cue_end in pieces:
        if end <= start or end-start < 15:
            continue
        chunk = text[start:end]
        attribution = ATTRIB_UNKNOWN
        identity = IDENTITY_UNKNOWN
        itype = "UNCLASSIFIED"
        endorsement = ENDORSE_NONE
        if kind == "NAMED":
            attribution, identity, itype = (
                ATTRIB_NAMED_REPORT, IDENTITY_NAMED, "REPORTED_OPINION")
        elif kind == "ANON":
            attribution, itype = ATTRIB_ANONYMOUS_REPORT, "REPORTED_OPINION"
        elif kind == "NARRATED":
            attribution, itype = ATTRIB_NARRATED, "NARRATIVE_EVIDENCE"
        elif kind == "AUTHOR":
            # A first-person cue is an unverified authorship *candidate*.
            attribution, itype, endorsement = (
                ATTRIB_AUTHOR_OWN, "PREFERENCE_STATEMENT", ENDORSE_EXPLICIT)
        elif _RE_LEXICAL.search(chunk):
            itype = "LEXICAL_EXPLANATION"
        elif _RE_LEGAL.search(chunk):
            itype = "LEGAL_INTERPRETATION"
        if _RE_OBJECTION.search(chunk):
            itype = "OBJECTION_OR_RESPONSE"
            endorsement = ENDORSE_AMBIGUOUS
        cid = "cand:" + _sha(
            (passage["interpretation_id"] + "|" +
             str(start) + "|" + str(end)).encode("utf-8"))[:40]
        source_start = passage["evidence_span"][0]
        result.append({
            "contract": CONTRACT,
            "candidate_id": cid,
            "passage_id": passage["interpretation_id"],
            "quran_reference": passage["quran_reference"],
            "work_id": passage["work_id"],
            "source_record_id": passage["source_record_id"],
            "source_sha256": passage["source_sha256"],
            "passage_span": list(passage["evidence_span"]),
            "raw_source_span": [source_start+start, source_start+end],
            "statement_start": start, "statement_end": end,
            "interpretation_statement": chunk,
            "evidence_sha256": _sha(chunk.encode("utf-8")),
            "candidate_kind": "LEXICAL_CUE_CANDIDATE",
            "interpretation_type": itype,
            "speaker_name": speaker,
            "speaker_identity_status": identity,
            "attribution_type": attribution,
            "reported_by": None,
            "author_endorsement": endorsement,
            "attribution_evidence_span": (
                [source_start+start, source_start+cue_end]
                if cue_end is not None else None),
            "attribution_confidence": (
                "MEDIUM" if kind == "NAMED" else "LOW"),
            "verification_status": "UNVERIFIED",
            "context_scope": "VERSE_LOCAL_EXEGESIS",
            "rights_status": "legal_review_pending",
            "scholarly_verified": False, "text_included": False,
            "publication_allowed": False, "juristic_inference_allowed": False,
            "public_fatwa_authorized": False, "p1_admitted": False,
        })
        _validate_candidate(result[-1])
    return result


def build_relationships(candidates: list[dict]) -> list[dict]:
    """Return *unresolved* candidate relations only within the same passage.

    Lexical cues alone do NOT establish which particular view an author
    prefers, objects to, or contradicts. Emit UNDETERMINED rather than
    invent a scoped target for a preference/objection.
    """
    _need(type(candidates) is list and len(candidates) <= _MAX_CANDIDATES,
          "T023_CANDIDATES_INVALID")
    by_passage: dict[str, list[dict]] = {}
    seen = set()
    for c in candidates:
        _validate_candidate(c)
        _need(c["candidate_id"] not in seen, "T023_DUPLICATE_CANDIDATE_ID")
        seen.add(c["candidate_id"])
        by_passage.setdefault(c["passage_id"], []).append(c)
    relations = []
    for pid, group in by_passage.items():
        ordered = sorted(group, key=lambda x: x["statement_start"])
        for i, a in enumerate(ordered):
            for b in ordered[i+1:]:
                _need(a["work_id"] == b["work_id"]
                      and a["source_record_id"] == b["source_record_id"]
                      and a["source_sha256"] == b["source_sha256"]
                      and a["quran_reference"] == b["quran_reference"]
                      and a["passage_span"] == b["passage_span"]
                      and a["statement_end"] <= b["statement_start"],
                      "T023_INCONSISTENT_RELATION_ENDPOINTS")
                rid = "rel:" + _sha(
                    (pid + "|" + a["candidate_id"] + "|" +
                     b["candidate_id"]).encode("utf-8"))[:40]
                relations.append({
                    "contract": CONTRACT, "relation_id": rid,
                    "from_candidate_id": a["candidate_id"],
                    "to_candidate_id": b["candidate_id"],
                    "passage_id": pid,
                    "relation_type": "UNDETERMINED",
                    "evidence_span": None,
                    "verification_status": "UNVERIFIED",
                    "scholarly_verified": False, "consensus_claimed": False,
                    "preference_by_system": False, "text_included": False,
                    "rights_status": "legal_review_pending",
                })
    return relations


def summarize_analysis(passages: list[dict], candidates: list[dict],
                       relations: list[dict]) -> dict:
    """Source-bound metadata counts, never protected statement text."""
    _need(type(passages) is list and type(candidates) is list
          and type(relations) is list, "T023_SUMMARY_INVALID")
    return {
        "contract": CONTRACT, "version": VERSION,
        "passages_processed": len(passages),
        "candidates_total": len(candidates),
        "count_semantics": "UNVERIFIED_LEXICAL_CANDIDATES_NOT_EXEGETICAL_OPINIONS",
        "named_report_cues": sum(1 for c in candidates
                                 if c["attribution_type"] == ATTRIB_NAMED_REPORT),
        "author_preference_cues": sum(1 for c in candidates
                                     if c["attribution_type"] == ATTRIB_AUTHOR_OWN),
        "unidentified_speaker_candidates": sum(1 for c in candidates
                                               if c["speaker_identity_status"] ==
                                               IDENTITY_UNKNOWN),
        "unclassified_candidates": sum(1 for c in candidates
                                      if c["interpretation_type"] == "UNCLASSIFIED"),
        "relations_total": len(relations),
        "relations_undetermined": sum(1 for r in relations
                                     if r["relation_type"] == "UNDETERMINED"),
        "relations_scientifically_verified": 0,
        "source_bytes_independently_authenticated_here": False,
        "scholarly_verified": False, "text_included": False,
        "consensus_claimed": False, "publication_allowed": False,
        "juristic_inference_allowed": False,
        "public_fatwa_authorized": False, "p1_admitted": False,
    }
