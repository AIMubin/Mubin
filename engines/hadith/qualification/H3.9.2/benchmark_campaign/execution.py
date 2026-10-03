from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .core import canonical_json_bytes, dump_jsonl, load_json, load_jsonl, sha256_bytes, sha256_file, write_json
from .factory import _task_rows, _validate_tasks_against_frozen_plan, enforce_partition_boundary


_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_SAFE_BASE_ENV = (
    "PATH", "LANG", "LC_ALL", "TMPDIR",
    "SSL_CERT_FILE", "SSL_CERT_DIR", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY",
)
_SECRET_FLAG_RE = re.compile(
    r"^(?:--)?(?:api[-_]?key|access[-_]?token|auth[-_]?token|token|password|secret|authorization)(?:=|$)",
    re.IGNORECASE,
)
_RESERVED_ADAPTER_FIELDS = {
    "task_fingerprint", "verifier_task_fingerprint", "model_family", "model_ref",
    "execution_binding",
}
_ADAPTER_DIAGNOSTIC_RE = re.compile(rb"(?:^|\n)MUBIN_DIAGNOSTIC:([a-z0-9_:-]{1,80})(?:\r?\n|$)")
_MAX_DIAGNOSTIC_SCAN_BYTES = 8192


def _extract_adapter_diagnostic(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    size = path.stat().st_size
    with path.open("rb") as fh:
        if size > _MAX_DIAGNOSTIC_SCAN_BYTES:
            fh.seek(size - _MAX_DIAGNOSTIC_SCAN_BYTES)
        data = fh.read(_MAX_DIAGNOSTIC_SCAN_BYTES)
    matches = list(_ADAPTER_DIAGNOSTIC_RE.finditer(data))
    if not matches:
        return None
    return matches[-1].group(1).decode("ascii")


def _normalized_family(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _collectable_task_failure(error_code: str | None) -> bool:
    if not isinstance(error_code, str):
        return False
    return (
        error_code.startswith("adapter:contract_")
        or error_code.startswith("adapter:model_output_")
    )


def _require_nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def load_agent_execution_config(path: Path, expected_role: str | None = None) -> dict[str, Any]:
    cfg = load_json(path)
    if not isinstance(cfg, dict):
        raise ValueError("agent execution config must be an object")
    allowed_top = {
        "schema_version", "role", "model_family", "model_ref", "adapter",
        "batch_size", "timeout_seconds", "max_attempts", "task_failure_policy",
    }
    unknown = set(cfg) - allowed_top
    if unknown:
        raise ValueError(f"unknown agent execution config fields: {sorted(unknown)}")
    if cfg.get("schema_version") != 1:
        raise ValueError("agent execution config schema_version must be 1")
    role = _require_nonempty_string(cfg.get("role"), "role")
    if role not in {"curator", "verifier"}:
        raise ValueError("role must be curator or verifier")
    if expected_role is not None and role != expected_role:
        raise ValueError(f"execution config role {role} does not match requested role {expected_role}")
    model_family = _require_nonempty_string(cfg.get("model_family"), "model_family")
    model_ref = _require_nonempty_string(cfg.get("model_ref"), "model_ref")

    adapter = cfg.get("adapter")
    if not isinstance(adapter, dict):
        raise ValueError("adapter must be an object")
    allowed_adapter = {"command", "env_allowlist", "artifacts"}
    unknown_adapter = set(adapter) - allowed_adapter
    if unknown_adapter:
        raise ValueError(f"unknown adapter config fields: {sorted(unknown_adapter)}")
    command = adapter.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(x, str) and x for x in command):
        raise ValueError("adapter.command must be a non-empty list of strings")
    joined = "\n".join(command)
    if "{input}" not in joined or "{output}" not in joined:
        raise ValueError("adapter.command must include {input} and {output} placeholders")
    for token in command:
        stripped = token.strip()
        if _SECRET_FLAG_RE.match(stripped) or stripped.casefold().startswith("bearer "):
            raise ValueError(
                "adapter.command must not carry secret-bearing arguments; use adapter.env_allowlist"
            )
    env_allowlist = adapter.get("env_allowlist", [])
    if not isinstance(env_allowlist, list) or not all(
        isinstance(x, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", x)
        for x in env_allowlist
    ):
        raise ValueError("adapter.env_allowlist must contain environment variable names only")
    if len(env_allowlist) != len(set(env_allowlist)):
        raise ValueError("adapter.env_allowlist contains duplicates")
    artifacts = adapter.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts or not all(
        isinstance(x, str) and x.strip() for x in artifacts
    ):
        raise ValueError("adapter.artifacts must be a non-empty list of file paths")
    if len(artifacts) != len(set(artifacts)):
        raise ValueError("adapter.artifacts contains duplicates")
    for raw in artifacts:
        p = Path(raw)
        if p.is_absolute() or ".." in p.parts:
            raise ValueError("adapter.artifacts must be campaign-root-relative paths without parent traversal")

    batch_size = cfg.get("batch_size", 8)
    timeout_seconds = cfg.get("timeout_seconds", 900)
    max_attempts = cfg.get("max_attempts", 2)
    task_failure_policy = cfg.get("task_failure_policy", "fail_fast")
    if not isinstance(batch_size, int) or not 1 <= batch_size <= 128:
        raise ValueError("batch_size must be an integer in [1, 128]")
    if not isinstance(timeout_seconds, int) or not 1 <= timeout_seconds <= 7200:
        raise ValueError("timeout_seconds must be an integer in [1, 7200]")
    if not isinstance(max_attempts, int) or not 1 <= max_attempts <= 3:
        raise ValueError("max_attempts must be an integer in [1, 3]")
    if task_failure_policy not in {"fail_fast", "record_rejection"}:
        raise ValueError("task_failure_policy must be fail_fast or record_rejection")
    if task_failure_policy == "record_rejection" and batch_size != 1:
        raise ValueError("record_rejection requires batch_size=1 so failures are task-local")

    return {
        "schema_version": 1,
        "role": role,
        "model_family": model_family,
        "model_ref": model_ref,
        "adapter": {
            "command": command,
            "env_allowlist": env_allowlist,
            "artifacts": artifacts,
        },
        "batch_size": batch_size,
        "timeout_seconds": timeout_seconds,
        "max_attempts": max_attempts,
        "task_failure_policy": task_failure_policy,
    }


def _adapter_artifact_bindings(root: Path, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    bindings: list[dict[str, Any]] = []
    root_resolved = root.resolve()
    for raw in cfg["adapter"]["artifacts"]:
        p = Path(raw)
        if p.is_absolute() or ".." in p.parts:
            raise ValueError(f"adapter artifact path must stay inside campaign root: {raw}")
        resolved = (root_resolved / p).resolve()
        try:
            resolved.relative_to(root_resolved)
        except ValueError as exc:
            raise ValueError(f"adapter artifact resolves outside campaign root: {raw}") from exc
        if not resolved.exists() or not resolved.is_file():
            raise ValueError(f"adapter artifact does not exist or is not a file: {raw}")
        bindings.append({
            "path": p.as_posix(),
            "sha256": sha256_file(resolved),
            "size_bytes": resolved.stat().st_size,
        })
    return bindings


def _config_binding(root: Path, cfg: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": cfg["schema_version"],
        "role": cfg["role"],
        "model_family": cfg["model_family"],
        "model_ref": cfg["model_ref"],
        "adapter_command_sha256": sha256_bytes(canonical_json_bytes(cfg["adapter"]["command"])),
        "adapter_artifacts": _adapter_artifact_bindings(root, cfg),
        "env_names": sorted(cfg["adapter"]["env_allowlist"]),
        "batch_size": cfg["batch_size"],
        "timeout_seconds": cfg["timeout_seconds"],
        "max_attempts": cfg["max_attempts"],
        "task_failure_policy": cfg["task_failure_policy"],
    }


def _verifier_task_fingerprint(row: dict[str, Any]) -> str:
    unsigned = dict(row)
    unsigned.pop("verifier_task_fingerprint", None)
    return sha256_bytes(canonical_json_bytes(unsigned))


def _load_execution_tasks(root: Path, path: Path, role: str) -> list[dict[str, Any]]:
    if role == "curator":
        rows = _task_rows(path)
        _validate_tasks_against_frozen_plan(root, rows)
        return rows

    rows = load_jsonl(path)
    ids = [str(r.get("task_id", "")) for r in rows]
    if any(not x for x in ids):
        raise ValueError("every verifier task requires a non-empty task_id")
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate verifier task IDs")
    for row in rows:
        original = row.get("task_fingerprint")
        if not isinstance(original, str) or _SHA256_RE.fullmatch(original) is None:
            raise ValueError(f"verifier task requires original task_fingerprint: {row.get('task_id')}")
        stored = row.get("verifier_task_fingerprint")
        expected = _verifier_task_fingerprint(row)
        if stored != expected:
            raise ValueError(f"verifier task fingerprint mismatch: {row.get('task_id')}")
    return rows


def _task_partition(rows: list[dict[str, Any]]) -> str:
    partitions = {str(r.get("partition", "")) for r in rows}
    if not rows:
        raise ValueError("agent execution requires at least one task")
    if len(partitions) != 1 or next(iter(partitions)) not in {"non_holdout", "holdout"}:
        raise ValueError("agent execution task file must contain one valid partition")
    return next(iter(partitions))


def _validate_index_binding(tasks: list[dict[str, Any]], index_dir: Path) -> dict[str, Any]:
    manifest_path = index_dir / "INDEX_MANIFEST.json"
    segments_path = index_dir / "segments.jsonl"
    if not manifest_path.exists() or not segments_path.exists():
        raise ValueError("source index requires INDEX_MANIFEST.json and segments.jsonl")
    manifest = load_json(manifest_path)
    manifest_sha = sha256_file(manifest_path)
    segments_sha = sha256_file(segments_path)
    if manifest.get("segments_sha256") != segments_sha:
        raise ValueError("source index segments hash does not match INDEX_MANIFEST.json")
    indexed_sources = set((manifest.get("per_source") or {}).keys())
    for task in tasks:
        scope = task.get("retrieval_scope")
        if not isinstance(scope, dict):
            raise ValueError(f"task retrieval_scope missing: {task.get('task_id')}")
        if scope.get("index_manifest_sha256") != manifest_sha:
            raise ValueError(f"task index manifest binding mismatch: {task.get('task_id')}")
        if scope.get("segments_sha256") != segments_sha:
            raise ValueError(f"task source-index segment binding mismatch: {task.get('task_id')}")
        source_ids = scope.get("source_ids")
        if not isinstance(source_ids, list) or set(source_ids) - indexed_sources:
            raise ValueError(f"task retrieval scope references unindexed source: {task.get('task_id')}")
        if task.get("allowed_source_pool") != source_ids:
            raise ValueError(f"task retrieval scope differs from allowed_source_pool: {task.get('task_id')}")
    return {
        "manifest_sha256": manifest_sha,
        "segments_sha256": segments_sha,
        "source_count": len(indexed_sources),
        "segment_count": int(manifest.get("segment_count", 0)),
    }


def _contract_path(root: Path, role: str) -> Path:
    name = "CURATOR_CONTRACT.md" if role == "curator" else "VERIFIER_CONTRACT.md"
    path = root / "agents" / name
    if not path.exists():
        raise ValueError(f"agent contract missing: {path}")
    return path


def _render_command(command: list[str], mapping: dict[str, str]) -> list[str]:
    rendered: list[str] = []
    for token in command:
        value = token
        for key, replacement in mapping.items():
            value = value.replace("{" + key + "}", replacement)
        rendered.append(value)
    return rendered


def _adapter_env(cfg: dict[str, Any], role: str, index_dir: Path, contract_path: Path,
                 input_path: Path, output_path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for name in _SAFE_BASE_ENV:
        if name in os.environ:
            env[name] = os.environ[name]
    for name in cfg["adapter"]["env_allowlist"]:
        if name not in os.environ:
            raise ValueError(f"allowlisted adapter environment variable is not set: {name}")
        env[name] = os.environ[name]
    env.update({
        "MUBIN_AGENT_PROTOCOL_VERSION": "1",
        "MUBIN_AGENT_ROLE": role,
        "MUBIN_MODEL_FAMILY": cfg["model_family"],
        "MUBIN_MODEL_REF": cfg["model_ref"],
        "MUBIN_SOURCE_INDEX_DIR": str(index_dir),
        "MUBIN_AGENT_CONTRACT": str(contract_path),
        "MUBIN_AGENT_INPUT": str(input_path),
        "MUBIN_AGENT_OUTPUT": str(output_path),
    })
    return env


def _validate_raw_adapter_rows(rows: list[dict[str, Any]], batch: list[dict[str, Any]],
                               role: str) -> list[dict[str, Any]]:
    expected = {str(t["task_id"]): t for t in batch}
    if len(rows) != len(batch):
        raise ValueError("adapter must return exactly one response per batch task")
    seen: set[str] = set()
    by_id: dict[str, dict[str, Any]] = {}
    for raw in rows:
        tid = str(raw.get("task_id", ""))
        if tid not in expected:
            raise ValueError(f"adapter returned unknown task_id: {tid}")
        if tid in seen:
            raise ValueError(f"adapter returned duplicate task_id: {tid}")
        seen.add(tid)
        reserved = _RESERVED_ADAPTER_FIELDS & set(raw)
        if reserved:
            raise ValueError(f"adapter attempted to set executor-reserved fields: {sorted(reserved)}")
        status = raw.get("status")
        if status not in {"candidate", "no_candidate"}:
            raise ValueError(f"adapter response status invalid: {tid}")
        if status == "no_candidate":
            if not isinstance(raw.get("reason"), str) or not raw["reason"].strip():
                raise ValueError(f"no_candidate response requires reason: {tid}")
        elif role == "curator":
            if not isinstance(raw.get("candidate"), dict):
                raise ValueError(f"curator candidate response missing candidate object: {tid}")
            if "answer" in raw:
                raise ValueError(f"curator adapter must not return verifier answer: {tid}")
        else:
            if not isinstance(raw.get("answer"), dict):
                raise ValueError(f"verifier candidate response missing answer object: {tid}")
            if "candidate" in raw:
                raise ValueError(f"verifier adapter must not return curator candidate: {tid}")
        by_id[tid] = raw
    return [by_id[str(task["task_id"])] for task in batch]


def _stamp_rows(raw_rows: list[dict[str, Any]], batch: list[dict[str, Any]],
                cfg: dict[str, Any], config_sha256: str, batch_id: str,
                adapter_command_sha256: str,
                adapter_artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tasks = {str(t["task_id"]): t for t in batch}
    stamped: list[dict[str, Any]] = []
    for raw in raw_rows:
        tid = str(raw["task_id"])
        task = tasks[tid]
        row = dict(raw)
        row["task_fingerprint"] = task["task_fingerprint"]
        row["model_family"] = cfg["model_family"]
        row["model_ref"] = cfg["model_ref"]
        row["execution_binding"] = {
            "protocol_version": 1,
            "config_sha256": config_sha256,
            "batch_id": batch_id,
            "raw_response_sha256": sha256_bytes(canonical_json_bytes(raw)),
            "adapter_command_sha256": adapter_command_sha256,
            "adapter_artifacts": adapter_artifacts,
        }
        stamped.append(row)
    return stamped


def _write_jsonl_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    dump_jsonl(tmp, rows)
    tmp.replace(path)


def _validate_existing_responses(rows: list[dict[str, Any]], tasks: dict[str, dict[str, Any]],
                                 cfg: dict[str, Any], config_sha256: str,
                                 adapter_command_sha256: str,
                                 adapter_artifacts: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for row in rows:
        tid = str(row.get("task_id", ""))
        if tid not in tasks:
            raise ValueError(f"existing response references unknown task: {tid}")
        if tid in seen:
            raise ValueError(f"existing response duplicates task: {tid}")
        seen.add(tid)
        if row.get("task_fingerprint") != tasks[tid].get("task_fingerprint"):
            raise ValueError(f"existing response task fingerprint mismatch: {tid}")
        if row.get("model_family") != cfg["model_family"] or row.get("model_ref") != cfg["model_ref"]:
            raise ValueError(f"existing response model identity differs from execution config: {tid}")
        binding = row.get("execution_binding")
        if not isinstance(binding, dict) or binding.get("config_sha256") != config_sha256:
            raise ValueError(f"existing response execution binding mismatch: {tid}")
        if binding.get("protocol_version") != 1 or not isinstance(binding.get("batch_id"), str):
            raise ValueError(f"existing response execution metadata invalid: {tid}")
        if binding.get("adapter_command_sha256") != adapter_command_sha256:
            raise ValueError(f"existing response adapter command binding mismatch: {tid}")
        artifacts = binding.get("adapter_artifacts")
        if canonical_json_bytes(artifacts) != canonical_json_bytes(adapter_artifacts):
            raise ValueError(f"existing response adapter artifact binding mismatch: {tid}")
        raw = dict(row)
        raw.pop("task_fingerprint", None)
        raw.pop("model_family", None)
        raw.pop("model_ref", None)
        raw.pop("execution_binding", None)
        expected_raw_sha = sha256_bytes(canonical_json_bytes(raw))
        if binding.get("raw_response_sha256") != expected_raw_sha:
            raise ValueError(f"existing response raw payload hash mismatch: {tid}")


def _manifest_identity(root: Path, role: str, partition: str, cfg: dict[str, Any],
                       tasks_path: Path, index: dict[str, Any], contract_path: Path) -> dict[str, Any]:
    binding = _config_binding(root, cfg)
    return {
        "protocol_version": 1,
        "role": role,
        "partition": partition,
        "model_family": cfg["model_family"],
        "model_ref": cfg["model_ref"],
        "config_sha256": sha256_bytes(canonical_json_bytes(binding)),
        "adapter_command_sha256": binding["adapter_command_sha256"],
        "adapter_artifacts": binding["adapter_artifacts"],
        "adapter_env_names": binding["env_names"],
        "tasks_sha256": sha256_file(tasks_path),
        "index_manifest_sha256": index["manifest_sha256"],
        "index_segments_sha256": index["segments_sha256"],
        "contract_sha256": sha256_file(contract_path),
    }


def run_agent_execution(root: Path, role: str, tasks_path: Path, index_dir: Path,
                        config_path: Path, output_path: Path, manifest_path: Path,
                        partition: str = "non_holdout", custodian_mode: bool = False,
                        resume: bool = False,
                        independent_from_manifest: Path | None = None) -> dict[str, Any]:
    if role not in {"curator", "verifier"}:
        raise ValueError("role must be curator or verifier")
    cfg = load_agent_execution_config(config_path, role)
    tasks = _load_execution_tasks(root, tasks_path, role)
    actual_partition = _task_partition(tasks)
    if actual_partition != partition:
        raise ValueError(f"task partition {actual_partition} does not match requested {partition}")
    if partition == "holdout" and cfg["task_failure_policy"] != "fail_fast":
        raise ValueError("holdout execution requires task_failure_policy=fail_fast")
    if partition == "holdout":
        for path in (tasks_path, index_dir, output_path, manifest_path):
            enforce_partition_boundary(root, "holdout", path, custodian_mode)

    prior: dict[str, Any] | None = None
    if role == "verifier":
        if independent_from_manifest is None:
            raise ValueError("verifier execution requires independent_from_manifest")
        prior = load_json(independent_from_manifest)
        if not isinstance(prior, dict) or prior.get("role") != "curator":
            raise ValueError("independent_from_manifest must be a Curator execution manifest")
        if prior.get("partition") != partition:
            raise ValueError("Curator and Verifier execution partitions must match")
        prior_family = _require_nonempty_string(prior.get("model_family"), "independent model_family")
        if _normalized_family(prior_family) == _normalized_family(cfg["model_family"]):
            raise ValueError("verifier model_family must differ from Curator model_family")
        if not isinstance(prior.get("config_sha256"), str) or _SHA256_RE.fullmatch(prior["config_sha256"]) is None:
            raise ValueError("Curator execution manifest is missing a valid config binding")
        if not isinstance(prior.get("completed_task_count"), int) or prior["completed_task_count"] < 1:
            raise ValueError("Curator execution manifest has no completed tasks")

    index = _validate_index_binding(tasks, index_dir)
    if prior is not None:
        if prior.get("index_manifest_sha256") != index["manifest_sha256"]:
            raise ValueError("Curator and Verifier source-index manifests differ")
        if prior.get("index_segments_sha256") != index["segments_sha256"]:
            raise ValueError("Curator and Verifier source-index segments differ")
    contract = _contract_path(root, role)
    identity = _manifest_identity(root, role, partition, cfg, tasks_path, index, contract)
    if prior is not None and independent_from_manifest is not None:
        identity.update({
            "independent_curator_manifest_sha256": sha256_file(independent_from_manifest),
            "independent_curator_config_sha256": prior["config_sha256"],
            "independent_curator_model_family": prior["model_family"],
            "independent_curator_model_ref": prior.get("model_ref"),
            "independent_curator_tasks_sha256": prior.get("tasks_sha256"),
        })
    config_sha = identity["config_sha256"]

    existing = load_jsonl(output_path) if output_path.exists() else []
    if existing and not resume:
        raise ValueError("output already contains responses; use resume to continue")
    task_map = {str(t["task_id"]): t for t in tasks}
    _validate_existing_responses(
        existing, task_map, cfg, config_sha,
        identity["adapter_command_sha256"],
        identity["adapter_artifacts"],
    )
    completed = {str(r["task_id"]) for r in existing}

    batches: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    if manifest_path.exists():
        if not resume:
            raise ValueError("execution manifest already exists; use resume to continue")
        previous = load_json(manifest_path)
        for key, value in identity.items():
            if previous.get(key) != value:
                raise ValueError(f"execution manifest identity mismatch: {key}")
        raw_batches = previous.get("batches", [])
        if not isinstance(raw_batches, list):
            raise ValueError("execution manifest batches must be a list")
        batches = list(raw_batches)
        raw_rejections = previous.get("rejections", [])
        if not isinstance(raw_rejections, list):
            raise ValueError("execution manifest rejections must be a list")
        seen_rejections: set[str] = set()
        for rejection in raw_rejections:
            if not isinstance(rejection, dict):
                raise ValueError("execution manifest rejection must be an object")
            tid = str(rejection.get("task_id", ""))
            if tid not in task_map:
                raise ValueError(f"execution manifest rejection references unknown task: {tid}")
            if tid in completed or tid in seen_rejections:
                raise ValueError(f"execution manifest rejection duplicates completed/rejected task: {tid}")
            if rejection.get("task_fingerprint") != task_map[tid].get("task_fingerprint"):
                raise ValueError(f"execution manifest rejection fingerprint mismatch: {tid}")
            if not _collectable_task_failure(rejection.get("error_code")):
                raise ValueError(f"execution manifest rejection has non-collectable failure: {tid}")
            batch_id = rejection.get("batch_id")
            if not isinstance(batch_id, str) or re.fullmatch(r"[a-f0-9]{24}", batch_id) is None:
                raise ValueError(f"execution manifest rejection batch_id invalid: {tid}")
            expected_batch_id = sha256_bytes(canonical_json_bytes({
                "role": role,
                "config_sha256": config_sha,
                "task_ids": [tid],
                "task_fingerprints": [task_map[tid]["task_fingerprint"]],
            }))[:24]
            if batch_id != expected_batch_id:
                raise ValueError(f"execution manifest rejection batch binding mismatch: {tid}")
            request_sha = rejection.get("request_sha256")
            if not isinstance(request_sha, str) or _SHA256_RE.fullmatch(request_sha) is None:
                raise ValueError(f"execution manifest rejection request hash invalid: {tid}")
            expected_request_sha = sha256_bytes(
                canonical_json_bytes([task_map[tid]])
            )
            if request_sha != expected_request_sha:
                raise ValueError(f"execution manifest rejection request binding mismatch: {tid}")
            attempts_allowed = rejection.get("attempts_allowed")
            attempts_used = rejection.get("attempts_used")
            if attempts_allowed != cfg["max_attempts"]:
                raise ValueError(f"execution manifest rejection attempt policy mismatch: {tid}")
            if (
                not isinstance(attempts_used, int)
                or attempts_used < 1
                or attempts_used > attempts_allowed
            ):
                raise ValueError(f"execution manifest rejection attempts invalid: {tid}")
            seen_rejections.add(tid)
            rejections.append(rejection)

        for rejection in rejections:
            matching_batches = [
                batch for batch in batches
                if (
                    isinstance(batch, dict)
                    and batch.get("outcome") == "rejected"
                    and batch.get("batch_id") == rejection["batch_id"]
                )
            ]
            if len(matching_batches) != 1:
                raise ValueError(
                    f"execution manifest rejection batch record mismatch: {rejection['task_id']}"
                )
            batch = matching_batches[0]
            if (
                batch.get("error_code") != rejection["error_code"]
                or batch.get("request_sha256") != rejection["request_sha256"]
                or batch.get("attempts_allowed") != rejection["attempts_allowed"]
                or batch.get("attempts_used") != rejection["attempts_used"]
            ):
                raise ValueError(
                    f"execution manifest rejection batch record mismatch: {rejection['task_id']}"
                )

    rejected_ids = {str(r["task_id"]) for r in rejections}
    pending = [
        t for t in tasks
        if str(t["task_id"]) not in completed
        and str(t["task_id"]) not in rejected_ids
    ]

    if cfg["task_failure_policy"] == "record_rejection" and not output_path.exists():
        _write_jsonl_atomic(output_path, existing)

    def persist_manifest() -> None:
        rejection_counts: dict[str, int] = {}
        for rejection in rejections:
            code = str(rejection["error_code"])
            rejection_counts[code] = rejection_counts.get(code, 0) + 1
        attempted = len(existing) + len(rejections)
        write_json(manifest_path, {
            **identity,
            "task_count": len(tasks),
            "attempted_task_count": attempted,
            "completed_task_count": len(existing),
            "rejected_task_count": len(rejections),
            "pending_task_count": len(tasks) - attempted,
            "rejection_counts": dict(sorted(rejection_counts.items())),
            "output_sha256": sha256_file(output_path) if output_path.exists() else None,
            "batches": batches,
            "rejections": rejections,
        })

    batch_size = cfg["batch_size"]
    for offset in range(0, len(pending), batch_size):
        batch = pending[offset:offset + batch_size]
        task_ids = [str(t["task_id"]) for t in batch]
        batch_id = sha256_bytes(canonical_json_bytes({
            "role": role,
            "config_sha256": config_sha,
            "task_ids": task_ids,
            "task_fingerprints": [t["task_fingerprint"] for t in batch],
        }))[:24]
        last_error_code: str | None = None
        stamped: list[dict[str, Any]] | None = None
        attempt_used = 0
        request_sha = sha256_bytes(canonical_json_bytes(batch))

        for attempt in range(1, cfg["max_attempts"] + 1):
            attempt_used = attempt
            with tempfile.TemporaryDirectory(prefix="mubin-h392-agent-") as td:
                tmp = Path(td)
                input_path = tmp / "input.jsonl"
                raw_output = tmp / "output.jsonl"
                dump_jsonl(input_path, batch)
                mapping = {
                    "input": str(input_path),
                    "output": str(raw_output),
                    "index_dir": str(index_dir),
                    "contract": str(contract),
                    "role": role,
                }
                command = _render_command(cfg["adapter"]["command"], mapping)
                env = _adapter_env(cfg, role, index_dir, contract, input_path, raw_output)
                diagnostic_path = tmp / "adapter-stderr.log"
                try:
                    with diagnostic_path.open("wb") as diagnostic_stream:
                        proc = subprocess.run(
                            command,
                            cwd=str(root),
                            env=env,
                            stdout=subprocess.DEVNULL,
                            stderr=diagnostic_stream,
                            check=False,
                            timeout=cfg["timeout_seconds"],
                        )
                    if proc.returncode != 0:
                        diagnostic = _extract_adapter_diagnostic(diagnostic_path)
                        last_error_code = (
                            f"adapter:{diagnostic}"
                            if diagnostic is not None
                            else f"nonzero_exit:{proc.returncode}"
                        )
                        continue
                    if not raw_output.exists():
                        last_error_code = "missing_output"
                        continue
                    try:
                        raw_rows = load_jsonl(raw_output)
                        checked = _validate_raw_adapter_rows(raw_rows, batch, role)
                    except ValueError as exc:
                        last_error_code = f"invalid_output:{exc}"
                        continue
                    stamped = _stamp_rows(
                        checked, batch, cfg, config_sha, batch_id,
                        identity["adapter_command_sha256"],
                        identity["adapter_artifacts"],
                    )
                    break
                except subprocess.TimeoutExpired:
                    last_error_code = "timeout"

        if stamped is None:
            if (
                cfg["task_failure_policy"] == "record_rejection"
                and len(batch) == 1
                and _collectable_task_failure(last_error_code)
            ):
                rejection = {
                    "task_id": task_ids[0],
                    "task_fingerprint": batch[0]["task_fingerprint"],
                    "batch_id": batch_id,
                    "error_code": last_error_code,
                    "request_sha256": request_sha,
                    "attempts_allowed": cfg["max_attempts"],
                    "attempts_used": attempt_used,
                }
                rejections.append(rejection)
                batches.append({
                    "batch_id": batch_id,
                    "task_count": 1,
                    "task_ids_sha256": sha256_bytes(canonical_json_bytes(task_ids)),
                    "request_sha256": request_sha,
                    "outcome": "rejected",
                    "error_code": last_error_code,
                    "attempts_allowed": cfg["max_attempts"],
                    "attempts_used": attempt_used,
                })
                persist_manifest()
                continue
            raise RuntimeError(
                f"adapter batch failed after {cfg['max_attempts']} attempts: {batch_id}: {last_error_code or 'unknown_error'}"
            )

        existing.extend(stamped)
        _write_jsonl_atomic(output_path, existing)
        batches.append({
            "batch_id": batch_id,
            "task_count": len(batch),
            "task_ids_sha256": sha256_bytes(canonical_json_bytes(task_ids)),
            "request_sha256": request_sha,
            "responses_sha256": sha256_bytes(canonical_json_bytes(stamped)),
            "outcome": "accepted",
            "attempts_allowed": cfg["max_attempts"],
            "attempts_used": attempt_used,
        })
        persist_manifest()

    if not manifest_path.exists():
        persist_manifest()

    return load_json(manifest_path)
