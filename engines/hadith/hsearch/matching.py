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
                   *, texts: dict | None = None) -> list[dict]:
    """Match mentions against witness candidates.

    texts: optional {witness_id: full_raw_text} for TEXTUALLY_SUPPORTED
    verification (substring must exist in the witness source raw text at the
    recorded span, and digest must recompute).
    """
    _need(type(mentions) is list and type(witnesses) is list,
          "HS_MATCH_INPUT_INVALID")
    if not witnesses:
        return [make_link(mention=m, witness=None, match_status="SOURCE_UNAVAILABLE",
                          match_method="no_authorized_source_available")
                for m in mentions]
    wit_ngrams = [(w, _ngrams(w.get("_text", "") or "")) for w in witnesses]
    links = []
    for m in mentions:
        best = None
        for w, ng in wit_ngrams:
            mg = _ngrams(m.get("_mention_text", "") or "")
            shared = len(mg & ng)
            if shared >= 1 and (best is None or shared > best[1]):
                best = (w, shared)
        if best is None:
            links.append(make_link(mention=m, witness=None,
                                   match_status="NO_MATCH",
                                   match_method="distinctive_ngram_overlap"))
            continue
        w, shared = best
        status = "CANDIDATE_MATCH"
        method = "distinctive_ngram_overlap"
        # upgrade requires verified long shared substring on both raw texts
        mt = (m.get("_mention_text") or "")
        wt = (w.get("_text") or "")
        if mt and wt:
            shared_len = _longest_shared(mt, wt)
            if shared_len >= _SHARED_SUBSTR_MIN:
                span = w.get("raw_source_span")
                snippet = wt[span[0]:span[1]] if span and len(wt) >= span[1] else ""
                import hashlib as _h
                digest_ok = (snippet and _h.sha256(
                    snippet.encode("utf-8")).hexdigest()
                    == w.get("evidence_sha256"))
                if digest_ok:
                    status = "TEXTUALLY_SUPPORTED"
                    method = f"verified_shared_substring>={_SHARED_SUBSTR_MIN}"
        links.append(make_link(mention=m, witness=w, match_status=status,
                               match_method=method))
    return links
