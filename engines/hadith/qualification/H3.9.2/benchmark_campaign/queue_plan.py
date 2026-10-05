from __future__ import annotations

from pathlib import Path
from typing import Any

from .core import load_json, write_json


RESERVE_SLOTS_PER_PRIMARY = 1


def _balanced_quotas(sources: list[str], total: int) -> list[dict[str, Any]]:
    if not sources:
        if total:
            raise ValueError("cannot allocate non-zero quota to an empty source pool")
        return []
    ordered = list(sources)
    q, r = divmod(total, len(ordered))
    return [
        {"anchor_source_id": sid, "target_cases": q + (1 if i < r else 0)}
        for i, sid in enumerate(ordered)
    ]


def build_curation_queue_plan(root: Path, spec: dict[str, Any], out_path: Path | None = None) -> dict[str, Any]:
    plan_path = root / "config" / "curation-plan.json"
    if not plan_path.exists():
        raise FileNotFoundError(plan_path)
    plan = load_json(plan_path)
    if plan.get("campaign_id") != spec.get("campaign_id"):
        raise ValueError("curation plan campaign_id mismatch")

    out: dict[str, Any] = {
        "campaign_id": spec["campaign_id"],
        "purpose": "operational curation quotas only; quotas never create or infer gold labels",
        "anchor_rule": "Each case is counted once against an operational anchor source, but source_ids must enumerate every canonical source used by the case.",
        "candidate_reserve_policy": {
            "reserve_slots_per_primary": RESERVE_SLOTS_PER_PRIMARY,
            "rule": (
                "Primary record quotas remain exact. Reserve candidate slots are "
                "distinct deterministic source-window opportunities and may replace "
                "only unusable primary candidate slots; they do not erase or bypass "
                "adjudication-required outcomes."
            ),
            "primary_slot_prefix_preserved": True,
        },
        "benchmarks": [],
    }
    total_target = 0
    for b in spec["benchmarks"]:
        bp = plan.get("benchmarks", {}).get(b["id"])
        if not isinstance(bp, dict):
            raise ValueError(f"curation plan missing benchmark: {b['id']}")
        hold = list(bp.get("holdout_source_pool", []))
        non = list(bp.get("non_holdout_source_pool", []))
        if set(hold) & set(non):
            raise ValueError(f"{b['id']}: source pools overlap")
        hold_target = int(b["target_holdout"])
        non_target = int(b["target_development"]) + int(b["target_validation"])
        hold_q = _balanced_quotas(hold, hold_target)
        non_q = _balanced_quotas(non, non_target)
        item = {
            "benchmark_id": b["id"],
            "milestone": b.get("milestone"),
            "target_total": b["target_total"],
            "holdout": {
                "target": hold_target,
                "source_pool": hold,
                "anchor_quotas": hold_q,
                "minimum_unique_families": b["min_holdout_families"],
                "gold_visibility": "custodian-only before sealing; never exposed on developer/tuning surface",
            },
            "non_holdout": {
                "target": non_target,
                "development_after_split": b["target_development"],
                "validation_after_split": b["target_validation"],
                "source_pool": non,
                "anchor_quotas": non_q,
                "minimum_unique_families": max(0, int(b["min_unique_families"]) - int(b["min_holdout_families"])),
            },
            "constraints": [
                "No case may bridge global holdout and non-holdout source partitions.",
                "family_id must represent the semantic family, not a wording/template bucket.",
                "Candidate discovery does not create a qualification label.",
                "Every source excerpt must be verified verbatim against the pinned local source cache.",
            ],
        }
        if b["id"] in {"cross-witness-identity", "report-family-identity"}:
            item["constraints"].append("All sources in a comparison/report-family graph must remain wholly inside one partition.")
        out["benchmarks"].append(item)
        total_target += int(b["target_total"])
    out["total_target"] = total_target
    out["total_candidate_slots"] = total_target * (1 + RESERVE_SLOTS_PER_PRIMARY)
    out["pending_cases"] = total_target
    out["completed_cases"] = 0
    if out_path is not None:
        write_json(out_path, out)
    return out
