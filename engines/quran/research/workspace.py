"""I0.1b: local-only operator workspace over the qualified research vault.

One RTL metadata surface binding I0.1a qualified retrieval with R0.1d
qualification states. LOOPBACK-ONLY, metadata-only, no text endpoints:
the private verse/tafsir text is never served here, no key, path or vault
location appears in any response, and the public Q0.1c reader shares
nothing with this process. Every response re-verifies the R0.1a evidence
registry and the signed qualification ledger before answering.
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from html import escape as escape_html
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

from engines.quran.research.operator_view import (
    operator_lookup, OperatorViewError, _states as _qualified_states)
from engines.quran.research import qualification as qual
from engines.quran.research.private_adapters import (
    PrivateResearchAdapters, ResearchAdapterError)
from qa import private_evidence_v01 as evidence
from qa.corpus_snapshot_v01 import resolve_current_snapshot

VERSION = "quran-operator-workspace/i0.1b"
CONTRACT = "mubin-operator-workspace-v0.1"
_CSP = ("default-src 'none'; script-src 'none'; style-src 'self'; "
        "connect-src 'self'; img-src 'self'; base-uri 'none'; "
        "form-action 'none'; frame-ancestors 'none'")


class WorkspaceError(ValueError):
    """Stable refusal codes; never contain private text or paths."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _adapters_from(args) -> PrivateResearchAdapters:
    return PrivateResearchAdapters(
        vault=Path(args.vault), corpus_db=Path(args.corpus_db),
        sidecar_db=Path(args.sidecar_db), registry=Path(args.registry),
        anchor_dir=Path(args.anchor_dir), evidence_key=Path(args.evidence_key))


def build_workspace_server(*, vault: Path, corpus_db: Path, sidecar_db: Path,
                           registry: Path, anchor_dir: Path,
                           evidence_key: Path, qualification_ledger: Path,
                           qualification_anchor_dir: Path,
                           qualification_key: Path, port: int = 0):
    """LOOPBACK-ONLY metadata workspace; never serves private text."""
    # I0.1c: pin the immutable snapshot when available (performance path);
    # fall back to the mutable vault original when no snapshot exists yet.
    try:
        snapshot = resolve_current_snapshot(Path(vault))
        pinned_corpus_db = snapshot["corpus_db"]
        snapshot_revision = snapshot["revision_id"]
    except Exception:
        pinned_corpus_db = Path(corpus_db)
        snapshot_revision = ""
    adapters = PrivateResearchAdapters(
        vault=Path(vault), corpus_db=pinned_corpus_db, sidecar_db=Path(sidecar_db),
        registry=Path(registry), anchor_dir=Path(anchor_dir),
        evidence_key=Path(evidence_key))
    qual_args = dict(ledger=Path(qualification_ledger),
                     qualification_anchor_dir=Path(qualification_anchor_dir),
                     qualification_key=Path(qualification_key), vault=Path(vault),
                     snapshot_revision=snapshot_revision)

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"
        server_version = "MubinOperator/0.1"
        sys_version = ""
        def log_message(self, fmt, *args):
            pass  # never log request queries (may contain references)
        def _send(self, status, data, media):
            self.send_response(status)
            self.send_header("Content-Type", media)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Cross-Origin-Resource-Policy", "same-origin")
            self.send_header("Content-Security-Policy", _CSP)
            self.end_headers()
            self.wfile.write(data)
        def _json(self, status, obj):
            self._send(status, json.dumps(obj, ensure_ascii=False,
                          allow_nan=False, sort_keys=True,
                          separators=(",", ":")).encode("utf-8"),
                       "application/json; charset=utf-8")
        def _deny(self, status, reason):
            self._json(status, {"error": reason,
                                "source_authenticated": False,
                                "text_included": False})
        def do_GET(self):
            authority = {f"127.0.0.1:{self.server.server_port}",
                         f"localhost:{self.server.server_port}"}
            if self.headers.get("Host", "") not in authority:
                return self._deny(403, "invalid_host")
            origin = self.headers.get("Origin")
            if origin is not None and origin not in {f"http://{a}" for a in authority}:
                return self._deny(403, "cross_origin_rejected")
            if self.headers.get("Sec-Fetch-Site") not in (None, "none", "same-origin"):
                return self._deny(403, "cross_site_rejected")
            if len(self.path.encode("utf-8", "replace")) > 1024:
                return self._deny(414, "request_target_too_long")
            parts = urlsplit(self.path)
            if parts.scheme or parts.netloc or parts.fragment or \
                    parts.path not in ("/", "/api/states", "/api/lookup"):
                return self._deny(404, "route_not_found")
            if parts.path in ("/", "/api/states") and parts.query:
                return self._deny(400, "invalid_query")
            try:
                if parts.path == "/":
                    return self._send(200, _workspace_html(adapters, qual_args),
                                      "text/html; charset=utf-8")
                if parts.path == "/api/states":
                    return self._json(200, _states_payload(adapters, qual_args))
                params = parse_qs(parts.query, strict_parsing=True,
                                  keep_blank_values=True, max_num_fields=3)
                if set(params) != {"ref"} or len(params["ref"]) != 1:
                    return self._deny(400, "invalid_query")
                lookup_args = {k: v for k, v in qual_args.items()
                               if k != "snapshot_revision"}
                report = operator_lookup(adapters, params["ref"][0], **lookup_args)
                return self._json(200, report)
            except OperatorViewError as exc:
                return self._json(409, {"status": "REFUSED",
                                        "reason_code": exc.code,
                                        "text_included": False})
            except (qual.QualificationError, ResearchAdapterError) as exc:
                return self._json(409, {"status": "REFUSED",
                                        "reason_code": exc.code,
                                        "text_included": False})
            except WorkspaceError as exc:
                return self._json(409, {"status": "REFUSED",
                                        "reason_code": exc.code,
                                        "text_included": False})
            except (ValueError, KeyError, TypeError, UnicodeError, OSError):
                return self._json(409, {"status": "REFUSED",
                                        "reason_code": "workspace_internal_refusal",
                                        "text_included": False})

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def _per_source_states(adapters, qual_args) -> tuple[list[dict], str, str, int, str]:
    """Signed, evidence-bound status snapshot. Never promote stale decisions.

    Missing ledger = explicitly *not initialized* (pending defaults);
    an empty/unpaired, damaged or rolled-back initialized ledger is REFUSED.
    Source-level states exclude record-scoped quarantines, reported separately.
    """
    evidence_head = adapters.evidence_head()
    ledger = qual_args["ledger"]
    anchors = qual_args["qualification_anchor_dir"]
    key = qual_args["qualification_key"]
    vault = qual_args["vault"]
    ledger_state = "initialized"
    before = None
    entries = []
    try:
        before = qual.verify_ledger(ledger, anchors, key, vault=vault)
        entries, signed_head = qual._attested_entries(
            ledger, anchors, key, vault=vault, allow_initial=True)
        if (signed_head != before["head_entry_sha256"]
                or len(entries) != before["entries"]):
            raise WorkspaceError("qualification_head_changed_during_lookup")
    except qual.QualificationError as exc:
        if exc.code != "LEDGER_NOT_INITIALIZED" or before is not None:
            raise
        ledger_state = "not_initialized"

    rows = []
    for source_id in sorted(qual.SOURCE_IDS):
        source = [entry["payload"] for entry in entries
                  if entry["payload"]["source_id"] == source_id]
        full = [item for item in source
                if item["scope"] == {"full_source": True}]
        scholarly, rights, matched, stale = _qualified_states(
            full, evidence_head)
        rows.append({
            "source_id": source_id,
            "scholarly_decision_state": scholarly,
            "rights_decision_state": rights,
            "matching_evidence_decisions": matched,
            "historical_evidence_decisions_present": stale,
            "record_quarantines_present": any(
                item["decision"] == "RECORD_QUARANTINED" for item in source),
        })

    try:
        after = qual.verify_ledger(ledger, anchors, key, vault=vault)
    except qual.QualificationError as exc:
        if exc.code != "LEDGER_NOT_INITIALIZED" or before is not None:
            raise
        after = None
    if ((before is None) != (after is None)
            or (before is not None and (
                before["head_entry_sha256"] != after["head_entry_sha256"]
                or before["entries"] != after["entries"]))):
        raise WorkspaceError("qualification_head_changed_during_lookup")
    if adapters.evidence_head() != evidence_head:
        raise WorkspaceError("evidence_head_changed_during_lookup")
    head = before["head_entry_sha256"] if before is not None else "0" * 64
    count = before["entries"] if before is not None else 0
    return rows, ledger_state, head, count, evidence_head


def _states_payload(adapters, qual_args) -> dict:
    rows, ledger_state, head, count, evidence_head = _per_source_states(
        adapters, qual_args)
    return {"contract": CONTRACT, "engine": VERSION,
            "evidence_head_sha256": evidence_head,
            "qualification_head_sha256": head,
            "qualification_decisions": count,
            "ledger_state": ledger_state,
            "sources": rows,
            "source_authenticated": False, "scholarly_verified": False,
            "rights_verified": False, "edition_verified": False,
            "text_included": False, "publication_allowed": False,
            "juristic_inference_allowed": False,
            "public_fatwa_authorized": False}


def _workspace_html(adapters, qual_args) -> bytes:
    rows, ledger_state, _, _, head = _per_source_states(adapters, qual_args)
    rows_html = []
    for row in rows:
        rows_html.append(
            "<tr><td>" + escape_html(row["source_id"]) + "</td>"
            + "<td>" + escape_html(row["scholarly_decision_state"]) + "</td>"
            + "<td>" + escape_html(row["rights_decision_state"]) + "</td>"
            + "<td>" + ("نعم" if row["record_quarantines_present"] else "لا")
            + "</td></tr>")
    notice = ("السجل غير مهيأ بعد — قرارات التأهيل الحقيقية تنتظر مراجعين مستقلين."
              if ledger_state == "not_initialized" else "")
    html = (
        '<!doctype html><html dir="rtl" lang="ar"><head><meta charset="utf-8">'
        "<title>مُبين — مساحة المشغل البحثية (بيانات وصفية فقط)</title>"
        '</head><body dir="rtl" lang="ar">'
        "<h1>مساحة المشغل — عرض حالات التأهيل</h1>"
        "<p>بيانات وصفية فقط؛ لا نصوص؛ رأس الأدلة: "
        + escape_html(head[:16]) + "…</p>"
        "<table><thead><tr><th>المصدر</th><th>محور السلامة</th>"
        "<th>محور الحقوق</th><th>حجر سجلات</th></tr></thead><tbody>"
        + "".join(rows_html) +
        "</tbody></table>"
        + (f"<p>{notice}</p>" if notice else "")
        + "<p>لا تُمنح أي صلاحية نشر أو اعتماد علمي أو استنباط أو فتوى.</p>"
        "</body></html>")
    return html.encode("utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", required=True)
    parser.add_argument("--corpus-db", required=True)
    parser.add_argument("--sidecar-db", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--anchor-dir", required=True)
    parser.add_argument("--evidence-key", required=True)
    parser.add_argument("--qualification-ledger", required=True)
    parser.add_argument("--qualification-anchor-dir", required=True)
    parser.add_argument("--qualification-key", required=True)
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args(argv)
    server = build_workspace_server(
        vault=args.vault, corpus_db=args.corpus_db, sidecar_db=args.sidecar_db,
        registry=args.registry, anchor_dir=args.anchor_dir,
        evidence_key=args.evidence_key,
        qualification_ledger=args.qualification_ledger,
        qualification_anchor_dir=args.qualification_anchor_dir,
        qualification_key=args.qualification_key, port=args.port)
    host, port = server.server_address[:2]
    print(json.dumps({"status": "WORKSPACE_LISTENING",
                      "bind": f"127.0.0.1:{port}",
                      "metadata_only": True, "text_included": False},
                     ensure_ascii=False))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
