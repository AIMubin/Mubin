"""Read-only, metadata-only W2 Bab al-Amr three-representation audit.

Replays three *specific historical extraction algorithms* from the exact
same frozen private W2 HTML bytes. Does not publish words, source content,
file paths, or source-derived excerpts. This is a forensic diagnostic, not a
new canonical extractor and not scholarly verification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from engines.usul.pilots.waraqat_witness2_extract import extract as stage06_extract
from engines.usul.pilots.waraqat_w2_full_extract import (
    W2_RAW_SHA, CONTENT_START, _convert, extract_sections,
)

VERSION = "waraqat-w2-representation-audit/0.1.0"
EXPECTED_BYTES = {"stage06": 1702, "legacy_full": 1706, "hardened_full": 1696}


def _sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def legacy_full_bab_amr(raw: bytes) -> bytes:
    """Replay the pre-hardening 6dfd5e0 W2 full-book extraction for h2#7.

    This reproduces the old slice boundary / regex conversion; it is *not*
    used for production W2 extraction or to establish HTML correctness.
    """
    page = raw.decode("utf-8", errors="strict")
    start = page.find(CONTENT_START)
    if start < 0:
        raise ValueError("legacy content root absent")
    begin = page.find(">", start)
    stop = page.find("<div", start + len(CONTENT_START))
    if begin < 0 or stop < 0 or begin >= stop:
        raise ValueError("legacy W2 content boundary absent")
    region = page[begin + 1:stop]
    headings = [(m.start(), m.end()) for m in re.finditer(
        r"<h2[^>]*>(.*?)</h2>", region, re.S | re.I)]
    if len(headings) != 21:
        raise ValueError("legacy W2 did not see the original 21 h2 headings")
    ix = 6  # W2 h2#7 corresponds to W1 chapter-006 (Bab al-Amr).
    hs, he = headings[ix]
    title = re.sub(r"<[^>]+>", "", region[hs:he]).strip()
    body_stop = headings[ix+1][0]
    body = _convert(region[he:body_stop]).strip()
    return (title+"\n"+body+"\n").encode("utf-8")


def hardened_full_bab_amr(raw: bytes) -> bytes:
    sections = extract_sections(raw)
    if len(sections) != 21:
        raise ValueError("hardened W2 did not extract 21 sections")
    matches = [s for s in sections if s["h2_ordinal"] == 7
               and s["title_folded"] == "الأمر"]
    if len(matches) != 1:
        raise ValueError("hardened W2 h2#7 does not uniquely identify Bab al-Amr")
    s = matches[0]
    return (s["title"]+"\n"+s["text"]+"\n").encode("utf-8")


def _nonempty_lines(text: str):
    return [line for line in text.splitlines() if line.strip()]


def _compare(left: bytes, right: bytes):
    a, b = left.decode("utf-8"), right.decode("utf-8")
    nonempty_a, nonempty_b = _nonempty_lines(a), _nonempty_lines(b)
    tokens_a, tokens_b = a.split(), b.split()
    compact_a, compact_b = "".join(a.split()), "".join(b.split())
    return {
        "raw_byte_identical": left == right,
        "nonempty_lines_identical": nonempty_a == nonempty_b,
        "whitespace_delimited_tokens_identical": tokens_a == tokens_b,
        "nonwhitespace_codepoints_identical": compact_a == compact_b,
        "line_count_left": len(a.splitlines()),
        "line_count_right": len(b.splitlines()),
        "nonempty_line_count_left": len(nonempty_a),
        "nonempty_line_count_right": len(nonempty_b),
        "token_count_left": len(tokens_a),
        "token_count_right": len(tokens_b),
    }


def audit(raw: bytes, *, enforce_historical_bytes=True):
    if _sha(raw) != W2_RAW_SHA:
        raise ValueError("W2 raw HTML digest differs from frozen pin")
    stage06, _ = stage06_extract(raw)
    # Old 6dfd5e0 CLI used Path.write_text(...), newline=None, on the
    # operator's Windows machine. The old report's right_bytes measured
    # ON-DISK bytes, not the LF-only in-memory derived export.
    # Simulate precisely the Windows text-mode LF -> CRLF translation.
    legacy_lf = legacy_full_bab_amr(raw)
    legacy_windows = legacy_lf.replace(b"\n", b"\r\n")
    variants = {
        "stage06": stage06,
        "legacy_full": legacy_windows,
        "hardened_full": hardened_full_bab_amr(raw),
    }
    records = {
        key: {"bytes": len(value), "sha256": _sha(value)}
        for key, value in variants.items()
    }
    comparisons = {
        f"{a}_vs_{b}": _compare(variants[a], variants[b])
        for a,b in (("stage06", "legacy_full"), ("stage06", "hardened_full"),
                    ("legacy_full", "hardened_full"))
    }
    sizes_verified = all(records[key]["bytes"] == n
                         for key, n in EXPECTED_BYTES.items())
    lines_verified = all(c["nonempty_lines_identical"]
                         for c in comparisons.values())
    tokens_verified = all(c["whitespace_delimited_tokens_identical"]
                          for c in comparisons.values())
    nonwhitespace_verified = all(c["nonwhitespace_codepoints_identical"]
                                 for c in comparisons.values())
    # A loss of interword spacing is not described as a "format-only" change.
    passed = (nonwhitespace_verified and tokens_verified and lines_verified
              and (not enforce_historical_bytes or sizes_verified))
    payload = {
        "engine": VERSION,
        "status": ("ALL_THREE_REPRESENTATIONS_FORMAT_ONLY_VERIFIED" if passed
                   else "REPRESENTATION_DIFFERENCE_UNRESOLVED"),
        "pinned_w2_html_sha256": W2_RAW_SHA,
        "stage06_and_legacy_are_diagnostic_only": True,
        "legacy_disk_encoding": "Windows newline=None text-mode UTF-8 (CRLF)",
        "legacy_lf_serialized_bytes": len(legacy_lf),
        "legacy_lf_linefeed_count": legacy_lf.count(b"\n"),
        "legacy_windows_extra_cr_bytes": len(legacy_windows)-len(legacy_lf),
        "legacy_lf_sha256": _sha(legacy_lf),
        "expected_historical_lengths_bytes": EXPECTED_BYTES,
        "historical_lengths_verified": sizes_verified,
        "variants": records,
        "comparisons": comparisons,
        "source_text_included": False,
        "scholarly_verified": False,
        "semantic_equivalence_verified": False,
        "redistribution_approved": False,
    }
    return payload


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw-html", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    try:
        report = audit(args.raw_html.read_bytes())
        code = (0 if report["status"]
                == "ALL_THREE_REPRESENTATIONS_FORMAT_ONLY_VERIFIED" else 1)
    except (OSError, ValueError, UnicodeError, TypeError, IndexError) as exc:
        report = {"engine": VERSION, "status": "FAIL",
                  "reason_code": type(exc).__name__,
                  "source_text_included": False}
        code = 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                   sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps({"status": report["status"],
                      "historical_lengths_verified":
                          report.get("historical_lengths_verified", False)},
                     ensure_ascii=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
