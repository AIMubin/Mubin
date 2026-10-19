"""Q0.1c: read-only, LOOPBACK-ONLY Quran snapshot browser.

No downloader, no text conversion, no source-authentication or rights verdict.
Reads already pinned raw Q0.1b SourceIndex; HTTP does not expose source files.
"""
from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit, parse_qs

from engines.quran.q01b.tanzil import SourceIndex, RawSourceError, load_raw

_HERE=Path(__file__).resolve().parent
_FILES={"/":("reader.html","text/html; charset=utf-8"),
        "/reader.js":("reader.js","application/javascript; charset=utf-8"),
        "/reader.css":("reader.css","text/css; charset=utf-8")}
_CSP=("default-src 'none'; script-src 'self'; style-src 'self'; "
      "connect-src 'self'; img-src 'self'; base-uri 'none'; "
      "form-action 'none'; frame-ancestors 'none'")
_PERCENT_BAD=re.compile(r"%(?![0-9a-fA-F]{2})")

class LoopbackServer(ThreadingHTTPServer):
    daemon_threads=True
    allow_reuse_address=False
    def get_request(self):
        sock,addr=super().get_request()
        sock.settimeout(5)
        return sock,addr

def _notice(index:SourceIndex, raw:bytes)->str:
    if index.manifest["source_kind"]=="synthetic_fixture":
        return "بيانات اختبار اصطناعية، وليست نصًا قرآنيًا موثّقًا."
    text=raw.decode("utf-8","strict")
    anchor="# PLEASE DO NOT REMOVE OR CHANGE THIS COPYRIGHT BLOCK"
    start=text.find(anchor)
    if start<0:
        raise RawSourceError("missing_unmodified_source_copyright_notice")
    return text[start:]

def _decode_query(raw_query:str, allowed:frozenset[str],
                  required:frozenset[str])->dict[str,str]:
    if _PERCENT_BAD.search(raw_query):
        raise ValueError("bad_percent_encoding")
    try:
        if not raw_query:
            params={}
        else:
            params=parse_qs(raw_query,strict_parsing=True,keep_blank_values=True,
                            encoding="utf-8",errors="strict",max_num_fields=5)
        if set(params)-allowed or not required.issubset(params) or any(len(v)!=1 for v in params.values()):
            raise ValueError("invalid_or_duplicate_query")
        return {k:v[0] for k,v in params.items()}
    except (ValueError,UnicodeError,OverflowError) as exc:
        raise ValueError("invalid_query") from exc

def build_http_server(index:SourceIndex, raw:bytes,*,port:int=8765)->LoopbackServer:
    if type(index) is not SourceIndex or type(raw) is not bytes:
        raise RawSourceError("unverified_or_missing_source_index")
    if hashlib.sha256(raw).hexdigest()!=index.raw_sha256:
        raise RawSourceError("source_index_bytes_mismatch")
    # Re-derive the loaded records from pinned original bytes; an otherwise
    # well-shaped SourceIndex can be forged by its public constructor.
    # This is a startup-only cost, not a per-request parser/normalizer.
    if index.manifest.get("source_kind")=="tanzil_domain_unattested_export":
        # No caller-supplied manifest can authorize this source kind: recompute
        # both structure and exact pinned bytes in the dedicated source adapter.
        from engines.quran.q01e.official import load_official_candidate
        checked=load_official_candidate(raw)
    else:
        try:
            manifest_bytes=json.dumps(dict(index.manifest),ensure_ascii=True,
                sort_keys=True,separators=(",",":")).encode("utf-8","strict")
        except (TypeError,ValueError,UnicodeError) as exc:
            raise RawSourceError("untrusted_source_manifest") from exc
        checked=load_raw(manifest_bytes,raw)
    if checked.verses!=index.verses or dict(checked.manifest)!=dict(index.manifest):
        raise RawSourceError("source_index_not_derived_from_pinned_raw_bytes")
    if type(port) is not int or not 0<=port<=65535:
        raise RawSourceError("invalid_loopback_port")
    notice=_notice(index,raw)

    class Handler(BaseHTTPRequestHandler):
        protocol_version="HTTP/1.0"
        def log_message(self,fmt,*args):
            # Do not log arbitrary request queries, potentially sensitive.
            pass
        def _send(self,status:int,data:bytes,media:str):
            self.send_response(status)
            self.send_header("Content-Type",media)
            self.send_header("Content-Length",str(len(data)))
            self.send_header("Cache-Control","no-store")
            self.send_header("Referrer-Policy","no-referrer")
            self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("X-Frame-Options","DENY")
            self.send_header("Cross-Origin-Resource-Policy","same-origin")
            self.send_header("Content-Security-Policy",_CSP)
            self.end_headers()
            self.wfile.write(data)
        def _json(self,status:int,obj:dict[str,Any]):
            self._send(status,json.dumps(obj,ensure_ascii=False,allow_nan=False,
                            sort_keys=True,separators=(",",":")).encode("utf-8"),
                       "application/json; charset=utf-8")
        def _deny(self,status:int,reason:str):
            self._json(status,{"error":reason,"source_authenticated":False})
        def do_GET(self):
            authority={f"127.0.0.1:{self.server.server_port}",
                       f"localhost:{self.server.server_port}"}
            if self.headers.get("Host","") not in authority:
                return self._deny(403,"invalid_host")
            origin=self.headers.get("Origin")
            if origin is not None and origin not in {f"http://{a}" for a in authority}:
                return self._deny(403,"cross_origin_rejected")
            if self.headers.get("Sec-Fetch-Site") not in (None,"none","same-origin"):
                return self._deny(403,"cross_site_rejected")
            if len(self.path.encode("utf-8","replace"))>1024:
                return self._deny(414,"request_target_too_long")
            try:
                p=urlsplit(self.path)
                if p.scheme or p.netloc or p.fragment or p.path not in {*_FILES,
                    "/api/status","/api/get","/api/find","/api/notice",
                    "/api/tafsir-catalog"}:
                    return self._deny(404,"route_not_found")
                if p.path in _FILES:
                    _decode_query(p.query,frozenset(),frozenset())
                    file_name,mime=_FILES[p.path]
                    return self._send(200,(_HERE/file_name).read_bytes(),mime)
                if p.path=="/api/status":
                    _decode_query(p.query,frozenset(),frozenset())
                    rep=index.report()
                    return self._json(200,{**rep,
                        "display_provenance":"candidate_unverified_mirror" if
                        rep["source_kind"]!="synthetic_fixture" else "synthetic_only",
                        "publisher_source":"Tanzil Project (attribution required)",
                        "official_tanzil_bytes_independently_verified":False})
                if p.path=="/api/notice":
                    _decode_query(p.query,frozenset(),frozenset())
                    return self._json(200,{"notice":notice,
                        "source_kind":index.manifest["source_kind"],
                        "from_verified_publisher":False})
                if p.path=="/api/tafsir-catalog":
                    from engines.quran.tafsir.catalog import catalog_for_ref, CatalogError
                    if index.manifest["source_kind"] not in (
                            "unverified_github_mirror","tanzil_domain_unattested_export"):
                        return self._deny(403,"unqualified_source_for_tafsir_catalog")
                    try:
                        args=_decode_query(p.query,frozenset({"ref"}),frozenset({"ref"}))
                        if not index.get(args["ref"])["found"]:
                            return self._deny(404,"verse_not_in_loaded_source")
                        return self._json(200,catalog_for_ref(
                            args["ref"],index.manifest["source_kind"]))
                    except (CatalogError,ValueError,TypeError,UnicodeError):
                        return self._deny(400,"invalid_catalog_reference")
                if p.path=="/api/get":
                    params=_decode_query(p.query,frozenset({"ref"}),frozenset({"ref"}))
                    return self._json(200,{"result":index.get(params["ref"]),
                        "source_authenticated":False,"rights_verified":False})
                params=_decode_query(p.query,frozenset({"q","mode","limit"}),
                                     frozenset({"q"}))
                mode=params.get("mode","exact")
                if mode not in ("exact","folded"):
                    raise ValueError("unsupported_search_mode")
                lim=params.get("limit","20")
                if not re.fullmatch(r"[1-9][0-9]?",lim) or int(lim)>50:
                    raise ValueError("invalid_limit")
                found=index.find(params["q"],fold_marks=(mode=="folded"),limit=int(lim))
                return self._json(200,{"results":found,"result_count":len(found),
                    "source_authenticated":False,"rights_verified":False})
            except (ValueError,RawSourceError,UnicodeError,OverflowError) as exc:
                return self._deny(400,"invalid_query_or_verse_reference")
        def do_POST(self):self._deny(405,"read_only")
        def do_PUT(self):self._deny(405,"read_only")
        def do_PATCH(self):self._deny(405,"read_only")
        def do_DELETE(self):self._deny(405,"read_only")

    return LoopbackServer(("127.0.0.1",port),Handler)
