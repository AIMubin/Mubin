"""Deterministic full-book W2 (islam.ms) section extractor - Stage B.

Pure function of the pinned W2 original HTML bytes (trusted sha verified by
the caller/pin ledger). Isolates <div id="content"> (site menu/search/footer
excluded), splits chapters on <h2> boundaries, converts each chapter with the
same bounded rules as the frozen W1 extractor, and pairs chapters with the
W1 inventory by folded-title uniqueness. The first h2 is the book-title
heading (kind TITLE_HEADING), documented as the extra 21st heading.

Offsets are reported against the DERIVED W2 UTF-8 export, never against the
original HTML byte stream. No text correction, no edition claims.
"""
from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re

from engines.usul.arabic_evidence_retrieval import SAFE_DIAGNOSTIC_MARKS

VERSION = "waraqat-w2-full-extract/0.1.0"
W2_RAW_SHA = "3c4de1baa99bad782b5fba066523ca9f12798525907edede93bd1046ef36f0fa"
CONTENT_START = '<div id="content"'
# Content scope rule: content runs from its opening tag to the NEXT top-level
# <div> (site chrome). Nested divs inside content are not expected in this
# witness; a witness with nested layout divs would need its own adapter.
MAX_BYTES = 8 * 1024 * 1024


class _ExtractionError(ValueError):
    pass


def _fold(title):
    folded = "".join(ch for ch in title if ord(ch) not in SAFE_DIAGNOSTIC_MARKS)
    return " ".join(folded.split())


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _convert(fragment):
    fragment = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.I)
    fragment = re.sub(r"</h2\s*>", "\n", fragment, flags=re.I)
    fragment = re.sub(r"<[^>]+>", "", fragment)
    from html import unescape
    fragment = unescape(fragment)
    return fragment.replace("\r\n", "\n").replace("\r", "\n")


def extract_sections(raw: bytes):
    if raw.startswith(b"\xef\xbb\xbf") or b"\x00" in raw:
        raise _ExtractionError("BOM or binary W2 capture refused")
    page = raw.decode("utf-8", errors="strict")
    start = page.find(CONTENT_START)
    stop = page.find("<div", start + len(CONTENT_START))
    if stop < 0:
        raise _ExtractionError("W2 content terminator not found")
    begin = page.find(">", start) + 1
    region = page[begin:stop]
    h2_spans = [(m.start(), m.end()) for m in
                re.finditer(r"<h2[^>]*>(.*?)</h2>", region, re.S | re.I)]
    if len(h2_spans) < 2:
        raise _ExtractionError("insufficient W2 chapter headings")
    sections = []
    for index, (hs, he) in enumerate(h2_spans):
        title = re.sub(r"<[^>]+>", "", region[hs:he]).strip()
        body_stop = h2_spans[index + 1][0] if index + 1 < len(h2_spans) else len(region)
        body = _convert(region[he:body_stop]).strip()
        sections.append({"h2_ordinal": index + 1, "title": title,
                         "title_folded": _fold(title),
                         "text": body, "heading_char_start": hs})
    return sections


def build_export(sections):
    """Deterministic derived W2 UTF-8 export: one heading line + body per section."""
    parts = []
    for s in sections:
        parts.append(s["title"] + "\n")
        parts.append(s["text"] + "\n")
    return "".join(parts).encode("utf-8")


def pair_with_w1(sections, w1_inventory):
    chapters = [s for s in w1_inventory["sections"]
                if s["kind"] == "HEADING_SECTION"]
    by_fold = {}
    for s in sections:
        key = _sha(s["title_folded"].encode("utf-8"))
        by_fold.setdefault(key, []).append(s)
    paired, unresolved, extras = [], [], []
    used = set()
    last_ordinal = 0
    for chapter in chapters:
        folded = chapter.get("heading_folded_sha256")
        candidates = by_fold.get(folded, [])
        if not candidates:
            candidates = by_fold.get(folded, [])
        free = [c for c in candidates if id(c) not in used]
        if len(free) != 1:
            unresolved.append({"w1_section_id": chapter["id"],
                               "folded_sha256": folded,
                               "reason": ("AMBIGUOUS_OR_DUPLICATE_TITLE" if len(free) > 1
                                          else "NO_FOLDED_TITLE_MATCH_IN_W2")})
            continue
        match = free[0]
        used.add(id(match))
        if match["h2_ordinal"] <= last_ordinal:
            unresolved.append({"w1_section_id": chapter["id"],
                               "reason": "TITLE_ORDER_CONFLICT"})
            continue
        last_ordinal = match["h2_ordinal"]
        paired.append({"w1_section_id": chapter["id"], "w2_section": match})
    for s in sections:
        if all(s is not p["w2_section"] for p in paired):
            folded_key = _sha(s["title_folded"].encode("utf-8"))
            kind = ("TITLE_HEADING"
                    if s["title_folded"].startswith("كتاب الورقات") else "UNPAIRED")
            extras.append({"h2_ordinal": s["h2_ordinal"], "title_folded": s["title_folded"],
                           "title_folded_sha256": folded_key, "kind": kind})
    return paired, unresolved, extras


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-html", type=Path, required=True)
    parser.add_argument("--w1-inventory", type=Path, required=True)
    parser.add_argument("--sections-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    raw = args.raw_html.read_bytes()
    if _sha(raw) != W2_RAW_SHA:
        raise _ExtractionError("W2 HTML digest differs from frozen pin")
    w1_inventory = json.loads(args.w1_inventory.read_text(encoding="utf-8"))
    sections = extract_sections(raw)
    export = build_export(sections)
    paired, unresolved, extras = pair_with_w1(sections, w1_inventory)
    args.sections_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for s in sections:
        path = args.sections_dir / (f"w2-h2-{s['h2_ordinal']:03d}.txt")
        path.write_text(s["title"] + "\n" + s["text"] + "\n", encoding="utf-8")
        files.append({"h2_ordinal": s["h2_ordinal"], "path": str(path),
                      "bytes": path.stat().st_size,
                      "sha256": _sha(path.read_bytes())})
    manifest = {
        "schema_version": "0.1.0", "engine": VERSION,
        "status": "W2_FULL_EXTRACTION_PASS",
        "source_html_sha256": W2_RAW_SHA,
        "source_html_bytes": len(raw),
        "offset_basis": "w2_derived_text_export (NOT original HTML offsets)",
        "sections_total": len(sections),
        "sections": [{"h2_ordinal": s["h2_ordinal"], "title_folded": s["title_folded"],
                      "chars": len(s["text"])} for s in sections],
        "paired_with_w1": len(paired), "unresolved": unresolved, "extras": extras,
        "export_sha256": _sha(export), "export_bytes": len(export),
        "section_files": files, "source_text_included": False,
        "scholarly_verified": False, "redistribution_approved": False,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
    print(json.dumps({"status": manifest["status"], "sections": len(sections),
                      "paired": len(paired), "extras": len(extras),
                      "export_sha256": manifest["export_sha256"]},
                     ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
