"""Batch all pinned original al-Waraqat W1 chapters with one CLI invocation.

The historical witness bytes are privately retained. Unlike Stage04–09, no
chapter-specific hardcoded SHA/byte-offset is needed beyond verifying the old
frozen Bab al-Amr fixture; no missing W2 section blocks W1 indexing.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from engines.usul.waraqat_batch import (
    BatchCoverageError, batch_retrieve_and_graph, inventory,
)

def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True,
                               indent=2) + "\n", encoding="utf-8")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--primary-html", type=Path, required=True)
    p.add_argument("--primary-export", type=Path, required=True)
    p.add_argument("--queries", type=Path, required=True)
    p.add_argument("--inventory", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    a = p.parse_args()
    try:
        if not a.primary_html.is_file() or not a.primary_export.is_file():
            result, inv, code = ({"status": "PENDING_PRIVATE_WITNESS_FILES",
                                  "source_text_included": False},
                                 {"status": "PENDING_PRIVATE_WITNESS_FILES",
                                  "source_text_included": False}, 3)
        else:
            if not a.queries.is_file() or not 0 < a.queries.stat().st_size <= 65536:
                raise BatchCoverageError("missing or oversized bounded query specifications")
            queries = json.loads(a.queries.read_text(encoding="utf-8"))
            exported, inv = inventory(a.primary_html.read_bytes())
            if a.primary_export.read_bytes() != exported:
                raise BatchCoverageError("private Stage04 original export is not W1 extraction")
            result = batch_retrieve_and_graph(exported, inv, queries)
            code = 0 if result["status"] == "FULL_W1_BATCH_PASS" else 1
    except (OSError, ValueError, UnicodeError, TypeError, KeyError) as exc:
        result, inv, code = (
            {"status": "FAIL", "reason_code": type(exc).__name__,
             "source_text_included": False},
            {"status": "FAIL", "reason_code": type(exc).__name__,
             "source_text_included": False},
            1,
        )
    _write(a.inventory, inv)
    _write(a.report, result)
    print(json.dumps({"status": result["status"], "exit_code": code,
                      "sections_passed": result.get("sections_passed"),
                      "sections_total": result.get("sections_total"),
                      "source_text_included": False}, ensure_ascii=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
