"""H-Search-01.3: conservative mention-to-witness matching.

Shared distinctive n-grams locate CANDIDATE matches; upgrading to
TEXTUALLY_SUPPORTED requires verified span/digest on both sides plus a
shared long substring. Wording similarity alone never merges narrations.
"""
from __future__ import annotations

import re
from engines.hadith.hsearch.contracts import make_link


def _need(ok, code):
    if not ok:
        raise ValueError(code)

_NGRAM = 12
_SHARED_SUBSTR_MIN = 25


def _fold(text: str) -> str:
    text = re.sub(r"[\u064B-\u065F\u0670\u0640]", "", text)  # harakat+tatweel
    text = re.sub(r"[\u0623\u0625\u0622]", "\u0627", text)
    text = text.replace("\u0649", "\u064a").replace("\u0629", "\u0647")
    return re.sub(r"\s+", " ", text)


def _ngrams(text: str):
    words = _fold(text).split(" ")
    return {" ".join(words[i:i + _NGRAM])
            for i in range(len(words) - _NGRAM + 1)}


def _longest_shared(a: str, b: str) -> int:
    fa, fb = _fold(a), _fold(b)
    best, la = 0, len(fa)
    for i in range(0, la - _SHARED_SUBSTR_MIN + 1, 5):
        for j in range(_SHARED_SUBSTR_MIN, la - i + 1, 5):
            sub = fa[i:i + j]
            if sub in fb:
                best = max(best, j)
            else:
                break
    return best


def match_mentions(mentions: list[dict], witnesses: list[dict],
                   *, source_texts: dict | None = None) -> list[dict]:
    """Match mentions against witness candidates.

    Memory-light: each source raw text is folded once and scanned linearly
    with mention 10-grams (no full-corpus n-gram sets). CANDIDATE_MATCH
    requires a shared >=10-word substring; TEXTUALLY_SUPPORTED additionally
    requires the witness block digest to recompute over its pinned span.
    source_texts: {source_id: raw_text} provided by the pipeline.
    """
    _need(type(mentions) is list and type(witnesses) is list,
          "HS_MATCH_INPUT_INVALID")
    if not witnesses:
        return [make_link(mention=m, witness=None,
                          match_status="SOURCE_UNAVAILABLE",
                          match_method="no_authorized_source_available")
                for m in mentions]
    folded_sources = {}
    for w in witnesses:
        sid = w.get("source_id")
        if sid not in folded_sources:
            raw = (source_texts or {}).get(sid, w.get("_text", "") or "")
            folded_sources[sid] = _fold(raw) if raw else ""
    links = []
    for m in mentions:
        mt = m.get("_mention_text") or ""
        fmt = _fold(mt) if mt else ""
        words = fmt.split(" ")
        best = None
        if len(words) >= 10:
            for i in range(len(words) - 9):
                probe = " ".join(words[i:i + 10])
                for sid, ftext in folded_sources.items():
                    if ftext and probe in ftext:
                        if best is None or len(probe) > len(best[2]):
                            best = (sid, w := next(
                                w for w in witnesses
                                if w.get("source_id") == sid), probe)
                        break
        if best is None:
            links.append(make_link(mention=m, witness=None,
                                   match_status="NO_MATCH",
                                   match_method="distinctive_substring_scan"))
            continue
        sid, w, probe = best
        status = "CANDIDATE_MATCH"
        method = "shared_10word_substring"
        if len(probe) >= _SHARED_SUBSTR_MIN:
            span = w.get("raw_source_span")
            wt = (source_texts or {}).get(sid, w.get("_text", "") or "")
            snippet = wt[span[0]:span[1]] if span and len(wt) >= span[1] else ""
            import hashlib as _h
            if snippet and _h.sha256(snippet.encode("utf-8")).hexdigest() \
                    == w.get("evidence_sha256"):
                status = "TEXTUALLY_SUPPORTED"
                method = "verified_shared_substring"
        links.append(make_link(mention=m, witness=w, match_status=status,
                               match_method=method))
    return links
