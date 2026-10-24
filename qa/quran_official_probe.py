"""Q0.1e-a: bounded HTTPS attempt for one exact Tanzil export preset.

Source bytes are ephemeral, never committed, printed or normalized. Transport
from an official-looking HTTPS host and content equivalence do NOT prove
independent publisher identity, edition approval, or use rights.
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from engines.quran.q01b.tanzil import MAX_RAW_BYTES, MAX_MANIFEST_BYTES, read_regular_file
from engines.quran.q01d.compare import compare_raw

OFFICIAL_URL = "https://tanzil.net/pub/download/index.php"
# Explicit release/preset hypothesis, NOT asserted equivalent to the mirror.
PRESET = {
    "quranType": "uthmani", "outType": "txt-2",
    "marks": "true", "sajdah": "true", "rub": "true",
    "tatweel": "true", "agree": "true",
}
_MAX_BODY = 4 * 1024 * 1024
_METHODS = ("GET", "POST")
_VALID_COMPARISONS = frozenset(("byte_identical", "verse_equal_bytes_different",
                                "verse_text_differs"))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Do not follow redirected Quran exports to an unrecognized host."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _fetch(method: str) -> bytes:
    if method not in _METHODS:
        raise ValueError("unknown_fetch_method")
    query = urllib.parse.urlencode(PRESET)
    url = OFFICIAL_URL + ("?" + query if method == "GET" else "")
    headers = {
        "User-Agent": "Mubin-Quran-Q01e-Research-Probe/1.0",
        "Accept": "text/plain,application/octet-stream;q=0.9,*/*;q=0.1",
        "Cache-Control": "no-cache",
    }
    data = query.encode("ascii") if method == "POST" else None
    if method == "POST":
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    opener = urllib.request.build_opener(NoRedirect)
    with opener.open(req, timeout=25) as resp:
        if resp.geturl() != url or resp.getcode() != 200:
            raise OSError("unexpected_transport_endpoint")
        content = resp.read(_MAX_BODY + 1)
    if not (0 < len(content) <= _MAX_BODY):
        raise OSError("unavailable_or_large_download")
    return content


def probe_source_bytes(blob: Any) -> bool:
    """Cheap fail-closed first gate; compare_raw does exhaustive verse parsing."""
    if type(blob) is not bytes or not (0 < len(blob) <= _MAX_BODY):
        return False
    if not blob.startswith(b"1|1|") or blob.startswith(b"\xef\xbb\xbf"):
        return False
    if b"\x00" in blob or b"\r" in blob or not blob.endswith(b"\n"):
        return False
    try:
        first_line = blob.split(b"\n", 1)[0].decode("utf-8", "strict")
        return (len(first_line) > 7 and
                any("\u0621" <= ch <= "\u064a" for ch in first_line[4:]))
    except UnicodeError:
        return False


def _failure() -> dict[str, Any]:
    return {
        "contract": "mubin-q01e-official-transport-attempt-v1",
        "preset": dict(PRESET),
        "outcome": "unavailable_or_invalid",
        "comparison": None,
        "retrieved_over_official_domain_https": False,
        "source_authenticated": False,
        "official_candidate_attested": False,
        "candidate_publisher_provenance_verified": False,
        "rights_verified": False,
        "eligible_for_religious_ruling": False,
        "candidate_raw_persisted_or_published": False,
    }


def run_probe(mirror_manifest: bytes, mirror: bytes, *,
              fetcher: Callable[[str], bytes] = _fetch) -> dict[str, Any]:
    """Always advisory even when bytes match and even with injected mocks."""
    report = _failure()
    for method in _METHODS:
        try:
            candidate = fetcher(method)
            if not probe_source_bytes(candidate):
                continue
            result = compare_raw(mirror_manifest, mirror, candidate)
            kind = result["comparison"]
            if kind not in _VALID_COMPARISONS or type(result["candidate_verse_count"]) is not int:
                continue
            if result["candidate_verse_count"] != 6236:
                continue
            digest = result["candidate_sha256"]
            diff_count = result["differing_verse_count"]
            refs = result["differing_refs"]
            if (type(digest) is not str or
                re.fullmatch(r"[a-f0-9]{64}", digest) is None or
                type(diff_count) is not int or not 0 <= diff_count <= 6236 or
                type(refs) is not list or len(refs) > 20 or len(refs) > diff_count or
                any(type(v) is not str or
                    re.fullmatch(r"[1-9][0-9]{0,2}:[1-9][0-9]{0,2}", v) is None
                    for v in refs)):
                continue
            # Only safe scalar fields/coordinates; never output Quran text.
            report.update({
                "outcome": "comparison_available_not_authenticated",
                "comparison": kind,
                "candidate_sha256": digest,
                "candidate_verse_count": 6236,
                "differing_verse_count": diff_count,
                "differing_refs": refs,
                "fetch_method": method,
            })
            # Transport label is not an identity certificate. It stays false
            # here since an injected fetcher may not be the official host.
            return report
        except (OSError, ValueError, TypeError, UnicodeError, KeyError,
                OverflowError, RecursionError, urllib.error.URLError):
            continue
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Tanzil-domain candidate probe (Q0.1e-a; no source authentication)")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--mirror", required=True)
    args = parser.parse_args(argv)
    try:
        m = read_regular_file(args.manifest, MAX_MANIFEST_BYTES)
        raw = read_regular_file(args.mirror, MAX_RAW_BYTES)
        report = run_probe(m, raw)
        # This CLI uses the fixed, real HTTP fetcher. TLS is transport
        # provenance only and is never a publisher signature.
        if report["outcome"] == "comparison_available_not_authenticated":
            report["retrieved_over_official_domain_https"] = True
        print(json.dumps(report, sort_keys=True, ensure_ascii=False))
        return 0  # advisory, no gate or false CI failure on network outages
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        print(json.dumps(_failure(), sort_keys=True, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
