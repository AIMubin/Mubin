"""Start a PRIVATE local-only read-only Quran prototype from pre-pinned raw bytes."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

from engines.quran.q01b.tanzil import (
    MAX_RAW_BYTES, MAX_MANIFEST_BYTES, load_raw, read_regular_file, RawSourceError
)
from .reader import build_http_server

def main(argv=None)->int:
    p=argparse.ArgumentParser(
        description="Q0.1c loopback-only Quran text browser (candidate source, NOT authenticated)")
    p.add_argument("--manifest",required=True,help="Q0.1b pinned manifest on disk")
    p.add_argument("--source",required=True,help="already obtained original, unmodified raw text file")
    p.add_argument("--port",type=int,default=8765,help="localhost port, default 8765")
    p.add_argument("--tafsir-db",type=str,default=None,
        help="optional pinned Q0.3 tafsir database enabling /api/research")
    args=p.parse_args(argv)
    try:
        manifest=read_regular_file(args.manifest,MAX_MANIFEST_BYTES)
        raw=read_regular_file(args.source,MAX_RAW_BYTES)
        idx=load_raw(manifest,raw)
        tafsir_db=Path(args.tafsir_db) if args.tafsir_db else None
        if tafsir_db is not None and (tafsir_db.is_symlink() or not tafsir_db.is_file()):
            print("Reader startup rejected: tafsir_db_unavailable",file=sys.stderr)
            return 2
        server=build_http_server(idx,raw,port=args.port,tafsir_db_path=tafsir_db)
    except (RawSourceError,ValueError,TypeError,OSError,OverflowError) as exc:
        print("Reader startup rejected: "+str(exc)[:150],file=sys.stderr)
        return 2
    print(json.dumps({
        "url":f"http://127.0.0.1:{server.server_port}/",
        "source_id":idx.manifest["source_id"],
        "source_authenticated":False,
        "rights_verified":False,
        "local_only":True},ensure_ascii=False),flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0

if __name__=="__main__":
    raise SystemExit(main())
