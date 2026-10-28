"""H-Search-01: find *candidate* narration cues in pinned Tafsir passages.

No source sentence without an actual cue is labelled a narration mention.
All spans are anchored in the raw imported Tafsir record and remain
UNVERIFIED. These rules do not authenticate the isnad or narration type.
"""
from __future__ import annotations

import re

from engines.hadith.hsearch.contracts import make_mention
from engines.tafsir.t023 import _validate_passage

_RE_MARFU = re.compile(
    r"(?:عن\s+رسول\s+الله|قال\s+رسول\s+الله|قال\s+النبي|قال\s*ﷺ)")
_RE_MAWQUF = re.compile(r"(?:قال\s+ابن\s+عباس|عن\s+ابن\s+عباس)")
# Linguistic markers for known Successors: not companion-stopped reports.
# Historical identity is still not independently established here.
_RE_MAQTU = re.compile(
    r"(?:عن\s+مجاهد|قال\s+مجاهد|عن\s+قتادة|قال\s+قتادة|"
    r"عن\s+الحسن|قال\s+الحسن|عن\s+سعيد\s+بن\s+جبير|"
    r"قال\s+سعيد\s+بن\s+جبير)")
_RE_UNDETERMINED = re.compile(r"(?:عن\s+السدي|قال\s+السدي)")
_RE_NARRATED = re.compile(r"(?:روى|أخرج|حدثنا|أخبرنا|أنبأنا)\b")
_MIN_LENGTH = 12
_MAX_MENTION_CHARS = 1000


def detect_mentions(passage: dict, *, min_len: int = _MIN_LENGTH) -> list[dict]:
    """Return strictly marked, bounded candidates; never whole plain prose."""
    _validate_passage(passage)
    if type(min_len) is not int or not 1 <= min_len <= 1000:
        raise ValueError("HS_MIN_LEN_INVALID")
    text = passage["interpretation_statement"]
    meta = {
        "quran_reference": passage["quran_reference"],
        "tafsir_work_id": passage["work_id"],
        "tafsir_source_record_id": passage["source_record_id"],
        "passage_id": passage["interpretation_id"],
        "passage_char_start": passage["evidence_span"][0],
    }
    markers = []
    for pattern, kind in (
        (_RE_MARFU, "MARFU"), (_RE_MAWQUF, "MAWQUF"),
        (_RE_MAQTU, "MAQTU"), (_RE_UNDETERMINED, "UNDETERMINED"),
        (_RE_NARRATED, "UNDETERMINED"),
    ):
        for match in pattern.finditer(text):
            markers.append((match.start(), match.end(), kind))
    markers.sort(key=lambda m: (m[0], -(m[1] - m[0])))
    unique = []
    for mark in markers:
        if unique and mark[0] < unique[-1][1]:
            continue
        unique.append(mark)
    out = []
    for i, (start, marker_end, kind) in enumerate(unique):
        next_start = unique[i + 1][0] if i + 1 < len(unique) else len(text)
        end = min(next_start, start + _MAX_MENTION_CHARS)
        # Keep the marker and following bounded context, not prior prose.
        if end - start < min_len or end < marker_end:
            continue
        out.append(make_mention(
            meta=meta, raw_text=text, span=(start, end),
            mention_type=kind, attribution_status="IMPLIED_BY_MARKER",
        ))
    return out


def detect_all(passages: list[dict]) -> list[dict]:
    if type(passages) is not list:
        raise ValueError("HS_PASSAGES_INVALID")
    mentions = []
    for p in passages:
        mentions.extend(detect_mentions(p))
    return mentions
