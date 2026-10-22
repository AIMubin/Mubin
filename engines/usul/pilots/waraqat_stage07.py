"""Stage07 local real-witness runner — fail-closed Stage06 provenance before search.

The two private frozen HTML captures, W1 original export/manifest, and both
section files must pass the Stage06 dual-source strict extraction replay.
All original source bytes remain local. No search candidate is a ruling.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from engines.usul.arabic_evidence_retrieval import (
    ArabicRetrievalError, retrieve,
)
from engines.usul.pilots.waraqat_stage06 import (
    compare_captured_witnesses, W1_SECTION_SHA, W1_RAW_SHA, W2_RAW_SHA,
    W1_URL, W2_URL, SECTION,
)
from engines.usul.pilots.waraqat_extract import TOOL_VERSION as W1_EXTRACTOR
from engines.usul.pilots.waraqat_witness2_extract import VERSION as W2_EXTRACTOR

# Frozen in the independent local Stage06 receipt, NOT recomputed from W2.
W2_SECTION_SHA = "db181b1d9466389d2b5aeaf50362dd57e716cc1e36d041948777e3fe0c9c9358"
RUNNER_VERSION = "waraqat-two-witness-stage07/0.1.0"


def _require(value, msg):
    if not value:
        raise ArabicRetrievalError("Stage07 Waraqat provenance: " + msg)


def replay_and_search(primary_html, primary_export, primary_manifest,
                      primary_section, secondary_html, secondary_section, queries):
    provenance = compare_captured_witnesses(
        primary_html, primary_export, primary_manifest, primary_section,
        secondary_html, secondary_section, W2_SECTION_SHA,
        verify_secondary_extraction=True,
    )
    _require(provenance["status"] == "STAGE06_DUAL_SOURCE_EXTRACTION_REPLAY_PASS"
             and provenance["primary_html_to_section_replay_verified"] is True
             and provenance["secondary_html_to_section_replay_verified"] is True
             and provenance["left"]["section_sha256"] == W1_SECTION_SHA
             and provenance["right"]["section_sha256"] == W2_SECTION_SHA
             and provenance["raw_html_witness1_sha256"] == W1_RAW_SHA
             and provenance["raw_html_witness2_sha256"] == W2_RAW_SHA,
             "Stage06 strict extraction and frozen witness identity required")
    output = retrieve([
        {
            "source_id": "pilot:waraqat-primary", "section_path": Path(primary_section),
            "section_sha256": W1_SECTION_SHA, "source_url": W1_URL,
            "section_locator": "الورقات / باب الأمر / 86–107",
            "offset_basis": "utf8_export", "source_byte_base": 3735,
            "source_line_base": 86,
        },
        {
            "source_id": "pilot:waraqat-comparator",
            "section_path": Path(secondary_section),
            "section_sha256": W2_SECTION_SHA, "source_url": W2_URL,
            "section_locator": "الورقات / باب الأمر / شاهد رقمي ثان",
            "offset_basis": "extracted_section", "source_byte_base": 0,
            "source_line_base": 1,
        },
    ], queries)
    _require(output["source_count"] == 2
             and [w["section_sha256"] for w in output["witnesses"]] ==
             [W1_SECTION_SHA, W2_SECTION_SHA],
             "retrieval results are not from both independently pinned sections")
    return {
        **output,
        "runner": RUNNER_VERSION,
        "status": "STAGE07_DUAL_WITNESS_ARABIC_RETRIEVAL_PASS",
        "stage06_strict_provenance": {
            "status": provenance["status"],
            "raw_html_primary_sha256": W1_RAW_SHA,
            "raw_html_comparator_sha256": W2_RAW_SHA,
            "first_extractor": W1_EXTRACTOR,
            "second_extractor": W2_EXTRACTOR,
            "both_html_to_section_replays_verified": True,
            "raw_character_diff_count": provenance["strict_change_count"],
            "lexical_content_equivalence_certified": False,
        },
        "query_cross_witness_semantic_agreement_verified": False,
        "full_book_coverage_verified": False,
        "meaning_preservation_verified": False,
        "public_fatwa_authorized": False,
        "source_text_included": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("primary-html", "primary-export", "primary-manifest",
                "primary-section", "secondary-html", "secondary-section",
                "queries", "report"):
        p.add_argument("--" + key, required=True, type=Path)
    args = p.parse_args()
    inputs = (args.primary_html, args.primary_export, args.primary_manifest,
              args.primary_section, args.secondary_html, args.secondary_section)
    try:
        if not all(path.is_file() for path in inputs):
            report, code = {
                "status": "PENDING_PRIVATE_WITNESS_FILES",
                "source_text_included": False, "scholarly_verified": False,
            }, 3
        else:
            if not args.queries.is_file() or not 0 < args.queries.stat().st_size <= 65536:
                raise ArabicRetrievalError("missing or oversized query specification")
            queries = json.loads(args.queries.read_text(encoding="utf-8"))
            report = replay_and_search(*inputs, queries)
            code = 0
    except (OSError, ValueError, UnicodeError) as exc:
        report, code = {
            "status": "FAIL", "reason_code": type(exc).__name__,
            "source_text_included": False, "scholarly_verified": False,
        }, 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "report": str(args.report),
        "source_text_included": False,
    }, ensure_ascii=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
