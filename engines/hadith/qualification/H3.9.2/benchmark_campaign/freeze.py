from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .core import canonical_json_bytes, load_json, sha256_bytes, sha256_file, write_json
from .manifests import emit_campaign_manifests
from .holdout_seal import sealed_gold_path
from .validate import validate_campaign


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
    ]
    curation_plan = root / "config" / "curation-plan.json"
    if curation_plan.exists():
        files.append(curation_plan)
    curation_quotas = root / "config" / "curation-quotas.json"
    if curation_quotas.exists():
        files.append(curation_quotas)
    return files


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
    derived = emit_campaign_manifests(root, spec, root / "artifacts")
    files: list[dict[str, Any]] = []
    sealed_files: list[Path] = []
    if spec.get("qualification", {}).get("require_sealed_holdout_gold") is True:
        sealed_files = [sealed_gold_path(root, b["id"]) for b in spec["benchmarks"]]
    freeze_files = [spec_path, *_record_files(root, spec), *_frozen_protocol_files(root), *sealed_files, *derived.values()]
    for p in freeze_files:
        if not p.exists():
            raise FileNotFoundError(p)
        files.append({"path": str(p.relative_to(root)), "sha256": sha256_file(p), "size_bytes": p.stat().st_size})
    core = {
        "campaign_id": spec["campaign_id"],
        "schema_version": 4,
        "files": files,
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
        "validation_sha256": sha256_bytes(canonical_json_bytes(validation)),
    }
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


def verify_freeze(root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    mismatches: list[dict[str, str]] = []
    for item in manifest.get("files", []):
        p = root / item["path"]
        if not p.exists():
            mismatches.append({"path": item["path"], "reason": "missing"})
            continue
        actual = sha256_file(p)
        if actual != item["sha256"]:
            mismatches.append({"path": item["path"], "reason": "sha256_mismatch", "expected": item["sha256"], "actual": actual})
    return {
        "freeze_id": manifest.get("freeze_id"),
        "verified": not mismatches,
        "mismatches": mismatches,
    }
