"""Offline, read-only file comparison: no network fetching or scholarly authority."""
from __future__ import annotations
import argparse
import json
import sys
from engines.quran.q01b.tanzil import read_regular_file, RawSourceError, MAX_RAW_BYTES, MAX_MANIFEST_BYTES
from .compare import CandidateError, compare_raw

def main(argv=None):
    parser=argparse.ArgumentParser(description='Quran Q0.1d: compare exact local source bytes; no official authentication')
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--mirror',required=True)
    parser.add_argument('--candidate',required=True)
    parser.add_argument('--limit-refs',type=int,default=20)
    parser.add_argument('--json',action='store_true')
    args=parser.parse_args(argv)
    try:
        m=read_regular_file(args.manifest,MAX_MANIFEST_BYTES)
        a=read_regular_file(args.mirror,MAX_RAW_BYTES)
        b=read_regular_file(args.candidate,MAX_RAW_BYTES)
    except (RawSourceError,OSError,TypeError,ValueError) as exc:
        print(json.dumps({'code':'INPUT_ERROR','valid_metadata':False,'source_authenticated':False,
                          'official_candidate_attested':False,'errors':[str(exc)[:120]]},ensure_ascii=False,sort_keys=True))
        return 2
    try:
        result=compare_raw(m,a,b,limit_refs=args.limit_refs)
        print(json.dumps(result,ensure_ascii=False,sort_keys=True))
        return 0
    except (CandidateError,ValueError,TypeError,UnicodeError,RecursionError,OverflowError) as exc:
        print(json.dumps({'code':'INVALID_CANDIDATE','valid_metadata':False,'source_authenticated':False,
                          'official_candidate_attested':False,'errors':[str(exc)[:120]]},ensure_ascii=False,sort_keys=True))
        return 1

if __name__=='__main__':sys.exit(main())
