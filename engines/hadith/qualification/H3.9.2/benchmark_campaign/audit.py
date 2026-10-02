from __future__ import annotations

from configparser import ConfigParser
from pathlib import Path
from typing import Any
import hashlib
import hmac
import re

from .core import canonical_json_bytes, load_json, sha256_file, write_json
from .freeze import verify_freeze
from .holdout_seal import load_holdout_key
from .validate import validate_campaign


def _read_architecture_gate(root: Path, path: Path | None, expected_system_commit: str | None) -> tuple[bool, dict[str, Any]]:
    evidence: dict[str, Any] = {"source": "missing_architecture_audit"}
    if path is None or not path.exists():
        return False, evidence
    try:
        obj = load_json(path)
    except Exception as exc:
        return False, {"source": "architecture_audit", "reason": f"unreadable:{exc}"}

    reasons: list[str] = []
    if obj.get("schema_version") != 1:
        reasons.append("schema_version")
    if obj.get("audit_kind") != "architecture_qualification":
        reasons.append("audit_kind")
    audit_id = obj.get("audit_id")
    if not isinstance(audit_id, str) or not audit_id or "example" in audit_id.lower():
        reasons.append("audit_id")
    if obj.get("frozen") is not True:
        reasons.append("not_frozen")
    if expected_system_commit is None or obj.get("candidate_commit") != expected_system_commit:
        reasons.append("candidate_commit")
    evs = obj.get("evidence")
    if not isinstance(evs, list) or not evs:
        reasons.append("evidence_missing")
    else:
        bundle_root = path.parent.resolve()
        for i, ev in enumerate(evs):
            if not isinstance(ev, dict):
                reasons.append(f"evidence_{i}_invalid")
                continue
            rel = ev.get("path")
            expected_sha = ev.get("sha256")
            if not isinstance(rel, str) or not isinstance(expected_sha, str) or re.fullmatch(r"[a-f0-9]{64}", expected_sha) is None:
                reasons.append(f"evidence_{i}_contract")
                continue
            p = (bundle_root / rel).resolve()
            try:
                p.relative_to(bundle_root)
            except ValueError:
                reasons.append(f"evidence_{i}_path_escape")
                continue
            if not p.exists() or sha256_file(p) != expected_sha:
                reasons.append(f"evidence_{i}_hash")
    if obj.get("architecture_gate_passed") is not True:
        reasons.append("gate_false")

    ok = not reasons
    return ok, {
        "source": "architecture_audit",
        "audit_id": audit_id,
        "candidate_commit": obj.get("candidate_commit"),
        "audit_sha256": sha256_file(path),
        "verified": ok,
        "reasons": reasons,
    }


def _read_benchmark_evaluation(root: Path, path: Path | None, expected_freeze_id: str | None,
                               holdout_key_path: Path | None) -> tuple[bool, dict[str, Any]]:
    if path is None or not path.exists():
        return False, {"reason": "missing_evaluation_report"}
    obj = load_json(path)
    freeze_match = obj.get("freeze_id") == expected_freeze_id and expected_freeze_id is not None
    all_pass = obj.get("all_benchmarks_passed") is True
    report_hash = sha256_file(path)
    model_lock_path = root / "artifacts" / "MODEL_LOCK.json"
    model_lock_hash = sha256_file(model_lock_path) if model_lock_path.exists() else None
    model_lock_ok = model_lock_hash is not None and obj.get("model_lock_sha256") == model_lock_hash

    attestation_ok = False
    if holdout_key_path is not None and holdout_key_path.exists():
        try:
            key = load_holdout_key(holdout_key_path)
            actual = obj.get("evaluation_attestation_hmac_sha256")
            unsigned = dict(obj)
            unsigned.pop("evaluation_attestation_hmac_sha256", None)
            expected = hmac.new(key, canonical_json_bytes(unsigned), hashlib.sha256).hexdigest()
            attestation_ok = isinstance(actual, str) and hmac.compare_digest(actual, expected)
        except Exception:
            attestation_ok = False

    marker_path = root / "artifacts" / "HOLDOUT_ACCESSED.json"
    marker_ok = False
    marker_reason = "missing_holdout_access_marker"
    if marker_path.exists():
        marker = load_json(marker_path)
        sealed = obj.get("sealed_holdout")
        sealed_marker_ok = isinstance(sealed, dict) and bool(
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

    qualified = bool(freeze_match and all_pass and marker_ok and model_lock_ok and attestation_ok)
    return qualified, {
        "reason": "verified_evaluation" if qualified else "evaluation_not_qualified",
        "freeze_id_matches": freeze_match,
        "all_benchmarks_passed": all_pass,
        "model_lock_matches": model_lock_ok,
        "evaluation_attestation_verified": attestation_ok,
        "holdout_access_marker": marker_reason,
        "evaluation_report_sha256": report_hash,
    }


def build_pre_m4_audit(root: Path, spec_path: Path, freeze_manifest: Path | None,
                       architecture_audit: Path | None, evaluation_report: Path | None = None,
                       holdout_key_path: Path | None = None) -> dict[str, Any]:
    spec = load_json(spec_path)
    validation = validate_campaign(root, spec)
    freeze_ok = False
    freeze_id = None
    freeze_reason = "missing_freeze_manifest"
    freeze_evidence: dict[str, Any] = {}
    if freeze_manifest is not None and freeze_manifest.exists():
        verification = verify_freeze(root, freeze_manifest)
        freeze_ok = bool(verification["verified"])
        freeze_id = verification.get("freeze_id")
        freeze_reason = "verified" if freeze_ok else "freeze_verification_failed"
        freeze_evidence = {
            "anchor_sha256": verification.get("anchor_sha256"),
            "source_commit": verification.get("source_commit"),
            "mismatches": verification.get("mismatches", []),
        }

    evaluation_ok, evaluation_evidence = _read_benchmark_evaluation(
        root, evaluation_report, freeze_id, holdout_key_path
    )
    benchmark_gate = bool(validation["all_benchmarks_qualified"] and freeze_ok and evaluation_ok)

    model_lock_path = root / "artifacts" / "MODEL_LOCK.json"
    expected_system_commit = None
    if model_lock_path.exists():
        lock = load_json(model_lock_path)
        expected_system_commit = lock.get("system_commit")
    architecture_gate, architecture_evidence = _read_architecture_gate(
        root, architecture_audit, expected_system_commit
    )

    h4_qualification_allowed = bool(benchmark_gate and architecture_gate)
    return {
        "campaign_id": spec["campaign_id"],
        "benchmark_gate_passed": benchmark_gate,
        "architecture_gate_passed": architecture_gate,
        "h4_development_allowed": True,
        "h4_qualification_allowed": h4_qualification_allowed,
        "h4_release_allowed": False,
        "h4_release_reason": "H4 release requires its own post-development release audit; H3.9.2 cannot authorize release.",
        "benchmark_evidence": {
            "all_benchmarks_qualified": validation["all_benchmarks_qualified"],
            "freeze_verified": freeze_ok,
            "freeze_id": freeze_id,
            "freeze_reason": freeze_reason,
            "freeze": freeze_evidence,
            "evaluation": evaluation_evidence,
            "violation_count": validation["violation_count"],
        },
        "architecture_evidence": architecture_evidence,
        "derivation": "h4_qualification_allowed = benchmark_gate_passed AND architecture_gate_passed; h4_development_allowed is independent",
    }


def write_ini(path: Path, audit: dict[str, Any]) -> None:
    cfg = ConfigParser()
    cfg["pre-h4-audit"] = {
        "benchmark_gate_passed": str(audit["benchmark_gate_passed"]).lower(),
        "architecture_gate_passed": str(audit["architecture_gate_passed"]).lower(),
        "h4_development_allowed": str(audit["h4_development_allowed"]).lower(),
        "h4_qualification_allowed": str(audit["h4_qualification_allowed"]).lower(),
        "h4_release_allowed": str(audit["h4_release_allowed"]).lower(),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        cfg.write(f)


def emit_pre_m4_audit(root: Path, spec_path: Path, freeze_manifest: Path | None,
                      architecture_audit: Path | None, evaluation_report: Path | None,
                      holdout_key_path: Path | None, json_out: Path, ini_out: Path) -> dict[str, Any]:
    audit = build_pre_m4_audit(
        root, spec_path, freeze_manifest, architecture_audit, evaluation_report, holdout_key_path
    )
    write_json(json_out, audit)
    write_ini(ini_out, audit)
    return audit
