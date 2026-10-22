"""Deterministic HTML→UTF-8 text extractor for the al-Waraqat digital witness.

Witness-specific and version-pinned by design: the islamicbook.ws page keeps
the complete book inside '<div id="content">' with no nested divs, and marks
chapter headings with <h5>. Extraction is a pure function of the raw HTML
bytes: same input bytes always produce byte-identical output. Site chrome
(header, navbar, footer, links, images) is excluded by the content boundary.

This tool performs NO text correction, paraphrase, diacritic normalization or
AI-assisted cleanup. It is not a printed-edition fidelity claim.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from pathlib import Path

TOOL_VERSION = "waraqat-extract/1.0.0"
CONTENT_START = '<div id="content">'
MAX_INPUT_BYTES = 8 * 1024 * 1024


def extract(raw: bytes) -> tuple[bytes, dict]:
    """Convert raw witness HTML bytes to UTF-8 text; return (text, stats)."""
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("input exceeds bounded size")
    text = raw.decode("utf-8")  # the witness declares and uses UTF-8
    start = text.find(CONTENT_START)
    if start < 0:
        raise ValueError("content boundary not found")
    begin = start + len(CONTENT_START)
    end = text.find("</div>", begin)
    if end < 0:
        raise ValueError("content terminator not found")
    region = text[begin:end]

    stats = {
        "tool_version": TOOL_VERSION,
        "raw_html_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_html_bytes": len(raw),
        "content_region_chars": len(region),
        "br_newlines_emitted": len(re.findall(r"<br\s*/?>", region, re.I)),
        "h5_headings_seen": len(re.findall(r"<h5>", region)),
        "tags_stripped": len(re.findall(r"<[^>]+>", region)),
        "rules": [
            "decode strict UTF-8 (witness-declared charset)",
            "isolate <div id='content'> .. next </div> (excludes header/nav/footer)",
            "<br> variants -> newline",
            "<h5> boundaries -> newline (heading becomes one standalone line)",
            "strip remaining tags",
            "html.unescape entity conversion",
            "CRLF/CR -> LF normalization only; no text edits, no reordering",
        ],
    }
    region = re.sub(r"<br\s*/?>", "\n", region, flags=re.I)
    region = region.replace("</h5>", "\n").replace("<h5>", "\n")
    region = re.sub(r"<[^>]+>", "", region)
    region = html.unescape(region)
    region = region.replace("\r\n", "\n").replace("\r", "\n")
    if "\x00" in region:
        raise ValueError("null byte in converted text")
    data = region.encode("utf-8")
    stats["extracted_utf8_sha256"] = hashlib.sha256(data).hexdigest()
    stats["extracted_utf8_bytes"] = len(data)
    stats["deterministic"] = True
    return data, stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-html", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    raw = args.raw_html.read_bytes()
    data, stats = extract(raw)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(data)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({"tool_version": TOOL_VERSION,
                      "extracted_sha256": stats["extracted_utf8_sha256"],
                      "extracted_bytes": stats["extracted_utf8_bytes"]},
                     ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
