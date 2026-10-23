"""U0.1 Stage09 — private al-Waraqat typed reference proposal runner.

The output is a research-only metadata receipt. Private Stage08 graph, P0 and
proposal inputs are NEVER modified; source bytes are not published. The
report path may not alias any input or an unrelated existing file.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile

from corpus.internal_research_ingest import _guard_private_path
from engines.usul.typed_evidence_binding import bind_exact_observations

WARAQAT_STAGE08_GRAPH_SHA256 = "72ca6bd80c4e70378dd9d2f1cfc75841024b292d2335479d167add1a8ca6fdb2"
RUNNER = "waraqat-stage09-typed-reference/0.1.0"
REPORT_KIND = "STAGE09_PRIVATE_TYPED_REFERENCE_REPORT_V1"
MAX_INPUT_BYTES = 2_000_000


class PrivateStage09Refusal(ValueError):
    """Expose stable refusal codes only: never a private filename or excerpt."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _private(path):
    try:
        return _guard_private_path(Path(path))
    except (OSError, ValueError, RuntimeError, TypeError):
        raise PrivateStage09Refusal("PRIVATE_STAGE09_PATH_REFUSED") from None


def _read_json(path):
    size = path.stat().st_size
    if not (0 < size <= MAX_INPUT_BYTES):
        raise PrivateStage09Refusal("PRIVATE_STAGE09_INPUT_SIZE_REFUSED")
    raw = path.read_bytes()
    if len(raw) != size:
        raise PrivateStage09Refusal("PRIVATE_STAGE09_INPUT_CHANGED")
    return json.loads(raw.decode("utf-8"))


def _safe_report_path(report_path, protected_inputs):
    """Reject current-input aliases and unrelated existing report targets.

    Caller must be the single trusted writer. Repeated invocations may
    replace only an existing Stage09 report, never arbitrary operator data.
    """
    dest = _private(report_path)
    _private(dest.parent)
    # Input validity is checked separately by main(). Even if an input has
    # become a symlink, a broken file, or a path inside Git, the destination
    # must still receive a fresh REFUSED receipt when independently safe.
    # Resolve candidate identities here ONLY to prevent report aliasing; do
    # not treat a resolved input path as authorized for reading.
    inputs = [Path(os.path.abspath(os.fspath(item)))
              for item in protected_inputs]
    try:
        for original in inputs:
            if (dest == original or dest.resolve() == original.resolve() or
                    (dest.exists() and original.exists()
                     and os.path.samefile(dest, original))):
                raise PrivateStage09Refusal("STAGE09_REPORT_INPUT_ALIAS_REFUSED")
        if dest.exists():
            if not dest.is_file():
                raise PrivateStage09Refusal("STAGE09_REPORT_DESTINATION_REFUSED")
            previous = _read_json(dest)
            if (type(previous) is not dict or
                    previous.get("report_kind") != REPORT_KIND or
                    previous.get("runner") != RUNNER or
                    previous.get("source_text_included") is not False):
                raise PrivateStage09Refusal("STAGE09_REPORT_DESTINATION_REFUSED")
    except PrivateStage09Refusal:
        raise
    except (OSError, ValueError, RuntimeError, UnicodeError, TypeError):
        raise PrivateStage09Refusal("STAGE09_REPORT_DESTINATION_REFUSED") from None
    return dest


def _write_report(destination, protected_inputs, result):
    """Fsync then atomic replace; revalidate destination before replacement."""
    destination = _safe_report_path(destination, protected_inputs)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", delete=False,
            dir=str(destination.parent), prefix=".stage09-report-", suffix=".tmp"
        ) as handle:
            temporary = Path(handle.name)
            handle.write(json.dumps(result, ensure_ascii=False, sort_keys=True,
                                    indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        _safe_report_path(destination, protected_inputs)
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("stage08-graph", "p0-bundle", "proposals", "report"):
        p.add_argument("--" + key, type=Path, required=True)
    args = p.parse_args(argv)
    inputs = (args.stage08_graph, args.p0_bundle, args.proposals)
    report_path = None
    try:
        report_path = _safe_report_path(args.report, inputs)
        safe_inputs = [_private(item) for item in inputs]
        if not all(file.is_file() for file in safe_inputs):
            result, code = {"status": "PENDING_STAGE09_SOURCE_BINDING_INPUTS"}, 3
        else:
            graph, p0_bundle, proposals = (_read_json(file) for file in safe_inputs)
            result = bind_exact_observations(
                graph, WARAQAT_STAGE08_GRAPH_SHA256, p0_bundle, proposals)
            result["local_source_replay_executed_here"] = False
            code = 0
    except PrivateStage09Refusal as exc:
        result, code = {"status": "REFUSED", "reason_code": exc.code}, 1
    except (ValueError, OSError, RuntimeError, UnicodeError, KeyError, TypeError,
            RecursionError, OverflowError):
        result, code = {"status": "FAIL", "reason_code": "STAGE09_BINDING_FAILED"}, 1
    result.update({
        "report_kind": REPORT_KIND,
        "runner": RUNNER,
        "source_text_included": False,
        "scholarly_verified": False,
        "redistribution_approved": False,
        "juristic_inference_allowed": False,
        "public_fatwa_authorized": False,
    })
    if report_path is not None:
        try:
            _write_report(report_path, inputs, result)
        except PrivateStage09Refusal as exc:
            result, code = {"status": "REFUSED", "reason_code": exc.code}, 1
        except (OSError, RuntimeError, UnicodeError, ValueError, TypeError):
            result, code = {"status": "REFUSED",
                            "reason_code": "STAGE09_REPORT_WRITE_FAILED"}, 1
    print(json.dumps({"status": result["status"],
                      "reason_code": result.get("reason_code"),
                      "source_text_included": False}, ensure_ascii=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
