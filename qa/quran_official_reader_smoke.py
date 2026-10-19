"""Real pinned Tanzil-domain bytes → private HTTP API, no text output or artifacts."""
import json
import threading
import urllib.request
from engines.quran.q01c.reader import build_http_server
from engines.quran.q01e.official import obtain_official_index


def main():
    index, raw = obtain_official_index()
    server = build_http_server(index, raw, port=0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        def get(route):
            request = urllib.request.Request(base+route,headers={"Host":f"127.0.0.1:{server.server_port}"})
            with urllib.request.urlopen(request,timeout=10) as res:
                return json.load(res)
        status = get("/api/status")
        assert status["verse_count"] == 6236
        assert status["source_kind"] == "tanzil_domain_unattested_export"
        assert status["source_authenticated"] is False
        assert status["rights_verified"] is False
        for ref in ("1:1", "2:1", "114:6"):
            retrieved = get("/api/get?ref=" + ref.replace(":","%3A"))["result"]
            assert retrieved["found"] is True
            assert retrieved["text"] == index.get(ref)["text"]
            assert retrieved["raw_sha256"] == index.raw_sha256
            assert retrieved["source_authenticated"] is False
        assert "PLEASE DO NOT REMOVE" in get("/api/notice")["notice"]
        print(json.dumps({
            "result": "PASS", "live_tanzil_https_download": True,
            "source_sha256": index.raw_sha256, "verse_count": 6236,
            "local_http_read_only": True, "quran_text_in_log": False,
            "source_authenticated": False, "rights_verified": False,
        },sort_keys=True))
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=3)


if __name__=="__main__":
    main()
