"""U0.4 offline source-display observation CLI, never a scholarly approval."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from .__main__ import _read
from .observations import assess_observations

def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description="Validate local research observations only")
    parser.add_argument("observations",type=Path)
    parser.add_argument("question_cards",type=Path)
    parser.add_argument("source_docket",type=Path)
    parser.add_argument("--json",action="store_true")
    args=parser.parse_args(argv)
    try:
        records,_=_read(args.observations)
        cards,_=_read(args.question_cards)
        docket,_=_read(args.source_docket)
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError, OverflowError) as exc:
        report={"valid_metadata":False,"code":"INPUT_ERROR",
                "scope":"unverified_site_display_observations_only",
                "eligible_for_engine":False,
                "errors":["invalid JSON or file input ("+type(exc).__name__+")"]}
        if args.json:
            print(json.dumps(report,sort_keys=True,ensure_ascii=False))
        else:
            print(report["errors"][0],file=sys.stderr)
        return 2
    report=assess_observations(records,cards,docket)
    if args.json:
        print(json.dumps(report,sort_keys=True,ensure_ascii=False))
    else:
        print("U0.4 site metadata: " + ("VALID" if report["valid_metadata"] else "INVALID") +
              f"; observations={report['observation_count']}; executable rules=0")
    return 0 if report["valid_metadata"] else 1

if __name__=="__main__":
    sys.exit(main())
