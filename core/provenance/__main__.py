"""Run P1 local provenance checks, without network access or source mutation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .validator import verify_bundle

MAX_JSON_BYTES = 5 * 1024 * 1024


def _load_json(path: str) -> dict:
    with open(path, "rb") as stream:
        raw = stream.read(MAX_JSON_BYTES + 1)
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError("JSON input exceeds 5 MiB limit")
    value = json.loads(raw.decode("utf-8", "strict"))
    if not isinstance(value, dict):
        raise ValueError("JSON input must be an object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m core.provenance",
        description="Verify local pinned UTF-8 source bytes and precise locators, not Islamic scholarship.",
    )
    parser.add_argument("bundle", help="P0 inference-bundle JSON")
    parser.add_argument("manifest", help="P1 source-snapshot-manifest JSON")
    parser.add_argument("corpus_root", help="Existing directory containing pinned local UTF-8 source files")
    parser.add_argument("--json", action="store_true", help="Print machine-readable receipts")
    args = parser.parse_args(argv)
    try:
        bundle = _load_json(args.bundle)
        manifest = _load_json(args.manifest)
        if not Path(args.corpus_root).is_dir():
            raise ValueError("corpus root does not exist or is not a directory")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError, RecursionError) as exc:
        print(f"INPUT_ERROR: {exc}", file=sys.stderr)
        return 2
    result = verify_bundle(bundle, manifest, args.corpus_root)
    if not result["valid"]:
        for item in result["errors"][:50]:
            print("INVALID: " + item, file=sys.stderr)
        if len(result["errors"]) > 50:
            print(f"INVALID: {len(result['errors']) - 50} further issue(s)", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        print(
            f"VALID: {len(result['receipts'])} local byte-exact receipt(s); "
            "origin, licensing and religious conclusions NOT independently certified"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
