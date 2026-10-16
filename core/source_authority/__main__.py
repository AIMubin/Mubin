"""Offline Hadith source-pin CLI; no external authority or rights attestation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .hadith_bridge import MAX_REGISTRY_BYTES, verify_hadith_cache


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m core.source_authority",
        description="Compare local Hadith source-cache bytes with frozen registry Git pins only.",
    )
    parser.add_argument("registry", help="Frozen H3.9.2 source-registry.json")
    parser.add_argument("source_cache", help="Existing local source cache directory")
    parser.add_argument("--json", action="store_true", help="Print metadata-only JSON verification report")
    args = parser.parse_args(argv)
    try:
        with Path(args.registry).open("rb") as stream:
            raw = stream.read(MAX_REGISTRY_BYTES + 1)
        if len(raw) > MAX_REGISTRY_BYTES:
            raise ValueError("registry JSON exceeds 5 MiB")
        registry = json.loads(raw.decode("utf-8", "strict"))
        if not isinstance(registry, dict):
            raise ValueError("registry input must be an object")
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        print(f"INPUT_ERROR: {exc}", file=sys.stderr)
        return 2

    report = verify_hadith_cache(registry, args.source_cache)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    elif report["valid"]:
        print(
            f"VALID: {len(report['sources'])} registry pin match(es); "
            "edition authenticity, licensing and scholarly meaning NOT verified"
        )
    else:
        for problem in report["errors"][:50]:
            print("INVALID: " + problem, file=sys.stderr)
        if len(report["errors"]) > 50:
            print(f"INVALID: {len(report['errors']) - 50} further issue(s)", file=sys.stderr)
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
