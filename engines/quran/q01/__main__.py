"""Offline Q0.1 CLI; no downloads, external APIs or corpus redistribution."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import stat
import sys
from .engine import SnapshotError,load_snapshot

def _read_regular(path:Path,limit:int)->bytes:
    # Do not dereference symlink leaf. Verify the opened descriptor itself.
    flags=os.O_RDONLY|getattr(os,'O_BINARY',0)|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0)
    descriptor=os.open(path,flags)
    try:
        meta=os.fstat(descriptor)
        if not stat.S_ISREG(meta.st_mode) or meta.st_size<=0 or meta.st_size>limit:
            raise OSError('non_regular_or_oversized_input')
        with os.fdopen(os.dup(descriptor),'rb') as stream:
            raw=stream.read(limit+1)
        if len(raw)>limit or len(raw)!=meta.st_size:
            raise OSError('short_or_oversized_input')
        return raw
    finally:
        os.close(descriptor)

def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description='Mubin Quran Q0.1: unverified-source offline verse lookup')
    p.add_argument('--manifest',required=True,type=Path)
    p.add_argument('--corpus',required=True,type=Path)
    p.add_argument('--json',action='store_true')
    actions=p.add_subparsers(dest='action',required=True)
    actions.add_parser('verify')
    get=actions.add_parser('get');get.add_argument('reference')
    find=actions.add_parser('find');find.add_argument('text');find.add_argument('--match',choices=['exact','arabic_marks_insensitive'],default='exact');find.add_argument('--limit',type=int,default=20)
    args=p.parse_args(argv)
    try:
        manifest=_read_regular(args.manifest,32*1024)
        corpus=_read_regular(args.corpus,8*1024*1024)
    except (OSError,UnicodeError,ValueError) as exc:
        payload={'valid_metadata':False,'source_authenticated':False,'error':'unsafe_or_unreadable_file','error_class':type(exc).__name__}
        print(json.dumps(payload,ensure_ascii=False,sort_keys=True) if args.json else payload['error'])
        return 2
    try:
        idx=load_snapshot(manifest,corpus)
        if args.action=='verify':payload=idx.report()
        elif args.action=='get':payload=idx.get(args.reference)
        else:payload={'results':idx.find(args.text,match=args.match,limit=args.limit),
                      'source_authenticated':False,'source_id':idx.manifest['source_id']}
    except (SnapshotError,TypeError,ValueError,UnicodeError,OverflowError,RecursionError) as exc:
        payload={'valid_metadata':False,'source_authenticated':False,'error':str(exc)[:100]}
        print(json.dumps(payload,ensure_ascii=False,sort_keys=True) if args.json else payload['error'])
        return 1
    print(json.dumps(payload,ensure_ascii=False,sort_keys=True) if args.json else payload)
    return 0

if __name__=='__main__':sys.exit(main())
