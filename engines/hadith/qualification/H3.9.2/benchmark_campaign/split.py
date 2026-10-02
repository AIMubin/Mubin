from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core import dump_jsonl, load_json, load_jsonl, write_json
from .holdout_seal import (load_holdout_key, seal_holdout_rows, sealed_gold_path,
                           sealed_store_descriptor, validate_public_seal_binding)


@dataclass(frozen=True)
class Component:
    key: str
    indices: tuple[int, ...]


def _components(records: list[dict[str, Any]]) -> list[Component]:
    """Build connected components over source_id <-> family_id.

    Any records connected through either source or family must stay on the same side
    of the holdout boundary. This prevents 'disjoint' splits that are disjoint only
    because IDs were assigned at record granularity.
    """
    n = len(records)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            if ra < rb:
                parent[rb] = ra
            else:
                parent[ra] = rb

    by_source: dict[str, list[int]] = defaultdict(list)
    by_family: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(records):
        source_ids = r.get("source_ids")
        if not isinstance(source_ids, list) or not source_ids:
            raise ValueError(f"record {r.get('case_id')!r}: source_ids must be a non-empty list before splitting")
        for source_id in source_ids:
            by_source[str(source_id)].append(i)
        by_family[str(r["family_id"])].append(i)
    for bucket in [*by_source.values(), *by_family.values()]:
        for i in bucket[1:]:
            union(bucket[0], i)

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    out = []
    for _, idxs in sorted(groups.items(), key=lambda kv: min(kv[1])):
        signature = min(str(records[i]["case_id"]) for i in idxs)
        out.append(Component(signature, tuple(sorted(idxs))))
    return out


def _exact_subset(components: list[Component], target: int) -> set[int] | None:
    """Deterministic subset-sum by component cardinality."""
    dp: dict[int, tuple[int, ...]] = {0: ()}
    for ci, comp in enumerate(components):
        size = len(comp.indices)
        for total, chosen in sorted(list(dp.items()), reverse=True):
            nxt = total + size
            if nxt > target or nxt in dp:
                continue
            dp[nxt] = (*chosen, ci)
    if target not in dp:
        return None
    return set(dp[target])


def build_splits(root: Path, spec: dict[str, Any], staging_dir: Path | None = None,
                 holdout_key_path: Path | None = None) -> dict[str, Any]:
    staging_dir = staging_dir or (root / "staging")
    curation_plan_path = root / "config" / "curation-plan.json"
    curation_plan = load_json(curation_plan_path) if curation_plan_path.exists() else None
    report: dict[str, Any] = {"campaign_id": spec["campaign_id"], "benchmarks": [], "all_feasible": True}
    require_seal = spec.get("qualification", {}).get("require_sealed_holdout_gold") is True
    holdout_key = load_holdout_key(holdout_key_path) if holdout_key_path is not None else None
    if require_seal and holdout_key is None:
        raise ValueError("sealed holdout policy requires --holdout-key-file when building splits")

    for b in spec["benchmarks"]:
        bid = b["id"]
        src = staging_dir / bid / "reviewed.jsonl"
        rows = load_jsonl(src)
        expected = b["target_total"]
        item: dict[str, Any] = {"benchmark_id": bid, "staging_count": len(rows)}
        if len(rows) != expected:
            item.update({"feasible": False, "reason": f"reviewed_count {len(rows)} != target_total {expected}"})
            report["all_feasible"] = False
            report["benchmarks"].append(item)
            continue

        comps = _components(rows)
        holdout_choice: set[int] | None
        if curation_plan is not None:
            bp = curation_plan.get("benchmarks", {}).get(bid)
            if not isinstance(bp, dict):
                item.update({"feasible": False, "reason": "benchmark missing from frozen curation plan"})
                report["all_feasible"] = False
                report["benchmarks"].append(item)
                continue
            hold_sources = set(bp.get("holdout_source_pool", []))
            non_sources = set(bp.get("non_holdout_source_pool", []))
            holdout_choice = set()
            mixed_component = None
            for ci, comp in enumerate(comps):
                srcs = set()
                for idx in comp.indices:
                    srcs.update(str(x) for x in rows[idx].get("source_ids", []))
                if not srcs:
                    mixed_component = {"component": ci, "reason": "no_sources"}
                    break
                in_hold = bool(srcs & hold_sources)
                in_non = bool(srcs & non_sources)
                outside = srcs - hold_sources - non_sources
                if outside or (in_hold and in_non):
                    mixed_component = {"component": ci, "sources": sorted(srcs), "outside": sorted(outside)}
                    break
                if in_hold:
                    holdout_choice.add(ci)
            if mixed_component is not None:
                item.update({"feasible": False, "reason": "component bridges frozen source partitions or uses unplanned source", "detail": mixed_component})
                report["all_feasible"] = False
                report["benchmarks"].append(item)
                continue
            planned_holdout = sum(len(comps[ci].indices) for ci in holdout_choice)
            if planned_holdout != b["target_holdout"]:
                item.update({"feasible": False, "reason": f"frozen source partition yields {planned_holdout} holdout records, expected {b['target_holdout']}"})
                report["all_feasible"] = False
                report["benchmarks"].append(item)
                continue
        else:
            holdout_choice = _exact_subset(comps, b["target_holdout"])
        if holdout_choice is None:
            item.update({
                "feasible": False,
                "reason": "no exact source/family-disjoint holdout partition at target cardinality",
                "component_sizes": [len(c.indices) for c in comps],
            })
            report["all_feasible"] = False
            report["benchmarks"].append(item)
            continue

        holdout_idxs: set[int] = set()
        for ci in holdout_choice:
            holdout_idxs.update(comps[ci].indices)
        non_holdout = [i for i in range(len(rows)) if i not in holdout_idxs]

        val_idxs = set(non_holdout[: b["target_validation"]])
        dev_idxs = set(non_holdout[b["target_validation"] :])
        if len(dev_idxs) != b["target_development"]:
            item.update({"feasible": False, "reason": "development cardinality mismatch after split"})
            report["all_feasible"] = False
            report["benchmarks"].append(item)
            continue

        assigned: list[dict[str, Any]] = []
        for i, r in enumerate(rows):
            x = dict(r)
            if i in holdout_idxs:
                x["split"] = "holdout"
            elif i in val_idxs:
                x["split"] = "validation"
            else:
                x["split"] = "development"
            assigned.append(x)

        seal_meta = None
        if require_seal:
            holdout_candidates = [r for r in assigned if r["split"] == "holdout"]
            assert holdout_key is not None
            has_plain = [isinstance(r.get("payload"), dict) and "gold" in r["payload"] for r in holdout_candidates]
            has_sealed = [isinstance(r.get("payload"), dict) and r["payload"].get("gold_sealed") is True and "gold" not in r["payload"] for r in holdout_candidates]
            if all(has_plain):
                seal_meta = seal_holdout_rows(root, spec["campaign_id"], bid, holdout_candidates, holdout_key)
                public_by_case = {str(r["case_id"]): r for r in seal_meta["public_rows"]}
                assigned = [public_by_case[str(r["case_id"])] if r["split"] == "holdout" else r for r in assigned]
            elif all(has_sealed):
                errors = validate_public_seal_binding(root, spec["campaign_id"], bid, holdout_candidates)
                if errors:
                    raise ValueError(f"{bid}: existing sealed staging does not match sealed store: {errors}")
                desc = sealed_store_descriptor(root, spec["campaign_id"], bid, holdout_candidates)
                seal_meta = {
                    "public_rows": holdout_candidates,
                    "sealed_path": sealed_gold_path(root, bid),
                    "sealed_sha256": desc["sha256"],
                    "key_id": desc["key_id"],
                    "holdout_count": desc["holdout_count"],
                    "public_index_sha256": desc["public_index_sha256"],
                }
            else:
                raise ValueError(f"{bid}: holdout staging mixes plaintext and sealed gold states")

        assigned.sort(key=lambda r: (r["split"], str(r["case_id"])))
        out = root / "benchmarks" / bid / "records.jsonl"
        dump_jsonl(out, assigned)
        if require_seal:
            staging_public = []
            for r in assigned:
                x = dict(r)
                x.pop("split", None)
                staging_public.append(x)
            dump_jsonl(src, staging_public)
        item.update({
            "feasible": True,
            "component_count": len(comps),
            "source_partition": "frozen_curation_plan" if curation_plan is not None else "deterministic_exact_subset",
            "counts": {
                "development": len(dev_idxs),
                "validation": len(val_idxs),
                "holdout": len(holdout_idxs),
            },
            "records_path": str(out.relative_to(root)),
            "holdout_gold": ({
                "sealed": True,
                "path": str(seal_meta["sealed_path"].relative_to(root)),
                "sha256": seal_meta["sealed_sha256"],
                "key_id": seal_meta["key_id"],
                "public_index_sha256": seal_meta["public_index_sha256"],
            } if seal_meta is not None else {"sealed": False}),
        })
        report["benchmarks"].append(item)

    write_json(root / "artifacts" / "SPLIT_REPORT.json", report)
    return report
