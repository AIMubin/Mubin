from __future__ import annotations

import argparse
import compileall
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unittest
from typing import Any

from .execution import _SAFE_BASE_ENV

_DIAGNOSTIC_PREFIX = "MUBIN_DIAGNOSTIC:"
_DIAGNOSTIC_RE = re.compile(r"^MUBIN_DIAGNOSTIC:([a-z0-9_:-]{1,80})$")
_CANARY_SOURCE_COUNT = 12


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("canary output row must be an object")
            rows.append(value)
    return rows


def _offline_suite(root: Path) -> dict[str, Any]:
    compile_targets = [
        root / "benchmark_campaign",
        root / "adapters",
        root / "tests",
    ]
    compile_passed = all(
        compileall.compile_dir(str(path), quiet=1)
        for path in compile_targets
    )
    if not compile_passed:
        return {
            "compile": "fail",
            "tests": "not_run",
            "tests_run": 0,
            "failures": 0,
            "errors": 0,
            "skipped": 0,
            "passed": False,
        }

    suite = unittest.defaultTestLoader.discover(str(root / "tests"))
    result = unittest.TextTestRunner(stream=sys.stderr, verbosity=1).run(suite)
    passed = result.wasSuccessful()
    return {
        "compile": "pass",
        "tests": "pass" if passed else "fail",
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "passed": passed,
    }


def _canary_evidence_text(task_type: str, source_index: int) -> str:
    if task_type == "classification":
        fact = (
            "MUBIN_READINESS_CANARY synthetic source evidence. "
            "النص يصرح أن الراوي ألف سمع من الراوي باء سماعاً مباشراً. "
            "ويصف المصدر هذه العلاقة صراحة بالوسم heard_from. "
        )
    elif task_type == "multilabel":
        fact = (
            "MUBIN_READINESS_CANARY synthetic source evidence. "
            "النص يصرح أن الراوي ألف لم يلق الراوي باء وأن الإسناد غير متصل. "
            "ويصف المصدر الحالة صراحة بالوسمين non_encounter و continuity_negative. "
        )
    else:
        raise ValueError("unsupported canary task type")
    prefix = f"source-{source_index:02d}. "
    repeated = (prefix + fact) * 12
    return repeated[:1700]


def _benchmark_labels(root: Path, benchmark_id: str, task_type: str) -> list[str]:
    spec = json.loads((root / "config" / "benchmark-spec.json").read_text(encoding="utf-8"))
    for benchmark in spec.get("benchmarks", []):
        if benchmark.get("id") != benchmark_id:
            continue
        evaluation = benchmark.get("evaluation")
        if not isinstance(evaluation, dict) or evaluation.get("task_type") != task_type:
            raise ValueError("readiness benchmark task type differs from benchmark spec")
        labels = evaluation.get("labels")
        if (
            not isinstance(labels, list)
            or not labels
            or not all(isinstance(label, str) and label for label in labels)
        ):
            raise ValueError("readiness benchmark label contract is invalid")
        return list(labels)
    raise ValueError("readiness benchmark is missing from benchmark spec")


def _build_canary_fixture(
    root: Path, base: Path, role: str, task_type: str
) -> tuple[Path, Path, dict[str, Any]]:
    if role not in {"curator", "verifier"}:
        raise ValueError("unsupported canary role")
    if task_type not in {"classification", "multilabel"}:
        raise ValueError("unsupported canary task type")

    index_dir = base / "index"
    index_dir.mkdir(parents=True, exist_ok=True)
    segments: list[dict[str, Any]] = []
    source_ids: list[str] = []
    for i in range(1, _CANARY_SOURCE_COUNT + 1):
        source_id = f"readiness-source-{i:02d}"
        source_ids.append(source_id)
        text = _canary_evidence_text(task_type, i)
        segments.append({
            "segment_id": f"readiness-segment-{i:02d}",
            "source_id": source_id,
            "source_blob_sha": hashlib.sha256(source_id.encode("utf-8")).hexdigest()[:40],
            "char_start": 0,
            "char_end": len(text),
            "text": text,
        })
    _write_jsonl(index_dir / "segments.jsonl", segments)

    if task_type == "classification":
        benchmark_id = "transmission-language"
        labels = _benchmark_labels(root, benchmark_id, task_type)
        if "heard_from" not in labels:
            raise ValueError("classification readiness target label missing from benchmark spec")
    else:
        benchmark_id = "external-critical-commentary"
        labels = _benchmark_labels(root, benchmark_id, task_type)
        if not {"non_encounter", "continuity_negative"}.issubset(set(labels)):
            raise ValueError("multilabel readiness target labels missing from benchmark spec")
    task: dict[str, Any] = {
        "task_id": f"readiness:{role}:{task_type}",
        "benchmark_id": benchmark_id,
        "partition": "non_holdout",
        "visibility": "development_safe",
        "risk_tier": 1,
        "auto_promotion": True,
        "anchor_source_id": source_ids[0],
        "allowed_source_pool": source_ids,
        "forbidden_source_pool": [],
        "allowed_labels": labels,
        "task_type": task_type,
        "retrieval_terms": ["MUBIN_READINESS_CANARY", *labels],
        "anchor_segment": segments[0],
    }
    if role == "verifier":
        task["candidate_input"] = {
            "question": (
                "Classify the readiness canary using only the supplied evidence "
                "and the allowed label vocabulary."
            )
        }

    task_path = base / "task.jsonl"
    _write_jsonl(task_path, [task])
    return index_dir, task_path, task


def _diagnostic_from_stderr(stderr: str) -> str | None:
    diagnostic: str | None = None
    for line in stderr.splitlines():
        match = _DIAGNOSTIC_RE.fullmatch(line.strip())
        if match:
            diagnostic = match.group(1)
    return diagnostic


def _validate_canary_output(role: str, task_type: str, output_path: Path) -> str | None:
    try:
        rows = _read_jsonl(output_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return "canary_output_invalid"
    if len(rows) != 1:
        return "canary_output_invalid"

    row = rows[0]
    if row.get("task_id") != f"readiness:{role}:{task_type}":
        return "canary_output_invalid"
    if row.get("status") != "candidate":
        return "canary_no_candidate"

    if role == "curator":
        candidate = row.get("candidate")
        if not isinstance(candidate, dict):
            return "canary_output_invalid"
        payload = candidate.get("payload")
        provenance = candidate.get("answer_provenance")
        if not isinstance(payload, dict) or not isinstance(provenance, dict):
            return "canary_output_invalid"
        gold = payload.get("gold")
        supports = provenance.get("supports")
    else:
        answer = row.get("answer")
        if not isinstance(answer, dict):
            return "canary_output_invalid"
        gold = answer.get("gold")
        supports = answer.get("supports")

    if not isinstance(supports, list) or not supports:
        return "canary_support_missing"

    if task_type == "classification":
        if gold != {"label": "heard_from"}:
            return "canary_semantic_mismatch"
    else:
        if not isinstance(gold, dict):
            return "canary_semantic_mismatch"
        labels = gold.get("labels")
        if (
            not isinstance(labels, list)
            or len(labels) != len(set(labels))
            or set(labels) != {"non_encounter", "continuity_negative"}
        ):
            return "canary_semantic_mismatch"
    return None


def _adapter_command(
    root: Path,
    role: str,
    endpoint: str,
    auth_style: str,
    json_mode: str,
    task_path: Path,
    output_path: Path,
    index_dir: Path,
    live_timeout: int,
) -> list[str]:
    contract = root / "agents" / (
        "CURATOR_CONTRACT.md" if role == "curator" else "VERIFIER_CONTRACT.md"
    )
    return [
        sys.executable,
        str(root / "adapters" / "chat_completions.py"),
        "--input", str(task_path),
        "--output", str(output_path),
        "--index", str(index_dir),
        "--contract", str(contract),
        "--base-url", endpoint,
        "--auth-style", auth_style,
        "--json-mode", json_mode,
        "--stream",
        "--timeout", str(live_timeout),
        "--max-evidence-sources", "12",
        "--max-excerpt-chars", "1800",
    ]


def _retryable_readiness_diagnostic(diagnostic: str | None) -> bool:
    if not isinstance(diagnostic, str):
        return False
    return (
        diagnostic == "connection_failed"
        or diagnostic.startswith("contract_")
        or diagnostic.startswith("model_output_")
        or diagnostic in {"canary_no_candidate", "canary_semantic_mismatch"}
    )


def _run_live_canary(
    root: Path,
    role: str,
    task_type: str,
    endpoint: str,
    model_ref: str,
    api_key: str,
    auth_style: str,
    json_mode: str,
    live_timeout: int,
) -> dict[str, Any]:
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix=f"mubin-h392-readiness-{role}-") as td:
        base = Path(td)
        index_dir, task_path, _task = _build_canary_fixture(root, base, role, task_type)
        output_path = base / "output.jsonl"
        env = {
            key: value
            for key, value in os.environ.items()
            if key in _SAFE_BASE_ENV
        }
        env.update({
            "MUBIN_AGENT_ROLE": role,
            "MUBIN_MODEL_REF": model_ref,
            "MUBIN_MODEL_API_KEY": api_key,
        })
        command = _adapter_command(
            root, role, endpoint, auth_style, json_mode,
            task_path, output_path, index_dir, live_timeout,
        )
        diagnostic: str | None = None
        returncode: int | None = None
        attempts_used = 0
        attempt_diagnostics: list[str] = []
        for attempt in range(1, 3):
            attempts_used = attempt
            output_path.unlink(missing_ok=True)
            try:
                proc = subprocess.run(
                    command,
                    cwd=str(root),
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                    timeout=live_timeout + 30,
                )
                returncode = proc.returncode
                if proc.returncode != 0:
                    diagnostic = (
                        _diagnostic_from_stderr(proc.stderr)
                        or "canary_nonzero_exit"
                    )
                    attempt_diagnostics.append(diagnostic)
                    if _retryable_readiness_diagnostic(diagnostic) and attempt == 1:
                        continue
                    break

                diagnostic = _validate_canary_output(role, task_type, output_path)
                if diagnostic is not None:
                    attempt_diagnostics.append(diagnostic)
                    if _retryable_readiness_diagnostic(diagnostic) and attempt == 1:
                        continue
                break
            except subprocess.TimeoutExpired:
                diagnostic = "canary_timeout"
                attempt_diagnostics.append(diagnostic)
                break
            except Exception:
                diagnostic = "canary_internal_error"
                attempt_diagnostics.append(diagnostic)
                break

    duration_ms = int((time.monotonic() - started) * 1000)
    passed = diagnostic is None and returncode == 0
    return {
        "role": role,
        "task_type": task_type,
        "passed": passed,
        "diagnostic": diagnostic,
        "attempt_diagnostics": attempt_diagnostics,
        "attempts_used": attempts_used,
        "duration_ms": duration_ms,
    }


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"required readiness environment variable is unset: {name}")
    return value


def _offline_report(root: Path) -> dict[str, Any]:
    offline = _offline_suite(root)
    return {
        "schema_version": 1,
        "campaign_id": "H3.9.2",
        "kind": "offline_readiness_gate",
        "github_sha": os.environ.get("GITHUB_SHA"),
        "offline_protocol": offline,
        "passed": bool(offline["passed"]),
    }


def _load_bound_offline_report(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("offline readiness report must be an object")
    if value.get("kind") != "offline_readiness_gate" or value.get("passed") is not True:
        raise ValueError("offline readiness gate has not passed")
    current_sha = os.environ.get("GITHUB_SHA")
    recorded_sha = value.get("github_sha")
    if current_sha and recorded_sha != current_sha:
        raise ValueError("offline readiness report is not bound to the current GitHub SHA")
    return value


def run_live_readiness(
    root: Path,
    offline_report: dict[str, Any],
    curator_auth_style: str,
    verifier_auth_style: str,
    curator_json_mode: str,
    verifier_json_mode: str,
    live_timeout: int,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema_version": 1,
        "campaign_id": "H3.9.2",
        "kind": "comprehensive_readiness_gate",
        "github_sha": os.environ.get("GITHUB_SHA"),
        "offline_protocol": offline_report["offline_protocol"],
        "live_canaries": [],
        "ready": False,
    }

    curator_endpoint = _required_env("MUBIN_READINESS_CURATOR_ENDPOINT")
    curator_model = _required_env("MUBIN_READINESS_CURATOR_MODEL_REF")
    curator_key = _required_env("MUBIN_READINESS_CURATOR_API_KEY")
    verifier_endpoint = _required_env("MUBIN_READINESS_VERIFIER_ENDPOINT")
    verifier_model = _required_env("MUBIN_READINESS_VERIFIER_MODEL_REF")
    verifier_key = _required_env("MUBIN_READINESS_VERIFIER_API_KEY")

    role_jobs = [
        (
            "curator", curator_endpoint, curator_model, curator_key,
            curator_auth_style, curator_json_mode,
        ),
        (
            "verifier", verifier_endpoint, verifier_model, verifier_key,
            verifier_auth_style, verifier_json_mode,
        ),
    ]

    def run_role_matrix(job: tuple[str, str, str, str, str, str]) -> list[dict[str, Any]]:
        role, endpoint, model_ref, api_key, auth_style, json_mode = job
        return [
            _run_live_canary(
                root, role, task_type, endpoint, model_ref, api_key,
                auth_style, json_mode, live_timeout,
            )
            for task_type in ("classification", "multilabel")
        ]

    with ThreadPoolExecutor(max_workers=2) as pool:
        matrices = list(pool.map(run_role_matrix, role_jobs))
    live = [item for matrix in matrices for item in matrix]
    live.sort(key=lambda x: (x["role"], x["task_type"]))
    report["live_canaries"] = live
    report["ready"] = all(item["passed"] for item in live)
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run the H3.9.2 offline + live endpoint readiness gate"
    )
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--offline-only", action="store_true")
    p.add_argument("--offline-report", type=Path)
    p.add_argument("--curator-auth-style", choices=["bearer", "api-key"], default="bearer")
    p.add_argument("--verifier-auth-style", choices=["bearer", "api-key"], default="bearer")
    p.add_argument("--curator-json-mode", choices=["off", "json_object"], default="off")
    p.add_argument("--verifier-json-mode", choices=["off", "json_object"], default="off")
    p.add_argument("--live-timeout", type=int, default=300)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    out = args.out if args.out.is_absolute() else root / args.out
    if args.live_timeout < 1 or args.live_timeout > 600:
        raise SystemExit("--live-timeout must be in [1, 600]")

    if args.offline_only and args.offline_report is not None:
        raise SystemExit("--offline-only and --offline-report are mutually exclusive")

    try:
        if args.offline_only:
            report = _offline_report(root)
            success = bool(report["passed"])
        else:
            if args.offline_report is None:
                offline = _offline_report(root)
                if not offline["passed"]:
                    report = {
                        "schema_version": 1,
                        "campaign_id": "H3.9.2",
                        "kind": "comprehensive_readiness_gate",
                        "github_sha": os.environ.get("GITHUB_SHA"),
                        "offline_protocol": offline["offline_protocol"],
                        "live_canaries": [],
                        "ready": False,
                    }
                    success = False
                else:
                    report = run_live_readiness(
                        root, offline,
                        args.curator_auth_style,
                        args.verifier_auth_style,
                        args.curator_json_mode,
                        args.verifier_json_mode,
                        args.live_timeout,
                    )
                    success = bool(report["ready"])
            else:
                offline_path = (
                    args.offline_report
                    if args.offline_report.is_absolute()
                    else root / args.offline_report
                )
                offline = _load_bound_offline_report(offline_path)
                report = run_live_readiness(
                    root, offline,
                    args.curator_auth_style,
                    args.verifier_auth_style,
                    args.curator_json_mode,
                    args.verifier_json_mode,
                    args.live_timeout,
                )
                success = bool(report["ready"])
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        report = {
            "schema_version": 1,
            "campaign_id": "H3.9.2",
            "kind": "comprehensive_readiness_gate",
            "github_sha": os.environ.get("GITHUB_SHA"),
            "offline_protocol": {"passed": False},
            "live_canaries": [],
            "ready": False,
            "diagnostic": "readiness_configuration_invalid",
        }
        success = False

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if success else 2


if __name__ == "__main__":
    raise SystemExit(main())
