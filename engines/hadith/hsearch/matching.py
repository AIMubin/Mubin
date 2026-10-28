"""H-Search-01: exact-location, conservative lexical candidate matching.

Each source file is independently git-blob-verified by the acquisition
layer. This matcher does not infer narration identity or issue grades.
A 10-word overlap only produces CANDIDATE_MATCH. To move to
TEXTUALLY_SUPPORTED requires separate independent, scoped evidence;
this routine NEVER performs that promotion.
"""
from __future__ import annotations

import hashlib
import re

from engines.hadith.hsearch.contracts import make_link


def _need(condition, code):
    if not condition:
        raise ValueError(code)


_MIN_WORDS = 10


def _fold(text: str) -> str:
    text = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", text)
    text = re.sub(r"[\u0623\u0625\u0622]", "\u0627", text)
    text = text.replace("\u0649", "\u064a").replace("\u0629", "\u0647")
    return re.sub(r"\s+", " ", text)


def _probes(text: str) -> list[str]:
    words = _fold(text).strip().split()
    if len(words) < _MIN_WORDS:
        return []
    return [" ".join(words[i:i + _MIN_WORDS])
            for i in range(len(words) - _MIN_WORDS + 1)]


def match_mentions(mentions: list[dict], witnesses: list[dict],
                   *, source_texts: dict | None = None) -> list[dict]:
    """Match only *inside* exact cited witness spans.

    source_texts keys are source IDs, not witness IDs. All witness snippets
    must rehash to their evidence_sha256 and their locator must refer to
    the same pinned source. Shared wording remains an unverified candidate.
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
    for w in witnesses:
        sid = w.get("source_id")
        raw = raw_sources.get(sid)
        _need(type(raw) is str, "HS_MATCH_SOURCE_NOT_BOUND")
        span = w.get("raw_source_span")
        _need(type(span) is list and len(span) == 2
              and all(type(n) is int for n in span)
              and 0 <= span[0] < span[1] <= len(raw),
              "HS_WITNESS_SPAN_INVALID")
        snippet = raw[span[0]:span[1]]
        _need(hashlib.sha256(snippet.encode("utf-8")).hexdigest()
              == w.get("evidence_sha256"), "HS_WITNESS_EVIDENCE_INVALID")
        indexed.setdefault(sid, []).append(w)
    folded_sources = {sid: _fold(raw_sources[sid])
                      for sid in indexed}
    links = []
    for m in mentions:
        mention_text = m.get("_mention_text")
        _need(type(mention_text) is str and bool(mention_text),
              "HS_MENTION_TEXT_NOT_BOUND")
        _need(hashlib.sha256(mention_text.encode("utf-8")).hexdigest()
              == m.get("evidence_sha256"), "HS_MENTION_EVIDENCE_INVALID")
        phrases = _probes(mention_text)
        chosen = None
        matched_probe = None
        for sid in sorted(indexed):
            # Cheap whole-source prefilter, but never cite a whole file:
            # the match must also occur inside the specific witness span.
            available = [p for p in phrases if p in folded_sources[sid]]
            if not available:
                continue
            raw = raw_sources[sid]
            for w in indexed[sid]:
                a, b = w["raw_source_span"]
                piece = _fold(raw[a:b])
                probe = next((p for p in available if p in piece), None)
                if probe is not None:
                    chosen, matched_probe = w, probe
                    break
            if chosen is not None:
                break
        if chosen is None:
            links.append(make_link(
                mention=m, witness=None, match_status="NO_MATCH",
                match_method="no_verified_witness_local_10word_overlap"))
            continue
        link = make_link(
            mention=m, witness=chosen, match_status="CANDIDATE_MATCH",
            match_method="pinned_witness_span_shared_10word_phrase")
        link["matching_phrase_sha256"] = hashlib.sha256(
            matched_probe.encode("utf-8")).hexdigest()
        link["identity_of_narration_confirmed"] = False
        links.append(link)
    return links
