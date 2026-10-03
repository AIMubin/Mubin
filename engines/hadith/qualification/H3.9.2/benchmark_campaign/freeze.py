from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any
import re
import subprocess

from .core import canonical_json_bytes, load_json, sha256_bytes, sha256_file, write_json
from .manifests import emit_campaign_manifests
from .holdout_seal import sealed_gold_path
from .validate import validate_campaign

FREEZE_SCHEMA_VERSION = 10
ANCHOR_SCHEMA_VERSION = 1
DEFAULT_ANCHOR_RELATIVE = Path("private/FREEZE_ANCHOR.json")


def _record_files(root: Path, spec: dict[str, Any]) -> list[Path]:
    return [root / "benchmarks" / b["id"] / "records.jsonl" for b in spec["benchmarks"]]


def _frozen_protocol_files(root: Path) -> list[Path]:
    files = [
        root / "sources" / "source-registry.json",
        root / "schemas" / "benchmark-record.schema.json",
        root / "schemas" / "source-registry.schema.json",
        root / "schemas" / "factory-curator-response.schema.json",
        root / "schemas" / "factory-verifier-response.schema.json",
        root / "config" / "factory-policy.json",
        root / "agents" / "CURATOR_CONTRACT.md",
        root / "agents" / "VERIFIER_CONTRACT.md",
        root / "requirements.txt",
        root / "benchmark_campaign" / "__init__.py",
        root / "benchmark_campaign" / "__main__.py",
        root / "benchmark_campaign" / "cli.py",
        root / "benchmark_campaign" / "validate.py",
        root / "benchmark_campaign" / "split.py",
        root / "benchmark_campaign" / "evaluate.py",
        root / "benchmark_campaign" / "audit.py",
        root / "benchmark_campaign" / "freeze.py",
        root / "benchmark_campaign" / "lifecycle.py",
        root / "benchmark_campaign" / "core.py",
        root / "benchmark_campaign" / "normalization.py",
        root / "benchmark_campaign" / "source_registry.py",
        root / "benchmark_campaign" / "holdout_seal.py",
        root / "benchmark_campaign" / "queue_plan.py",
        root / "benchmark_campaign" / "curation.py",
        root / "benchmark_campaign" / "manifests.py",
        root / "benchmark_campaign" / "source_cache.py",
        root / "benchmark_campaign" / "factory.py",
        root / "benchmark_campaign" / "execution.py",
        root / "AGENT_EXECUTION.md",
        root / "adapters" / "chat_completions.py",
    ]
    for rel in ("config/curation-plan.json", "config/curation-quotas.json"):
        p = root / rel
        if p.exists():
            files.append(p)
    return files


def _derived_manifest_files(root: Path) -> list[Path]:
    return [
        root / "artifacts" / "HOLDOUT_MANIFEST.json",
        root / "artifacts" / "PROVENANCE_MANIFEST.json",
        root / "artifacts" / "DISJOINTNESS_REPORT.json",
    ]


def _validate_evaluation_contract(spec: dict[str, Any]) -> None:
    for b in spec["benchmarks"]:
        ev = b.get("evaluation")
        if not isinstance(ev, dict):
            raise ValueError(f"{b['id']}: evaluation contract missing")
        if ev.get("task_type") not in {"classification", "multilabel"}:
            raise ValueError(f"{b['id']}: unsupported evaluation task_type")
        thresholds = ev.get("thresholds")
        if not isinstance(thresholds, dict) or not thresholds:
            raise ValueError(f"{b['id']}: preregistered thresholds missing")
        for metric, rule in thresholds.items():
            if not isinstance(rule, dict) or ("min" not in rule and "max" not in rule):
                raise ValueError(f"{b['id']}: invalid threshold rule for {metric}")
        labels = ev.get("labels")
        if not isinstance(labels, list) or not labels or len(labels) != len(set(labels)):
            raise ValueError(f"{b['id']}: labels must be a non-empty unique list")
        if spec.get("qualification", {}).get("require_label_coverage") is True:
            coverage_key = "minimum_label_counts" if ev["task_type"] == "classification" else "minimum_positive_label_counts"
            coverage = ev.get(coverage_key)
            if not isinstance(coverage, dict) or set(coverage) != set(labels):
                raise ValueError(f"{b['id']}: {coverage_key} must cover every preregistered label exactly")
            if any(not isinstance(v, int) or v < 1 for v in coverage.values()):
                raise ValueError(f"{b['id']}: {coverage_key} values must be positive integers")
        for name, minimum in ev.get("minimum_denominators", {}).items():
            if not isinstance(name, str) or not isinstance(minimum, int) or minimum < 1:
                raise ValueError(f"{b['id']}: invalid minimum denominator")


def _safe_relative(root: Path, p: Path) -> str:
    root_resolved = root.resolve()
    p_resolved = p.resolve()
    try:
        return str(p_resolved.relative_to(root_resolved))
    except ValueError as exc:
        raise ValueError(f"freeze file escapes campaign root: {p}") from exc


def _policy() -> dict[str, Any]:
    return {
        "holdout_policy": {
            "source_disjoint": True,
            "family_disjoint": True,
            "fingerprint_disjoint": True,
            "synthetic_eligible": False,
            "final_holdout_policy": "one-shot; byte-identical prediction replay only",
            "gold_storage": "AES-256-GCM sealed store; plaintext gold absent from public holdout records",
            "key_storage": "external; never frozen or distributed with campaign",
        },
        "evaluation_policy": {
            "thresholds_preregistered": True,
            "tuning_data": ["development", "validation"],
            "holdout_for_tuning": False,
        },
    }


def _freeze_file_paths(root: Path, spec_path: Path, spec: dict[str, Any]) -> list[Path]:
    sealed_files: list[Path] = []
    if spec.get("qualification", {}).get("require_sealed_holdout_gold") is True:
        sealed_files = [sealed_gold_path(root, b["id"]) for b in spec["benchmarks"]]
    return [
        spec_path,
        *_record_files(root, spec),
        *_frozen_protocol_files(root),
        *sealed_files,
        *_derived_manifest_files(root),
    ]


def _build_core(root: Path, spec_path: Path, spec: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    seen: set[str] = set()
    for p in _freeze_file_paths(root, spec_path, spec):
        if not p.exists():
            raise FileNotFoundError(p)
        rel = _safe_relative(root, p)
        if rel in seen:
            raise ValueError(f"duplicate path in freeze set: {rel}")
        seen.add(rel)
        files.append({"path": rel, "sha256": sha256_file(p), "size_bytes": p.stat().st_size})
    files.sort(key=lambda x: x["path"])
    policy = _policy()
    return {
        "campaign_id": spec["campaign_id"],
        "schema_version": FREEZE_SCHEMA_VERSION,
        "spec_path": _safe_relative(root, spec_path),
        "files": files,
        **policy,
        "validation_sha256": sha256_bytes(canonical_json_bytes(validation)),
    }


def build_freeze_manifest(root: Path, spec_path: Path) -> dict[str, Any]:
    spec = load_json(spec_path)
    if (root / "artifacts" / "TUNING_STARTED.json").exists():
        raise ValueError("campaign cannot be frozen after tuning has started")
    if (root / "artifacts" / "HOLDOUT_ACCESSED.json").exists():
        raise ValueError("campaign cannot be frozen after holdout access")
    _validate_evaluation_contract(spec)
    validation = validate_campaign(root, spec)
    if not validation["all_benchmarks_qualified"]:
        raise ValueError("campaign cannot be frozen: benchmark qualification failed")
    emit_campaign_manifests(root, spec, root / "artifacts")
    core = _build_core(root, spec_path, spec, validation)
    freeze_id = sha256_bytes(canonical_json_bytes(core))
    return {
        **core,
        "freeze_id": freeze_id,
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "immutable": True,
    }


def freeze_campaign(root: Path, spec_path: Path, out_path: Path) -> dict[str, Any]:
    if out_path.exists():
        raise FileExistsError(f"refusing to overwrite frozen manifest: {out_path}")
    manifest = build_freeze_manifest(root, spec_path)
    write_json(out_path, manifest)
    return manifest


def _git_repo_root(path: Path) -> Path:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            text=True, stderr=subprocess.STDOUT,
        ).strip()
    except Exception as exc:
        raise ValueError("qualification operation requires a Git checkout") from exc
    return Path(out).resolve()


def _verify_manifest_at_commit(manifest_path: Path, source_commit: str) -> tuple[Path, str]:
    repo_root = _git_repo_root(manifest_path.parent)
    try:
        subprocess.run(
            ["git", "-C", str(repo_root), "cat-file", "-e", f"{source_commit}^{{commit}}"],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        raise ValueError("source_commit does not resolve to a Git commit") from exc
    rel = str(manifest_path.resolve().relative_to(repo_root))
    try:
        committed = subprocess.check_output(
            ["git", "-C", str(repo_root), "show", f"{source_commit}:{rel}"],
            stderr=subprocess.STDOUT,
        )
    except Exception as exc:
        raise ValueError("freeze manifest is not present at source_commit") from exc
    if hashlib.sha256(committed).hexdigest() != sha256_file(manifest_path):
        raise ValueError("working freeze manifest differs from the manifest stored at source_commit")
    return repo_root, rel


def create_freeze_anchor(manifest_path: Path, anchor_path: Path, source_commit: str) -> dict[str, Any]:
    if not re.fullmatch(r"[a-f0-9]{40}", source_commit):
        raise ValueError("source_commit must be a full 40-hex Git commit SHA")
    if anchor_path.exists():
        raise FileExistsError(f"refusing to overwrite freeze anchor: {anchor_path}")
    repo_root, manifest_repo_path = _verify_manifest_at_commit(manifest_path, source_commit)
    manifest = load_json(manifest_path)
    obj = {
        "schema_version": ANCHOR_SCHEMA_VERSION,
        "freeze_id": manifest.get("freeze_id"),
        "manifest_sha256": sha256_file(manifest_path),
        "source_commit": source_commit,
        "manifest_repo_path": manifest_repo_path,
        "git_binding_verified": True,
        "policy": "detached anchor; store outside tracked campaign tree and pin source_commit in protected Git history/release record",
    }
    write_json(anchor_path, obj)
    return obj


def verify_freeze(root: Path, manifest_path: Path, anchor_path: Path | None = None) -> dict[str, Any]:
    mismatches: list[dict[str, Any]] = []
    try:
        manifest = load_json(manifest_path)
    except Exception as exc:
        return {"freeze_id": None, "verified": False, "mismatches": [{"reason": f"manifest_unreadable:{exc}"}]}

    if manifest.get("schema_version") != FREEZE_SCHEMA_VERSION:
        mismatches.append({"reason": "freeze_schema_version"})
    if manifest.get("immutable") is not True:
        mismatches.append({"reason": "freeze_not_marked_immutable"})
    spec_rel = manifest.get("spec_path")
    if not isinstance(spec_rel, str) or not spec_rel:
        mismatches.append({"reason": "spec_path_missing"})
        return {"freeze_id": manifest.get("freeze_id"), "verified": False, "mismatches": mismatches}
    spec_path = root / spec_rel
    try:
        _safe_relative(root, spec_path)
        spec = load_json(spec_path)
        validation = validate_campaign(root, spec)
        expected_core = _build_core(root, spec_path, spec, validation)
    except Exception as exc:
        mismatches.append({"reason": "freeze_rebuild_failed", "detail": str(exc)})
        return {"freeze_id": manifest.get("freeze_id"), "verified": False, "mismatches": mismatches}

    for key, expected in expected_core.items():
        if manifest.get(key) != expected:
            mismatches.append({"reason": f"manifest_core_mismatch:{key}"})
    expected_freeze_id = sha256_bytes(canonical_json_bytes(expected_core))
    if manifest.get("freeze_id") != expected_freeze_id:
        mismatches.append({"reason": "freeze_id_mismatch", "expected": expected_freeze_id, "actual": manifest.get("freeze_id")})

    anchor_path = anchor_path or (root / DEFAULT_ANCHOR_RELATIVE)
    anchor_sha256 = None
    source_commit = None
    if not anchor_path.exists():
        mismatches.append({"reason": "detached_anchor_missing", "path": str(anchor_path)})
    else:
        try:
            anchor = load_json(anchor_path)
            anchor_sha256 = sha256_file(anchor_path)
            source_commit = anchor.get("source_commit")
            if anchor.get("schema_version") != ANCHOR_SCHEMA_VERSION:
                mismatches.append({"reason": "anchor_schema_version"})
            if anchor.get("freeze_id") != expected_freeze_id:
                mismatches.append({"reason": "anchor_freeze_id_mismatch"})
            if anchor.get("manifest_sha256") != sha256_file(manifest_path):
                mismatches.append({"reason": "anchor_manifest_hash_mismatch"})
            if not isinstance(source_commit, str) or re.fullmatch(r"[a-f0-9]{40}", source_commit) is None:
                mismatches.append({"reason": "anchor_source_commit_invalid"})
            elif anchor.get("git_binding_verified") is not True:
                mismatches.append({"reason": "anchor_git_binding_not_verified"})
            else:
                try:
                    repo_root = _git_repo_root(manifest_path.parent)
                    rel = anchor.get("manifest_repo_path")
                    if not isinstance(rel, str) or not rel:
                        raise ValueError("manifest_repo_path missing")
                    committed = subprocess.check_output(
                        ["git", "-C", str(repo_root), "show", f"{source_commit}:{rel}"],
                        stderr=subprocess.STDOUT,
                    )
                    if hashlib.sha256(committed).hexdigest() != sha256_file(manifest_path):
                        mismatches.append({"reason": "anchor_git_manifest_mismatch"})
                except Exception as exc:
                    mismatches.append({"reason": "anchor_git_binding_failed", "detail": str(exc)})
        except Exception as exc:
            mismatches.append({"reason": "anchor_unreadable", "detail": str(exc)})

    return {
        "freeze_id": manifest.get("freeze_id"),
        "verified": not mismatches,
        "mismatches": mismatches,
        "anchor_sha256": anchor_sha256,
        "source_commit": source_commit,
    }
