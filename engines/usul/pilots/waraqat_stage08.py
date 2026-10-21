"""Stage08 research-only graph from the frozen real al-Waraqat W1/W2 captures.

Re-executes Stage07's exact dual HTML extraction gate on LOCAL private files.
Research rule and objection pointers are query-navigation hints only, NOT
evidence for a rule, a checked exception or a legal conclusion.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from engines.usul.evidence_context_graph import (
    ContextGraphError, build_context_graph,
)
from engines.usul.pilots.waraqat_stage07 import (
    replay_and_search, W1_SECTION_SHA, W2_SECTION_SHA, W1_URL, W2_URL,
)

VERSION = "waraqat-stage08-graph/0.1.0"
WORK_TITLE = "الورقات في أصول الفقه"
AUTHOR = "عبد الملك بن عبد الله الجويني"


def replay_and_graph(primary_html, primary_export, primary_manifest,
                     primary_section, secondary_html, secondary_section,
                     queries, pointers):
    stage07 = replay_and_search(
        primary_html, primary_export, primary_manifest, primary_section,
        secondary_html, secondary_section, queries,
    )
    if stage07["status"] != "STAGE07_DUAL_WITNESS_ARABIC_RETRIEVAL_PASS" or (
            stage07["stage06_strict_provenance"][
                "both_html_to_section_replays_verified"] is not True):
        raise ContextGraphError("strict Stage07 dual witness source replay required")
    descriptors = [
        {
            "source_id": "pilot:waraqat-primary",
            "section_path": Path(primary_section),
            "section_sha256": W1_SECTION_SHA,
            "source_url": W1_URL,
            "section_locator": "الورقات / باب الأمر / 86–107",
            "offset_basis": "utf8_export",
            "source_byte_base": 3735, "source_line_base": 86,
        },
        {
            "source_id": "pilot:waraqat-comparator",
            "section_path": Path(secondary_section),
            "section_sha256": W2_SECTION_SHA,
            "source_url": W2_URL,
            "section_locator": "الورقات / باب الأمر / شاهد رقمي ثان",
            "offset_basis": "extracted_section",
            "source_byte_base": 0, "source_line_base": 1,
        },
    ]
    graph = build_context_graph(
        stage07, descriptors, queries, pointers,
        context_radius_lines=1,
        work_title=WORK_TITLE, author=AUTHOR,
    )
    return {
        **graph,
        "runner": VERSION,
        "status": "STAGE08_DUAL_SOURCE_CONTEXT_GRAPH_PASS",
        "source_replay_status": stage07["status"],
        "source_replay_verified_by_runner": True,
        "primary_section_sha256": W1_SECTION_SHA,
        "secondary_section_sha256": W2_SECTION_SHA,
        "rule_citation_truth_verified": False,
        "objections_semantically_reviewed": False,
        "public_fatwa_authorized": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("primary-html", "primary-export", "primary-manifest",
                "primary-section", "secondary-html", "secondary-section",
                "queries", "pointers", "report"):
        parser.add_argument("--" + arg, type=Path, required=True)
    p = parser.parse_args()
    files = (p.primary_html, p.primary_export, p.primary_manifest,
             p.primary_section, p.secondary_html, p.secondary_section)
    try:
        if not all(f.is_file() for f in files):
            result, status = {
                "status": "PENDING_PRIVATE_WITNESS_FILES",
                "scholarly_verified": False,
                "source_text_included": False,
            }, 3
        else:
            for name, path in (("queries", p.queries), ("pointers", p.pointers)):
                if not path.is_file() or not 0 < path.stat().st_size <= 65536:
                    raise ContextGraphError(name + " JSON input is absent or oversized")
            queries = json.loads(p.queries.read_text(encoding="utf-8"))
            pointers = json.loads(p.pointers.read_text(encoding="utf-8"))
            result = replay_and_graph(*files, queries, pointers)
            status = 0
    except (OSError, UnicodeError, ValueError) as exc:
        result, status = {
            "status": "FAIL",
            "reason_code": type(exc).__name__,
            "scholarly_verified": False,
            "source_text_included": False,
        }, 1
    p.report.parent.mkdir(parents=True, exist_ok=True)
    p.report.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n",
                        encoding="utf-8")
    print(json.dumps({"status": result["status"], "report": str(p.report),
                      "source_text_included": False}, ensure_ascii=True))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
