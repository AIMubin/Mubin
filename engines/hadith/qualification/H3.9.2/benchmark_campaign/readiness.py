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
            "MUBIN_READINESS_CANARY factual evidence. "
            "The readiness classification is supported. "
            "The literal label supported is explicitly present. "
        )
    elif task_type == "multilabel":
        fact = (
            "MUBIN_READINESS_CANARY factual evidence. "
            "Both alpha and beta are explicitly present and supported. "
            "The literal labels alpha and beta both apply. "
        )
    else:
        raise ValueError("unsupported canary task type")
    prefix = f"source-{source_index:02d}. "
    repeated = (prefix + fact) * 12
    return repeated[:1700]


def _build_canary_fixture(base: Path, role: str, task_type: str) -> tuple[Path, Path, dict[str, Any]]:
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
            "source_blob_sha": hashlib.sha1(source_id.encode("utf-8")).hexdigest(),
            "char_start": 0,
            "char_end": len(text),
            "text": text,
        })
    _write_jsonl(index_dir / "segments.jsonl", segments)

    labels = (
        ["supported", "unsupported"]
        if task_type == "classification"
        else ["alpha", "beta"]
    )
    task: dict[str, Any] = {
        "task_id": f"readiness:{role}:{task_type}",
        "benchmark_id": "readiness-canary",
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
        if gold != {"label": "supported"}:
            return "canary_semantic_mismatch"
    else:
        if not isinstance(gold, dict):
            return "canary_semantic_mismatch"
        labels = gold.get("labels")
        if (
            not isinstance(labels, list)
            or len(labels) != len(set(labels))
            or set(labels) != {"alpha", "beta"}
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
        index_dir, task_path, _task = _build_canary_fixture(base, role, task_type)
        output_path = base / "output.jsonl"
        env = {
            key: value
            for key, value in os.environ.items()
            if key in {
                "PATH", "PYTHONPATH", "HOME", "LANG", "LC_ALL", "SSL_CERT_FILE",
                "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE",
            }
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
                diagnostic = _diagnostic_from_stderr(proc.stderr) or "canary_nonzero_exit"
            else:
                diagnostic = _validate_canary_output(role, task_type, output_path)
        except subprocess.TimeoutExpired:
            diagnostic = "canary_timeout"

    duration_ms = int((time.monotonic() - started) * 1000)
    passed = diagnostic is None and returncode == 0
    return {
        "role": role,
        "task_type": task_type,
        "passed": passed,
        "diagnostic": diagnostic,
        "duration_ms": duration_ms,
    }


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"required readiness environment variable is unset: {name}")
    return value


def run_readiness(
    root: Path,
    curator_auth_style: str,
    verifier_auth_style: str,
    curator_json_mode: str,
    verifier_json_mode: str,
    live_timeout: int,
) -> dict[str, Any]:
    offline = _offline_suite(root)
    report: dict[str, Any] = {
        "schema_version": 1,
        "campaign_id": "H3.9.2",
        "kind": "comprehensive_readiness_gate",
        "offline_protocol": offline,
        "live_canaries": [],
        "ready": False,
    }
    if not offline["passed"]:
        return report

    curator_endpoint = _required_env("MUBIN_READINESS_CURATOR_ENDPOINT")
    curator_model = _required_env("MUBIN_READINESS_CURATOR_MODEL_REF")
    curator_key = _required_env("MUBIN_READINESS_CURATOR_API_KEY")
    verifier_endpoint = _required_env("MUBIN_READINESS_VERIFIER_ENDPOINT")
    verifier_model = _required_env("MUBIN_READINESS_VERIFIER_MODEL_REF")
    verifier_key = _required_env("MUBIN_READINESS_VERIFIER_API_KEY")

    jobs = [
        (
            "curator", "classification", curator_endpoint, curator_model, curator_key,
            curator_auth_style, curator_json_mode,
        ),
        (
            "verifier", "multilabel", verifier_endpoint, verifier_model, verifier_key,
            verifier_auth_style, verifier_json_mode,
        ),
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                _run_live_canary,
                root, role, task_type, endpoint, model_ref, api_key,
                auth_style, json_mode, live_timeout,
            )
            for (
                role, task_type, endpoint, model_ref, api_key,
                auth_style, json_mode,
            ) in jobs
        ]
        live = [future.result() for future in futures]

    live.sort(key=lambda x: x["role"])
    report["live_canaries"] = live
    report["ready"] = all(item["passed"] for item in live)
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run the H3.9.2 offline + live endpoint readiness gate"
    )
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--out", type=Path, required=True)
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

    try:
        report = run_readiness(
            root,
            args.curator_auth_style,
            args.verifier_auth_style,
            args.curator_json_mode,
            args.verifier_json_mode,
            args.live_timeout,
        )
    except ValueError as exc:
        report = {
            "schema_version": 1,
            "campaign_id": "H3.9.2",
            "kind": "comprehensive_readiness_gate",
            "offline_protocol": {"passed": False},
            "live_canaries": [],
            "ready": False,
            "diagnostic": "readiness_configuration_invalid",
        }
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
        print(str(exc), file=sys.stderr)
        return 2

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
