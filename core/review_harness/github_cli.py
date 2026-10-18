"""R2 read-only GitHub CLI; defaults to safe advisory mode even with pending CI."""
from __future__ import annotations
import argparse
import json
import os
import sys
from .github_live import fetch_pr_snapshot, assess_live_snapshot, RemoteEvidenceError


def main(argv: list[str] | None = None) -> int:
    p=argparse.ArgumentParser(description='Observe GitHub PR metadata read-only; NEVER auto-merge')
    p.add_argument('--pr',type=int,required=True)
    p.add_argument('--expected-head',default=None)
    p.add_argument('--require-p0',action='store_true')
    p.add_argument('--json',action='store_true')
    args=p.parse_args(argv)
    try:
        snapshot=fetch_pr_snapshot(args.pr,expected_head_sha=args.expected_head)
        required={'Mubin P0 inference foundation':'.github/workflows/mubin-inference-foundation.yml'} if args.require_p0 else {}
        report=assess_live_snapshot(snapshot,required_workflows=required)
    except RemoteEvidenceError as exc:
        report={'valid_metadata':False,'engineering_lane':'UNAVAILABLE',
                'eligible_for_auto_merge':False,'ci_head_verified':False,
                'error':str(exc)}
        print(json.dumps(report,sort_keys=True) if args.json else report['error'])
        return 2
    print(json.dumps(report,sort_keys=True,ensure_ascii=False) if args.json
          else f'R2 PR #{args.pr}: {report["engineering_lane"]} {report["inferred_tier"]}')
    return 0

if __name__=='__main__':sys.exit(main())
