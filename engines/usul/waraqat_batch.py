"""Full al-Waraqat W1 chapter inventory and reusable batch retrieval/context.

The frozen W1 original HTML is the trust root. The original extractor is
replayed exactly ONCE, chapter boundaries are mapped to original UTF-8 export
line starts, and every byte (including the preface) is accounted for.

Outputs are metadata-only. W2 comparison and semantic/juristic interpretation
are INDEPENDENT optional workstreams, not mandatory for successful W1 coverage.
"""
from __future__ import annotations

from bisect import bisect_left
import hashlib
import html
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from engines.usul.arabic_evidence_retrieval import retrieve
from engines.usul.evidence_context_graph import build_context_graph
from engines.usul.pilots.waraqat_extract import (
    CONTENT_START, TOOL_VERSION as EXTRACTOR_VERSION, extract,
)
from engines.usul.pilots.waraqat_stage06 import (
    W1_RAW_SHA, W1_EXPORT_SHA, W1_SECTION_SHA, W1_URL,
)

VERSION = "waraqat-w1-full-book-batch/0.1.0"
CHAPTER_RE = re.compile(r"<h5>(.*?)</h5>", re.DOTALL)
MAX_CHAPTERS = 96
AMR_START = 3735
AMR_END = 4967
QUERY_COUNT_LIMIT = 20


class BatchCoverageError(ValueError):
    pass


def _need(ok, message):
    if not ok:
        raise BatchCoverageError(message)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _render_region(region):
    """Keep the frozen W1 extractor's EXACT conversion rules."""
    region = re.sub(r"<br\s*/?>", "\n", region, flags=re.I)
    region = region.replace("</h5>", "\n").replace("<h5>", "\n")
    region = re.sub(r"<[^>]+>", "", region)
    region = html.unescape(region)
    return region.replace("\r\n", "\n").replace("\r", "\n")


def _line_starts(raw):
    lines = raw.splitlines(keepends=True)
    _need(bool(lines) and b"".join(lines) == raw, "UTF-8 line partition lost bytes")
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))
    return starts


def inventory(raw_html, *, expected_html_sha=W1_RAW_SHA,
              expected_export_sha=W1_EXPORT_SHA, require_frozen_amr=True):
    """Return an immutable all-byte source inventory + exact exported bytes.

    The trusted digests MUST already be externally frozen; don't silently
    change them to hashes of newly downloaded HTML.
    """
    _need(type(raw_html) is bytes and bool(raw_html),
          "nonempty raw original HTML bytes required")
    _need(_sha(raw_html) == expected_html_sha, "original W1 HTML pin mismatch")
    exported, stats = extract(raw_html)
    _need(_sha(exported) == expected_export_sha,
          "original W1 UTF-8 export pin mismatch")
    source = raw_html.decode("utf-8", errors="strict")
    begin = source.find(CONTENT_START)
    _need(begin >= 0, "missing W1 content boundary")
    begin += len(CONTENT_START)
    end = source.find("</div>", begin)
    _need(end > begin, "invalid content scope")
    region = source[begin:end]
    _need(_render_region(region).encode("utf-8") == exported,
          "chapter boundary converter drifted from frozen source extractor")
    headings = list(CHAPTER_RE.finditer(region))
    _need(2 <= len(headings) <= MAX_CHAPTERS and
          len(headings) == stats["h5_headings_seen"],
          "missing/extra/unsupported chapter heading markup")
    starts = _line_starts(exported)
    records = []
    offsets = []
    headings_text = []
    for index, match in enumerate(headings, 1):
        inner = match.group(1)
        _need("<" not in inner and ">" not in inner,
              "nested HTML inside W1 chapter heading not allowed")
        text = html.unescape(inner).strip()
        _need(bool(text) and "\n" not in text and "\r" not in text,
              "invalid multiline heading")
        # The frozen extractor translates the exact <h5> opening tag to LF.
        offset = len(_render_region(region[:match.start()]).encode("utf-8")) + 1
        line_idx = bisect_left(starts, offset)
        _need(line_idx < len(starts)-1 and starts[line_idx] == offset,
              "chapter title not located at original UTF-8 line boundary")
        line = exported[starts[line_idx]:starts[line_idx+1]].decode("utf-8")
        _need(line.strip() == text,
              "chapter title or character position differs from original export")
        _need(not offsets or offset > offsets[-1], "heading order reversed")
        offsets.append(offset)
        headings_text.append(text)
        records.append({
            "id": f"waraqat:w1:chapter-{index:03d}",
            "kind": "HEADING_SECTION",
            "heading_ordinal": index,
            "heading_sha256": _sha(text.encode("utf-8")),
            "source_line_start": line_idx + 1,
            "source_byte_start": offset,
        })
    _need(offsets[0] > 0, "missing prologue span")
    sections = [{
        "id": "waraqat:w1:prologue",
        "kind": "PRELUDE",
        "heading_ordinal": None,
        "heading_sha256": None,
        "source_byte_start": 0,
        "source_line_start": 1,
    }, *records]
    for i, row in enumerate(sections):
        stop = sections[i + 1]["source_byte_start"] if i+1 < len(sections) else len(exported)
        first = row["source_byte_start"]
        _need(0 <= first < stop <= len(exported),
              "invalid zero-length or overlapping original source span")
        section = exported[first:stop]
        firstline = row["source_line_start"]
        lastline = bisect_left(starts, stop)
        _need(lastline < len(starts) and starts[lastline] == stop,
              "chapter end is not original UTF-8 line boundary")
        row["source_byte_end_exclusive"] = stop
        row["source_line_end_exclusive"] = lastline + 1
        row["byte_count"] = len(section)
        row["line_count"] = lastline + 1 - firstline
        row["section_sha256"] = _sha(section)
        row["source_text_included"] = False
    _need(sections[0]["source_byte_start"] == 0
          and sections[-1]["source_byte_end_exclusive"] == len(exported)
          and all(a["source_byte_end_exclusive"] == b["source_byte_start"]
                  for a, b in zip(sections, sections[1:])),
          "full original W1 book byte coverage not contiguous")
    if require_frozen_amr:
        indices = [i for i, h in enumerate(headings_text) if h == "الأمر"]
        _need(len(indices) == 1, "frozen Bab al-Amr heading missing/ambiguous")
        k = indices[0]
        _need(k+1 < len(headings_text) and headings_text[k+1] == "النهي",
              "historical Bab al-Amr next heading does not match")
        bab = records[k]
        _need(bab["source_byte_start"] == AMR_START
              and bab["source_byte_end_exclusive"] == AMR_END
              and bab["section_sha256"] == W1_SECTION_SHA
              and bab["line_count"] == 22,
              "new inventory breaks frozen Stage04 Bab al-Amr source coverage")
    meta = {
        "engine": VERSION,
        "status": "FULL_W1_SOURCE_INVENTORY_PASS",
        "witness_id": "pilot:waraqat-primary",
        "source_url": W1_URL,
        "source_raw_html_sha256": expected_html_sha,
        "source_export_sha256": expected_export_sha,
        "original_extractor_version": EXTRACTOR_VERSION,
        "source_export_byte_count": len(exported),
        "source_export_line_count": len(starts)-1,
        "chapter_heading_count": len(headings),
        "partition_count_including_prelude": len(sections),
        "all_original_bytes_partitioned_once": True,
        "sections": sections,
        "source_text_included": False,
        "scholarly_verified": False,
        "redistribution_approved": False,
        "juristic_inference_allowed": False,
    }
    meta["inventory_sha256"] = _sha(_canonical(meta))
    return exported, meta


def batch_retrieve_and_graph(exported, inventory_report, queries):
    """Index each pinned W1 partition, then generate SHA-only context graphs.

    Query-miss is a legitimate indexed section; unexpected failures isolate
    just that section and are reported, not hidden. No witness-2 equivalence.
    """
    _need(type(queries) is list and 1 <= len(queries) <= QUERY_COUNT_LIMIT,
          "bounded explicit Arabic query set required")
    _need(type(exported) is bytes
          and _sha(exported) == inventory_report["source_export_sha256"],
          "source export differs from frozen inventory")
    result = []
    with TemporaryDirectory(prefix="mubin-w1-batch-") as temporary:
        root = Path(temporary)
        for section in inventory_report["sections"]:
            start, stop = section["source_byte_start"], section["source_byte_end_exclusive"]
            piece = exported[start:stop]
            _need(_sha(piece) == section["section_sha256"],
                  "root source differs from listed section hash")
            path = root / (section["id"].replace(":", "_") + ".txt")
            path.write_bytes(piece)
            witness = {
                "source_id": "pilot:waraqat-primary",
                "section_path": path,
                "section_sha256": section["section_sha256"],
                "source_url": W1_URL,
                "section_locator": section["id"],
                "offset_basis": "utf8_export",
                "source_byte_base": start,
                "source_line_base": section["source_line_start"],
            }
            record = {
                "section_id": section["id"],
                "section_sha256": section["section_sha256"],
                "status": "PASS",
                "comparison_status": "SECOND_WITNESS_COMPARISON_NOT_RUN",
                "semantic_interpretation_status": "NOT_EVALUATED",
                "source_text_included": False,
            }
            try:
                retrieved = retrieve([witness], queries)
                graph = build_context_graph(
                    retrieved, [witness], queries, pointers=[],
                    context_radius_lines=1,
                    work_title="الورقات في أصول الفقه",
                    author="عبد الملك بن عبد الله الجويني",
                )
                record["indexed_section_bytes"] = retrieved["witnesses"][0]["indexed_section_bytes"]
                record["exact_match_count"] = sum(
                    x["strict_match_count"] for x in retrieved["witnesses"][0]["queries"]
                )
                record["candidate_edges_count"] = graph["edges_by_kind"].get(
                    "QUERY_LOCATES_OCCURRENCE", 0
                ) - record["exact_match_count"]
                record["unique_occurrence_count"] = graph["nodes_by_kind"].get(
                    "TEXT_OCCURRENCE", 0
                )
                record["context_count"] = graph["nodes_by_kind"].get(
                    "HASHED_CONTEXT", 0
                )
                record["graph_sha256"] = graph["graph_sha256"]
            except (ValueError, OSError, UnicodeError) as exc:
                record["status"] = "SECTION_PROCESSING_FAILED"
                record["reason_code"] = type(exc).__name__
            result.append(record)
    passing = sum(row["status"] == "PASS" for row in result)
    payload = {
        "engine": VERSION,
        "status": ("FULL_W1_BATCH_PASS" if passing == len(result)
                   else "W1_BATCH_PARTIAL_REQUIRES_REVIEW"),
        "inventory_sha256": inventory_report["inventory_sha256"],
        "sections_total": len(result),
        "sections_passed": passing,
        "sections_failed": len(result) - passing,
        "sections": result,
        "all_stages_are_metadata_only": True,
        "secondary_witness_not_required_for_w1_coverage": True,
        "cross_witness_comparison_verified": False,
        "full_qarinah_coverage_verified": False,
        "semantic_rules_qualified": False,
        "scholarly_verified": False,
        "redistribution_approved": False,
        "public_fatwa_authorized": False,
        "source_text_included": False,
    }
    return {**payload, "batch_sha256": _sha(_canonical(payload))}
