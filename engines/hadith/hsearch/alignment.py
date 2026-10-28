"""Reversible, codepoint-accurate Arabic folding for source citations.

Search normalization is strictly a *derived index*. Each folded codepoint
retains the [start, end) range of contributing original raw codepoints.
No normalized offsets are ever presented as source offsets.

A matched sequence is a lexical witness, NOT a hadith-identity claim.
"""
from __future__ import annotations

import hashlib
import re

_DIACRITICS = set(chr(i) for i in range(0x064B, 0x0660)) | {"\u0670", "\u0640"}
_ALEF = {"\u0623": "\u0627", "\u0625": "\u0627", "\u0622": "\u0627"}


def fold_with_raw_map(raw: str) -> tuple[str, list[tuple[int, int]]]:
    """Return (normalized text, per-character raw [start,end) span).

    Unicode codepoint positions, not UTF-8 byte offsets. A removed
    diacritic after a codepoint is absorbed into that prior raw span;
    contiguous whitespace is represented by one normalized space.
    """
    if type(raw) is not str:
        raise ValueError("HS_ALIGNMENT_RAW_TEXT_INVALID")
    folded: list[str] = []
    origins: list[tuple[int, int]] = []
    for i, ch in enumerate(raw):
        if ch in _DIACRITICS:
            if origins:
                a, _ = origins[-1]
                origins[-1] = (a, i + 1)
            continue
        if ch.isspace():
            if folded and folded[-1] == " ":
                a, _ = origins[-1]
                origins[-1] = (a, i + 1)
            else:
                folded.append(" ")
                origins.append((i, i + 1))
            continue
        value = _ALEF.get(ch, "\u064a" if ch == "\u0649" else
                          "\u0647" if ch == "\u0629" else ch)
        folded.append(value)
        origins.append((i, i + 1))
    return "".join(folded), origins


def _raw_span(raw: str, folded: str,
              mapping: list[tuple[int, int]], start: int,
              end: int) -> tuple[int, int]:
    if not (0 <= start < end <= len(mapping)):
        raise ValueError("HS_ALIGNMENT_FOLDED_SPAN_INVALID")
    a, b = mapping[start][0], mapping[end - 1][1]
    if not 0 <= a < b <= len(raw):
        raise ValueError("HS_ALIGNMENT_RAW_SPAN_INVALID")
    # Validate each returned source window by independently re-folding
    # its *literal original text*, including any attached harakat.
    restored, _ = fold_with_raw_map(raw[a:b])
    if restored != folded[start:end]:
        raise ValueError("HS_ALIGNMENT_ROUNDTRIP_FAILED")
    return a, b


def align_shared_tokens(mention_raw: str, witness_raw: str, *,
                        min_words: int = 10) -> dict | None:
    """Find one shared *whole-token* normalized sequence and both raw spans.

    Deterministic: earliest candidate in the mention and earliest in
    the witness. Overlapping tokens, intra-word matches, incomplete
    snippets, and normalized-only fake offsets cannot pass.
    """
    if type(mention_raw) is not str or type(witness_raw) is not str:
        raise ValueError("HS_ALIGNMENT_INPUT_INVALID")
    if type(min_words) is not int or not 2 <= min_words <= 30:
        raise ValueError("HS_ALIGNMENT_MIN_WORDS_INVALID")
    mf, mm = fold_with_raw_map(mention_raw)
    wf, wm = fold_with_raw_map(witness_raw)
    a = list(re.finditer(r"\S+", mf))
    b = list(re.finditer(r"\S+", wf))
    if len(a) < min_words or len(b) < min_words:
        return None
    # This runs only on the bounded, independently verified witness block.
    candidates: dict[tuple[str, ...], tuple[int, int]] = {}
    for i in range(len(b) - min_words + 1):
        seq = tuple(wf[t.start():t.end()] for t in b[i:i + min_words])
        candidates.setdefault(seq, (b[i].start(), b[i + min_words - 1].end()))
    for i in range(len(a) - min_words + 1):
        seq = tuple(mf[t.start():t.end()] for t in a[i:i + min_words])
        matched = candidates.get(seq)
        if matched is None:
            continue
        ma, mb = _raw_span(
            mention_raw, mf, mm, a[i].start(), a[i + min_words - 1].end())
        wa, wb = _raw_span(witness_raw, wf, wm, matched[0], matched[1])
        expected = " ".join(seq)
        # Matching normalizes whitespace while source citations retain
        # literal whitespace. Validate the exact *word* sequence.
        ma_tokens = " ".join(re.findall(r"\S+",
                                      fold_with_raw_map(mention_raw[ma:mb])[0]))
        wa_tokens = " ".join(re.findall(r"\S+",
                                      fold_with_raw_map(witness_raw[wa:wb])[0]))
        if ma_tokens != expected or wa_tokens != expected:
            raise ValueError("HS_ALIGNMENT_TOKEN_ROUNDTRIP_FAILED")
        return {
            "folded_word_count": min_words,
            "folded_phrase_sha256": hashlib.sha256(
                expected.encode("utf-8")).hexdigest(),
            "tafsir_relative_span": [ma, mb],
            "hadith_relative_span": [wa, wb],
            "tafsir_raw_phrase_sha256": hashlib.sha256(
                mention_raw[ma:mb].encode("utf-8")).hexdigest(),
            "hadith_raw_phrase_sha256": hashlib.sha256(
                witness_raw[wa:wb].encode("utf-8")).hexdigest(),
            "identity_of_narration_confirmed": False,
            "text_included": False,
        }
    return None
