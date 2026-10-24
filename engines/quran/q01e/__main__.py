"""Private loopback reader for frozen Tanzil-domain bytes (not a certified Quran)."""
from __future__ import annotations
import argparse
import json
import sys

from .official import obtain_official_index, OfficialSourceError
from engines.quran.q01c.reader import build_http_server


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Mubin Q0.1e private Tanzil-domain reader, pinned bytes only")
    p.add_argument("--port", type=int, default=8765)
    args = p.parse_args(argv)
    try:
        index, raw = obtain_official_index()
        server = build_http_server(index, raw, port=args.port)
    except (OfficialSourceError, ValueError, TypeError, OSError, OverflowError) as exc:
        print("رفض تشغيل قارئ المصدر المحدد: خطأ في المصدر أو الاتصال أو إعداد المنفذ", file=sys.stderr)
        return 2
    print(json.dumps({
        "url": f"http://127.0.0.1:{server.server_port}/",
        "source_id": index.manifest["source_id"],
        "raw_sha256": index.raw_sha256,
        "source_authenticated": False,
        "rights_verified": False,
        "local_only": True,
        "raw_source_persisted": False,
    }, ensure_ascii=False), flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
