"""No-download CLI for caller-supplied raw source bytes and pinned manifest."""
from __future__ import annotations
import argparse
import json
import sys
from .tanzil import read_regular_file, load_raw, RawSourceError, MAX_RAW_BYTES, MAX_MANIFEST_BYTES

def main(argv=None):
    p=argparse.ArgumentParser(description='Q0.1b offline source mirror verifier; not scripture authentication')
    p.add_argument('--manifest',required=True)
    p.add_argument('--source',required=True)
    p.add_argument('--json',action='store_true')
    sub=p.add_subparsers(dest='action',required=True)
    sub.add_parser('verify')
    sub.add_parser('get').add_argument('reference')
    find=sub.add_parser('find')
    find.add_argument('query')
    find.add_argument('--fold-marks',action='store_true')
    find.add_argument('--limit',type=int,default=20)
    args=p.parse_args(argv)
    try:
        mb=read_regular_file(args.manifest,MAX_MANIFEST_BYTES)
        raw=read_regular_file(args.source,MAX_RAW_BYTES)
    except (RawSourceError,ValueError,TypeError) as exc:
        report={'valid_metadata':False,'source_authenticated':False,'code':'INPUT_ERROR','errors':[str(exc)]}
        print(json.dumps(report,ensure_ascii=False,sort_keys=True))
        return 2
    try:
        idx=load_raw(mb,raw)
        if args.action=='verify':res=idx.report()
        elif args.action=='get':res=idx.get(args.reference)
        else:res={'results':idx.find(args.query,fold_marks=args.fold_marks,limit=args.limit)}
        res={**res,'source_authenticated':False,'rights_verified':False}
        print(json.dumps(res,ensure_ascii=False,sort_keys=True))
        return 0
    except (RawSourceError,ValueError,UnicodeError,TypeError,RecursionError,OverflowError) as exc:
        report={'valid_metadata':False,'source_authenticated':False,'code':'INVALID_SOURCE','errors':[str(exc)[:120]]}
        print(json.dumps(report,ensure_ascii=False,sort_keys=True))
        return 1

if __name__=='__main__':sys.exit(main())
