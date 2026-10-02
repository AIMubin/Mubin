from __future__ import annotations

from configparser import ConfigParser
from pathlib import Path
from typing import Any

from .core import load_json, sha256_file, write_json
from .freeze import verify_freeze
from .validate import validate_campaign


def _read_architecture_gate(path: Path | None) -> tuple[bool, str]:
    if path is None or not path.exists():
        return False, "missing_architecture_audit"
    obj = load_json(path)
    value = obj.get("architecture_gate_passed")
    if value is True:
        return True, "architecture_audit"
    return False, "architecture_audit"


def _read_benchmark_evaluation(root: Path, path: Path | None, expected_freeze_id: str | None) -> tuple[bool, dict[str, Any]]:
    if path is None or not path.exists():
        return False, {"reason": "missing_evaluation_report"}
    obj = load_json(path)
    freeze_match = obj.get("freeze_id") == expected_freeze_id and expected_freeze_id is not None
    all_pass = obj.get("all_benchmarks_passed") is True
    report_hash = sha256_file(path)
    model_lock_path = root / "artifacts" / "MODEL_LOCK.json"
    model_lock_hash = sha256_file(model_lock_path) if model_lock_path.exists() else None
    model_lock_ok = model_lock_hash is not None and obj.get("model_lock_sha256") == model_lock_hash
    marker_path = root / "artifacts" / "HOLDOUT_ACCESSED.json"
    marker_ok = False
    marker_reason = "missing_holdout_access_marker"
    if marker_path.exists():
        marker = load_json(marker_path)
        sealed = obj.get("sealed_holdout")
        sealed_marker_ok = True
        if isinstance(sealed, dict):
            sealed_marker_ok = bool(
                marker.get("sealed_store_hashes") == sealed.get("store_hashes")
                and marker.get("holdout_key_id") == sealed.get("key_id")
            )
        marker_ok = bool(
            marker.get("freeze_id") == expected_freeze_id
            and marker.get("evaluation_report_sha256") == report_hash
            and marker.get("prediction_hashes") == obj.get("prediction_hashes")
            and marker.get("model_lock_sha256") == model_lock_hash
            and sealed_marker_ok
        )
        marker_reason = "verified" if marker_ok else "holdout_access_marker_mismatch"
    qualified = bool(freeze_match and all_pass and marker_ok and model_lock_ok)
    return qualified, {
        "reason": "verified_evaluation" if qualified else "evaluation_not_qualified",
        "freeze_id_matches": freeze_match,
        "all_benchmarks_passed": all_pass,
        "model_lock_matches": model_lock_ok,
        "holdout_access_marker": marker_reason,
        "evaluation_report_sha256": report_hash,
    }


def build_pre_m4_audit(root: Path, spec_path: Path, freeze_manifest: Path | None,
                       architecture_audit: Path | None, evaluation_report: Path | None = None) -> dict[str, Any]:
    spec = load_json(spec_path)
    validation = validate_campaign(root, spec)
    freeze_ok = False
    freeze_id = None
    freeze_reason = "missing_freeze_manifest"
    if freeze_manifest is not None and freeze_manifest.exists():
        verification = verify_freeze(root, freeze_manifest)
        freeze_ok = bool(verification["verified"])
        freeze_id = verification.get("freeze_id")
        freeze_reason = "verified" if freeze_ok else "freeze_verification_failed"

    evaluation_ok, evaluation_evidence = _read_benchmark_evaluation(root, evaluation_report, freeze_id)
    benchmark_gate = bool(validation["all_benchmarks_qualified"] and freeze_ok and evaluation_ok)
    architecture_gate, architecture_source = _read_architecture_gate(architecture_audit)
    m4_allowed = bool(benchmark_gate and architecture_gate)
    return {
        "campaign_id": spec["campaign_id"],
        "benchmark_gate_passed": benchmark_gate,
        "architecture_gate_passed": architecture_gate,
        "h4_entry_allowed": m4_allowed,
        "benchmark_evidence": {
            "all_benchmarks_qualified": validation["all_benchmarks_qualified"],
            "freeze_verified": freeze_ok,
            "freeze_id": freeze_id,
            "freeze_reason": freeze_reason,
            "evaluation": evaluation_evidence,
            "violation_count": validation["violation_count"],
        },
        "architecture_evidence": {"source": architecture_source},
        "derivation": "h4_entry_allowed = benchmark_gate_passed AND architecture_gate_passed",
        "benchmark_gate_derivation": "benchmark_gate_passed = dataset_qualified AND freeze_verified AND frozen_holdout_evaluation_passed",
    }


def write_ini(path: Path, audit: dict[str, Any]) -> None:
    cfg = ConfigParser()
    cfg["pre-h4-audit"] = {
        "benchmark_gate_passed": str(audit["benchmark_gate_passed"]).lower(),
        "architecture_gate_passed": str(audit["architecture_gate_passed"]).lower(),
        "h4_entry_allowed": str(audit["h4_entry_allowed"]).lower(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        cfg.write(f)


def emit_pre_m4_audit(root: Path, spec_path: Path, freeze_manifest: Path | None,
                      architecture_audit: Path | None, evaluation_report: Path | None,
                      json_out: Path, ini_out: Path) -> dict[str, Any]:
    audit = build_pre_m4_audit(root, spec_path, freeze_manifest, architecture_audit, evaluation_report)
    write_json(json_out, audit)
    write_ini(ini_out, audit)
    return audit
