"""Pinned W1/W2 chapter-pair comparison. No chapter may silently disappear.

The operator must supply BOTH privately frozen source exports and W2 raw HTML.
Recompute W2 extraction and verify per-section manifest hashes; only then
compare. A partial batch is nonzero and never called COMPLETE.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from engines.usul.waraqat_batch import validate_inventory, BatchCoverageError
from engines.usul.pilots.waraqat_stage06 import W1_RAW_SHA, W1_EXPORT_SHA
from engines.usul.pilots.waraqat_w2_full_extract import (
    W2_RAW_SHA, VERSION as EXTRACTOR_VERSION, extract_sections, build_export, _fold,
)
from engines.usul.witness_alignment import align_sections, WitnessAlignmentError

VERSION = "waraqat-w2-pair-compare/0.1.1"
SHA = re.compile(r"^[0-9a-f]{64}$")


class PairComparisonError(ValueError):
    pass


def _need(value, message):
    if not value:
        raise PairComparisonError(message)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def validate_w2_manifest(manifest, w2_raw_html, files_dir, *,
                         trusted_w2_sha=W2_RAW_SHA):
    """Cross-check frozen W2 HTML, regenerated export, manifest and saved files."""
    _need(type(manifest) is dict and type(w2_raw_html) is bytes,
          "invalid W2 manifest/source")
    _need(_sha(w2_raw_html) == trusted_w2_sha
          and manifest.get("source_html_sha256") == trusted_w2_sha
          and manifest.get("engine") == EXTRACTOR_VERSION
          and manifest.get("status") == "W2_FULL_EXTRACTION_PASS"
          and manifest.get("source_text_included") is False
          and manifest.get("offset_basis")
          == "w2_derived_text_export (NOT original HTML offsets)",
          "W2 provenance or extraction status invalid")
    manifest_sha = manifest.get("manifest_sha256")
    _need(type(manifest_sha) is str
          and manifest_sha == _sha(_canonical({
              k:v for k,v in manifest.items() if k != "manifest_sha256"})),
          "W2 manifest canonical hash mismatch")
    sections = extract_sections(w2_raw_html)
    exported = build_export(sections)
    _need(manifest.get("export_sha256") == _sha(exported)
          and manifest.get("export_bytes") == len(exported)
          and manifest.get("sections_total") == len(sections),
          "W2 HTML replay differs from manifest export")
    summaries, files = manifest.get("sections"), manifest.get("section_files")
    _need(type(summaries) is list and type(files) is list
          and len(summaries) == len(files) == len(sections),
          "W2 section inventory incomplete")
    offset, verified = 0, {}
    for i, (section, meta, file_meta) in enumerate(zip(sections, summaries, files), 1):
        _need(type(meta) is dict and type(file_meta) is dict
              and meta.get("h2_ordinal") == file_meta.get("h2_ordinal") == i,
              "W2 section order/ordinal invalid")
        expected_bytes = (section["title"]+"\n"+section["text"]+"\n").encode("utf-8")
        filename = f"w2-h2-{i:03d}.txt"
        _need(file_meta.get("path") == filename
              and file_meta.get("bytes") == len(expected_bytes)
              and file_meta.get("sha256") == _sha(expected_bytes)
              and meta.get("derived_byte_start") == offset
              and meta.get("derived_byte_end_exclusive") == offset+len(expected_bytes)
              and meta.get("title_sha256") == _sha(section["title"].encode("utf-8"))
              and meta.get("title_folded_sha256") ==
              _sha(_fold(section["title"]).encode("utf-8")),
              "W2 section manifest contents/coordinates invalid")
        path = Path(files_dir)/filename
        actual = path.read_bytes()
        _need(actual == expected_bytes, "W2 saved section changed since extraction")
        verified[i] = path
        offset += len(expected_bytes)
    _need(offset == len(exported), "W2 saved sections fail full export coverage")
    return sections, verified


def compare_all(inventory, w1_export, manifest, w2_raw_html, w2_sections_dir, *,
                trusted_w1_export_sha=W1_EXPORT_SHA,
                trusted_w1_html_sha=W1_RAW_SHA,
                trusted_w2_sha=W2_RAW_SHA):
    validate_inventory(w1_export, inventory,
                       trusted_export_sha=trusted_w1_export_sha,
                       trusted_html_sha=trusted_w1_html_sha)
    w2_sections, files = validate_w2_manifest(
        manifest, w2_raw_html, w2_sections_dir, trusted_w2_sha=trusted_w2_sha)
    chapters = [x for x in inventory["sections"] if x["kind"] == "HEADING_SECTION"]
    w1_counts = Counter(x["heading_folded_sha256"] for x in chapters)
    w2_counts = Counter(_sha(s["title_folded"].encode("utf-8")) for s in w2_sections)
    lookup = {_sha(s["title_folded"].encode("utf-8")): s for s in w2_sections
              if w2_counts[_sha(s["title_folded"].encode("utf-8"))] == 1}
    paired, skipped = [], [{"w1_section_id": "waraqat:w1:prologue",
                            "reason": "PRELUDE_HAS_NO_W2_COUNTERPART_BY_DESIGN"}]
    last = 0
    for chapter in chapters:
        key = chapter["heading_folded_sha256"]
        section = lookup.get(key)
        if w1_counts[key] != 1 or w2_counts[key] != 1 or section is None:
            skipped.append({"w1_section_id": chapter["id"],
                            "reason": "UNPAIRED_OR_AMBIGUOUS_TITLE"})
        elif section["h2_ordinal"] <= last:
            skipped.append({"w1_section_id": chapter["id"],
                            "reason": "TITLE_ORDER_CONFLICT"})
        else:
            paired.append((chapter, section))
            last = section["h2_ordinal"]
    referenced = {s["h2_ordinal"] for _,s in paired}
    extras = [s for s in w2_sections if s["h2_ordinal"] not in referenced]
    expected_extras = len(extras) == 1 and extras[0]["h2_ordinal"] == 1 and (
        extras[0]["title_folded"] == "كتاب الورقات")
    if not expected_extras:
        skipped.append({"reason": "UNRESOLVED_W2_EXTRA_HEADINGS",
                        "count": len(extras)})
    _need(manifest.get("paired_with_w1") == len(paired)
          and manifest.get("unresolved") == []
          and len(manifest.get("extras", [])) == 1
          and manifest["extras"][0].get("kind") == "TITLE_HEADING"
          and expected_extras,
          "W2 declared pair coverage or extra heading invalid")
    results = []
    with TemporaryDirectory(prefix="mubin-private-pair-") as tmp:
        for chapter, section in paired:
            piece = w1_export[chapter["source_byte_start"]:
                              chapter["source_byte_end_exclusive"]]
            left_path = Path(tmp)/(chapter["id"].replace(":", "_")+".txt")
            left_path.write_bytes(piece)
            right_path = files[section["h2_ordinal"]]
            try:
                alignment = align_sections(
                    left_path, right_path,
                    left_sha256=chapter["section_sha256"],
                    right_sha256=_sha(right_path.read_bytes()),
                    left_source_id="pilot:waraqat-primary",
                    right_source_id="pilot:waraqat-comparator",
                    left_locator=chapter["id"],
                    right_locator=f"w2:h2-{section['h2_ordinal']}")
            except (WitnessAlignmentError, ValueError, OSError) as exc:
                skipped.append({"w1_section_id": chapter["id"],
                                "reason": "ALIGNMENT_REFUSED",
                                "reason_code": type(exc).__name__})
                continue
            counts = Counter(e["class"] for e in alignment["strict_changes"])
            results.append({
                "w1_section_id": chapter["id"],
                "w2_h2_ordinal": section["h2_ordinal"],
                "overall_classification": alignment["overall_classification"],
                "strict_change_count": alignment["strict_change_count"],
                "profiles": {k:v for k,v in alignment["profiles"].items()
                             if type(v) is bool},
                "classification_counts": dict(counts),
                "left_bytes": len(piece),
                "right_bytes": right_path.stat().st_size,
            })
    complete = (len(results) == len(chapters) and len(skipped) == 1
                and len(paired) == len(chapters))
    payload = {
        "engine": VERSION,
        "status": ("W2_PAIR_COMPARE_COMPLETE" if complete
                   else "W2_PAIR_COMPARE_PARTIAL_REQUIRES_REVIEW"),
        "compared_sections": len(results),
        "chapters_expected": len(chapters),
        "skipped": skipped,
        "results": results,
        "source_text_included": False,
        "scholarly_verified": False,
        "redistribution_approved": False,
        "semantic_equivalence_verified": False,
    }
    payload["report_sha256"] = _sha(_canonical(payload))
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--w1-export", type=Path, required=True)
    parser.add_argument("--w2-manifest", type=Path, required=True)
    parser.add_argument("--w2-raw-html", type=Path, required=True,
                        help="frozen private W2 HTML required to replay extraction")
    parser.add_argument("--w2-sections-dir", type=Path, required=True)
    parser.add_argument("--w1-sections-dir", type=Path,
                        help="deprecated; comparator uses private temporary files")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = compare_all(
            json.loads(args.inventory.read_text(encoding="utf-8")),
            args.w1_export.read_bytes(),
            json.loads(args.w2_manifest.read_text(encoding="utf-8")),
            args.w2_raw_html.read_bytes(),
            args.w2_sections_dir)
        code = 0 if payload["status"] == "W2_PAIR_COMPARE_COMPLETE" else 1
    except (OSError, ValueError, UnicodeError, TypeError, KeyError,
            BatchCoverageError) as exc:
        payload = {"engine": VERSION, "status": "FAIL",
                   "reason_code": type(exc).__name__,
                   "source_text_included": False}
        code = 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False,
                                  sort_keys=True, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"],
                      "compared": payload.get("compared_sections", 0),
                      "skipped": len(payload.get("skipped", []))}, ensure_ascii=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
