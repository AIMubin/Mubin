"""T0.2.3 CLI: identification + attribution + candidate relations.

Pipeline: T0.1 pinned lookup -> maintainer's byte-verified raw extraction
(t02_cli.extract_local_verse) -> T0.2.3 candidates and relations.
Default output is counts-only (CI-safe); --include-text is LOCAL ONLY.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from engines.tafsir.t01 import lookup_verse
from engines.tafsir.t02_cli import extract_local_verse
from engines.tafsir.t023 import (
    build_relationships, identify_candidates, summarize_analysis,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m engines.tafsir.t023_cli",
        description="T0.2.3 identification, attribution and candidate relations")
    parser.add_argument("reference", help="Sura:ayah, e.g. 2:43")
    parser.add_argument("--database", type=Path,
                        default=Path("corpus-data/linked/quran_tafsir.db"))
    parser.add_argument("--include-text", action="store_true",
                        help="LOCAL ONLY: include candidate text in stdout")
    args = parser.parse_args(argv)
    try:
        lookup = lookup_verse(args.database, args.reference,
                              include_private_text=True)
        passages = extract_local_verse(args.database, lookup)
    except Exception as exc:
        code = getattr(exc, "code", "T023_LOOKUP_FAILED")
        print(json.dumps({"status": "REFUSED", "code": code,
                          "text_included": False}, ensure_ascii=False))
        return 2
    candidates = []
    for p in passages:
        candidates.extend(identify_candidates(p))
    relations = build_relationships(candidates)
    summary = summarize_analysis(passages, candidates, relations)
    payload = {"status": "OK", "quran_reference": args.reference,
               "summary": summary}
    if args.include_text:
        payload["warning"] = "LOCAL RESEARCH VIEW - DO NOT PIPE TO CI/LOGS"
        payload["candidates"] = candidates
        payload["relations"] = relations
        payload["passage_count"] = len(passages)
    else:
        payload["note"] = ("counts only; rerun with --include-text locally "
                           "for full candidates")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
