"""H-Search-01: source-bound candidate matching with reversible raw offsets.

A shared ten-token normalized phrase does NOT establish an identical hadith,
chain, grading, attribution, or exegetical judgment. Even after alignment
the link stays CANDIDATE_MATCH, not TEXTUALLY_SUPPORTED.
"""
from __future__ import annotations

import hashlib
import re

from engines.hadith.hsearch.alignment import align_shared_tokens
from engines.hadith.hsearch.contracts import make_link


def _need(ok, code):
    if not ok:
        raise ValueError(code)


_MIN_WORDS = 10
_SHA40 = re.compile(r"[0-9a-f]{40}")


def _fold(text: str) -> str:
    """Memory-light normalization for large files; offset maps stay local."""
    text = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", text)
    text = re.sub(r"[\u0623\u0625\u0622]", "\u0627", text)
    text = text.replace("\u0649", "\u064a").replace("\u0629", "\u0647")
    return re.sub(r"\s+", " ", text)


def _probes(text: str) -> list[str]:
    words = _fold(text).split()
    return [" ".join(words[i:i + _MIN_WORDS])
            for i in range(len(words) - _MIN_WORDS + 1)]


def _git_blob_sha(text: str) -> str:
    data = text.encode("utf-8")
    return hashlib.sha1(
        f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def match_mentions(mentions: list[dict], witnesses: list[dict],
                   *, source_texts: dict | None = None) -> list[dict]:
    """Locate first 10-token phrase inside a pinned *witness block*.

    The source must rehash to the declared Git blob. The witness block
    and mention both rehash to their cited UTF-8 evidence digest. The
    exact phrase's original raw codepoint span is recovered on *both*
    sides, and separately rehashed. The result remains only lexical.
    """
    _need(type(mentions) is list and type(witnesses) is list,
          "HS_MATCH_INPUT_INVALID")
    if not witnesses:
        return [make_link(
            mention=m, witness=None, match_status="SOURCE_UNAVAILABLE",
            match_method="no_authorized_source_available") for m in mentions]
    raw_sources = source_texts or {}
    _need(type(raw_sources) is dict, "HS_SOURCE_MAP_INVALID")
    indexed: dict[str, list[dict]] = {}
    blob_by_source: dict[str, str] = {}
    for w in witnesses:
        sid = w.get("source_id")
        raw = raw_sources.get(sid)
        _need(type(raw) is str, "HS_MATCH_SOURCE_NOT_BOUND")
        blob = w.get("source_blob_sha")
        _need(type(blob) is str and _SHA40.fullmatch(blob) is not None,
              "HS_WITNESS_BLOB_PIN_INVALID")
        if sid not in blob_by_source:
            blob_by_source[sid] = _git_blob_sha(raw)
        _need(blob_by_source[sid] == blob, "HS_MATCH_SOURCE_BLOB_MISMATCH")
        span = w.get("raw_source_span")
        _need(type(span) is list and len(span) == 2
              and all(type(n) is int for n in span)
              and 0 <= span[0] < span[1] <= len(raw),
              "HS_WITNESS_SPAN_INVALID")
        snippet = raw[span[0]:span[1]]
        _need(hashlib.sha256(snippet.encode("utf-8")).hexdigest()
              == w.get("evidence_sha256"), "HS_WITNESS_EVIDENCE_INVALID")
        indexed.setdefault(sid, []).append((w, _fold(snippet)))
    # File-wide search is a prefilter ONLY. A result must subsequently be
    # relocated *inside* the cited witness and pass folded→raw round-trip.
    folded_sources = {sid: _fold(raw_sources[sid])
                      for sid in indexed}
    links = []
    for m in mentions:
        mention_text = m.get("_mention_text")
        _need(type(mention_text) is str and bool(mention_text),
              "HS_MENTION_TEXT_NOT_BOUND")
        _need(hashlib.sha256(mention_text.encode("utf-8")).hexdigest()
              == m.get("evidence_sha256"), "HS_MENTION_EVIDENCE_INVALID")
        mspan = m.get("raw_source_span")
        _need(type(mspan) is list and len(mspan) == 2
              and all(type(n) is int for n in mspan)
              and mspan[1] - mspan[0] == len(mention_text)
              and mspan[0] >= 0, "HS_MENTION_RAW_SPAN_INVALID")
        probes = _probes(mention_text)
        chosen, aligned = None, None
        for sid in sorted(indexed):
            available = [p for p in probes if p in folded_sources[sid]]
            if not available:
                continue
            raw = raw_sources[sid]
            for w, folded_block in indexed[sid]:
                if not any(p in folded_block for p in available):
                    continue
                wa, wb = w["raw_source_span"]
                witness_text = raw[wa:wb]
                candidate = align_shared_tokens(
                    mention_text, witness_text, min_words=_MIN_WORDS)
                if candidate is not None:
                    chosen, aligned = w, candidate
                    break
            if chosen is not None:
                break
        if chosen is None:
            links.append(make_link(
                mention=m, witness=None, match_status="NO_MATCH",
                match_method="no_pinned_witness_10wholeword_match"))
            continue
        link = make_link(
            mention=m, witness=chosen, match_status="CANDIDATE_MATCH",
            match_method="aligned_folded_10word_lexical_overlap")
        ma, mb = aligned["tafsir_relative_span"]
        wa, wb = aligned["hadith_relative_span"]
        witness_start = chosen["raw_source_span"][0]
        link.update({
            "folded_phrase_sha256": aligned["folded_phrase_sha256"],
            "folded_word_count": aligned["folded_word_count"],
            "tafsir_shared_raw_span": [mspan[0] + ma, mspan[0] + mb],
            "hadith_shared_raw_span": [witness_start + wa, witness_start + wb],
            "tafsir_shared_raw_sha256": aligned["tafsir_raw_phrase_sha256"],
            "hadith_shared_raw_sha256": aligned["hadith_raw_phrase_sha256"],
            "shared_span_unit": "UNICODE_CODEPOINT_OFFSETS_IN_IMPORTED_RAW_TEXT",
            "textually_grounded_lexical_overlap": True,
            "tafsir_source_record_id": m.get("tafsir_source_record_id"),
            "hadith_source_blob_sha": chosen["source_blob_sha"],
            "hadith_source_version_id": chosen.get("source_version_id"),
            "identity_of_narration_confirmed": False,
            "scholarly_verified": False,
            "text_included": False,
        })
        links.append(link)
    return links
