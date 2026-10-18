"""U0.2 offline candidate metadata CLI; never fetches or stores book contents."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .__main__ import _read
from .docket import assess_docket


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate non-executable Usul chapter metadata")
    parser.add_argument("docket", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        document, _ = _read(args.docket)
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError, OverflowError) as exc:
        report = {
            "valid_metadata": False,
            "code": "INPUT_ERROR",
            "scope": "source_candidate_metadata_only",
            "eligible_for_engine": False,
            "errors": [f"invalid JSON/UTF-8 or file input ({type(exc).__name__})"],
        }
        if args.json:
            print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        else:
            print(report["errors"][0], file=sys.stderr)
        return 2
    report = assess_docket(document)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        print(f"U0.2 metadata: {'VALID' if report['valid_metadata'] else 'INVALID'}; "
              f"queued={report['candidate_count']}; executable rules=0")
    return 0 if report["valid_metadata"] else 1


if __name__ == "__main__":
    sys.exit(main())
