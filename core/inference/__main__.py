"""P0 structural validator CLI. This command never certifies scholarly correctness."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .validator import validate_bundle

MAX_INPUT_BYTES = 5 * 1024 * 1024


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m core.inference",
        description="Validate P0 inference-bundle structure only; NOT a scholarly verdict.",
    )
    parser.add_argument("bundle", help="Path to UTF-8 JSON inference bundle")
    args = parser.parse_args(argv)
    path = Path(args.bundle)
    try:
        if path.stat().st_size > MAX_INPUT_BYTES:
            print("INPUT_ERROR: JSON bundle exceeds P0 CLI limit of 5 MiB", file=sys.stderr)
            return 2
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        print(f"INPUT_ERROR: {exc}", file=sys.stderr)
        return 2

    errors = validate_bundle(data)
    if errors:
        for item in errors[:50]:
            print("INVALID: " + item, file=sys.stderr)
        if len(errors) > 50:
            print(f"INVALID: {len(errors) - 50} more diagnostic(s) omitted", file=sys.stderr)
        return 1

    print("VALID: structural_only; external source authenticity and religious correctness NOT verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
