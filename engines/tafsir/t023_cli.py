"""T0.2.3 local-only heuristics over Q0.3 pinned and T0.2 raw-verified data.

Default output is metadata counts only. --include-text is a deliberate,
private source-content disclosure to the operator's terminal, never CI.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from engines.tafsir.t01 import lookup_verse
from engines.tafsir.t02_cli import extract_local_verse
from engines.tafsir.t023 import (
    identify_candidates, build_relationships, summarize_analysis,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m engines.tafsir.t023_cli",
        description="T0.2.3 unverified source-cue analysis")
    parser.add_argument("reference", help="Sura:ayah, e.g. 2:43")
    parser.add_argument("--database", type=Path,
                        default=Path("corpus-data/linked/quran_tafsir.db"))
    parser.add_argument("--include-text", action="store_true",
                        help="LOCAL RESEARCH ONLY: print protected source excerpts")
    args = parser.parse_args(argv)
    try:
        lookup = lookup_verse(args.database, args.reference,
                              include_private_text=True)
        passages = extract_local_verse(args.database, lookup)
        candidates = []
        for p in passages:
            candidates.extend(identify_candidates(p))
        relations = build_relationships(candidates)
        summary = summarize_analysis(passages, candidates, relations)
    except Exception:  # No original text, exception, or private path in output.
        print(json.dumps({
            "status": "REFUSED", "code": "T023_PRIVATE_ANALYSIS_FAILED",
            "text_included": False,
        }, sort_keys=True))
        return 2
    payload = {
        "status": "OK", "quran_reference": args.reference,
        "summary": summary,
        "text_included": bool(args.include_text),
    }
    if args.include_text:
        payload["warning"] = (
            "UNVERIFIED PRIVATE SOURCE EXCERPTS - DO NOT LOG OR PUBLISH")
        payload["candidates"] = candidates
        payload["relations"] = relations
        payload["passage_count"] = len(passages)
    else:
        payload["note"] = (
            "Lexical candidate counts only, not certified tafsir opinions")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
