from __future__ import annotations

from pathlib import Path
from typing import Any

from .core import load_json, sha256_file, write_json
from .freeze import verify_freeze


def export_tuning_pack(root: Path, spec: dict[str, Any], out_dir: Path, freeze_manifest: Path) -> dict[str, Any]:
    from .core import dump_jsonl, load_jsonl
    verification = verify_freeze(root, freeze_manifest)
    if not verification["verified"]:
        raise ValueError("tuning pack cannot be exported before a verified benchmark freeze")
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {"campaign_id": spec["campaign_id"], "freeze_id": verification["freeze_id"], "benchmarks": []}
    for b in spec["benchmarks"]:
        rows = [r for r in load_jsonl(root / "benchmarks" / b["id"] / "records.jsonl") if r.get("split") != "holdout"]
        out = out_dir / f"{b['id']}.jsonl"
        dump_jsonl(out, rows)
        report["benchmarks"].append({"benchmark_id": b["id"], "count": len(rows), "sha256": sha256_file(out)})
    write_json(out_dir / "TUNING_PACK_MANIFEST.json", report)
    return report


def mark_tuning_started(root: Path, freeze_manifest: Path, model_ref: str, model_config_path: Path | None = None) -> dict[str, Any]:
    verification = verify_freeze(root, freeze_manifest)
    if not verification["verified"]:
        raise ValueError("tuning cannot start before a verified benchmark freeze")
    if (root / "artifacts" / "HOLDOUT_ACCESSED.json").exists():
        raise RuntimeError("tuning cannot start after final holdout access under the same freeze")
    if (root / "artifacts" / "MODEL_LOCK.json").exists():
        raise RuntimeError("tuning cannot start or change after the candidate model is locked")
    marker = root / "artifacts" / "TUNING_STARTED.json"
    if marker.exists():
        prior = load_json(marker)
        expected_cfg = sha256_file(model_config_path) if model_config_path else None
        if prior.get("freeze_id") != verification["freeze_id"] or prior.get("model_ref") != model_ref or prior.get("model_config_sha256") != expected_cfg:
            raise RuntimeError("tuning marker already exists for a different model/configuration")
        return prior
    obj = {
        "freeze_id": verification["freeze_id"],
        "model_ref": model_ref,
        "model_config_sha256": sha256_file(model_config_path) if model_config_path else None,
        "rule": "tuning may use development/validation only; holdout remains sealed until final evaluation",
    }
    write_json(marker, obj)
    return obj


def lock_model(root: Path, freeze_manifest: Path, model_ref: str, model_config_path: Path | None = None) -> dict[str, Any]:
    verification = verify_freeze(root, freeze_manifest)
    if not verification["verified"]:
        raise ValueError("model cannot be locked before a verified benchmark freeze")
    if (root / "artifacts" / "HOLDOUT_ACCESSED.json").exists():
        raise RuntimeError("model cannot be locked after final holdout access")
    marker = root / "artifacts" / "MODEL_LOCK.json"
    obj = {
        "freeze_id": verification["freeze_id"],
        "model_ref": model_ref,
        "model_config_sha256": sha256_file(model_config_path) if model_config_path else None,
        "rule": "candidate model/configuration is immutable for final holdout evaluation under this freeze",
    }
    if marker.exists():
        prior = load_json(marker)
        if prior != obj:
            raise RuntimeError("MODEL_LOCK already exists for a different candidate")
        return prior
    write_json(marker, obj)
    return obj
