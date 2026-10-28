"""H-Search-01.2: narration-mention detection inside grounded tafsir passages.

Lexical markers locate CANDIDATE mentions; they never establish hadith type
or isnad authenticity. Ambiguous mentions stay UNDETERMINED.
"""
from __future__ import annotations

import re
from engines.hadith.hsearch.contracts import make_mention

_RE_MARFU = re.compile(r"(?:عن\s+رسول\s+الله|قال\s+رسول\s+الله[^ا-ي]|قال\s+النبي|قال\s*ﷺ)")
_RE_MAWQUF = re.compile(r"(?:قال\s+ابن\s+عباس|عن\s+ابن\s+عباس|عن\s+مجاهد|قال\s+مجاهد|عن\s+قتادة|قال\s+قتادة|عن\s+السدي|قال\s+السدي|عن\s+الحسن|عن\s+سعيد\s+بن\s+جبير)")
_RE_NARRATED = re.compile(r"(?:روى|أخرج|حدثنا|أخبرنا|أنبأنا)\b")
_RE_MIN_LEN = 20


def _segment_at_markers(text: str, markers: list[tuple[int, str, str]]
                        ) -> list[tuple[int, int, str, str]]:
    """Split text into segments starting at each marker."""
    if not markers:
        return [(0, len(text), "UNDETERMINED", "UNKNOWN")] \
            if len(text) >= _RE_MIN_LEN else []
    segs = []
    if markers[0][0] > 0:
        segs.append((0, markers[0][0], "UNDETERMINED", "UNKNOWN"))
    for i, (pos, mtype, attr) in enumerate(markers):
        end = markers[i + 1][0] if i + 1 < len(markers) else len(text)
        segs.append((pos, end, mtype, attr))
    return segs


def detect_mentions(passage: dict, *, min_len: int = 20) -> list[dict]:
    """Detect narration mentions in one T0.2/T0.2.3 grounded passage.

    passage: dict with quran_reference, tafsir_work_id,
    tafsir_source_record_id, interpretation_statement (exact raw substring),
    evidence_span.
    """
    text = passage.get("interpretation_statement") or ""
    if type(text) is not str or len(text) < _RE_MIN_LEN:
        return []
    meta = {
        "quran_reference": passage["quran_reference"],
        "tafsir_work_id": passage["work_id"],
        "tafsir_source_record_id": passage["source_record_id"],
    }
    markers = []
    for m in _RE_MARFU.finditer(text):
        markers.append((m.start(), "MARFU", "EXPLICIT_IN_TEXT"))
    for m in _RE_MAWQUF.finditer(text):
        # skip positions already claimed by marfu markers
        if any(a <= m.start() < b for a, b, _, _ in
               [(x[0], x[0] + 10, "", "") for x in markers]):
            continue
        markers.append((m.start(), "MAWQUF", "EXPLICIT_IN_TEXT"))
    markers.sort(key=lambda x: x[0])
    segs = _segment_at_markers(text, markers)
    out = []
    for s0, s1, mtype, attr in segs:
        e1 = s1
        while e1 > s0 and text[e1 - 1] in " \t":
            e1 -= 1
        if e1 - s0 < min_len:
            continue
        # narrated-verb markers inside a segment keep its type; a PLAIN
        # segment containing a narration verb stays UNDETERMINED
        out.append(make_mention(meta=meta, raw_text=text, span=(s0, e1),
                                mention_type=mtype,
                                attribution_status=attr))
    return out


def detect_all(passages: list[dict]) -> list[dict]:
    mentions = []
    for p in passages:
        mentions.extend(detect_mentions(p))
    return mentions
