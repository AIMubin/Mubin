"""UT-01.3: conservative, reversible Stage07 lexical research navigation.

This is NOT semantic matching, hadith or tafsir validation, juristic inference,
or evidence of rule applicability. Only the source-independent UT-01.2
contract verifies the two sides. We return that link *unaltered* in a
separate UT-01.3 envelope: downstream can validate_link(envelope["link"]).
"""
from __future__ import annotations

import hashlib
import re

from engines.tafsir.t02 import SPAN_UNIT as TAFSIR_SPAN_UNIT
from engines.usul.arabic_evidence_retrieval import (
    FOLD_MARKS, _fold_with_map,
)
from engines.usul.ut012 import (
    LINK_CANDIDATE, LINK_UNDETERMINED, OFFSET_UTF8_BYTES,
    UsulTafsirLinkError, build_link, validate_link,
)

CONTRACT = "mubin-usul-tafsir-matching-v1"
VERSION = "usul-tafsir-matching/0.1.1"
TIE_EXACT = "EXACT"
TIE_FOLDED = "FOLDED_CANDIDATE"
TIE_NONE = "NONE"
QARINAH_PRESENT = "PRESENT_AS_TEXT"
QARINAH_NOT_OBSERVED = "NOT_OBSERVED_IN_SCOPE"
QARINAH_NOTE = (
    "A marker not observed in this bounded phrase is not evidence that "
    "no qarinah exists in the source, or that a condition is absent."
)
_FLAGS = (
    "scholarly_verified", "rule_application_verified",
    "cross_source_semantic_equivalence_verified",
    "juristic_inference_allowed", "public_fatwa_authorized",
    "text_included", "p1_admitted",
)
_MAX_TEXT = 200_000
_MAX_TERM = 128
# A fixed technical reason code avoids accidental verbatim private-source
# quotations in otherwise metadata-only research links.
REASON_PINNED_EXACT = "SOURCE_BOUND_STAGE07_EXACT_LEXICAL_OVERLAP"
_SCOPE = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")


def _need(condition, code):
    if not condition:
        raise UsulTafsirLinkError(code)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _term_valid(term):
    return (type(term) is str and 1 <= len(term) <= _MAX_TERM
            and bool(term.strip())
            and not any(ord(ch) < 32 for ch in term))


def _boundary(text: str, a: int, b: int) -> bool:
    """Avoid matching a word *inside* another Arabic/Unicode word."""
    return ((a == 0 or not (text[a - 1].isalnum() or text[a - 1] == "_"))
            and (b == len(text) or not (text[b].isalnum() or text[b] == "_")))


def _locations(text: str, term: str) -> list[dict]:
    _need(type(text) is str and len(text) <= _MAX_TEXT
          and _term_valid(term), "UT013_LOCATE_INPUT_INVALID")
    # Exact/byte-identical query takes precedence. No lossy normalization.
    out = []
    pos = 0
    while len(out) < 2048:
        start = text.find(term, pos)
        if start < 0:
            break
        end = start + len(term)
        if _boundary(text, start, end):
            out.append({
                "tie": TIE_EXACT, "span": [start, end],
                "digest": _digest(text[start:end].encode("utf-8")),
                "profile": "literal_exact_v1",
            })
        pos = start + 1
    if out:
        return out
    # Stage07 reversible, conservative mark-only folding: DOES NOT alter
    # Alef/Hamza, collapse spaces, strip word order or normalize meaning.
    folded, mapped = _fold_with_map(text, FOLD_MARKS)
    target, _ = _fold_with_map(term, FOLD_MARKS)
    if not target or len(target) < 3:
        return []
    pos = 0
    while len(out) < 2048:
        start = folded.find(target, pos)
        if start < 0:
            break
        finish = start + len(target)
        a, b = mapped[start], mapped[finish - 1] + 1
        if _boundary(text, a, b):
            piece = text[a:b]
            re_folded, _ = _fold_with_map(piece, FOLD_MARKS)
            if re_folded == target:
                out.append({
                    "tie": TIE_FOLDED, "span": [a, b],
                    "digest": _digest(piece.encode("utf-8")),
                    "profile": FOLD_MARKS,
                })
        pos = start + 1
    return out


def locate_term(text: str, term: str) -> dict:
    """Return verified source-codepoint span + literal digest, even folded."""
    matches = _locations(text, term)
    return matches[0] if matches else {"tie": TIE_NONE, "span": None,
                                     "digest": None, "profile": None}


def locate_term_utf8_bytes(raw_bytes: bytes, term: str) -> dict:
    """The *same* exact raw match, expressed in original UTF-8 byte offsets."""
    _need(type(raw_bytes) is bytes and len(raw_bytes) <= 500_000,
          "UT013_SECTION_BYTES_INVALID")
    try:
        text = raw_bytes.decode("utf-8", "strict")
    except UnicodeError as exc:
        raise UsulTafsirLinkError("UT013_SOURCE_NOT_UTF8") from exc
    loc = locate_term(text, term)
    if loc["span"] is None:
        return loc
    a, b = loc["span"]
    start = len(text[:a].encode("utf-8"))
    end = len(text[:b].encode("utf-8"))
    _need(raw_bytes[start:end].decode("utf-8") == text[a:b]
          and _digest(raw_bytes[start:end]) == loc["digest"],
          "UT013_BYTE_SPAN_ROUNDTRIP_FAILED")
    return {**loc, "span": [start, end]}


def _source_binding(usul_graph, rule_query_id, source_id, section_sha, raw):
    """Validate *whole section bytes* and retrieve pinned exact occurrences."""
    _need(type(raw) is bytes and len(raw) <= 500_000,
          "UT013_RAW_USUL_BYTES_REQUIRED")
    _need(_digest(raw) == section_sha,
          "UT013_WARAQAT_SECTION_RAW_SHA_MISMATCH")
    sections = [n for n in usul_graph["nodes"]
                if n.get("kind") == "PINNED_SECTION"
                and n.get("source_id") == source_id
                and n.get("section_sha256") == section_sha]
    _need(len(sections) == 1
          and sections[0].get("byte_length") == len(raw),
          "UT013_SECTION_LENGTH_OR_PIN_MISMATCH")
    sec = sections[0]
    queries = [n for n in usul_graph["nodes"]
               if n.get("kind") == "SEARCH_QUERY"
               and n.get("query_id") == rule_query_id
               and n.get("witness_id") == source_id]
    _need(len(queries) == 1, "UT013_PINNED_RULE_QUERY_NOT_FOUND")
    query = queries[0]
    _need(any(e.get("kind") == "QUERY_SCOPED_TO_SECTION"
              and e.get("from") == query["id"] and e.get("to") == sec["id"]
              for e in usul_graph["edges"]),
          "UT013_QUERY_SECTION_NOT_BOUND")
    edges = usul_graph["edges"]
    nodes = {n["id"]: n for n in usul_graph["nodes"]}
    occurrences = {}
    for e in edges:
        if (e.get("kind") != "QUERY_LOCATES_OCCURRENCE"
                or e.get("from") != query["id"]
                or e.get("classification") != "EXACT_LITERAL_ONLY"
                or e.get("semantic_equivalence_verified") is not False):
            continue
        node = nodes.get(e.get("to"))
        if node is None or node.get("section_id") != sec["id"]:
            continue
        a, b = node.get("section_byte_start"), node.get(
            "section_byte_end_exclusive")
        if (type(a) is int and type(b) is int
                and 0 <= a < b <= len(raw)
                and _digest(raw[a:b]) == node.get("original_span_sha256")):
            occurrences.setdefault((a, b), []).append(node["id"])
    return query, occurrences


def _qarinah_status(text: str) -> dict:
    # A textual mention can be in a quotation or a negated clause. Neither
    # presence nor lack of marker determines the existence/role of a qarinah.
    found = locate_term(text, "القرينة")["tie"] != TIE_NONE
    return {
        "status": QARINAH_PRESENT if found else QARINAH_NOT_OBSERVED,
        "note": ("Qarinah marker observed as text only; no role assessed"
                 if found else QARINAH_NOTE),
    }


def match_candidate(*, candidate: dict, passage: dict, tafsir_raw_text: str,
                    usul_catalog: dict, usul_graph: dict,
                    usul_raw_text: bytes, rule_candidate_id: str,
                    research_pointer_id: str, rule_query_terms: list[str],
                    candidacy_reason: str | None = None,
                    candidacy_scope: str | None = None) -> dict:
    """Produce source-attested lexical evidence, not an applied Usul rule.

    The one query term must exactly match the *research pointer's pinned
    Stage07 query literal SHA-256*. Candidate promotion requires a
    separately pinned Stage08 EXACT source occurrence and an exact literal
    Tafsir cue. An independent operator-supplied scoped reason is also
    mandatory; otherwise status stays UNDETERMINED.
    """
    _need(type(candidate) is dict and type(passage) is dict
          and type(usul_catalog) is dict and type(usul_graph) is dict,
          "UT013_INPUT_INVALID")
    _need(type(rule_query_terms) is list and len(rule_query_terms) == 1
          and _term_valid(rule_query_terms[0]),
          "UT013_ONE_PINNED_STAGE07_QUERY_REQUIRED")
    # Validate both independently pinned chains BEFORE trusting source
    # metadata in the matcher or operator supplied terms.
    undecided = build_link(
        quran_reference=candidate.get("quran_reference"),
        tafsir_candidate=candidate, tafsir_passage=passage,
        tafsir_original_raw_text=tafsir_raw_text,
        usul_catalog=usul_catalog, usul_graph=usul_graph,
        rule_candidate_id=rule_candidate_id,
        research_pointer_id=research_pointer_id,
    )
    validate_link(
        undecided, tafsir_candidate=candidate, tafsir_passage=passage,
        tafsir_original_raw_text=tafsir_raw_text,
        usul_catalog=usul_catalog, usul_graph=usul_graph,
    )
    rule = next(r for r in usul_catalog["rule_candidates"]
                if r["id"] == rule_candidate_id)
    anchor = rule["research_anchor"]
    term = rule_query_terms[0]
    query, allowed_occurrences = _source_binding(
        usul_graph, anchor["query_id"], anchor["source_id"],
        anchor["section_sha256"], usul_raw_text)
    _need(query.get("query_utf8_sha256") ==
          _digest(term.encode("utf-8")),
          "UT013_UNPINNED_STAGE07_QUERY_LITERAL")
    tafsir_text = candidate["interpretation_statement"]
    t_locations = _locations(tafsir_text, term)
    t_loc = (t_locations[0] if t_locations else
             {"tie": TIE_NONE, "span": None, "digest": None,
              "profile": None})
    try:
        u_text = usul_raw_text.decode("utf-8", "strict")
    except UnicodeError as exc:
        raise UsulTafsirLinkError("UT013_SOURCE_NOT_UTF8") from exc
    u_locs = []
    for hit in _locations(u_text, term):
        a, b = hit["span"]
        start = len(u_text[:a].encode("utf-8"))
        end = len(u_text[:b].encode("utf-8"))
        _need(_digest(usul_raw_text[start:end]) == hit["digest"],
              "UT013_SOURCE_MATCH_DIGEST_FAILED")
        u_locs.append({**hit, "span": [start, end]})
    # Prefer a literal occurrence attested by Stage07; a substring in the
    # section alone does not establish a legitimate rule-query observation.
    bound = next((hit for hit in u_locs
                  if hit["tie"] == TIE_EXACT
                  and tuple(hit["span"]) in allowed_occurrences), None)
    u_loc = bound if bound is not None else (
        u_locs[0] if u_locs else {"tie": TIE_NONE, "span": None,
                                "digest": None, "profile": None})
    can_propose = (t_loc["tie"] == TIE_EXACT
                   and bound is not None)
    if candidacy_reason is not None:
        _need(can_propose, "UT013_REASON_WITHOUT_PINNED_EXACT_TIE")
        _need(candidacy_reason == REASON_PINNED_EXACT
              and type(candidacy_scope) is str
              and _SCOPE.fullmatch(candidacy_scope) is not None,
              "UT013_REASON_SCOPE_INVALID")
    if candidacy_scope is not None and candidacy_reason is None:
        raise UsulTafsirLinkError("UT013_SCOPE_WITHOUT_REASON")
    occurrence = (sorted(allowed_occurrences[tuple(bound["span"])])[0]
                  if bound is not None and candidacy_reason else None)
    linked = (
        build_link(
            quran_reference=candidate["quran_reference"],
            tafsir_candidate=candidate, tafsir_passage=passage,
            tafsir_original_raw_text=tafsir_raw_text,
            usul_catalog=usul_catalog, usul_graph=usul_graph,
            rule_candidate_id=rule_candidate_id,
            research_pointer_id=research_pointer_id,
            occurrence_ids=[occurrence] if occurrence else [],
            candidacy_reason=candidacy_reason,
            candidacy_scope=candidacy_scope,
        ) if candidacy_reason else undecided
    )
    validate_link(
        linked, tafsir_candidate=candidate, tafsir_passage=passage,
        tafsir_original_raw_text=tafsir_raw_text,
        usul_catalog=usul_catalog, usul_graph=usul_graph,
    )
    _need(linked["link_status"] ==
          (LINK_CANDIDATE if candidacy_reason else LINK_UNDETERMINED),
          "UT013_LINK_STATUS_INVALID")
    return {
        "contract": CONTRACT, "version": VERSION,
        "link_id": linked["link_id"], "link_status": linked["link_status"],
        "link": linked,  # Unmodified, UT-01.2-valid reference!
        "matching": {
            "tie_level": (
                TIE_EXACT if can_propose else
                TIE_FOLDED if (t_loc["tie"] != TIE_NONE
                              and u_loc["tie"] != TIE_NONE
                              and TIE_FOLDED in (t_loc["tie"], u_loc["tie"]))
                else TIE_NONE
            ),
            "tafsir_tie": t_loc,
            "usul_tie_utf8": u_loc,
            "tafsir_raw_source_span": (
                [candidate["raw_source_span"][0] + t_loc["span"][0],
                 candidate["raw_source_span"][0] + t_loc["span"][1]]
                if t_loc["span"] else None
            ),
            "usul_section_relative_byte_span": u_loc["span"],
            "usul_exact_stage07_occurrence_id": occurrence,
            "usul_source_section_sha256": anchor["section_sha256"],
            "tafsir_span_unit": TAFSIR_SPAN_UNIT,
            "usul_span_unit": OFFSET_UTF8_BYTES,
            "evidence_is_lexical_only": True,
            "rule_form_not_derived": True,
        },
        "qarinah": _qarinah_status(tafsir_text),
        **{flag: False for flag in _FLAGS},
    }


def validate_match(record: dict, **inputs) -> None:
    """Re-run all pinned source checks, then compare whole envelope exactly."""
    _need(type(record) is dict, "UT013_RECORD_INVALID")
    rebuilt = match_candidate(**inputs)
    _need(record == rebuilt, "UT013_ENVELOPE_TAMPERED")


def summarize(matches: list[dict]) -> dict:
    _need(type(matches) is list and len(matches) <= 4096
          and all(type(m) is dict and m.get("contract") == CONTRACT
                  for m in matches), "UT013_MATCHES_INVALID")
    status, levels = {}, {}
    for m in matches:
        st = m["link"]["link_status"]
        _need(m.get("link_id") == m["link"].get("link_id")
              and m["link_status"] == st
              and all(m.get(flag) is False
                      and m["link"].get(flag) is False for flag in _FLAGS),
              "UT013_MATCH_RECORD_INVALID")
        level = m["matching"]["tie_level"]
        _need(level in (TIE_EXACT, TIE_FOLDED, TIE_NONE),
              "UT013_TIE_LEVEL_INVALID")
        status[st] = status.get(st, 0) + 1
        levels[level] = levels.get(level, 0) + 1
    return {
        "contract": CONTRACT, "version": VERSION,
        "matches_total": len(matches),
        "links_by_status": status, "ties_by_level": levels,
        **{flag: False for flag in _FLAGS},
        "consensus_claimed": False,
        "preference_by_system": False,
    }
