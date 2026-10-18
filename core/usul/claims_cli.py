"""U0.3 offline research question CLI: success means metadata consistency only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .__main__ import _read
from .claims import assess_cards

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check research-only Usul questions")
    parser.add_argument("cards", type=Path)
    parser.add_argument("source_docket", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        cards, _ = _read(args.cards)
        docket, _ = _read(args.source_docket)
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError, OverflowError) as exc:
        result = {"valid_metadata": False, "code":"INPUT_ERROR",
                  "scope":"research_questions_only", "eligible_for_engine":False,
                  "errors": ["invalid input file or JSON (" + type(exc).__name__ + ")"]}
        if args.json:
            print(json.dumps(result, sort_keys=True, ensure_ascii=False))
        else:
            print(result["errors"][0], file=sys.stderr)
        return 2
    result = assess_cards(cards, docket)
    if args.json:
        print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    else:
        print("U0.3 researcher questions: " + ("VALID" if result["valid_metadata"] else "INVALID")
              + f"; queued={result['hypothesis_count']}; verified rules=0")
    return 0 if result["valid_metadata"] else 1

if __name__ == "__main__":
    sys.exit(main())
