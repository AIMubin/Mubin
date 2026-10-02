from __future__ import annotations

import hashlib
import hmac
from collections import Counter
from pathlib import Path
from typing import Any

from .core import canonical_json_bytes, load_json, load_jsonl, sha256_file, write_json
from .freeze import verify_freeze
from .holdout_seal import decrypt_gold_map, key_id, load_holdout_key, sealed_gold_path


def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def _macro_f1(gold: list[str], pred: list[str], labels: list[str]) -> float:
    scores = []
    for label in labels:
        tp = sum(g == label and p == label for g, p in zip(gold, pred))
        fp = sum(g != label and p == label for g, p in zip(gold, pred))
        fn = sum(g == label and p != label for g, p in zip(gold, pred))
        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn)
        scores.append(_safe_div(2 * precision * recall, precision + recall))
    return sum(scores) / len(scores) if scores else 0.0


def _multilabel_micro(gold: list[set[str]], pred: list[set[str]]) -> dict[str, float]:
    tp = sum(len(g & p) for g, p in zip(gold, pred))
    fp = sum(len(p - g) for g, p in zip(gold, pred))
    fn = sum(len(g - p) for g, p in zip(gold, pred))
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = _safe_div(2 * precision * recall, precision + recall)
    return {"micro_precision": precision, "micro_recall": recall, "micro_f1": f1}


def _threshold_pass(metrics: dict[str, float], thresholds: dict[str, Any],
                    denominators: dict[str, int] | None = None,
                    minimum_denominators: dict[str, int] | None = None) -> tuple[bool, list[dict[str, Any]]]:
    checks = []
    passed = True
    for metric, rule in thresholds.items():
        actual = float(metrics.get(metric, float("nan")))
        if "min" in rule:
            ok = actual >= float(rule["min"])
            expected = {"min": rule["min"]}
        elif "max" in rule:
            ok = actual <= float(rule["max"])
            expected = {"max": rule["max"]}
        else:
            ok = False
            expected = rule
        passed = passed and ok
        checks.append({"metric": metric, "actual": actual, "expected": expected, "passed": ok})

    denominators = denominators or {}
    for name, minimum in (minimum_denominators or {}).items():
        actual = int(denominators.get(name, 0))
        ok = actual >= int(minimum)
        passed = passed and ok
        checks.append({
            "metric": f"{name}_denominator",
            "actual": actual,
            "expected": {"min": int(minimum)},
            "passed": ok,
        })
    return passed, checks


def evaluate_holdout(root: Path, spec_path: Path, freeze_manifest: Path, predictions_dir: Path,
                     out_path: Path, consume: bool = True, holdout_key_path: Path | None = None) -> dict[str, Any]:
    verification = verify_freeze(root, freeze_manifest)
    if not verification["verified"]:
        raise ValueError("cannot evaluate: freeze verification failed")
    spec = load_json(spec_path)
    freeze_id = verification["freeze_id"]
    require_seal = spec.get("qualification", {}).get("require_sealed_holdout_gold") is True
    holdout_key = None
    if require_seal:
        if holdout_key_path is None:
            raise ValueError("sealed final holdout evaluation requires --holdout-key-file")
        holdout_key = load_holdout_key(holdout_key_path)
    access_marker = root / "artifacts" / "HOLDOUT_ACCESSED.json"
    model_lock_path = root / "artifacts" / "MODEL_LOCK.json"
    if not model_lock_path.exists():
        raise ValueError("final holdout evaluation requires MODEL_LOCK.json")
    model_lock = load_json(model_lock_path)
    if model_lock.get("freeze_id") != freeze_id:
        raise ValueError("MODEL_LOCK freeze_id does not match the verified benchmark freeze")
    if model_lock.get("freeze_anchor_sha256") != verification.get("anchor_sha256"):
        raise ValueError("MODEL_LOCK is not bound to the current detached freeze anchor")
    for required in ("system_commit", "model_artifact_sha256", "model_config_sha256", "generation_config_sha256"):
        if not isinstance(model_lock.get(required), str) or not model_lock.get(required):
            raise ValueError(f"MODEL_LOCK missing content-addressed field: {required}")
    model_lock_sha256 = sha256_file(model_lock_path)

    prediction_hashes = {}
    for b in spec["benchmarks"]:
        p = predictions_dir / f"{b['id']}.jsonl"
        if not p.exists():
            raise FileNotFoundError(p)
        prediction_hashes[b["id"]] = sha256_file(p)

    sealed_store_hashes = {}
    if require_seal:
        for b in spec["benchmarks"]:
            p = sealed_gold_path(root, b["id"])
            if not p.exists():
                raise FileNotFoundError(p)
            sealed_store_hashes[b["id"]] = sha256_file(p)

    if access_marker.exists():
        prior = load_json(access_marker)
        if prior.get("freeze_id") != freeze_id or prior.get("prediction_hashes") != prediction_hashes:
            raise RuntimeError("holdout already accessed for this campaign; new predictions require a new benchmark version/freeze")

    results = []
    all_pass = True
    for b in spec["benchmarks"]:
        bid = b["id"]
        rows = [r for r in load_jsonl(root / "benchmarks" / bid / "records.jsonl") if r.get("split") == "holdout"]
        if require_seal:
            assert holdout_key is not None
            gold_map = decrypt_gold_map(root, spec["campaign_id"], bid, rows, holdout_key)
        else:
            gold_map = {str(r["case_id"]): r["payload"]["gold"] for r in rows}
        preds = load_jsonl(predictions_dir / f"{bid}.jsonl")
        pred_map = {str(p["case_id"]): p for p in preds}
        if len(pred_map) != len(preds):
            raise ValueError(f"{bid}: duplicate prediction case_id")
        expected_ids = {str(r["case_id"]) for r in rows}
        if set(pred_map) != expected_ids:
            missing = sorted(expected_ids - set(pred_map))
            extra = sorted(set(pred_map) - expected_ids)
            raise ValueError(f"{bid}: prediction case IDs mismatch; missing={missing[:5]} extra={extra[:5]}")

        contract = b["evaluation"]
        task = contract["task_type"]
        metrics: dict[str, float] = {}
        denominators: dict[str, int] = {}
        allowed_labels = set(contract.get("labels", []))
        if task == "multilabel":
            gold = [set(gold_map[str(r["case_id"])]["labels"]) for r in rows]
            pred = [set(pred_map[str(r["case_id"])]["prediction"]["labels"]) for r in rows]
            if any(not p.issubset(allowed_labels) for p in pred):
                raise ValueError(f"{bid}: prediction contains label outside preregistered label set")
            metrics.update(_multilabel_micro(gold, pred))
            metrics["exact_accuracy"] = _safe_div(sum(g == p for g, p in zip(gold, pred)), len(gold))
        elif task == "classification":
            labels = list(contract["labels"])
            gold = [str(gold_map[str(r["case_id"])]["label"]) for r in rows]
            pred = [str(pred_map[str(r["case_id"])]["prediction"]["label"]) for r in rows]
            if any(p not in allowed_labels for p in pred):
                raise ValueError(f"{bid}: prediction contains label outside preregistered label set")
            metrics["accuracy"] = _safe_div(sum(g == p for g, p in zip(gold, pred)), len(gold))
            metrics["macro_f1"] = _macro_f1(gold, pred, labels)
        else:
            raise ValueError(f"unsupported task_type: {task}")

        safety = contract.get("safety_metrics", {})
        if "unsafe_merge" in safety:
            cfg = safety["unsafe_merge"]
            num = den = 0
            for r in rows:
                g = str(gold_map[str(r["case_id"])]["label"])
                p = str(pred_map[str(r["case_id"])]["prediction"]["label"])
                if g in cfg["negative_gold_labels"]:
                    den += 1
                    if p in cfg["merge_prediction_labels"]:
                        num += 1
            denominators["unsafe_merge"] = den
            metrics["unsafe_merge_rate"] = _safe_div(num, den)
        if "direction" in safety:
            num = den = 0
            for r in rows:
                gd = gold_map[str(r["case_id"])].get("direction")
                if gd is None:
                    continue
                den += 1
                pd = pred_map[str(r["case_id"])]["prediction"].get("direction")
                if pd != gd:
                    num += 1
            denominators["direction"] = den
            metrics["direction_error_rate"] = _safe_div(num, den)
        if "scope_collapse" in safety:
            cfg = safety["scope_collapse"]
            num = den = 0
            for r in rows:
                g = str(gold_map[str(r["case_id"])]["label"])
                p = str(pred_map[str(r["case_id"])]["prediction"]["label"])
                if g in cfg["protected_gold_labels"]:
                    den += 1
                    if p in cfg["forbidden_prediction_labels"]:
                        num += 1
            denominators["scope_collapse"] = den
            metrics["scope_collapse_rate"] = _safe_div(num, den)
        if safety.get("provenance_preservation"):
            vals = []
            for r in rows:
                provenance = pred_map[str(r["case_id"])]["prediction"].get("provenance")
                ok = (
                    isinstance(provenance, dict)
                    and sorted(str(x) for x in provenance.get("source_ids", []))
                        == sorted(str(x) for x in r.get("source_ids", []))
                    and provenance.get("family_id") == r.get("family_id")
                )
                vals.append(ok)
            denominators["provenance_preservation"] = len(vals)
            metrics["provenance_preservation_rate"] = _safe_div(sum(vals), len(vals))

        passed, checks = _threshold_pass(
            metrics,
            contract["thresholds"],
            denominators,
            contract.get("minimum_denominators"),
        )
        all_pass = all_pass and passed
        results.append({
            "benchmark_id": bid,
            "holdout_count": len(rows),
            "metrics": {k: round(v, 6) for k, v in sorted(metrics.items())},
            "threshold_checks": checks,
            "safety_denominators": denominators,
            "passed": passed,
        })

    report = {
        "campaign_id": spec["campaign_id"],
        "freeze_id": freeze_id,
        "model_lock_sha256": model_lock_sha256,
        "prediction_hashes": prediction_hashes,
        "sealed_holdout": ({
            "key_id": key_id(holdout_key),
            "store_hashes": sealed_store_hashes,
        } if require_seal and holdout_key is not None else None),
        "benchmarks": results,
        "all_benchmarks_passed": all_pass,
    }
    if holdout_key is None:
        raise ValueError("final evaluation attestation requires sealed holdout key")
    report["evaluation_attestation_hmac_sha256"] = hmac.new(
        holdout_key, canonical_json_bytes(report), hashlib.sha256
    ).hexdigest()
    write_json(out_path, report)
    if consume and not access_marker.exists():
        write_json(access_marker, {
            "campaign_id": spec["campaign_id"],
            "freeze_id": freeze_id,
            "model_lock_sha256": model_lock_sha256,
            "prediction_hashes": prediction_hashes,
            "sealed_store_hashes": sealed_store_hashes,
            "holdout_key_id": key_id(holdout_key) if holdout_key is not None else None,
            "evaluation_report_sha256": sha256_file(out_path),
            "policy": "one-shot final holdout; replay allowed only for byte-identical predictions",
        })
    return report
