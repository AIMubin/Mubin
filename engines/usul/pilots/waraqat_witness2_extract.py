"""Provisional Stage06 W2 HTML->Bab al-Amr UTF-8 section extraction.

Works with the online islam.ms witness's h2 section layout as documented by
source operator. Pure and deterministic on captured HTML bytes. This adapter
has NOT been validated against the privately pinned W2 raw HTML snapshot.
Do NOT certify its output's historical accuracy or printed-edition provenance.
"""
from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re

VERSION = "waraqat-islamms-h2-extract/0.1.0-candidate"
W2_RAW_SHA = "3c4de1baa99bad782b5fba066523ca9f12798525907edede93bd1046ef36f0fa"
MAX_BYTES = 8 * 1024 * 1024
MARKS = set(range(0x64B, 0x660)) | {0x670} | set(range(0x6D6, 0x6EE))
BLOCK_BOUNDARIES = {"p", "div", "br", "ul", "li", "blockquote"}
DISALLOWED_INSIDE = {"script", "style", "iframe", "form", "button", "nav"}
ARABIC_START = "الأمر"
ARABIC_END = "النهي"


def _heading(text):
    return " ".join(
        "".join(ch for ch in text if ord(ch) not in MARKS).split()
    )


class SectionHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_heading = False
        self.heading_fragments = []
        self.section_fragments = []
        self.state = "before"
        self.start_count = 0
        self.end_count = 0
        self.other_h2_between = []
        self.h2_count = 0
        self.rejected = None

    def handle_starttag(self, tag, attrs):
        if tag == "h2":
            if self.in_heading:
                self.rejected = "nested h2 is not supported"
            self.in_heading = True
            self.heading_fragments = []
            self.h2_count += 1
        elif self.state == "within" and tag in DISALLOWED_INSIDE:
            self.rejected = "unrelated active or site-chrome element within section"
        elif self.state == "within" and not self.in_heading and tag == "br":
            self.section_fragments.append("\n")

    def handle_startendtag(self, tag, attrs):
        if tag == "br" and self.state == "within" and not self.in_heading:
            self.section_fragments.append("\n")

    def handle_endtag(self, tag):
        if tag == "h2":
            if not self.in_heading:
                self.rejected = "closing h2 without start"
                return
            label = "".join(self.heading_fragments)
            normalized = _heading(label)
            self.in_heading = False
            if normalized == ARABIC_START:
                self.start_count += 1
                if self.state != "before":
                    self.rejected = "repeated or late starting heading"
                self.state = "within"
                self.section_fragments.append(label.strip())
                self.section_fragments.append("\n")
            elif normalized == ARABIC_END:
                self.end_count += 1
                if self.state == "within":
                    self.state = "after"
                elif self.state == "before":
                    self.rejected = "end heading before start"
            elif self.state == "within":
                self.other_h2_between.append(normalized)
                self.rejected = "intermediate h2 heading in source section"
        elif self.state == "within" and not self.in_heading and tag in BLOCK_BOUNDARIES:
            self.section_fragments.append("\n")

    def handle_data(self, data):
        if self.in_heading:
            self.heading_fragments.append(data)
        elif self.state == "within":
            self.section_fragments.append(data)


def extract(raw: bytes):
    if not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("invalid or oversized W2 original HTML")
    if raw.startswith(b"\xef\xbb\xbf") or b"\x00" in raw:
        raise ValueError("invalid BOM/binary original HTML")
    try:
        html_source = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("W2 HTML is not strict UTF-8") from exc
    parser = SectionHTMLParser()
    parser.feed(html_source)
    parser.close()
    if (parser.rejected or parser.in_heading or parser.start_count != 1
            or parser.end_count != 1 or parser.state != "after"):
        raise ValueError("ambiguous W2 Bab al-Amr section: " +
                         (parser.rejected or "missing/duplicate/misordered headings"))
    section = "".join(parser.section_fragments).replace("\r\n", "\n").replace("\r", "\n")
    # Do not remove shadda, hamza, brackets, text tokens or merge whitespace:
    # only remove exterior source-region whitespace and preserve a final LF.
    section = section.strip() + "\n"
    data = section.encode("utf-8")
    if not data or len(data) > 16384:
        raise ValueError("empty/oversized extracted W2 chapter")
    return data, {
        "version": VERSION,
        "status": "DETERMINISTIC_HTML_PARSER_CANDIDATE",
        "raw_html_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_html_bytes": len(raw),
        "h2_headings_seen": parser.h2_count,
        "start_heading_matches": parser.start_count,
        "end_heading_matches": parser.end_count,
        "section_sha256": hashlib.sha256(data).hexdigest(),
        "section_bytes": len(data),
        "comparison_to_original_edition_verified": False,
        "html_source_frozen_capture_verified_here": False,
        "private_witness_replay_performed_by_ci": False,
        "meaning_preservation_verified": False,
        "redistribution_approved": False,
    }


def main():
    arg = argparse.ArgumentParser(description=__doc__)
    arg.add_argument("--raw-html", type=Path, required=True)
    arg.add_argument("--out", type=Path, required=True)
    arg.add_argument("--report", type=Path, required=True)
    p = arg.parse_args()
    try:
        if not p.raw_html.is_file():
            result, code = {"status": "PENDING_PRIVATE_WITNESS_FILES"}, 3
        else:
            raw = p.raw_html.read_bytes()
            if hashlib.sha256(raw).hexdigest() != W2_RAW_SHA:
                raise ValueError("W2 raw HTML digest differs from published capture")
            out, result = extract(raw)
            result["html_source_frozen_capture_verified_here"] = True
            result["status"] = "W2_PINNED_HTML_SECTION_EXTRACTION_PASS"
            p.out.parent.mkdir(parents=True, exist_ok=True)
            p.out.write_bytes(out)
            code = 0
    except (ValueError, OSError, UnicodeError) as exc:
        result, code = {"status": "FAIL", "reason_code": type(exc).__name__}, 1
    p.report.parent.mkdir(parents=True, exist_ok=True)
    p.report.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n",
                        encoding="utf-8")
    print(json.dumps({"status": result["status"],
                      "report": str(p.report)}, ensure_ascii=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
