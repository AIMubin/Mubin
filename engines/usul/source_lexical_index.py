"""U0.1 Stage 05: byte-anchored lexical evidence retrieval from a P0 source export.

Replays Stage 04's independently pinned manifest and section coverage before
indexing every line in the requested section. Optionally verifies the upstream
HTML -> UTF-8 export with a separately pinned raw HTML digest. Index and
search reports contain locations and hashes, not source text or query text.
Exact literal matching ONLY; zero hits never means "no legal qarinah".
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from engines.usul.source_snapshot_coverage import (
    MAX_SOURCE_BYTES, SHA256, SnapshotContractError,
    _bound_read, _line_index, audit,
)

ENGINE_VERSION = "usul-lexical-index/0.1.0"
PROFILE = "literal_exact_v1"
MAX_QUERIES = 32
MAX_QUERY_CHARS = 256
MAX_MATCHES_PER_QUERY = 4096
IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.:-]{2,127}$")


class LexicalContractError(ValueError):
    pass


def _require(value, msg):
    if not value:
        raise LexicalContractError(msg)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _canonical_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _check_queries(queries):
    _require(type(queries) is list and 1 <= len(queries) <= MAX_QUERIES,
             "queries: expected a bounded nonempty array")
    seen = set()
    for i, query in enumerate(queries):
        _require(type(query) is dict and set(query) == {"id", "literal", "profile"},
                 f"queries[{i}]: expected id, literal and profile")
        qid, literal = query["id"], query["literal"]
        _require(type(qid) is str and IDENTIFIER.fullmatch(qid) is not None
                 and qid not in seen, f"queries[{i}]: invalid or duplicate id")
        seen.add(qid)
        _require(query["profile"] == PROFILE,
                 f"queries[{i}]: unsupported normalizer/profile")
        _require(type(literal) is str and 1 <= len(literal) <= MAX_QUERY_CHARS
                 and literal.strip() and not any(ord(c) < 32 or ord(c) == 127 for c in literal),
                 f"queries[{i}]: empty, multiline or control-character query")
    return queries


def index_and_search(snapshot_path, manifest_path, trusted_manifest_sha256,
                     section_id, queries, *, raw_html_path=None,
                     trusted_raw_html_sha256=None):
    """No index/search result unless exact section coverage has passed.

    Optional raw HTML validation is stronger than snapshot-only and proves
    deterministic equivalence for the *specified converter*, not a critical
    edition or a source-host authenticity guarantee.
    """
    _check_queries(queries)
    _require(type(section_id) is str and IDENTIFIER.fullmatch(section_id) is not None,
             "invalid section ID")
    _require((raw_html_path is None) == (trusted_raw_html_sha256 is None),
             "raw HTML and its independently trusted digest must be supplied together")
    coverage = audit(Path(snapshot_path), Path(manifest_path),
                     trusted_manifest_sha256=trusted_manifest_sha256)
    _require(coverage["status"] == "SNAPSHOT_COVERAGE_PASS",
             "Stage 04 section coverage did not pass")
    sections = [x for x in coverage["sections"] if x["section_id"] == section_id]
    _require(len(sections) == 1, "section not uniquely attested by Stage 04")
    sec = sections[0]

    raw = _bound_read(Path(snapshot_path), MAX_SOURCE_BYTES)
    # Mitigate a change between the Stage-04 audit and the indexer read.
    _require(_sha(raw) == coverage["snapshot_sha256"],
             "source changed between coverage and indexing")
    lines, source_lines = _line_index(raw)
    indexed = source_lines[sec["begin_line_inclusive"]-1:sec["end_line_exclusive"]-1]
    _require(len(indexed) == sec["line_count"], "source-index line coverage mismatch")
    _require(indexed and indexed[0]["byte_start"] == sec["start_byte"]
             and indexed[-1]["byte_end"] == sec["end_byte_exclusive"],
             "source-index byte coverage mismatch")
    section_bytes = raw[sec["start_byte"]:sec["end_byte_exclusive"]]
    _require(b"".join(lines[sec["begin_line_inclusive"]-1:sec["end_line_exclusive"]-1])
             == section_bytes and _sha(section_bytes) == sec["section_sha256"],
             "indexed lines are not an exact reconstruction of the pinned section")

    upstream = {
        "status": "NOT_RECHECKED",
        "raw_html_sha256": None,
        "extractor": None,
        "source_export_reproduced_from_html": False,
    }
    if raw_html_path is not None:
        _require(type(trusted_raw_html_sha256) is str
                 and SHA256.fullmatch(trusted_raw_html_sha256) is not None,
                 "invalid independent raw HTML digest")
        from engines.usul.pilots.waraqat_extract import TOOL_VERSION, extract
        original_html = _bound_read(Path(raw_html_path), MAX_SOURCE_BYTES)
        _require(_sha(original_html) == trusted_raw_html_sha256,
                 "raw HTML SHA-256 does not match independently pinned capture")
        try:
            exported, stats = extract(original_html)
        except (UnicodeError, ValueError) as exc:
            raise LexicalContractError("HTML to UTF-8 extraction failed") from exc
        _require(exported == raw,
                 "raw HTML does not reproduce the entire pinned text export")
        upstream = {
            "status": "PINNED_HTML_TO_EXPORT_REPLAY_PASS",
            "raw_html_sha256": _sha(original_html),
            "extractor": TOOL_VERSION,
            "source_export_reproduced_from_html": True,
        }

    entries = [
        {
            "section_id": section_id,
            "line_number": line["line_number"],
            "byte_start": line["byte_start"],
            "byte_end_exclusive": line["byte_end"],
            "line_sha256": line["sha256"],
        } for line in indexed
    ]
    query_reports = []
    for query in queries:
        literal = query["literal"]
        literal_bytes = literal.encode("utf-8")
        matches = []
        for entry in entries:
            line_bytes = raw[entry["byte_start"]:entry["byte_end_exclusive"]]
            # UTF-8 validated by Stage04; byte-offsets preserve original chars.
            line = line_bytes.decode("utf-8")
            at = 0
            while (hit := line.find(literal, at)) != -1:
                start = entry["byte_start"] + len(line[:hit].encode("utf-8"))
                end = start + len(literal_bytes)
                _require(raw[start:end] == literal_bytes,
                         "lexical match cannot be mapped to original UTF-8 bytes")
                matches.append({
                    "section_id": section_id,
                    "line_number": entry["line_number"],
                    "line_sha256": entry["line_sha256"],
                    "column_codepoints_zero_based": hit,
                    "byte_start": start,
                    "byte_end_exclusive": end,
                    "match_sha256": _sha(raw[start:end]),
                    "source_text_included": False,
                })
                _require(len(matches) <= MAX_MATCHES_PER_QUERY,
                         "too many matches: refusing truncated or partial index")
                # Allow overlapping occurrences; one code point at a time.
                at = hit + 1
        query_reports.append({
            "query_id": query["id"],
            "query_profile": PROFILE,
            "query_utf8_sha256": _sha(literal_bytes),
            "query_characters": len(literal),
            "classification": "LEXICAL_MATCH_ONLY",
            "result_status": ("EXACT_LITERAL_MATCHES_IN_PINNED_SECTION" if matches
                              else "NO_EXACT_LITERAL_MATCH_IN_PINNED_SECTION"),
            "match_count": len(matches),
            "matches": matches,
            "absence_of_legal_qarinah_verified": False,
            "juristic_inference_allowed": False,
            "source_text_included": False,
            "query_text_included": False,
        })

    return {
        "engine": ENGINE_VERSION,
        "status": "LEXICAL_INDEX_PASS",
        "coverage_status": coverage["status"],
        "source_id": coverage["source_id"],
        "work_title": coverage["work_title"],
        "author": coverage["author"],
        "edition": coverage["edition"],
        "source_url": coverage["source_url"],
        "source_locator": coverage["locator"],
        "snapshot_sha256": coverage["snapshot_sha256"],
        "trusted_manifest_sha256": trusted_manifest_sha256,
        "section_id": section_id,
        "section_sha256": sec["section_sha256"],
        "section_start_line": sec["begin_line_inclusive"],
        "section_end_line_exclusive": sec["end_line_exclusive"],
        "line_index": entries,
        "line_index_sha256": _sha(_canonical_bytes(entries)),
        "line_index_complete_within_section": True,
        "indexed_line_count": len(entries),
        "indexed_byte_count": len(section_bytes),
        "upstream_replay": upstream,
        "queries": query_reports,
        "query_matching_scope": "EXACT_LITERAL_WITHIN_ONE_PINNED_UTF8_SECTION_ONLY",
        "lexical_search_is_semantic_qarinah_detection": False,
        "full_book_or_print_edition_verified": False,
        "scholarly_verified": False,
        "redistribution_approved": False,
        "source_text_included": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--trusted-manifest-sha256", required=True)
    parser.add_argument("--section-id", required=True)
    parser.add_argument("--queries", type=Path, required=True,
                        help="Private UTF-8 JSON array of id/literal/profile")
    parser.add_argument("--raw-html", type=Path)
    parser.add_argument("--trusted-raw-html-sha256")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        if not args.source.is_file():
            result, code = {
                "status": "PENDING_SOURCE", "scholarly_verified": False,
                "reason": "Private source text unavailable; no lexical replay",
            }, 3
        else:
            qpath = Path(args.queries)
            _require(0 < qpath.stat().st_size <= 65536,
                     "private query spec size outside limit")
            queries = json.loads(qpath.read_text(encoding="utf-8"))
            result = index_and_search(
                args.source, args.manifest, args.trusted_manifest_sha256,
                args.section_id, queries, raw_html_path=args.raw_html,
                trusted_raw_html_sha256=args.trusted_raw_html_sha256,
            )
            code = 0
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        result, code = {
            "status": "FAIL", "error_type": type(exc).__name__,
            "scholarly_verified": False, "redistribution_approved": False,
        }, 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({
        "status": result["status"], "report": str(args.report),
        "source_text_reproduced": False,
    }, ensure_ascii=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
