"""Waraqat full-primary-witness chapter campaign, without single-Bab hardcoding.

Input is the SAME Stage04 SHA-frozen W1 HTML+UTF8 export. Derive all
<h5>-headed text sections and optional preface in one pass, then run the
already-tested Stage07 retrieval and Stage08 contextual graph for each.
No original text or query literal is committed in reports. W2, lexical
equivalence, scholarly review and P0 semantics are independent gates.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import tempfile

from engines.usul.arabic_evidence_retrieval import (
    MAX_SECTION_BYTES, _validate_queries, retrieve,
)
from engines.usul.evidence_context_graph import build_context_graph
from engines.usul.pilots.waraqat_extract import (
    CONTENT_START, extract as extract_w1, TOOL_VERSION,
)
from engines.usul.pilots.waraqat_chapter_crosswalk import (
    candidate_crosswalk, HeadingCrosswalkError,
)
from engines.usul.pilots.waraqat_stage06 import (
    W1_EXPORT_SHA, W1_RAW_SHA, W1_SECTION_SHA, W1_URL,
)

VERSION = "waraqat-primary-chapter-batch/0.1.0"
MAX_HEADINGS = 96
EXPECTED_AMR_LINE = 86
EXPECTED_AMR_BEGIN = 3735
EXPECTED_AMR_END = 4967
MAX_REPORT_BYTES = 2 * 1024 * 1024


class BatchCoverageError(ValueError):
    pass


def _need(ok, why):
    if not ok:
        raise BatchCoverageError(why)


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def _canonical(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _headings(raw_html):
    """Read h5 header *labels* only from the same strict W1 content region."""
    source = raw_html.decode("utf-8", errors="strict")
    start = source.find(CONTENT_START)
    _need(start >= 0 and source.count(CONTENT_START) == 1,
          "W1 content boundary missing/ambiguous")
    start += len(CONTENT_START)
    end = source.find("</div>", start)
    _need(end > start, "W1 content terminator missing")
    region = source[start:end]
    opens = re.findall(r"<h5>", region)
    closes = re.findall(r"</h5>", region)
    labels = re.findall(r"<h5>(.*?)</h5>", region, flags=re.DOTALL)
    _need(opens and len(opens) == len(closes) == len(labels)
          and len(labels) <= MAX_HEADINGS,
          "missing, unbalanced or excessive h5 chapter headings")
    titles = []
    for label in labels:
        _need("<" not in label and ">" not in label,
              "nested tags inside h5 headings require explicit extractor review")
        title = html.unescape(label).strip()
        _need(title and len(title) <= 150 and "\n" not in title
              and "\r" not in title, "invalid chapter title")
        titles.append(title)
    _need(len(set(titles)) == len(titles),
          "duplicate chapter headings require explicit human/source disambiguation")
    return titles


def inventory(raw_html: bytes, export: bytes, *, raw_pin, export_pin):
    """Pure metadata-only full-text chapter partition, all bytes addressed.

    raw_pin/export_pin MUST be externally frozen, never computed here to act
    as their own authentication. The last heading runs to EOF.
    """
    _need(type(raw_pin) is str and type(export_pin) is str
          and raw_pin == _sha(raw_html) and export_pin == _sha(export),
          "W1 input bytes mismatch independently frozen source digests")
    replayed, stats = extract_w1(raw_html)
    _need(replayed == export, "W1 HTML does not reconstruct pinned UTF8 export")
    _need(0 < len(export) <= 8_388_608 and b"\x00" not in export
          and not export.startswith(b"\xef\xbb\xbf"),
          "unsafe original export")
    titles = _headings(raw_html)
    lines = export.splitlines(keepends=True)
    _need(lines and b"".join(lines) == export, "export bytes not fully partitioned")
    offsets, cursor = [], 0
    for line in lines:
        offsets.append(cursor)
        cursor += len(line)
    decoded = [line.decode("utf-8", errors="strict").strip() for line in lines]
    locations = []
    for title in titles:
        candidates = [i for i, value in enumerate(decoded) if value == title]
        _need(len(candidates) == 1,
              "an h5 label has no unique standalone source line")
        locations.append(candidates[0])
    _need(locations == sorted(locations) and len(set(locations)) == len(locations),
          "chapter markers are out of original source order")
    _need(len(locations) == stats["h5_headings_seen"],
          "header inventory differs from HTML text exporter")
    cuts = [offsets[i] for i in locations] + [len(export)]
    chapters = []
    for i, title in enumerate(titles):
        a, b = cuts[i], cuts[i + 1]
        span = export[a:b]
        _need(a < b and span and span.startswith(lines[locations[i]]),
              "chapter section has broken source boundary")
        chapters.append({
            "id": f"pilot:waraqat-w1-section-{i + 1:03d}",
            "heading": title,
            "order": i + 1,
            "source_byte_start": a,
            "source_byte_end_exclusive": b,
            "source_line_start": locations[i] + 1,
            "line_count": len(lines[locations[i]:locations[i+1] if i+1<len(locations) else len(lines)]),
            "section_sha256": _sha(span),
            "section_bytes": len(span),
            "pin_origin": "DETERMINISTIC_DERIVATION_FROM_FROZEN_PRIMARY_EXPORT",
        })
    prefix = export[:cuts[0]]
    _need(prefix + b"".join(export[c["source_byte_start"]:c["source_byte_end_exclusive"]]
                            for c in chapters) == export,
          "chapter inventory does not cover the entire pinned W1 export")
    # Historic Bab al-Amr invariance: the new generalized inventory must NOT
    # invalidate the already locally checked Stage04–08 section boundaries.
    pairs = [(c, chapters[i+1]) for i, c in enumerate(chapters[:-1])
             if c["heading"] == "الأمر" and chapters[i+1]["heading"] == "النهي"]
    _need(len(pairs) == 1, "frozen باب الأمر→النهي section pair not preserved")
    amr = pairs[0][0]
    _need(amr["source_line_start"] == EXPECTED_AMR_LINE
          and amr["source_byte_start"] == EXPECTED_AMR_BEGIN
          and amr["source_byte_end_exclusive"] == EXPECTED_AMR_END
          and amr["section_sha256"] == W1_SECTION_SHA,
          "new batch inventory would regress Stage04 باب الأمر receipt")
    return {
        "engine": VERSION,
        "status": "PRIMARY_WITNESS_CHAPTER_INVENTORY_PASS",
        "witness_id": "pilot:waraqat-primary",
        "source_url": W1_URL,
        "extractor": TOOL_VERSION,
        "raw_html_sha256": raw_pin,
        "export_sha256": export_pin,
        "export_bytes": len(export),
        "export_lines": len(lines),
        "heading_count": len(titles),
        "chapter_count": len(chapters),
        "preface": {
            "byte_start": 0, "byte_end_exclusive": len(prefix),
            "sha256": _sha(prefix), "bytes": len(prefix),
            "classification": "UNHEADED_SOURCE_PREFIX_NOT_SILENTLY_DROPPED",
        },
        "chapters": chapters,
        "complete_original_byte_partition_verified": True,
        "bab_amr_frozen_stage04_replay_verified": True,
        "w2_full_chapter_alignment_verified": False,
        "public_source_text_included": False,
        "scholarly_verified": False,
        "redistribution_approved": False,
    }


def campaign(raw_html, export, queries, *, raw_pin, export_pin, secondary_html=None):
    """One pass over all W1 chapters. Failed isolated chapters stay visible."""
    _validate_queries(queries)
    index = inventory(raw_html, export, raw_pin=raw_pin, export_pin=export_pin)
    results = []
    with tempfile.TemporaryDirectory(prefix="mubin-waraqat-batch-") as folder:
        for c in index["chapters"]:
            if c["section_bytes"] > MAX_SECTION_BYTES:
                results.append({
                    "chapter_id": c["id"], "status": "SECTION_TOO_LARGE_REQUIRES_CHUNKING",
                    "reason_code": "MAX_SECTION_BYTES",
                    "primary_source_safe": True,
                    "w2_alignment": "PENDING_COMPARATOR_CHAPTER_INVENTORY",
                })
                continue
            section = export[c["source_byte_start"]:c["source_byte_end_exclusive"]]
            path = Path(folder) / (c["id"].split("-")[-1] + ".txt")
            path.write_bytes(section)
            witness = {
                "source_id": "pilot:waraqat-primary",
                "source_url": W1_URL,
                "section_path": path,
                "section_sha256": c["section_sha256"],
                "section_locator": "الورقات / " + c["heading"],
                "offset_basis": "utf8_export",
                "source_byte_base": c["source_byte_start"],
                "source_line_base": c["source_line_start"],
            }
            try:
                search = retrieve([witness], queries)
                graph = build_context_graph(
                    search, [witness], queries, pointers=[],
                    work_title="الورقات في أصول الفقه",
                    author="عبد الملك بن عبد الله الجويني",
                )
                _need(graph["stage07_witness_count"] == 1 and
                      graph["all_edge_references_valid"] is True,
                      "invalid graph references")
                results.append({
                    "chapter_id": c["id"],
                    "status": "PRIMARY_INDEX_AND_CONTEXT_GRAPH_PASS",
                    "section_sha256": c["section_sha256"],
                    "literal_match_count": sum(
                        x["strict_match_count"] for x in search["witnesses"][0]["queries"]
                    ),
                    "candidate_edge_count": graph["edges_by_kind"].get(
                        "QUERY_LOCATES_OCCURRENCE", 0
                    ) - sum(x["strict_match_count"]
                            for x in search["witnesses"][0]["queries"]),
                    "graph_nodes": len(graph["nodes"]),
                    "graph_edges": len(graph["edges"]),
                    "graph_sha256": graph["graph_sha256"],
                    "w2_alignment": "PENDING_COMPARATOR_CHAPTER_INVENTORY",
                    "semantic_qarinah_verified": False,
                })
            except (ValueError, OSError, UnicodeError) as exc:
                results.append({
                    "chapter_id": c["id"],
                    "status": "CHAPTER_PIPELINE_BLOCKED",
                    "reason_code": type(exc).__name__,
                    "w2_alignment": "PENDING_COMPARATOR_CHAPTER_INVENTORY",
                })
    passed = sum(x["status"] == "PRIMARY_INDEX_AND_CONTEXT_GRAPH_PASS" for x in results)
    comparison = None
    if secondary_html is not None:
        try:
            comparison = candidate_crosswalk(index, secondary_html)
        except (ValueError, UnicodeError) as exc:
            comparison = {
                "status": "W2_HEADING_CROSSWALK_BLOCKED",
                "reason_code": type(exc).__name__,
                "w2_chapter_byte_extraction_verified": False,
                "full_witness_comparison_qualified": False,
            }
    result = {
        "engine": VERSION,
        "status": ("PRIMARY_WITNESS_BATCH_COVERAGE_PASS"
                   if passed == index["chapter_count"]
                   else "PRIMARY_WITNESS_BATCH_PARTIAL"),
        "inventory": index,
        "chapter_results": results,
        "w2_heading_crosswalk": comparison,
        "chapters_processed": index["chapter_count"],
        "chapters_passed": passed,
        "chapters_blocked": index["chapter_count"] - passed,
        "source_scope": "ONE_PINNED_PRIMARY_DIGITAL_WITNESS",
        "w2_comparator_available_for_all_chapters": False,
        "semantic_qarinah_verified": False,
        "source_edition_verified": False,
        "scholarly_verified": False,
        "redistribution_approved": False,
        "juristic_inference_allowed": False,
        "public_fatwa_authorized": False,
        "source_text_included": False,
    }
    result["report_sha256"] = _sha(_canonical(result))
    _need(len(_canonical(result)) <= MAX_REPORT_BYTES,
          "bounded batch report size exceeded")
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--primary-html", required=True, type=Path)
    p.add_argument("--primary-export", required=True, type=Path)
    p.add_argument("--queries", required=True, type=Path)
    p.add_argument("--secondary-html", type=Path)
    p.add_argument("--report", required=True, type=Path)
    args = p.parse_args()
    try:
        if not args.primary_html.is_file() or not args.primary_export.is_file():
            report, code = {
                "status": "PENDING_PRIVATE_WITNESS_FILES", "source_text_included": False
            }, 3
        else:
            _need(args.queries.is_file() and 0 < args.queries.stat().st_size <= 65536,
                  "missing or oversized queries")
            queries = json.loads(args.queries.read_text(encoding="utf-8"))
            html_data = args.primary_html.read_bytes()
            export_data = args.primary_export.read_bytes()
            _need(len(html_data) <= 8_388_608 and len(export_data) <= 8_388_608,
                  "input larger than W1 contract")
            if args.secondary_html is not None and not args.secondary_html.is_file():
                raise BatchCoverageError("requested secondary HTML is missing")
            secondary = (args.secondary_html.read_bytes()
                         if args.secondary_html is not None else None)
            report = campaign(html_data, export_data, queries,
                              raw_pin=W1_RAW_SHA, export_pin=W1_EXPORT_SHA,
                              secondary_html=secondary)
            code = (0 if report["status"] == "PRIMARY_WITNESS_BATCH_COVERAGE_PASS"
                    and (report["w2_heading_crosswalk"] is None or
                         report["w2_heading_crosswalk"]["status"] ==
                         "W2_HEADING_CROSSWALK_CANDIDATES_ONLY") else 2)
    except (OSError, ValueError, UnicodeError) as exc:
        report, code = {"status": "FAIL", "reason_code": type(exc).__name__,
                        "source_text_included": False}, 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n",
                           encoding="utf-8")
    print(json.dumps({"status": report["status"], "report": str(args.report),
                      "source_text_included": False}, ensure_ascii=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
