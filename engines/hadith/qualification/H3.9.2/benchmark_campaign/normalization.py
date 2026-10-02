from __future__ import annotations

import re
from typing import Any

from .core import canonical_json_bytes, sha256_bytes

_ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
_WS = re.compile(r"\s+")


def normalize_arabic_text(text: str) -> str:
    """Conservative normalization for duplicate/leakage fingerprints.

    This is intentionally not a semantic normalizer. It removes Arabic diacritics,
    tatweel, normalizes common alif/ya variants, and collapses whitespace so trivial
    orthographic differences cannot bypass leakage checks.
    """
    text = _ARABIC_DIACRITICS.sub("", text)
    text = text.replace("ـ", "")
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ى", "ي")
    return _WS.sub(" ", text).strip()


def canonical_task_input(payload: dict[str, Any]) -> Any:
    if "input" not in payload:
        raise ValueError("payload.input is required for qualification records")
    value = payload["input"]
    return _normalize_value(value)


def _normalize_value(value: Any) -> Any:
    if isinstance(value, str):
        return normalize_arabic_text(value)
    if isinstance(value, list):
        return [_normalize_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize_value(value[k]) for k in sorted(value)}
    return value


def fingerprint_payload(payload: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(canonical_task_input(payload)))
