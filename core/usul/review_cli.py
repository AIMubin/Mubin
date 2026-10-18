"""Offline U0.5 review-queue metadata CLI. No actual human review intake."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from .__main__ import _read
from .review_queue import assess_review_queue

def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description="Validate unsubmitted U0.5 review queue")
    for name in ("queue","observations","cards","docket"):
        parser.add_argument(name,type=Path)
    parser.add_argument("--json",action="store_true")
    args=parser.parse_args(argv)
    try:
        queue,_=_read(args.queue)
        observations,_=_read(args.observations)
        cards,_=_read(args.cards)
        docket,_=_read(args.docket)
    except (OSError,ValueError,TypeError,UnicodeError,RecursionError,OverflowError) as exc:
        result={"scope":"unsubmitted_scholarly_review_queue_only",
                "valid_metadata":False,"eligible_for_engine":False,
                "code":"INPUT_ERROR",
                "errors":["invalid JSON, UTF-8 or file ("+type(exc).__name__+")"]}
        if args.json:
            print(json.dumps(result,sort_keys=True,ensure_ascii=False))
        else:
            print(result["errors"][0],file=sys.stderr)
        return 2
    report=assess_review_queue(queue,observations,cards,docket)
    if args.json:
        print(json.dumps(report,sort_keys=True,ensure_ascii=False))
    else:
        print("U0.5 unsubmitted reviews: "+("VALID" if report["valid_metadata"] else "INVALID")
              +f"; open tasks={report['open_evidence_task_count']}; verified reviewers=0")
    return 0 if report["valid_metadata"] else 1

if __name__=="__main__":
    sys.exit(main())
