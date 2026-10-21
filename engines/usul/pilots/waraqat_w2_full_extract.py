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
from html import unescape
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


def _content_region(page):
    """Find the exact closing div of the frozen witness content wrapper."""
    start = page.find(CONTENT_START)
    if start < 0 or page.find(CONTENT_START, start+1) >= 0:
        raise _ExtractionError("W2 content root missing or duplicated")
    opening_end = page.find(">", start)
    if opening_end < 0:
        raise _ExtractionError("unterminated content root")
    depth = 1
    # Never stop on the *next* div: nested layout divs are legitimate.
    tag = re.compile(r"</?div\b[^>]*>", flags=re.I)
    for match in tag.finditer(page, opening_end+1):
        depth += -1 if match.group().startswith("</") else 1
        if depth == 0:
            return page[opening_end+1:match.start()]
    raise _ExtractionError("W2 content root has no balanced closing div")


def extract_sections(raw: bytes):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        raise _ExtractionError("W2 source absent or oversized")
    if raw.startswith(b"\xef\xbb\xbf") or b"\x00" in raw:
        raise _ExtractionError("BOM or binary W2 capture refused")
    page = raw.decode("utf-8", errors="strict")
    region = _content_region(page)
    if re.search(r"<(?:script|style|iframe|form)\b", region, flags=re.I):
        raise _ExtractionError("active/unsupported content markup in W2 witness")
    titles = list(re.finditer(r"<h2(?:\s[^>]*)?>(.*?)</h2\s*>",
                             region, re.S | re.I))
    opens = len(re.findall(r"<h2(?=[\s>])", region, flags=re.I))
    closes = len(re.findall(r"</h2\s*>", region, flags=re.I))
    if not 2 <= len(titles) <= 256 or opens != len(titles) or closes != len(titles):
        raise _ExtractionError("ambiguous or incomplete W2 chapter heading markup")
    sections = []
    for index, match in enumerate(titles):
        title_raw = match.group(1)
        if "<" in title_raw or ">" in title_raw:
            raise _ExtractionError("nested W2 chapter heading markup")
        title = unescape(title_raw).strip()
        if not title or "\n" in title or "\r" in title:
            raise _ExtractionError("empty or multiline W2 chapter heading")
        body_stop = titles[index + 1].start() if index + 1 < len(titles) else len(region)
        body = _convert(region[match.end():body_stop]).strip()
        sections.append({"h2_ordinal": index + 1, "title": title,
                         "title_folded": _fold(title),
                         "text": body, "heading_char_start": match.start()})
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
        free = [c for c in candidates if id(c) not in used]
        if len(candidates) != 1 or len(free) != 1 or sum(
                c.get("heading_folded_sha256") == folded for c in chapters) != 1:
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
                    if s["h2_ordinal"] == 1
                    and s["title_folded"] == "كتاب الورقات" else "UNPAIRED")
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
    files, summaries, byte_cursor = [], [], 0
    for s in sections:
        path = args.sections_dir / (f"w2-h2-{s['h2_ordinal']:03d}.txt")
        section_bytes = (s["title"] + "\n" + s["text"] + "\n").encode("utf-8")
        path.write_bytes(section_bytes)
        files.append({"h2_ordinal": s["h2_ordinal"], "path": path.name,
                      "bytes": len(section_bytes),
                      "sha256": _sha(section_bytes)})
        summaries.append({
            "h2_ordinal": s["h2_ordinal"],
            "title_sha256": _sha(s["title"].encode("utf-8")),
            "title_folded_sha256": _sha(s["title_folded"].encode("utf-8")),
            "derived_byte_start": byte_cursor,
            "derived_byte_end_exclusive": byte_cursor + len(section_bytes),
            "chars": len(s["text"]),
        })
        byte_cursor += len(section_bytes)
    if byte_cursor != len(export):
        raise _ExtractionError("derived W2 export and saved section bytes differ")
    good = (len(unresolved) == 0 and len(paired) == len(w1_inventory["sections"])-1
            and len(extras) == 1 and extras[0]["kind"] == "TITLE_HEADING")
    manifest = {
        "schema_version": "0.1.1", "engine": VERSION,
        "status": ("W2_FULL_EXTRACTION_PASS" if good
                   else "W2_EXTRACTION_PARTIAL_REQUIRES_REVIEW"),
        "source_html_sha256": W2_RAW_SHA,
        "source_html_bytes": len(raw),
        "offset_basis": "w2_derived_text_export (NOT original HTML offsets)",
        "sections_total": len(sections),
        "sections": summaries,
        "paired_with_w1": len(paired), "unresolved": unresolved,
        "extras": [{"h2_ordinal": x["h2_ordinal"],
                    "title_folded_sha256": x["title_folded_sha256"],
                    "kind": x["kind"]} for x in extras],
        "export_sha256": _sha(export), "export_bytes": len(export),
        "section_files": files, "source_text_included": False,
        "scholarly_verified": False, "redistribution_approved": False,
    }
    manifest["manifest_sha256"] = _sha(json.dumps(
        manifest, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8"))
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
    print(json.dumps({"status": manifest["status"], "sections": len(sections),
                      "paired": len(paired), "extras": len(extras),
                      "export_sha256": manifest["export_sha256"]},
                     ensure_ascii=True))
    return 0 if good else 1


if __name__ == "__main__":
    raise SystemExit(main())
