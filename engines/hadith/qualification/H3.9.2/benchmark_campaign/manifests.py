from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .core import load_jsonl, write_json
from .holdout_seal import sealed_gold_path, sealed_store_descriptor
from .validate import validate_campaign


def build_holdout_manifest(root: Path, spec: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"campaign_id": spec["campaign_id"], "benchmarks": []}
    for b in spec["benchmarks"]:
        records = load_jsonl(root / "benchmarks" / b["id"] / "records.jsonl")
        rows = [
            {
                "case_id": r.get("case_id"),
                "source_ids": r.get("source_ids"),
                "family_id": r.get("family_id"),
                "content_fingerprint": r.get("content_fingerprint"),
                "gold_status": r.get("gold_status"),
            }
            for r in records if r.get("split") == "holdout"
        ]
        item = {"benchmark_id": b["id"], "count": len(rows), "records": rows}
        if spec.get("qualification", {}).get("require_sealed_holdout_gold") is True:
            public_rows = [r for r in records if r.get("split") == "holdout"]
            sealed_path = sealed_gold_path(root, b["id"])
            if sealed_path.exists():
                item["sealed_gold"] = sealed_store_descriptor(root, spec["campaign_id"], b["id"], public_rows)
            else:
                item["sealed_gold"] = {
                    "present": False,
                    "path": str(sealed_path.relative_to(root)),
                    "reason": "benchmark holdout has not been populated/sealed yet",
                }
        out["benchmarks"].append(item)
    return out


def build_provenance_manifest(root: Path, spec: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"campaign_id": spec["campaign_id"], "benchmarks": []}
    for b in spec["benchmarks"]:
        records = load_jsonl(root / "benchmarks" / b["id"] / "records.jsonl")
        source_counts: Counter[str] = Counter()
        family_counts: Counter[str] = Counter()
        gold_counts: Counter[str] = Counter()
        source_splits: dict[str, set[str]] = defaultdict(set)
        family_splits: dict[str, set[str]] = defaultdict(set)
        for r in records:
            sources = r.get("source_ids", [])
            family = str(r.get("family_id", ""))
            split = str(r.get("split", ""))
            gold = str(r.get("gold_status", ""))
            if isinstance(sources, list):
                for source in sources:
                    source = str(source)
                    source_counts[source] += 1
                    source_splits[source].add(split)
            family_counts[family] += 1
            gold_counts[gold] += 1
            family_splits[family].add(split)
        out["benchmarks"].append({
            "benchmark_id": b["id"],
            "sources": [
                {"source_id": k, "count": source_counts[k], "splits": sorted(source_splits[k])}
                for k in sorted(source_counts) if k
            ],
            "families": [
                {"family_id": k, "count": family_counts[k], "splits": sorted(family_splits[k])}
                for k in sorted(family_counts) if k
            ],
            "gold_status_counts": dict(sorted(gold_counts.items())),
        })
    return out


def build_disjointness_report(root: Path, spec: dict[str, Any]) -> dict[str, Any]:
    validation = validate_campaign(root, spec)
    no_overlap = not validation.get("global_violations") and all(
        b["source_disjoint"] and b["family_disjoint"] and b["fingerprint_disjoint"]
        for b in validation["benchmarks"]
    )
    return {
        "campaign_id": spec["campaign_id"],
        "all_disjoint": no_overlap,
        "population_complete": validation["all_benchmarks_qualified"],
        "qualification_ready": bool(no_overlap and validation["all_benchmarks_qualified"]),
        "global_disjointness": validation.get("global_disjointness", {}),
        "global_violations": validation.get("global_violations", []),
        "benchmarks": [
            {
                "benchmark_id": b["benchmark_id"],
                "source_disjoint": b["source_disjoint"],
                "family_disjoint": b["family_disjoint"],
                "fingerprint_disjoint": b["fingerprint_disjoint"],
                "leakage_violations": [
                    v for v in b["violations"] if str(v["code"]).startswith("leakage.")
                ],
            }
            for b in validation["benchmarks"]
        ],
    }


def emit_campaign_manifests(root: Path, spec: dict[str, Any], artifacts_dir: Path) -> dict[str, Path]:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "holdout": artifacts_dir / "HOLDOUT_MANIFEST.json",
        "provenance": artifacts_dir / "PROVENANCE_MANIFEST.json",
        "disjointness": artifacts_dir / "DISJOINTNESS_REPORT.json",
    }
    write_json(paths["holdout"], build_holdout_manifest(root, spec))
    write_json(paths["provenance"], build_provenance_manifest(root, spec))
    write_json(paths["disjointness"], build_disjointness_report(root, spec))
    return paths
