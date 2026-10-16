"""Offline Shamela bibliographic pilot validator CLI; no network or book text."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .shamela import MAX_CATALOG_BYTES, assess_shamela_catalog


def _reject_duplicate_members(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Fail on ambiguous object keys rather than silently using last-wins."""
    unique: dict[str, object] = {}
    for key, value in pairs:
        if key in unique:
            raise ValueError("duplicate JSON object member")
        unique[key] = value
    return unique


def _reject_json_constant(name: str) -> None:
    """NaN/Infinity are not valid interoperable JSON numbers."""
    raise ValueError("nonstandard JSON numeric constant")


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate metadata-only Shamela catalog (no download/rights certification)."
    )
    parser.add_argument("catalog", help="JSON bibliographic metadata catalog")
    parser.add_argument("--json", action="store_true", help="print structured validation result")
    args = parser.parse_args(argv)
    try:
        with Path(args.catalog).open("rb") as fp:
            data = fp.read(MAX_CATALOG_BYTES + 1)
        if len(data) > MAX_CATALOG_BYTES:
            raise ValueError("catalog exceeds JSON byte limit")
        source = json.loads(
            data.decode("utf-8", "strict"),
            object_pairs_hook=_reject_duplicate_members,
            parse_constant=_reject_json_constant,
        )
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        result = {"valid": False, "code": "INPUT_ERROR", "errors": [
            f"invalid or unreadable catalog input ({type(exc).__name__})"
        ]}
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(result["errors"][0], file=sys.stderr)
        return 2
    result = assess_shamela_catalog(source)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(
            f"Shamela S0.1: {'VALID' if result['valid'] else 'INVALID'} "
            f"(metadata only; {result['entry_count']} entries)"
        )
        for problem in result["errors"]:
            print(" - " + problem)
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(run())
