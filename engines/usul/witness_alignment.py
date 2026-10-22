"""U0.1 Stage06 — conservative, byte-addressed alignment of two PRIVATE text witnesses.

Only exact UTF-8 snapshot hashes and observed textual differences are proved.
Normalizations are diagnostics, NEVER evidence of semantic/lexical equivalence.
Raw text is never emitted; opcodes locate both unchanged and changed spans.
"""
from __future__ import annotations

import argparse
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import re

PROFILE_VERSION = "usul-witness-alignment/0.1.0"
MAX_SECTION_BYTES = 16384
MAX_DIFFERENCE_EVENTS = 2048
SHA = re.compile(r"^[0-9a-f]{64}$")
ARABIC_MARKS = (set(range(0x64B, 0x660)) | {0x670} |
                set(range(0x6D6, 0x6EE)))
EDITORIAL_BRACKETS = "[]"
# Whitelist of *only* known Unicode whitespace code points; never drop ZWNJ
# or tatweel, alef/hamza distinctions, punctuation other than square brackets.
SPACE = {" ", "\t", "\n", "\r", "\f", "\v", "\u00a0"}


class WitnessAlignmentError(ValueError):
    pass


def _need(value, message):
    if not value:
        raise WitnessAlignmentError(message)


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _read_pinned(path, pin):
    _need(type(pin) is str and SHA.fullmatch(pin) is not None,
          "independently frozen SHA256 is required for each witness")
    file = Path(path)
    size = file.stat().st_size
    _need(0 < size <= MAX_SECTION_BYTES, "witness text out of bounded section size")
    data = file.read_bytes()
    _need(len(data) == size and _sha(data) == pin,
          "witness section content differs from independently frozen digest")
    _need(not data.startswith(b"\xef\xbb\xbf") and b"\x00" not in data,
          "BOM or binary text refused")
    try:
        decoded = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise WitnessAlignmentError("invalid UTF-8 section") from exc
    return decoded, data


def _base(text):
    """Remove only named marks and editorial bracket *characters*, NOT content."""
    return "".join(ch for ch in text if
                   ord(ch) not in ARABIC_MARKS and ch not in EDITORIAL_BRACKETS)


def _space(text):
    return "".join(" " if ch in SPACE else ch for ch in text)


def _collapse(text):
    return re.sub(" +", " ", _space(text)).strip()


def _no_space(text):
    return "".join(ch for ch in text if ch not in SPACE)


def _byte_starts(text):
    starts = [0]
    for char in text:
        starts.append(starts[-1] + len(char.encode("utf-8")))
    return starts


def _line_number(text, char_start):
    return text.count("\n", 0, char_start) + 1


def _classify(left, right):
    if left == right:
        return "EXACT_EQUAL"
    a, b = _base(left), _base(right)
    if a == b:
        return "ARABIC_MARKS_OR_EDITORIAL_BRACKET_DIFFERENCE"
    if _collapse(a) == _collapse(b):
        return "WHITESPACE_DIFFERENCE"
    if _no_space(a) == _no_space(b):
        return "TOKEN_BOUNDARY_DIFFERENCE_CANDIDATE"
    return "TEXTUAL_DIFFERENCE_REQUIRES_REVIEW"


def _changed_regions(a, b):
    """Strict character opcodes; no normalization when positioning changes."""
    al, bl = _byte_starts(a), _byte_starts(b)
    result = []
    for tag, i, j, k, m in SequenceMatcher(
        None, a, b, autojunk=False
    ).get_opcodes():
        if tag == "equal":
            continue
        _need(len(result) < MAX_DIFFERENCE_EVENTS,
              "alignment too complex to report completely")
        left, right = a[i:j], b[k:m]
        result.append({
            "op": tag,
            "class": _classify(left, right),
            "left": {
                "byte_start": al[i], "byte_end_exclusive": al[j],
                "line_start": _line_number(a, i),
                "span_sha256": _sha(left.encode("utf-8")),
            },
            "right": {
                "byte_start": bl[k], "byte_end_exclusive": bl[m],
                "line_start": _line_number(b, k),
                "span_sha256": _sha(right.encode("utf-8")),
            },
            "source_text_included": False,
        })
    return result


def align_sections(left_path, right_path, *,
                   left_sha256, right_sha256,
                   left_source_id, right_source_id,
                   left_locator, right_locator):
    """Produce metadata-only comparison, all strict changes anchored to raw bytes.

    No claim of faithful HTML extraction, no-source-completeness, or meaning.
    """
    for field, value in (("left_source_id", left_source_id),
                         ("right_source_id", right_source_id),
                         ("left_locator", left_locator),
                         ("right_locator", right_locator)):
        _need(type(value) is str and value.strip() and len(value) <= 512,
              f"invalid {field}")
    _need(left_source_id != right_source_id, "witness identities must differ")
    a, data_a = _read_pinned(left_path, left_sha256)
    b, data_b = _read_pinned(right_path, right_sha256)
    events = _changed_regions(a, b)
    base_a, base_b = _base(a), _base(b)
    exact = data_a == data_b
    base_equal = base_a == base_b
    collapsed = _collapse(base_a) == _collapse(base_b)
    boundary_equal = _no_space(base_a) == _no_space(base_b)
    return {
        "engine": PROFILE_VERSION,
        "status": "PINNED_TEXT_WITNESS_ALIGNMENT_PASS",
        "left": {"source_id": left_source_id,
                 "section_locator": left_locator,
                 "section_sha256": left_sha256,
                 "section_bytes": len(data_a),
                 "raw_whitespace_token_count": len(a.split())},
        "right": {"source_id": right_source_id,
                  "section_locator": right_locator,
                  "section_sha256": right_sha256,
                  "section_bytes": len(data_b),
                  "raw_whitespace_token_count": len(b.split())},
        "profiles": {
            "raw_byte_identical": exact,
            "marks_and_brackets_ignored_identical": base_equal,
            "after_whitespace_collapsing_identical": collapsed,
            "after_all_whitespace_removed_identical": boundary_equal,
            "normalization_profile": "arabic_marks_editorial_brackets_only_v1",
            "alignment_profile": "raw_codepoint_diff_v1",
            "warning": "Normalized equality only diagnoses representation; it NEVER proves lexical or juristic equivalence.",
        },
        "overall_classification": _classify(a, b),
        "strict_change_count": len(events),
        "strict_changes": events,
        "unmatched_spans_fully_reported": True,
        "originals_preserved": True,
        "normalization_erases_semantic_changes_verified": False,
        "meaning_preservation_verified": False,
        "lexical_content_equivalence_certified": False,
        "source_html_to_section_provenance_verified": False,
        "printed_edition_verified": False,
        "scholarly_verified": False,
        "redistribution_approved": False,
        "semantic_qarinah_verified": False,
        "source_text_included": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("left", "right", "report"):
        parser.add_argument("--" + option, required=True, type=Path)
    for option in ("left-sha256", "right-sha256", "left-source-id",
                   "right-source-id", "left-locator", "right-locator"):
        parser.add_argument("--" + option, required=True)
    args = parser.parse_args()
    try:
        if not args.left.is_file() or not args.right.is_file():
            result, status = {
                "status": "PENDING_PRIVATE_WITNESS_FILES",
                "scholarly_verified": False,
                "source_text_included": False,
            }, 3
        else:
            result = align_sections(
                args.left, args.right,
                left_sha256=args.left_sha256,
                right_sha256=args.right_sha256,
                left_source_id=args.left_source_id,
                right_source_id=args.right_source_id,
                left_locator=args.left_locator, right_locator=args.right_locator,
            )
            status = 0
    except (OSError, ValueError) as exc:
        result, status = {
            "status": "FAIL",
            "reason_code": type(exc).__name__,
            "scholarly_verified": False,
            "source_text_included": False,
        }, 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": result["status"], "report": str(args.report)},
                     ensure_ascii=True))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
