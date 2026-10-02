from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import re

from .core import canonical_json_bytes, load_json, sha256_bytes, sha256_file, write_json
from .manifests import emit_campaign_manifests
from .holdout_seal import sealed_gold_path
from .validate import validate_campaign

FREEZE_SCHEMA_VERSION = 5
ANCHOR_SCHEMA_VERSION = 1
DEFAULT_ANCHOR_RELATIVE = Path("private/FREEZE_ANCHOR.json")


def _record_files(root: Path, spec: dict[str, Any]) -> list[Path]:
    return [root / "benchmarks" / b["id"] / "records.jsonl" for b in spec["benchmarks"]]


def _frozen_protocol_files(root: Path) -> list[Path]:
    files = [
        root / "sources" / "source-registry.json",
        root / "schemas" / "benchmark-record.schema.json",
        root / "schemas" / "source-registry.schema.json",
        root / "requirements.txt",
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


def create_freeze_anchor(manifest_path: Path, anchor_path: Path, source_commit: str) -> dict[str, Any]:
    if not re.fullmatch(r"[a-f0-9]{40}", source_commit):
        raise ValueError("source_commit must be a full 40-hex Git commit SHA")
    if anchor_path.exists():
        raise FileExistsError(f"refusing to overwrite freeze anchor: {anchor_path}")
    manifest = load_json(manifest_path)
    obj = {
        "schema_version": ANCHOR_SCHEMA_VERSION,
        "freeze_id": manifest.get("freeze_id"),
        "manifest_sha256": sha256_file(manifest_path),
        "source_commit": source_commit,
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
        except Exception as exc:
            mismatches.append({"reason": "anchor_unreadable", "detail": str(exc)})

    return {
        "freeze_id": manifest.get("freeze_id"),
        "verified": not mismatches,
        "mismatches": mismatches,
        "anchor_sha256": anchor_sha256,
        "source_commit": source_commit,
    }
