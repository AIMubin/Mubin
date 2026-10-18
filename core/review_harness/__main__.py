"""Read-only, network-free review harness for untrusted review packets."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import stat
import sys
from .validator import assess_packet, build_review_plan

MAX_BYTES = 128 * 1024

def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    d: dict[str, object] = {}
    for k, v in pairs:
        if k in d:
            raise ValueError("duplicate JSON object member")
        d[k] = v
    return d

def _reject_constant(_: str) -> None:
    raise ValueError("nonfinite number")

def read_packet(path: Path) -> object:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        s = os.fstat(fd)
        if not stat.S_ISREG(s.st_mode) or s.st_size > MAX_BYTES:
            raise ValueError("not regular file / oversize")
        raw = os.read(fd, MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("oversize file")
        return json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=_unique_pairs,
                          parse_constant=_reject_constant)
    finally:
        os.close(fd)

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mubin untrusted review-packet analyzer")
    parser.add_argument("packet", type=Path)
    parser.add_argument("--mode", choices=("assess", "plan"), default="assess")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        p = read_packet(args.packet)
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        result = {"valid_metadata": False, "disposition": "INPUT_ERROR",
                  "eligible_for_auto_merge": False, "errors": ["invalid file or JSON"]}
        if args.json:
            print(json.dumps(result, sort_keys=True))
        else:
            print("Invalid review input", file=sys.stderr)
        return 2
    report = build_review_plan(p) if args.mode == "plan" else assess_packet(p)
    if args.json:
        print(json.dumps(report, sort_keys=True, ensure_ascii=False, allow_nan=False))
    else:
        print("Mubin review harness: " + ("VALID" if report["valid_metadata"] else "INVALID"))
        print(report.get("disposition", "PLAN_ONLY"))
    return 0 if report["valid_metadata"] else 1

if __name__ == "__main__":
    sys.exit(main())
