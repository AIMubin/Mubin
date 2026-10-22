"""Offline U0.1 frozen fixture CLI. Never reads religious texts or connects out."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import sys

from .benchmark import run_frozen_suite

MAX_CLI_INPUT = 256 * 1024


def _no_duplicate_object_members(pairs: list[tuple[str, object]]) -> dict[str, object]:
    values: dict[str, object] = {}
    for key, value in pairs:
        if key in values:
            raise ValueError('duplicate JSON member')
        values[key] = value
    return values


def _no_nonjson_constants(value: str) -> None:
    raise ValueError('invalid non-JSON numeric constant')


def _read(path: Path) -> tuple[object, bytes]:
    # No blocking on attacker-supplied FIFO or device; do not follow symlinks.
    # The frozen fixture SHA-256 also detects in-place source modification.
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('input must be an ordinary, non-symlink file')
    if info.st_size > MAX_CLI_INPUT:
        raise ValueError('input too large')
    flags = os.O_RDONLY | getattr(os, 'O_NONBLOCK', 0)
    flags |= getattr(os, 'O_CLOEXEC', 0) | getattr(os, 'O_NOFOLLOW', 0)
    flags |= getattr(os, 'O_BINARY', 0)
    fd = os.open(path, flags)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('input descriptor not a regular file')
        with os.fdopen(fd, 'rb') as stream:
            fd = -1
            raw = stream.read(MAX_CLI_INPUT + 1)
    finally:
        if fd >= 0:
            os.close(fd)
    if len(raw) > MAX_CLI_INPUT:
        raise ValueError('input too large')
    result = json.loads(raw.decode('utf-8', 'strict'),
                        object_pairs_hook=_no_duplicate_object_members,
                        parse_constant=_no_nonjson_constants)
    # Reject surrogate escapes as well as bad raw UTF-8; do not silently
    # fingerprint ambiguous/noninteroperable Unicode values.
    json.dumps(result, ensure_ascii=False, allow_nan=False).encode('utf-8', 'strict')
    return result, raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Run frozen U0.1 synthetic AST evaluation suite')
    parser.add_argument('rulebook', type=Path)
    parser.add_argument('cases', type=Path)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    try:
        rulebook, raw_rulebook = _read(args.rulebook)
        suite, raw_suite = _read(args.cases)
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError) as err:
        result = {'passed':False,'code':'INPUT_ERROR',
                  'scope':'synthetic_benchmark_only',
                  'errors':[f'Invalid JSON/UTF-8 input ({type(err).__name__})']}
        if args.json:
            print(json.dumps(result,ensure_ascii=False,sort_keys=True))
        else:
            print(result['errors'][0],file=sys.stderr)
        return 2
    try:
        report = run_frozen_suite(rulebook,suite,raw_rulebook,raw_suite)
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        report = {'passed':False,'code':'INVALID_SUITE',
                  'scope':'synthetic_benchmark_only','failures':[]}
    if args.json:
        print(json.dumps(report,ensure_ascii=False,sort_keys=True))
    else:
        print('U0.1 synthetic rule AST: ' + ('PASS' if report['passed'] else 'FAIL'))
        print(f"positive {report.get('positive_passed',0)}/15; adversarial {report.get('adversarial_passed',0)}/25")
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
