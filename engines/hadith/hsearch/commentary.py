"""H-Search-01.4: critical commentary retrieval (reported judgments only).

Mubin never issues hadith judgments. Judgments are retrieved only when
explicitly present in a source near a located narration, with speaker,
work, exact phrase, span, and digest. Absence within searched scope is
reported as NO_CRITICAL_JUDGMENT_FOUND.
"""
from __future__ import annotations

import re
from engines.hadith.hsearch.contracts import JUDGMENT_PRESENCE, _need


def _sha(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()

_RE_JUDGMENT_CUES = re.compile(
    r"(?:ضعيف|لا\s+يصح|منكر|شاذ|صحيح|حسن|غريب|معضل|مدرج|لا\s+أعرفه|مجهول)")


def find_commentary(text: str, locator: str, *, source_id: str,
                    work_id: str, version_id: str, blob_sha: str) -> dict:
    """Scan ONE witness-adjacent source block for explicit judgment cues.

    Returns a redacted judgment record: never invents scope beyond the block.
    """
    _need(type(text) is str and text, "HS_TEXT_EMPTY")
    hits = list(_RE_JUDGMENT_CUES.finditer(text))
    if not hits:
        return {"presence": "NO_CRITICAL_JUDGMENT_FOUND",
                "source_id": source_id, "work_id": work_id,
                "locator": locator, "speaker": None, "phrase": None,
                "phrase_span": None, "phrase_sha256": None,
                "verification_status": "UNVERIFIED_CRITICAL_ATTRIBUTION",
                "scope_note": "judgment applies only to the exact text "
                              "scoped in the source; never generalized",
                "scholarly_verified": False, "text_included": False}
    first = hits[0]
    # expand to sentence-ish window around first cue
    s0 = max(0, text.rfind(".", 0, first.start()))
    s0 = s0 + 1 if s0 > 0 else 0
    e0 = text.find(".", first.end())
    e0 = len(text) if e0 < 0 else e0 + 1
    phrase = text[s0:e0].strip()
    return {
        "presence": "UNVERIFIED_CRITICAL_ATTRIBUTION",
        "source_id": source_id, "work_id": work_id, "locator": locator,
        "speaker": None,  # speaker requires explicit attribution evidence
        "phrase": None,   # redacted here; phrase text stays local
        "phrase_span": [s0, e0],
        "phrase_sha256": _sha(text[s0:e0].encode("utf-8")),
        "verification_status": "UNVERIFIED_CRITICAL_ATTRIBUTION",
        "scope_note": "judgment applies only to the exact text scoped in "
                      "the source; never generalized",
        "scholarly_verified": False, "text_included": False,
    }
