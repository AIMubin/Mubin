"""T0.2.3: interpretation identification, attribution, and candidate
relations over T0.2 grounded passages.

A passage (SourcePassage) is NOT necessarily one interpretive statement.
This module identifies InterpretationCandidate records inside passages,
distinguishes author-endorsed views from reported opinions (never attribute
a quoted view to the book author merely because it appears in the book),
and proposes relations between candidates only when explicit textual
evidence exists. Insufficient evidence yields UNCLASSIFIED / UNKNOWN /
UNDETERMINED. No consensus inference, no system-side preference, no
word-similarity agreement.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from engines.tafsir.t02 import _sha, _need, TafsirT02Error

CONTRACT = "mubin-tafsir-t023-identification-v1"
VERSION = "tafsir-t023/0.1.0"

# --- interpretation types (limited taxonomy; UNCLASSIFIED is the default) ---
TYPES = frozenset((
    "LEXICAL_EXPLANATION", "VERSE_MEANING", "REPORTED_OPINION",
    "NARRATIVE_EVIDENCE", "LEGAL_INTERPRETATION", "PREFERENCE_STATEMENT",
    "OBJECTION_OR_RESPONSE", "UNCLASSIFIED"))

# --- attribution types ---
ATTRIB_AUTHOR_OWN = "AUTHOR_OWN_EXPLICIT"
ATTRIB_NAMED_REPORT = "NAMED_REPORT"
ATTRIB_ANONYMOUS_REPORT = "ANONYMOUS_REPORT"
ATTRIB_NARRATED = "NARRATED_WITH_CHAIN_OR_SOURCE"
ATTRIB_UNKNOWN = "UNKNOWN"
ATTRIB_TYPES = frozenset((ATTRIB_AUTHOR_OWN, ATTRIB_NAMED_REPORT,
                          ATTRIB_ANONYMOUS_REPORT, ATTRIB_NARRATED,
                          ATTRIB_UNKNOWN))

IDENTITY_NAMED = "NAMED_IN_TEXT"
IDENTITY_UNKNOWN = "UNKNOWN"
ENDORSE_NONE = "NONE"
ENDORSE_EXPLICIT = "AUTHOR_EXPLICIT_ENDORSEMENT"
ENDORSE_AMBIGUOUS = "AMBIGUOUS"

RELATIONS = frozenset((
    "AGREEMENT_CANDIDATE", "DISAGREEMENT_CANDIDATE", "QUALIFICATION",
    "ELABORATION", "ALTERNATIVE_INTERPRETATION", "OBJECTION", "PREFERENCE",
    "UNDETERMINED"))

# --- lexical cue markers: indicators ONLY, never proof by themselves ---
_RE_NAMED_REPORT = re.compile(r"(?:و|أو)?\s*قال\s+([\u0621-\u064A\u0640\s]{2,40}?)(?=\s*(?:في|عن|:|،|\.|\u06d4)|$)")
_RE_ANON_REPORT = re.compile(r"(?:و)?\s*قيل\b")
_RE_NARRATED = re.compile(r"(?:و)?\s*(?:روى|أخبر|حدثنا|أنبأ|ذكر عن)\b")
_RE_AUTHOR_PREF = re.compile(r"(?:والصواب|والأولى|وعندنا|وأصح\s+الأقوال|أولى\s+بالصواب|والمراد|والأظهر)")
_RE_DISAGREEMENT_MARK = re.compile(r"(?:و)?\s*(?:اختلف|واختلف|خلاف|فيه\s+خلاف)\b")
_RE_OBJECTION = re.compile(r"(?:ولا\s+يجوز|دفع\s+هذا|اعتراض|والرد\s+على|هذا\s+غير\s+صحيح|بطل\s+هذا)")
_RE_LEXICAL = re.compile(r"(?:معنى|لفظ|تسمية|وتسمى|وتعرف)\b")
_RE_LEGAL = re.compile(r"(?:يجب|وجوب|فرض|حكم|لا\s+يجوز|كراهة|ندب)\b")


def _confidence_of(attribution: str, named: bool) -> str:
    """Ordinal confidence is an internal ordering label, NEVER evidence of truth."""
    if attribution == ATTRIB_NAMED_REPORT and named:
        return "MEDIUM"
    if attribution in (ATTRIB_NAMED_REPORT, ATTRIB_NARRATED):
        return "MEDIUM"
    if attribution in (ATTRIB_AUTHOR_OWN, ATTRIB_ANONYMOUS_REPORT):
        return "LOW"
    return "LOW"


def identify_candidates(passage: dict) -> list[dict]:
    """Identify interpretation candidates inside one T0.2 grounded passage.

    passage requires: interpretation_id, quran_reference, work_id,
    source_record_id, source_sha256, evidence_span (list [s,e]),
    interpretation_statement (exact substring of the raw source),
    plus optional raw_text so spans can be re-based to the original.
    Every candidate span indexes into the passage statement text itself.
    """
    _need(type(passage) is dict, "T023_PASSAGE_NOT_DICT")
    for f in ("interpretation_id", "quran_reference", "work_id",
              "source_record_id", "source_sha256", "evidence_span",
              "interpretation_statement"):
        _need(f in passage, f"T023_PASSAGE_FIELD_MISSING_{f}")
    text = passage["interpretation_statement"]
    _need(type(text) is str and text, "T023_PASSAGE_TEXT_EMPTY")
    base_id = passage["interpretation_id"]

    # Split into sub-segments at attribution markers so a single passage can
    # yield several candidates (author view + reported views separately).
    markers: list[dict] = []
    for m in _RE_NAMED_REPORT.finditer(text):
        markers.append({"start": m.start(), "kind": "NAMED",
                        "speaker": m.group(1).strip()})
    for m in _RE_ANON_REPORT.finditer(text):
        markers.append({"start": m.start(), "kind": "ANON", "speaker": None})
    for m in _RE_NARRATED.finditer(text):
        markers.append({"start": m.start(), "kind": "NARRATED", "speaker": None})
    for m in _RE_AUTHOR_PREF.finditer(text):
        markers.append({"start": m.start(), "kind": "PREF", "speaker": None})
    markers.sort(key=lambda x: x["start"])

    segments: list[dict] = []
    if not markers:
        segments.append({"start": 0, "end": len(text), "kind": "PLAIN",
                         "speaker": None})
    else:
        if markers[0]["start"] > 0:
            segments.append({"start": 0, "end": markers[0]["start"],
                             "kind": "PLAIN", "speaker": None})
        for i, mk in enumerate(markers):
            end = markers[i + 1]["start"] if i + 1 < len(markers) else len(text)
            segments.append({"start": mk["start"], "end": end,
                             "kind": mk["kind"], "speaker": mk.get("speaker")})
    # merge/degenerate tiny segments
    segments = [s for s in segments if s["end"] - s["start"] >= 15]

    candidates = []
    for idx, seg in enumerate(segments):
        s0, s1 = seg["start"], seg["end"]
        chunk = text[s0:s1]
        kind = seg["kind"]
        if kind == "NAMED":
            attribution, speaker = ATTRIB_NAMED_REPORT, seg["speaker"]
            identity = IDENTITY_NAMED
            itype = "REPORTED_OPINION"
            endorse = ENDORSE_NONE
        elif kind == "ANON":
            attribution, speaker = ATTRIB_ANONYMOUS_REPORT, None
            identity = IDENTITY_UNKNOWN
            itype = "REPORTED_OPINION"
            endorse = ENDORSE_NONE
        elif kind == "NARRATED":
            attribution, speaker = ATTRIB_NARRATED, None
            identity = IDENTITY_UNKNOWN
            itype = "NARRATIVE_EVIDENCE"
            endorse = ENDORSE_NONE
        elif kind == "PREF":
            attribution = ATTRIB_AUTHOR_OWN
            speaker = None
            identity = IDENTITY_UNKNOWN
            itype = "PREFERENCE_STATEMENT"
            endorse = ENDORSE_EXPLICIT
        else:
            attribution = ATTRIB_UNKNOWN
            speaker = None
            identity = IDENTITY_UNKNOWN
            itype = "UNCLASSIFIED"
            endorse = ENDORSE_NONE
        # secondary type refinement (still rule indicators only)
        if itype in ("UNCLASSIFIED", "VERSE_MEANING"):
            if _RE_LEXICAL.search(chunk):
                itype = "LEXICAL_EXPLANATION"
            elif _RE_LEGAL.search(chunk):
                itype = "LEGAL_INTERPRETATION"
            elif itype == "UNCLASSIFIED":
                itype = "VERSE_MEANING"
        # objection refinement
        if _RE_OBJECTION.search(chunk):
            itype = "OBJECTION_OR_RESPONSE"
            endorse = ENDORSE_AMBIGUOUS
        confidence = _confidence_of(attribution, identity == IDENTITY_NAMED)
        cid = "cand:" + _sha((base_id + "|" + str(s0) + "|" + str(s1)).encode())[:40]
        candidates.append({
            "contract": CONTRACT,
            "candidate_id": cid,
            "passage_id": base_id,
            "quran_reference": passage["quran_reference"],
            "work_id": passage["work_id"],
            "source_record_id": passage["source_record_id"],
            "source_sha256": passage["source_sha256"],
            "passage_span": passage["evidence_span"],
            "statement_start": s0, "statement_end": s1,
            "interpretation_statement": chunk,
            "evidence_sha256": _sha(chunk.encode("utf-8")),
            "interpretation_type": itype,
            "speaker_name": speaker,
            "speaker_identity_status": identity,
            "attribution_type": attribution,
            "reported_by": None,
            "author_endorsement": endorse,
            "attribution_evidence_span": [s0, s1] if kind != "PLAIN" else None,
            "attribution_confidence": confidence,
            "verification_status": "UNVERIFIED",
            "context_scope": "VERSE_LOCAL_EXEGESIS",
            "rights_status": "legal_review_pending",
            "scholarly_verified": False,
            "text_included": False,
            "publication_allowed": False,
            "juristic_inference_allowed": False,
            "public_fatwa_authorized": False,
            "p1_admitted": False,
        })
    return candidates


def build_relationships(candidates: list[dict]) -> list[dict]:
    """Propose relations ONLY with explicit textual evidence.

    Conservative rules:
      - explicit author preference marker in candidate B + earlier candidate A
        in the same passage  -> PREFERENCE (A, B)
      - objection marker in candidate B referring back + earlier A
        -> OBJECTION (A, B)
      - explicit disagreement marker (اختلف) in the passage containing both
        -> ALTERNATIVE_INTERPRETATION (A, B)
      - everything else -> UNDETERMINED
    No agreement from word similarity; no disagreement from different wording;
    no consensus inference.
    """
    _need(type(candidates) is list, "T023_CANDIDATES_NOT_LIST")
    by_passage: dict[str, list[dict]] = {}
    for c in candidates:
        _need(type(c) is dict and "passage_id" in c and "candidate_id" in c,
              "T023_CANDIDATE_INVALID")
        by_passage.setdefault(c["passage_id"], []).append(c)
    relations = []
    for pid, group in by_passage.items():
        ordered = sorted(group, key=lambda c: c["statement_start"])
        for i, a in enumerate(ordered):
            for b in ordered[i + 1:]:
                rel_type = "UNDETERMINED"
                evidence_span = None
                if (b["attribution_type"] == ATTRIB_AUTHOR_OWN
                        and b["author_endorsement"] == ENDORSE_EXPLICIT
                        and b["interpretation_type"] == "PREFERENCE_STATEMENT"):
                    rel_type = "PREFERENCE"
                    evidence_span = list(b["attribution_evidence_span"] or [])
                elif (b["interpretation_type"] == "OBJECTION_OR_RESPONSE"
                        and a["interpretation_type"] == "REPORTED_OPINION"):
                    rel_type = "OBJECTION"
                    evidence_span = list(b["attribution_evidence_span"] or [])
                elif (a["attribution_type"] == ATTRIB_NAMED_REPORT
                        and b["attribution_type"] == ATTRIB_NAMED_REPORT
                        and a["speaker_name"] != b["speaker_name"]):
                    rel_type = "ALTERNATIVE_INTERPRETATION"
                elif (a["interpretation_type"] == "REPORTED_OPINION"
                        and b["interpretation_type"] == "REPORTED_OPINION"):
                    rel_type = "UNDETERMINED"
                rid = "rel:" + _sha((a["candidate_id"] + "|" + b["candidate_id"]).encode())[:40]
                relations.append({
                    "contract": CONTRACT,
                    "relation_id": rid,
                    "from_candidate_id": a["candidate_id"],
                    "to_candidate_id": b["candidate_id"],
                    "passage_id": pid,
                    "relation_type": rel_type,
                    "evidence_span": evidence_span,
                    "verification_status": "UNVERIFIED",
                    "scholarly_verified": False,
                    "consensus_claimed": False,
                    "preference_by_system": False,
                    "text_included": False,
                    "rights_status": "legal_review_pending",
                })
    return relations


def summarize_analysis(passages: list[dict], candidates: list[dict],
                       relations: list[dict]) -> dict:
    """Counts only; never statement text."""
    attributed = [c for c in candidates
                  if c["attribution_type"] in (ATTRIB_NAMED_REPORT, ATTRIB_NARRATED)]
    unknown = [c for c in candidates
               if c["speaker_identity_status"] == IDENTITY_UNKNOWN
               and c["attribution_type"] in (ATTRIB_UNKNOWN, ATTRIB_ANONYMOUS_REPORT)]
    undetermined = [r for r in relations if r["relation_type"] == "UNDETERMINED"]
    return {
        "contract": CONTRACT, "version": VERSION,
        "passages_processed": len(passages),
        "candidates_total": len(candidates),
        "explicit_attribution_count": len(attributed),
        "unknown_attribution_count": len(unknown),
        "relations_total": len(relations),
        "relations_undetermined": len(undetermined),
        "excluded_insufficient_evidence": sum(
            1 for c in candidates if c["interpretation_type"] == "UNCLASSIFIED"),
        "candidate_ids": [c["candidate_id"] for c in candidates],
        "scholarly_verified": False,
        "text_included": False,
        "consensus_claimed": False,
        "publication_allowed": False,
        "juristic_inference_allowed": False,
        "public_fatwa_authorized": False,
        "p1_admitted": False,
    }
