"""U0.1 Stage07: reversible Arabic literal and folded *candidate* retrieval.

Every returned hit is located on ORIGINAL, SHA256-pinned UTF-8 source bytes.
Exact hits and orthographic candidates are always in separate collections.
Folds never change the source and do not change hamza, alef, negation,
tatweel, word order or the CONTENT between editorial square brackets.
No match proves a legal claim; no zero-hit proves absence of a qarinah.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from engines.usul.witness_alignment import (
    ARABIC_MARKS, EDITORIAL_BRACKETS, SPACE, SHA, MAX_SECTION_BYTES,
)

VERSION = "usul-arabic-evidence/0.1.0"
EXACT = "literal_exact_v1"
FOLD_MARKS = "ignore_arabic_marks_v1"
FOLD_BRACKETS = "ignore_arabic_marks_and_brackets_v1"
FOLD_SPACES = "ignore_arabic_marks_brackets_and_spaces_v1"
PROFILES = (FOLD_MARKS, FOLD_BRACKETS, FOLD_SPACES)
QUERY_ID = re.compile(r"^[a-z][a-z0-9_.:-]{2,127}$")
MAX_QUERIES = 20
MAX_QUERY_CHARS = 128
MAX_MATCHES = 2048
MAX_WITNESSES = 4


class ArabicRetrievalError(ValueError):
    pass


def _require(ok, reason):
    if not ok:
        raise ArabicRetrievalError(reason)


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _validate_queries(queries):
    _require(type(queries) is list and 1 <= len(queries) <= MAX_QUERIES,
             "queries must be a bounded list")
    seen = set()
    for q in queries:
        _require(type(q) is dict and set(q) == {"id", "literal", "candidate_profiles"},
                 "invalid query schema")
        qid, literal, selected = q["id"], q["literal"], q["candidate_profiles"]
        _require(type(qid) is str and QUERY_ID.fullmatch(qid) and qid not in seen,
                 "invalid or repeated query ID")
        seen.add(qid)
        _require(type(literal) is str and 1 <= len(literal) <= MAX_QUERY_CHARS
                 and literal.strip() and not any(ord(c) < 32 or ord(c) == 127
                                                 for c in literal),
                 "invalid literal (empty, overlarge or contains control characters)")
        _require(type(selected) is list and len(selected) == len(set(
            item for item in selected if isinstance(item, str)
        )) and all(type(p) is str and p in PROFILES for p in selected)
                 and list(selected) == sorted(selected, key=PROFILES.index),
                 "unsupported/duplicate/out-of-order profile")
    return queries


def _validate_witnesses(witnesses):
    _require(type(witnesses) is list and 1 <= len(witnesses) <= MAX_WITNESSES,
             "witnesses must be a bounded array")
    seen = set()
    for w in witnesses:
        _require(type(w) is dict and set(w) == {
            "source_id", "section_path", "section_sha256", "source_url",
            "section_locator", "offset_basis", "source_byte_base",
            "source_line_base",
        }, "invalid witness descriptor schema")
        _require(type(w["source_id"]) is str
                 and QUERY_ID.fullmatch(w["source_id"])
                 and w["source_id"] not in seen, "invalid/duplicate witness ID")
        seen.add(w["source_id"])
        _require(type(w["section_path"]) in (str, Path),
                 "invalid local section path")
        _require(type(w["section_sha256"]) is str
                 and SHA.fullmatch(w["section_sha256"]), "untrusted section digest")
        _require(type(w["source_url"]) is str and w["source_url"].startswith("https://")
                 and len(w["source_url"]) <= 1024, "invalid source URL")
        _require(type(w["section_locator"]) is str and w["section_locator"].strip()
                 and len(w["section_locator"]) <= 256, "invalid section locator")
        _require(w["offset_basis"] in ("utf8_export", "extracted_section"),
                 "unknown absolute byte-offset coordinate system")
        _require(type(w["source_byte_base"]) is int and 0 <= w["source_byte_base"] <= 8000000
                 and type(w["source_line_base"]) is int and w["source_line_base"] >= 1,
                 "invalid section source coordinate bases")
        if w["offset_basis"] == "extracted_section":
            _require(w["source_byte_base"] == 0 and w["source_line_base"] == 1,
                     "section-only coordinates must be relative to the section")
    return witnesses


def _fold_char(ch, profile):
    if ord(ch) in ARABIC_MARKS:
        return ""
    if profile in (FOLD_BRACKETS, FOLD_SPACES) and ch in EDITORIAL_BRACKETS:
        return ""
    if profile == FOLD_SPACES and ch in SPACE:
        return ""
    return ch


def _fold_with_map(text, profile):
    """Return diagnostic text plus a reversible map to ORIGINAL codepoints.

    Every emitted character points at exactly one source codepoint. Characters
    removed in the diagnostic view remain inside the original match's byte
    slice between first and last surviving codepoints. No replacements or
    Unicode normalization are performed.
    """
    chars, source_indexes = [], []
    for i, ch in enumerate(text):
        out = _fold_char(ch, profile)
        if out:
            chars.append(out)
            source_indexes.append(i)
    return "".join(chars), source_indexes


def _line_index(raw):
    # splitlines() splits on additional unicode line separators *only when
    # given decoded text*. Splitting UTF-8 BYTES keeps exact LF/CRLF offsets.
    lines = raw.splitlines(keepends=True)
    _require(b"".join(lines) == raw, "line partition does not reconstruct section")
    result = []
    offset = 0
    for i, line in enumerate(lines):
        result.append((offset, offset + len(line), _hash(line)))
        offset += len(line)
    _require(offset == len(raw), "line index omitted source bytes")
    return lines, result


def _locate(line, start_col, end_col, row_start, line_digest, line_no,
            original_text, *, profile, query_digest, normalized_digest=None):
    starts = [0]
    for c in line:
        starts.append(starts[-1] + len(c.encode("utf-8")))
    a, b = row_start + starts[start_col], row_start + starts[end_col]
    original = original_text[a:b]
    _require(bool(original), "cannot report empty original source span")
    return {
        "profile": profile,
        "coordinate_basis": "PINNED_ORIGINAL_SECTION_UTF8",
        "section_byte_start": a,
        "section_byte_end_exclusive": b,
        "section_line_number": line_no,
        "section_column_codepoints_zero_based": start_col,
        "original_bytes_sha256": _hash(original),
        "original_line_sha256": line_digest,
        "query_utf8_sha256": query_digest,
        "diagnostic_folded_match_sha256": normalized_digest,
        "source_text_included": False,
    }


def _find_all(text, literal):
    at = 0
    while (found := text.find(literal, at)) != -1:
        yield found
        at = found + 1  # overlapping literal matches intentionally included


def retrieve(witnesses, queries):
    """Reproducible metadata-only retrieval; callers supply TRUSTED section pins.

    For real al-Waraqat sources the Stage07 pilot separately replays and pins
    both original HTML captures BEFORE calling this generic function.
    """
    _validate_queries(queries)
    _validate_witnesses(witnesses)
    reports = []
    for w in witnesses:
        path = Path(w["section_path"])
        length = path.stat().st_size
        _require(0 < length <= MAX_SECTION_BYTES, "section size outside bound")
        raw = path.read_bytes()
        _require(len(raw) == length and _hash(raw) == w["section_sha256"],
                 "section changed or digest differs from trusted pin")
        _require(not raw.startswith(b"\xef\xbb\xbf") and b"\x00" not in raw,
                 "BOM/binary-looking section refused")
        try:
            raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ArabicRetrievalError("section must be strict UTF-8") from exc
        lines, index = _line_index(raw)
        line_proof = [
            {"line": i + 1, "byte_start": row[0],
             "byte_end_exclusive": row[1], "sha256": row[2]}
            for i, row in enumerate(index)
        ]
        entries = []
        for query in queries:
            literal = query["literal"]
            query_digest = _hash(literal.encode("utf-8"))
            strict, candidates = [], {p: [] for p in query["candidate_profiles"]}
            for i, (line_bytes, (row_start, _, line_digest)) in enumerate(zip(lines, index)):
                line = line_bytes.decode("utf-8")
                for pos in _find_all(line, literal):
                    strict.append(_locate(line, pos, pos + len(literal), row_start,
                                          line_digest, i + 1, raw, profile=EXACT,
                                          query_digest=query_digest))
                    _require(len(strict) <= MAX_MATCHES, "exact match set exceeds bound")
                for profile in query["candidate_profiles"]:
                    view, origin = _fold_with_map(line, profile)
                    folded_query, _ = _fold_with_map(literal, profile)
                    _require(bool(folded_query),
                             "fold profile makes the query empty; refusing search")
                    for at in _find_all(view, folded_query):
                        begin = origin[at]
                        end = origin[at + len(folded_query) - 1] + 1
                        hit = _locate(line, begin, end, row_start, line_digest,
                                      i + 1, raw, profile=profile,
                                      query_digest=query_digest,
                                      normalized_digest=_hash(folded_query.encode("utf-8")))
                        # Do not duplicate *literal-identical* source spans as
                        # "extra" orthographic candidates.
                        if raw[hit["section_byte_start"]:hit["section_byte_end_exclusive"]] == literal.encode("utf-8"):
                            continue
                        candidates[profile].append(hit)
                        _require(len(candidates[profile]) <= MAX_MATCHES,
                                 "candidate match set exceeds bound")
            entries.append({
                "query_id": query["id"],
                "query_utf8_sha256": query_digest,
                "exact_profile": EXACT,
                "strict_match_count": len(strict),
                "strict_matches": strict,
                "candidate_profiles": [
                    {"profile": p, "classification": "ORTHOGRAPHIC_CANDIDATE_ONLY",
                     "match_count": len(candidates[p]), "matches": candidates[p]}
                    for p in query["candidate_profiles"]
                ],
                "zero_exact_hits_does_not_prove_absence": True,
                "zero_candidate_hits_does_not_prove_absence": True,
                "semantic_equivalence_verified": False,
                "source_text_included": False,
                "query_text_included": False,
            })
        reports.append({
            "source_id": w["source_id"],
            "source_url": w["source_url"],
            "section_locator": w["section_locator"],
            "section_sha256": w["section_sha256"],
            "indexed_section_bytes": len(raw),
            "indexed_section_lines": len(lines),
            "line_index_sha256": _hash(_canonical(line_proof)),
            "line_index_complete": True,
            "offset_basis": w["offset_basis"],
            "source_byte_base": w["source_byte_base"],
            "source_line_base": w["source_line_base"],
            "absolute_offsets_are_for": w["offset_basis"],
            "queries": entries,
        })
    return {
        "engine": VERSION,
        "status": "ARABIC_SOURCE_RETRIEVAL_PASS",
        "source_count": len(reports),
        "profile_order": list(PROFILES),
        "witnesses": reports,
        "all_offsets_reference_original_section_bytes": True,
        "normalized_match_is_only_candidate": True,
        "orthographic_fold_does_not_normalize_hamza_or_negation": True,
        "juristic_inference_allowed": False,
        "semantic_qarinah_verified": False,
        "scholarly_verified": False,
        "redistribution_approved": False,
        "source_text_included": False,
    }
