"""Optional W2 digital-witness h2 heading map; never blocks W1 book coverage.

Independently frozen W2 HTML SHA → h2 title fingerprints → diagnostic
one-to-one candidate title pairs. This does NOT extract, align, or certify
whole-book W2 chapter text, editions, rights, or semantic equivalence.
"""
from __future__ import annotations

from collections import Counter
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path

from engines.usul.arabic_evidence_retrieval import SAFE_DIAGNOSTIC_MARKS
from engines.usul.pilots.waraqat_stage06 import W2_RAW_SHA

VERSION = "waraqat-w2-heading-map/0.1.0"
MAX_HTML_BYTES = 8*1024*1024
MAX_H2_HEADINGS = 256


class HeadingMapError(ValueError):
    pass


def _need(check, why):
    if not check:
        raise HeadingMapError(why)


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def _canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _fold_title(s):
    # No alef, composed/decomposed hamza, or lexical negation substitutions.
    return " ".join("".join(
        ch for ch in s if ord(ch) not in SAFE_DIAGNOSTIC_MARKS
    ).split())


class _H2Reader(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.open = False
        self.parts = []
        self.titles = []
        self.error = None

    def handle_starttag(self, tag, attrs):
        if tag == "h2":
            if self.open:
                self.error = "nested headings"
            self.open = True
            self.parts = []
        elif self.open and tag in ("script", "style", "nav", "form", "iframe"):
            self.error = "unsafe active markup inside heading"

    def handle_endtag(self, tag):
        if tag == "h2":
            if not self.open:
                self.error = "closing heading without opening"
            else:
                value = "".join(self.parts).strip()
                if not value or "\n" in value or "\r" in value:
                    self.error = "empty/multiline heading"
                else:
                    self.titles.append(value)
            self.open = False

    def handle_data(self, data):
        if self.open:
            self.parts.append(data)


def map_headings(w2_raw_html, w1_inventory, *, trusted_w2_sha=W2_RAW_SHA):
    _need(type(w2_raw_html) is bytes and 0 < len(w2_raw_html) <= MAX_HTML_BYTES
          and _sha(w2_raw_html) == trusted_w2_sha,
          "W2 HTML missing, oversized or differs from independent frozen pin")
    _need(not w2_raw_html.startswith(b"\xef\xbb\xbf") and b"\x00" not in w2_raw_html,
          "unexpected W2 binary/BOM capture")
    _need(type(w1_inventory) is dict
          and w1_inventory.get("status") == "FULL_W1_SOURCE_INVENTORY_PASS"
          and w1_inventory.get("all_original_bytes_partitioned_once") is True
          and type(w1_inventory.get("inventory_sha256")) is str,
          "W1 full original source inventory required")
    payload = {k: v for k, v in w1_inventory.items() if k != "inventory_sha256"}
    _need(_sha(_canonical(payload)) == w1_inventory["inventory_sha256"],
          "W1 inventory canonical digest invalid")
    sections = w1_inventory["sections"]
    _need(type(sections) is list and 2 <= len(sections) <= 97,
          "W1 sections malformed")
    _need(all(type(x) is dict and x.get("kind") in ("PRELUDE", "HEADING_SECTION")
              for x in sections), "W1 inventory section contract changed")
    parser = _H2Reader()
    parser.feed(w2_raw_html.decode("utf-8", errors="strict"))
    parser.close()
    _need(parser.error is None and not parser.open and
          2 <= len(parser.titles) <= MAX_H2_HEADINGS,
          "unsafe or missing W2 h2 headings")
    h2 = [{
        "h2_ordinal": i + 1,
        "heading_sha256": _sha(title.encode("utf-8")),
        "heading_folded_sha256": _sha(_fold_title(title).encode("utf-8")),
        "source_text_included": False,
    } for i, title in enumerate(parser.titles)]
    w1_headers = [x for x in sections if x["kind"] == "HEADING_SECTION"]
    _need(all(type(x.get("heading_folded_sha256")) is str
              and len(x["heading_folded_sha256"]) == 64
              for x in w1_headers), "W1 title comparison keys unavailable")
    w1_keys = Counter(x["heading_folded_sha256"] for x in w1_headers)
    w2_keys = Counter(x["heading_folded_sha256"] for x in h2)
    counterpart = {k: x for x in h2 for k in [x["heading_folded_sha256"]]
                   if w2_keys[k] == 1}
    paired, unresolved, last = [], [], 0
    for x in w1_headers:
        folded = x["heading_folded_sha256"]
        if w1_keys[folded] != 1 or w2_keys[folded] != 1:
            unresolved.append({
                "w1_section_id": x["id"],
                "diagnostic_status": ("AMBIGUOUS_OR_DUPLICATE_TITLE"
                                      if max(w1_keys[folded],w2_keys[folded]) > 1
                                      else "NO_EXACT_FOLDED_TITLE"),
            })
            continue
        w2 = counterpart[folded]
        if w2["h2_ordinal"] <= last:
            unresolved.append({
                "w1_section_id": x["id"], "diagnostic_status": "TITLE_ORDER_CONFLICT",
            })
            continue
        paired.append({
            "w1_section_id": x["id"],
            "w2_h2_ordinal": w2["h2_ordinal"],
            "classification": "DIAGNOSTIC_TITLE_CANDIDATE_ONLY",
            "original_heading_bytes_equal": x["heading_sha256"] == w2["heading_sha256"],
            "chapter_section_bytes_aligned": False,
        })
        last = w2["h2_ordinal"]
    report = {
        "engine": VERSION,
        "status": "W2_HEADING_MAPPING_CANDIDATES_RECORDED",
        "source_w2_html_sha256": trusted_w2_sha,
        "source_w1_inventory_sha256": w1_inventory["inventory_sha256"],
        "w1_chapter_count": len(w1_headers),
        "all_w2_h2_count_in_document": len(h2),
        "w2_h2_title_fingerprints": h2,
        "candidate_title_pairs": paired,
        "unpaired_or_conflicted_w1": unresolved,
        "pair_count": len(paired),
        "unresolved_count": len(unresolved),
        "w2_section_extraction_verified": False,
        "whole_book_comparison_verified": False,
        "semantic_equivalence_verified": False,
        "scholarly_verified": False,
        "redistribution_approved": False,
        "source_text_included": False,
    }
    return {**report, "report_sha256": _sha(_canonical(report))}
