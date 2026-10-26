"""Measure actual loopback HTTP lookup latency (NOT direct SQLite timing).

No private text, secrets, vault paths or response bodies are written. Server
startup and browser rendering are excluded. Designed for a local operator who
has started workspace.py --pinned-snapshot with real-vault evidence.
"""
from __future__ import annotations

import argparse
from http.client import HTTPConnection
import json
import math
import statistics
import time
from urllib.parse import quote, urlsplit


def percentile(values: list[float], pct: float) -> float:
    """Linear interpolation of ordered samples for p50/p95."""
    ordered = sorted(values)
    position = (len(ordered) - 1) * pct / 100
    lo, hi = math.floor(position), math.ceil(position)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", required=True,
                        help="http://127.0.0.1:PORT or http://localhost:PORT")
    parser.add_argument("--ref", default="2:1")
    parser.add_argument("--samples", type=int, default=60)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args(argv)
    target = urlsplit(args.origin)
    if (target.scheme != "http" or
            target.hostname not in ("127.0.0.1", "localhost") or
            not target.port or
            target.username or target.password or target.path or
            target.query or target.fragment or
            not 5 <= args.samples <= 500 or
            not 0 <= args.warmup <= 100 or
            not 0 < args.timeout <= 120):
        parser.error("local_origin_or_benchmark_parameters_invalid")

    samples: list[float] = []
    endpoint = "/api/lookup?ref=" + quote(args.ref, safe=":")
    # HTTP/1.0 workspace: one connection per end-to-end HTTP response.
    for i in range(args.warmup + args.samples):
        con = HTTPConnection("127.0.0.1", target.port, timeout=args.timeout)
        try:
            start = time.perf_counter_ns()
            con.request("GET", endpoint, headers={
                "Host": f"{target.hostname}:{target.port}"})
            response = con.getresponse()
            raw = response.read()
            duration_ms = (time.perf_counter_ns() - start) / 1_000_000
            document = json.loads(raw)
            if (response.status != 200 or
                    document.get("research_mode") != "metadata_only" or
                    document.get("text_included") is not False or
                    document.get("publication_allowed") is not False or
                    document.get("public_fatwa_authorized") is not False):
                raise ValueError("WORKSPACE_LOOKUP_NOT_VERIFIED")
            if i >= args.warmup:
                samples.append(duration_ms)
        finally:
            con.close()
    print(json.dumps({
        "status": "HTTP_LOOKUP_BENCHMARK_OK",
        "transport": "loopback_http_full_response_no_browser_rendering",
        "excludes": ["server_startup", "browser_rendering", "initial_full_digest_validation"],
        "ref": args.ref, "samples": len(samples), "warmup": args.warmup,
        "mean_ms": round(statistics.mean(samples), 3),
        "p50_ms": round(percentile(samples, 50), 3),
        "p95_ms": round(percentile(samples, 95), 3),
        "p99_ms": round(percentile(samples, 99), 3),
        "max_ms": round(max(samples), 3),
        "source_authenticated": False, "publication_allowed": False,
        "public_fatwa_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
