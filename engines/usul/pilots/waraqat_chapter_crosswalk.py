"""Candidate-only chapter-heading alignment for frozen W1 and W2 witnesses.

Never extracts or certifies W2 chapter sections: the previous Bab al-Amr W2
extraction remains independently frozen. Other W2 h2 headings are page-structure
candidates until reviewed. A match of titles is NOT textual equivalence.
"""
from __future__ import annotations

import hashlib
from html.parser import HTMLParser
import re

from engines.usul.pilots.waraqat_stage06 import W2_RAW_SHA
from engines.usul.pilots.waraqat_witness2_extract import _heading as w2_heading

VERSION = "waraqat-chapter-heading-crosswalk/0.1.0"
MAX_H2 = 128


class HeadingCrosswalkError(ValueError):
    pass


class Headings(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_h2 = False
        self.content = []
        self.labels = []
        self.error = False

    def handle_starttag(self, tag, attrs):
        if tag == "h2":
            if self.in_h2:
                self.error = True
            else:
                self.in_h2 = True
                self.content = []

    def handle_endtag(self, tag):
        if tag == "h2":
            if not self.in_h2:
                self.error = True
            else:
                self.labels.append("".join(self.content).strip())
                self.in_h2 = False
                self.content = []

    def handle_data(self, data):
        if self.in_h2:
            self.content.append(data)


def discover_w2_headings(raw_html: bytes, *, independently_pinned_sha: str):
    if (not isinstance(raw_html, bytes)
            or not 0 < len(raw_html) <= 8 * 1024 * 1024
            or hashlib.sha256(raw_html).hexdigest() != independently_pinned_sha):
        raise HeadingCrosswalkError("W2 raw capture lacks independently pinned integrity")
    try:
        text = raw_html.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise HeadingCrosswalkError("W2 HTML must be strict UTF-8") from exc
    parser = Headings()
    parser.feed(text)
    parser.close()
    if parser.error or parser.in_h2 or not 0 < len(parser.labels) <= MAX_H2:
        raise HeadingCrosswalkError("ambiguous or missing h2 labels")
    safe = []
    for i, label in enumerate(parser.labels, 1):
        if not label or len(label) > 150 or any(x in label for x in "\r\n\x00"):
            raise HeadingCrosswalkError("unsafe/empty h2 label")
        safe.append({
            "document_h2_ordinal": i,
            "heading": label,
            "match_key_diagnostic": w2_heading(label),
            "classification": "UNREVIEWED_PAGE_H2_HEADING",
        })
    return safe


def candidate_crosswalk(w1_inventory, raw_html: bytes, *, w2_pin=W2_RAW_SHA):
    if (type(w1_inventory) is not dict or
        w1_inventory.get("status") != "PRIMARY_WITNESS_CHAPTER_INVENTORY_PASS" or
        w1_inventory.get("complete_original_byte_partition_verified") is not True):
        raise HeadingCrosswalkError("source-verified W1 chapter inventory required")
    headings = discover_w2_headings(raw_html, independently_pinned_sha=w2_pin)
    result = []
    for chapter in w1_inventory["chapters"]:
        key = w2_heading(chapter["heading"])
        hits = [x["document_h2_ordinal"] for x in headings
                if x["match_key_diagnostic"] == key]
        result.append({
            "w1_chapter_id": chapter["id"],
            "w1_section_sha256": chapter["section_sha256"],
            "w2_h2_ordinal_candidates": hits,
            "status": (
                "ONE_HEADING_CANDIDATE_NOT_TEXT_ALIGNED" if len(hits) == 1
                else "NO_HEADING_CANDIDATE" if not hits
                else "AMBIGUOUS_HEADING_CANDIDATES"
            ),
            "normalized_heading_identity_only": True,
            "textual_equivalence_certified": False,
        })
    return {
        "engine": VERSION,
        "status": "W2_HEADING_CROSSWALK_CANDIDATES_ONLY",
        "w2_html_sha256": w2_pin,
        "w2_h2_count": len(headings),
        "w2_h2_inventory": headings,
        "w1_chapter_links": result,
        "w2_chapter_byte_extraction_verified": False,
        "full_witness_comparison_qualified": False,
        "semantic_equivalence_verified": False,
        "scholarly_verified": False,
        "redistribution_approved": False,
        "source_text_included": False,
    }
