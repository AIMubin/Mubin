"""T0.2 CLI: extract structured interpretation records from T0.1 output.

Local operator tool. Text stays on the machine unless --include-text is
explicitly passed; summaries (ids and counts) are always CI-safe.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from engines.tafsir.t01 import lookup_verse
from engines.tafsir.t02 import (
    extract_from_t01_record, summarize, TafsirT02Error,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m engines.tafsir.t02_cli",
        description="T0.2 source-grounded interpretation extraction")
    parser.add_argument("reference", help="Sura:ayah, e.g. 2:43")
    parser.add_argument("--database", type=Path,
                        default=Path("corpus-data/linked/quran_tafsir.db"))
    parser.add_argument("--include-text", action="store_true",
                        help="Include statement text in stdout: LOCAL ONLY, "
                             "never pipe to CI or logs")
    parser.add_argument("--summary-only", action="store_true",
                        help="Print counts and ids only (CI-safe)")
    args = parser.parse_args(argv)
    try:
        lookup = lookup_verse(args.database, args.reference,
                              include_private_text=True)
    except Exception as exc:  # stable code passthrough
        code = getattr(exc, "code", "T02_LOOKUP_FAILED")
        print(json.dumps({"status": "REFUSED", "code": code,
                          "text_included": False}, ensure_ascii=False))
        return 2
    records = []
    for tafsir in lookup.get("tafsirs", []):
        records.extend(extract_from_t01_record(tafsir))
    if args.summary_only or not args.include_text:
        safe = []
        for r in records:
            slim = dict(r)
            slim["interpretation_statement"] = ""
            slim["text_included"] = False
            safe.append(slim)
        payload = {"status": "OK", "quran_reference": args.reference,
                   "summary": summarize(records),
                   "records_redacted": len(records),
                   "note": "statement text withheld; rerun with "
                           "--include-text locally to view"}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        payload = {"status": "OK", "quran_reference": args.reference,
                   "summary": summarize(records),
                   "records": records,
                   "warning": "LOCAL RESEARCH VIEW - DO NOT PIPE TO CI/LOGS"}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
