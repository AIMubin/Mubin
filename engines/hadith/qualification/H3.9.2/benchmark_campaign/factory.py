from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
import hashlib
import json
import re

from .core import canonical_json_bytes, dump_jsonl, load_json, load_jsonl, sha256_bytes, sha256_file, write_json
from .curation import seal_reviewed_record
from .source_cache import cache_filename, verify_cached_source, verify_source_cache
from .source_registry import load_source_registry, source_map


def _policy(root: Path) -> dict[str, Any]:
    return load_json(root / "config" / "factory-policy.json")


def _curation_plan(root: Path) -> dict[str, Any]:
    return load_json(root / "config" / "curation-plan.json")


def _quota_plan(root: Path) -> dict[str, Any]:
    return load_json(root / "config" / "curation-quotas.json")


def partition_source_ids(root: Path, partition: str) -> set[str]:
    if partition not in {"holdout", "non_holdout", "all"}:
        raise ValueError("partition must be holdout, non_holdout, or all")
    global_partition = _curation_plan(root).get("global_source_partition", {})
    holdout = set(global_partition.get("holdout", []))
    non_holdout = set(global_partition.get("non_holdout", []))
    if partition == "holdout":
        return holdout
    if partition == "non_holdout":
        return non_holdout
    return holdout | non_holdout


def _is_inside(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def enforce_partition_boundary(root: Path, partition: str, artifact_path: Path, custodian_mode: bool) -> None:
    if partition in {"holdout", "all"}:
        if not custodian_mode:
            raise ValueError("holdout-bearing operations require custodian_mode")
        if _is_inside(root, artifact_path):
            raise ValueError("holdout-bearing artifact paths must be outside the campaign checkout")


def _task_rows(path: Path) -> list[dict[str, Any]]:
    rows = load_jsonl(path)
    ids = [str(r.get("task_id", "")) for r in rows]
    if any(not x for x in ids):
        raise ValueError("every factory task requires a non-empty task_id")
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate factory task IDs")
    for row in rows:
        stored = row.get("task_fingerprint")
        unsigned = dict(row)
        unsigned.pop("task_fingerprint", None)
        expected = sha256_bytes(canonical_json_bytes(unsigned))
        if stored != expected:
            raise ValueError(f"factory task fingerprint mismatch: {row.get('task_id')}")
    return rows


def _task_partition(rows: list[dict[str, Any]]) -> str:
    partitions = {str(t.get("partition", "")) for t in rows}
    if not rows:
        return "empty"
    if partitions == {"holdout"}:
        return "holdout"
    if partitions == {"non_holdout"}:
        return "non_holdout"
    raise ValueError("do not mix holdout and non-holdout tasks in one factory operation")


def _validate_tasks_against_frozen_plan(
    root: Path,
    rows: list[dict[str, Any]],
    *,
    capacity_extension_path: Path | None = None,
    require_capacity_execution: bool = False,
) -> None:
    expected_plan = build_factory_plan(root)
    slots = {str(s["slot_id"]): s for s in expected_plan["slots"]}
    if capacity_extension_path is not None:
        from .capacity_extension import validate_frozen_capacity_extension

        extension = validate_frozen_capacity_extension(
            root,
            capacity_extension_path,
            rows,
            require_execution_enabled=require_capacity_execution,
        )
        for item in extension["extensions"]:
            slot = item["new_reserve_slot"]
            slot_id = str(slot["slot_id"])
            if slot_id in slots:
                raise ValueError(
                    f"capacity extension collides with frozen Factory slot: {slot_id}"
                )
            slots[slot_id] = slot
    cplan = _curation_plan(root)
    factory_policy = _policy(root)
    registry = source_map(load_source_registry(root))
    policy_fields = (
        "benchmark_id", "partition", "anchor_source_id", "task_type",
        "allowed_labels", "auto_promotion", "risk_tier", "visibility",
    )
    reserve_fields = (
        "candidate_slot_kind", "replacement_for_slot_id", "reserve_attempt",
    )
    for task in rows:
        slot_id = str(task.get("slot_id", ""))
        expected = slots.get(slot_id)
        if expected is None:
            raise ValueError(f"factory task references unknown frozen slot: {slot_id}")
        if task.get("task_id") != slot_id:
            raise ValueError(f"factory task_id must equal frozen slot_id: {slot_id}")
        for field in policy_fields:
            if task.get(field) != expected.get(field):
                raise ValueError(f"factory task {field} differs from frozen slot: {slot_id}")
        for field in reserve_fields:
            if task.get(field) != expected.get(field):
                raise ValueError(f"factory task {field} differs from frozen slot: {slot_id}")
        bid = expected["benchmark_id"]
        partition = expected["partition"]
        bp = cplan.get("benchmarks", {}).get(bid, {})
        pool_key = "holdout_source_pool" if partition == "holdout" else "non_holdout_source_pool"
        other_key = "non_holdout_source_pool" if partition == "holdout" else "holdout_source_pool"
        if task.get("allowed_source_pool") != bp.get(pool_key):
            raise ValueError(f"factory task allowed_source_pool differs from frozen plan: {slot_id}")
        if task.get("forbidden_source_pool") != bp.get(other_key):
            raise ValueError(f"factory task forbidden_source_pool differs from frozen plan: {slot_id}")
        expected_terms = list(factory_policy.get("benchmarks", {}).get(bid, {}).get("candidate_keywords", []))
        if task.get("retrieval_terms") != expected_terms:
            raise ValueError(f"factory task retrieval_terms differ from frozen policy: {slot_id}")
        retrieval = task.get("retrieval_scope")
        if not isinstance(retrieval, dict):
            raise ValueError(f"factory task retrieval_scope missing: {slot_id}")
        if retrieval.get("access_mode") != "full_partition_index":
            raise ValueError(f"factory task retrieval_scope mode mismatch: {slot_id}")
        if retrieval.get("partition") != partition:
            raise ValueError(f"factory task retrieval_scope partition mismatch: {slot_id}")
        if retrieval.get("source_ids") != bp.get(pool_key):
            raise ValueError(f"factory task retrieval_scope source pool mismatch: {slot_id}")
        for hash_field in ("segments_sha256", "index_manifest_sha256"):
            value = retrieval.get(hash_field)
            if not isinstance(value, str) or re.fullmatch(r"[a-f0-9]{64}", value) is None:
                raise ValueError(f"factory task retrieval_scope {hash_field} invalid: {slot_id}")
        seg = task.get("anchor_segment")
        if not isinstance(seg, dict):
            raise ValueError(f"factory task anchor_segment missing: {slot_id}")
        anchor = expected["anchor_source_id"]
        src = registry.get(anchor)
        if src is None or seg.get("source_id") != anchor or seg.get("source_blob_sha") != src.get("source_blob_sha"):
            raise ValueError(f"factory task anchor segment is not bound to frozen anchor source: {slot_id}")
        text = seg.get("text")
        if not isinstance(text, str) or seg.get("text_sha256") != hashlib.sha256(text.encode("utf-8")).hexdigest():
            raise ValueError(f"factory task anchor segment text hash mismatch: {slot_id}")
        locator = seg.get("locator")
        if not isinstance(locator, str) or not locator.startswith(f"gitblob:{src['source_blob_sha']}#char="):
            raise ValueError(f"factory task anchor segment locator mismatch: {slot_id}")


def _segment_text(text: str, max_chars: int, overlap: int) -> list[tuple[int, int, str]]:
    if max_chars < 512:
        raise ValueError("max_chars must be >= 512")
    if overlap < 0 or overlap >= max_chars // 2:
        raise ValueError("overlap must be >= 0 and < max_chars/2")
    if not text:
        return []
    out: list[tuple[int, int, str]] = []
    start = 0
    n = len(text)
    while start < n:
        hard_end = min(n, start + max_chars)
        end = hard_end
        if hard_end < n:
            floor = start + max_chars // 2
            newline = text.rfind("\n", floor, hard_end)
            if newline > start:
                end = newline + 1
        chunk = text[start:end]
        if chunk.strip():
            out.append((start, end, chunk))
        if end >= n:
            break
        next_start = max(0, end - overlap)
        if next_start <= start:
            next_start = end
        start = next_start
    return out


def build_source_index(root: Path, cache_dir: Path, out_dir: Path, partition: str = "non_holdout",
                       custodian_mode: bool = False, max_chars: int = 3200,
                       overlap: int = 320) -> dict[str, Any]:
    enforce_partition_boundary(root, partition, cache_dir, custodian_mode)
    enforce_partition_boundary(root, partition, out_dir, custodian_mode)
    source_ids = partition_source_ids(root, partition)
    check = verify_source_cache(root, cache_dir, allowed_source_ids=source_ids)
    if not check["all_verified"]:
        bad = [x["source_id"] for x in check["sources"] if not x.get("verified")]
        raise ValueError(f"source cache is incomplete or unverified: {bad}")

    registry = source_map(load_source_registry(root))
    segments: list[dict[str, Any]] = []
    per_source: Counter[str] = Counter()
    for source_id in sorted(source_ids):
        src = registry[source_id]
        cache_path = cache_dir / cache_filename(source_id)
        byte_check = verify_cached_source(cache_path, src)
        if not byte_check["verified"]:
            raise ValueError(f"pinned source cache hash mismatch: {source_id}")
        text = cache_path.read_text(encoding="utf-8", errors="strict")
        for start, end, chunk in _segment_text(text, max_chars, overlap):
            text_sha = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
            segment_id = sha256_bytes(canonical_json_bytes({
                "source_id": source_id,
                "source_blob_sha": src["source_blob_sha"],
                "char_start": start,
                "char_end": end,
                "text_sha256": text_sha,
            }))
            segments.append({
                "source_id": source_id,
                "source_blob_sha": src["source_blob_sha"],
                "segment_id": segment_id,
                "locator": f"gitblob:{src['source_blob_sha']}#char={start}:{end}",
                "char_start": start,
                "char_end": end,
                "text": chunk,
                "text_sha256": text_sha,
            })
            per_source[source_id] += 1

    out_dir.mkdir(parents=True, exist_ok=True)
    index_path = out_dir / "segments.jsonl"
    dump_jsonl(index_path, segments)
    manifest = {
        "partition": partition,
        "source_count": len(source_ids),
        "segment_count": len(segments),
        "segments_sha256": hashlib.sha256(index_path.read_bytes()).hexdigest(),
        "per_source": dict(sorted(per_source.items())),
        "source_cache_manifest": check,
    }
    write_json(out_dir / "INDEX_MANIFEST.json", manifest)
    return manifest


def build_factory_plan(root: Path, out_path: Path | None = None) -> dict[str, Any]:
    quotas = _quota_plan(root)
    spec = load_json(root / "config" / "benchmark-spec.json")
    bspec = {b["id"]: b for b in spec["benchmarks"]}
    policy = _policy(root)
    reserve_policy = quotas.get("candidate_reserve_policy", {})
    reserve_slots_per_primary = reserve_policy.get("reserve_slots_per_primary", 0)
    if reserve_slots_per_primary and reserve_policy.get("policy_version") != 1:
        raise ValueError("unsupported candidate reserve policy version")
    if reserve_slots_per_primary and reserve_policy.get("primary_slot_prefix_preserved") is not True:
        raise ValueError("reserve candidate policy must preserve the primary slot prefix")
    if (
        not isinstance(reserve_slots_per_primary, int)
        or isinstance(reserve_slots_per_primary, bool)
        or reserve_slots_per_primary < 0
        or reserve_slots_per_primary > 4
    ):
        raise ValueError("reserve_slots_per_primary must be an integer in [0, 4]")

    def make_slot(
        bid: str,
        bp: dict[str, Any],
        sb: dict[str, Any],
        partition_name: str,
        sid: str,
        ordinal: int,
        *,
        reserve_attempt: int | None = None,
    ) -> dict[str, Any]:
        primary_slot_id = f"{bid}:{partition_name}:{sid}:{ordinal:04d}"
        slot = {
            "slot_id": primary_slot_id,
            "benchmark_id": bid,
            "partition": partition_name,
            "anchor_source_id": sid,
            "ordinal": ordinal,
            "task_type": sb["evaluation"]["task_type"],
            "allowed_labels": sb["evaluation"]["labels"],
            "auto_promotion": bp["auto_promotion"],
            "risk_tier": bp["risk_tier"],
            "visibility": "custodian_only" if partition_name == "holdout" else "development_safe",
        }
        if reserve_attempt is not None:
            slot["slot_id"] = (
                f"{primary_slot_id}:reserve:{reserve_attempt:02d}"
            )
            slot["candidate_slot_kind"] = "reserve"
            slot["replacement_for_slot_id"] = primary_slot_id
            slot["reserve_attempt"] = reserve_attempt
        return slot

    slots: list[dict[str, Any]] = []

    # Primary slots are generated first and remain byte-for-semantic identical to
    # the original 1,280-slot plan. This preserves all pre-existing primary slot
    # IDs, hashes, task offsets, and task fingerprints.
    for q in quotas["benchmarks"]:
        bid = q["benchmark_id"]
        bp = policy["benchmarks"][bid]
        sb = bspec[bid]
        for partition_key, partition_name in (("non_holdout", "non_holdout"), ("holdout", "holdout")):
            for anchor in q[partition_key]["anchor_quotas"]:
                sid = anchor["anchor_source_id"]
                for ordinal in range(1, int(anchor["target_cases"]) + 1):
                    slots.append(
                        make_slot(bid, bp, sb, partition_name, sid, ordinal)
                    )

    primary_slot_count = len(slots)
    primary_holdout_slots = sum(
        1 for slot in slots if slot["partition"] == "holdout"
    )
    primary_non_holdout_slots = sum(
        1 for slot in slots if slot["partition"] == "non_holdout"
    )
    if primary_slot_count != int(quotas["total_target"]):
        raise ValueError("primary factory slot count does not match frozen curation target")

    # Reserve slots are distinct source-window opportunities. They are appended
    # after the complete primary prefix so offsets 0..895 on the non-holdout
    # surface remain unchanged. Each reserve is explicitly linked to the primary
    # slot it may replace; adjudication-required primary outcomes are not erased.
    if reserve_slots_per_primary:
        for q in quotas["benchmarks"]:
            bid = q["benchmark_id"]
            bp = policy["benchmarks"][bid]
            sb = bspec[bid]
            for partition_key, partition_name in (("non_holdout", "non_holdout"), ("holdout", "holdout")):
                for anchor in q[partition_key]["anchor_quotas"]:
                    sid = anchor["anchor_source_id"]
                    for ordinal in range(1, int(anchor["target_cases"]) + 1):
                        for reserve_attempt in range(1, reserve_slots_per_primary + 1):
                            slots.append(
                                make_slot(
                                    bid, bp, sb, partition_name, sid, ordinal,
                                    reserve_attempt=reserve_attempt,
                                )
                            )

    candidate_holdout_slots = sum(
        1 for slot in slots if slot["partition"] == "holdout"
    )
    candidate_non_holdout_slots = sum(
        1 for slot in slots if slot["partition"] == "non_holdout"
    )
    plan = {
        "campaign_id": spec["campaign_id"],
        "factory_version": 1,
        "slot_count": len(slots),
        "target_total": quotas["total_target"],
        "primary_slot_count": primary_slot_count,
        "reserve_slot_count": len(slots) - primary_slot_count,
        "reserve_slots_per_primary": reserve_slots_per_primary,
        "primary_holdout_slots": primary_holdout_slots,
        "primary_non_holdout_slots": primary_non_holdout_slots,
        # Legacy aliases remain for callers that predate candidate reserves.
        "holdout_slots": primary_holdout_slots,
        "non_holdout_slots": primary_non_holdout_slots,
        "candidate_holdout_slots": candidate_holdout_slots,
        "candidate_non_holdout_slots": candidate_non_holdout_slots,
        "slots": slots,
    }
    expected_candidate_total = int(quotas.get(
        "total_candidate_slots",
        int(quotas["total_target"]) * (1 + reserve_slots_per_primary),
    ))
    if plan["slot_count"] != expected_candidate_total:
        raise ValueError("candidate factory slot count does not match frozen reserve policy")
    if out_path is not None:
        write_json(out_path, plan)
    return plan


def _segment_score(text: str, keywords: list[str]) -> int:
    return sum(text.count(k) for k in keywords if k)


def build_factory_tasks(
    root: Path,
    plan_path: Path,
    index_dir: Path,
    out_path: Path,
    partition: str = "non_holdout",
    custodian_mode: bool = False,
    capacity_extension_path: Path | None = None,
) -> dict[str, Any]:
    if partition not in {"holdout", "non_holdout"}:
        raise ValueError("factory tasks are built one partition at a time")
    enforce_partition_boundary(root, partition, index_dir, custodian_mode)
    enforce_partition_boundary(root, partition, out_path, custodian_mode)
    plan = load_json(plan_path)
    expected_plan = build_factory_plan(root)
    if canonical_json_bytes(plan) != canonical_json_bytes(expected_plan):
        raise ValueError("factory plan does not match the frozen quotas/spec/policy")
    if capacity_extension_path is not None:
        if partition != "non_holdout":
            raise ValueError("schema-28 capacity extension is non_holdout only")
        from .capacity_extension import validate_frozen_capacity_extension

        extension = validate_frozen_capacity_extension(
            root,
            capacity_extension_path,
            require_execution_enabled=True,
        )
        plan = json.loads(json.dumps(plan, ensure_ascii=False))
        existing_ids = {str(slot["slot_id"]) for slot in plan["slots"]}
        for item in extension["extensions"]:
            slot = item["new_reserve_slot"]
            slot_id = str(slot["slot_id"])
            if slot_id in existing_ids:
                raise ValueError(
                    f"capacity extension collides with frozen candidate plan: {slot_id}"
                )
            plan["slots"].append(slot)
            existing_ids.add(slot_id)
    policy = _policy(root)
    cplan = _curation_plan(root)
    index_manifest_path = index_dir / "INDEX_MANIFEST.json"
    if not index_manifest_path.exists():
        raise FileNotFoundError(index_manifest_path)
    index_manifest = load_json(index_manifest_path)
    segments_path = index_dir / "segments.jsonl"
    if index_manifest.get("partition") != partition:
        raise ValueError("source index partition does not match requested task partition")
    if index_manifest.get("segments_sha256") != hashlib.sha256(segments_path.read_bytes()).hexdigest():
        raise ValueError("source index segments hash mismatch")
    segments = load_jsonl(segments_path)
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for seg in segments:
        by_source[str(seg["source_id"])].append(seg)

    tasks: list[dict[str, Any]] = []
    usage: Counter[str] = Counter()
    primary_segment_by_slot: dict[str, str] = {}
    reserve_segments_by_primary: dict[str, set[str]] = defaultdict(set)
    for slot in [s for s in plan["slots"] if s["partition"] == partition]:
        bid = slot["benchmark_id"]
        anchor = slot["anchor_source_id"]
        bp = policy["benchmarks"][bid]
        candidates = by_source.get(anchor, [])
        if not candidates:
            raise ValueError(f"source index has no segments for anchor source: {anchor}")
        ranked = sorted(
            candidates,
            key=lambda x: (-_segment_score(str(x["text"]), bp.get("candidate_keywords", [])), str(x["segment_id"])),
        )
        ranked_index = usage[anchor] % len(ranked)
        if slot.get("candidate_slot_kind") == "reserve":
            primary_slot_id = slot.get("replacement_for_slot_id")
            if not isinstance(primary_slot_id, str) or not primary_slot_id:
                raise ValueError("reserve slot requires replacement_for_slot_id")
            primary_segment_id = primary_segment_by_slot.get(primary_slot_id)
            if primary_segment_id is None:
                raise ValueError(
                    "reserve slot must follow its primary slot in the candidate plan"
                )
            forbidden_segment_ids = {
                primary_segment_id,
                *reserve_segments_by_primary[primary_slot_id],
            }
            checked = 0
            while (
                str(ranked[ranked_index]["segment_id"]) in forbidden_segment_ids
                and checked < len(ranked)
            ):
                usage[anchor] += 1
                ranked_index = usage[anchor] % len(ranked)
                checked += 1
            if str(ranked[ranked_index]["segment_id"]) in forbidden_segment_ids:
                raise ValueError(
                    f"source lacks a distinct reserve segment for frozen slot: {primary_slot_id}"
                )
        seg = ranked[ranked_index]
        usage[anchor] += 1
        if slot.get("candidate_slot_kind") == "reserve":
            reserve_segments_by_primary[str(slot["replacement_for_slot_id"])].add(
                str(seg["segment_id"])
            )
        else:
            primary_segment_by_slot[str(slot["slot_id"])] = str(seg["segment_id"])
        pool_key = "holdout_source_pool" if partition == "holdout" else "non_holdout_source_pool"
        other_key = "non_holdout_source_pool" if partition == "holdout" else "holdout_source_pool"
        bplan = cplan["benchmarks"][bid]
        task = {
            "task_id": slot["slot_id"],
            "slot_id": slot["slot_id"],
            "benchmark_id": bid,
            "partition": partition,
            "visibility": slot["visibility"],
            "risk_tier": slot["risk_tier"],
            "auto_promotion": slot["auto_promotion"],
            "anchor_source_id": anchor,
            "allowed_source_pool": bplan[pool_key],
            "forbidden_source_pool": bplan[other_key],
            "allowed_labels": slot["allowed_labels"],
            "task_type": slot["task_type"],
            "retrieval_terms": list(bp.get("candidate_keywords", [])),
            "retrieval_scope": {
                "access_mode": "full_partition_index",
                "partition": partition,
                "source_ids": bplan[pool_key],
                "segments_sha256": index_manifest["segments_sha256"],
                "index_manifest_sha256": hashlib.sha256(
                    index_manifest_path.read_bytes()
                ).hexdigest(),
            },
            "anchor_segment": seg,
            "instructions": {
                "contract": "agents/CURATOR_CONTRACT.md",
                "require_human_authored_support": True,
                "no_ai_opinion_as_gold": True,
                "return_no_candidate_when_unsupported": True,
            },
        }
        for field in (
            "candidate_slot_kind", "replacement_for_slot_id", "reserve_attempt",
        ):
            if field in slot:
                task[field] = slot[field]
        task["task_fingerprint"] = sha256_bytes(canonical_json_bytes(task))
        tasks.append(task)
    dump_jsonl(out_path, tasks)
    return {
        "partition": partition,
        "task_count": len(tasks),
        "tasks_sha256": hashlib.sha256(out_path.read_bytes()).hexdigest(),
        "source_usage": dict(sorted(usage.items())),
    }


_ANSWER_BEARING_INPUT_KEYS = {
    "gold", "label", "labels", "answer", "answers", "verdict", "judgment", "judgement",
    "grade", "ruling", "classification", "prediction", "target", "support", "supports",
}


def _canonical_model_family(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _blind_input_error(value: Any, task: dict[str, Any], path: str = "input") -> str | None:
    allowed_labels = {_canonical_model_family(str(x)) for x in task.get("allowed_labels", [])}
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = str(key).strip().casefold().replace("-", "_").replace(".", "_")
            if normalized_key == "allowed_labels":
                if child != task.get("allowed_labels"):
                    return f"allowed_labels differs from task label contract at {path}.{key}"
                # The full preregistered label vocabulary is already exposed to the
                # Verifier as task metadata. An exact duplicate does not reveal the
                # Curator's selected gold and must not be mistaken for answer leakage.
                continue
            tokens = {x for x in normalized_key.split("_") if x}
            if normalized_key in _ANSWER_BEARING_INPUT_KEYS or tokens & _ANSWER_BEARING_INPUT_KEYS:
                return f"answer-bearing key at {path}.{key}"
            err = _blind_input_error(child, task, f"{path}.{key}")
            if err is not None:
                return err
        return None
    if isinstance(value, list):
        for i, child in enumerate(value):
            err = _blind_input_error(child, task, f"{path}[{i}]")
            if err is not None:
                return err
        return None
    if isinstance(value, str) and _canonical_model_family(value) in allowed_labels:
        return f"explicit benchmark label value at {path}"
    return None


def _verifier_task_from_curator(
    task: dict[str, Any],
    response: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    """Project a Curator candidate into the exact blinded Verifier task.

    Returns (task, None) for a safe candidate, (None, blindness_reason) for an
    unsafe candidate, and raises on malformed candidate structure. This helper
    is shared by live preparation and historical evidence validation so a
    stored Verifier task can be checked against the exact projection that
    should have been sent.
    """
    if response.get("status") != "candidate":
        return None, None
    tid = str(task["task_id"])
    candidate = response.get("candidate")
    if not isinstance(candidate, dict):
        raise ValueError(f"candidate payload missing: {tid}")
    payload = candidate.get("payload")
    if not isinstance(payload, dict) or "input" not in payload:
        raise ValueError(f"candidate payload.input missing: {tid}")
    blind_error = _blind_input_error(payload["input"], task)
    if blind_error is not None:
        return None, blind_error
    verifier_task = {
        "task_id": tid,
        "task_fingerprint": task["task_fingerprint"],
        "benchmark_id": task["benchmark_id"],
        "partition": task["partition"],
        "visibility": task["visibility"],
        "allowed_source_pool": task["allowed_source_pool"],
        "forbidden_source_pool": task["forbidden_source_pool"],
        "allowed_labels": task["allowed_labels"],
        "task_type": task["task_type"],
        "retrieval_terms": task["retrieval_terms"],
        "anchor_source_id": task["anchor_source_id"],
        "retrieval_scope": task["retrieval_scope"],
        "anchor_segment": task["anchor_segment"],
        "candidate_input": payload["input"],
        "instructions": {
            "contract": "agents/VERIFIER_CONTRACT.md",
            "blind_to_curator_gold": True,
            "blind_to_curator_supports": True,
            "independent_source_check": True,
        },
    }
    unsigned_verifier_task = dict(verifier_task)
    verifier_task["verifier_task_fingerprint"] = sha256_bytes(
        canonical_json_bytes(unsigned_verifier_task)
    )
    return verifier_task, None


def prepare_verifier_tasks(
    root: Path,
    tasks_path: Path,
    curator_responses_path: Path,
    out_path: Path,
    partition: str = "non_holdout",
    custodian_mode: bool = False,
    capacity_extension_path: Path | None = None,
) -> dict[str, Any]:
    if partition not in {"holdout", "non_holdout"}:
        raise ValueError("partition must be holdout or non_holdout")
    if partition == "holdout":
        for p in (tasks_path, curator_responses_path, out_path):
            enforce_partition_boundary(root, "holdout", p, custodian_mode)
    task_rows = _task_rows(tasks_path)
    actual_partition = _task_partition(task_rows)
    if actual_partition != partition:
        raise ValueError(f"factory task partition {actual_partition} does not match requested {partition}")
    _validate_tasks_against_frozen_plan(
        root,
        task_rows,
        capacity_extension_path=capacity_extension_path,
        require_capacity_execution=capacity_extension_path is not None,
    )
    tasks = {str(t["task_id"]): t for t in task_rows}
    responses = load_jsonl(curator_responses_path)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    input_candidates = 0
    blindness_rejections = 0
    for response in responses:
        tid = str(response.get("task_id", ""))
        if tid in seen:
            raise ValueError(f"duplicate curator response for task: {tid}")
        seen.add(tid)
        task = tasks.get(tid)
        if task is None:
            raise ValueError(f"curator response references unknown task: {tid}")
        if response.get("task_fingerprint") != task.get("task_fingerprint"):
            raise ValueError(f"curator response task fingerprint mismatch: {tid}")
        if response.get("status") != "candidate":
            continue
        input_candidates += 1
        verifier_task, blind_error = _verifier_task_from_curator(task, response)
        if blind_error is not None:
            if partition == "holdout":
                raise ValueError(
                    f"candidate payload.input violates verifier blindness: {tid}: {blind_error}"
                )
            # On the non-holdout collection surface this is a candidate-quality
            # failure, not an orchestration-integrity failure. Keep the Curator
            # response for reconciliation/adjudication, but do not expose the
            # unsafe input to the independent Verifier.
            blindness_rejections += 1
            continue
        if verifier_task is None:
            raise ValueError(f"candidate did not produce verifier task: {tid}")
        out.append(verifier_task)
    dump_jsonl(out_path, out)
    return {
        "input_candidates": input_candidates,
        "verifier_tasks": len(out),
        "rejected_candidates": blindness_rejections,
        "rejection_counts": (
            {"candidate_input_blindness": blindness_rejections}
            if blindness_rejections
            else {}
        ),
        "tasks_sha256": hashlib.sha256(out_path.read_bytes()).hexdigest(),
    }


def _gold_contract_error(gold: Any, task: dict[str, Any]) -> str | None:
    if not isinstance(gold, dict):
        return "gold_must_be_object"
    allowed = set(str(x) for x in task.get("allowed_labels", []))
    task_type = task.get("task_type")
    if task_type == "classification":
        label = gold.get("label")
        if not isinstance(label, str) or label not in allowed:
            return "classification_label_outside_contract"
        return None
    if task_type == "multilabel":
        labels = gold.get("labels")
        if not isinstance(labels, list) or not labels:
            return "multilabel_labels_must_be_nonempty_list"
        if not all(isinstance(label, str) for label in labels):
            return "multilabel_labels_must_be_strings"
        if len(labels) != len(set(labels)):
            return "multilabel_labels_must_be_unique"
        if not set(labels).issubset(allowed):
            return "multilabel_label_outside_contract"
        return None
    return "unsupported_task_type"


def _gold_agrees(curator_gold: dict[str, Any], verifier_gold: dict[str, Any],
                 task: dict[str, Any]) -> bool:
    """Compare gold using the preregistered task semantics.

    Multilabel evaluation is set-based, so label ordering is not semantic.
    Any non-label fields remain exact/canonical to avoid silently weakening
    future extensions to the gold contract.
    """
    if task.get("task_type") != "multilabel":
        return canonical_json_bytes(curator_gold) == canonical_json_bytes(verifier_gold)

    curator_labels = curator_gold.get("labels")
    verifier_labels = verifier_gold.get("labels")
    if not isinstance(curator_labels, list) or not isinstance(verifier_labels, list):
        return False
    if set(curator_labels) != set(verifier_labels):
        return False

    curator_extra = {k: v for k, v in curator_gold.items() if k != "labels"}
    verifier_extra = {k: v for k, v in verifier_gold.items() if k != "labels"}
    return canonical_json_bytes(curator_extra) == canonical_json_bytes(verifier_extra)


def _validate_response_identity(response: dict[str, Any], task: dict[str, Any], role: str) -> None:
    if response.get("task_fingerprint") != task.get("task_fingerprint"):
        raise ValueError(f"{role} task fingerprint mismatch: {task['task_id']}")
    for field in ("model_family", "model_ref"):
        if not isinstance(response.get(field), str) or not response[field].strip():
            raise ValueError(f"{role} response requires {field}: {task['task_id']}")
    binding = response.get("execution_binding")
    if not isinstance(binding, dict):
        raise ValueError(f"{role} response requires execution_binding: {task['task_id']}")
    for field in ("config_sha256", "raw_response_sha256", "adapter_command_sha256"):
        value = binding.get(field)
        if not isinstance(value, str) or re.fullmatch(r"[a-f0-9]{64}", value) is None:
            raise ValueError(f"{role} execution binding {field} invalid: {task['task_id']}")
    if binding.get("protocol_version") != 1 or not isinstance(binding.get("batch_id"), str):
        raise ValueError(f"{role} execution binding metadata invalid: {task['task_id']}")
    artifacts = binding.get("adapter_artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError(f"{role} execution binding adapter artifacts missing: {task['task_id']}")
    for artifact in artifacts:
        if (
            not isinstance(artifact, dict)
            or not isinstance(artifact.get("path"), str)
            or not artifact["path"].strip()
            or not isinstance(artifact.get("sha256"), str)
            or re.fullmatch(r"[a-f0-9]{64}", artifact["sha256"]) is None
            or not isinstance(artifact.get("size_bytes"), int)
            or artifact["size_bytes"] < 1
        ):
            raise ValueError(f"{role} execution binding adapter artifact invalid: {task['task_id']}")
    raw = dict(response)
    raw.pop("task_fingerprint", None)
    raw.pop("model_family", None)
    raw.pop("model_ref", None)
    raw.pop("execution_binding", None)
    if binding.get("raw_response_sha256") != sha256_bytes(canonical_json_bytes(raw)):
        raise ValueError(f"{role} raw response hash mismatch: {task['task_id']}")


_FACTORY_LOCATOR_RE = re.compile(r"^gitblob:([a-f0-9]{40})#char=(\d+):(\d+)$")


def _slot_binding_sha256(slot: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(slot))


def _verify_factory_locator(root: Path, source_cache_dir: Path, source_id: str,
                            locator: str, excerpt: str) -> dict[str, Any]:
    registry = source_map(load_source_registry(root))
    src = registry.get(source_id)
    if src is None or src.get("qualification_eligible") is not True:
        raise ValueError(f"factory source is not qualification eligible: {source_id}")
    if not isinstance(locator, str):
        raise ValueError(f"factory locator must be a string: {source_id}")
    match = _FACTORY_LOCATOR_RE.fullmatch(locator)
    if match is None:
        raise ValueError(f"factory locator must use gitblob:<sha>#char=start:end: {source_id}")
    blob_sha, raw_start, raw_end = match.groups()
    if blob_sha != src.get("source_blob_sha"):
        raise ValueError(f"factory locator blob does not match pinned source: {source_id}")
    start, end = int(raw_start), int(raw_end)
    if start < 0 or end <= start:
        raise ValueError(f"factory locator character range is invalid: {source_id}")
    cache_path = source_cache_dir / cache_filename(source_id)
    if not cache_path.exists() or not verify_cached_source(cache_path, src)["verified"]:
        raise ValueError(f"factory source cache is missing or unverified: {source_id}")
    source_text = cache_path.read_text(encoding="utf-8", errors="strict")
    if end > len(source_text):
        raise ValueError(f"factory locator exceeds source length: {source_id}")
    if source_text[start:end] != excerpt:
        raise ValueError(f"factory locator does not resolve exactly to excerpt: {source_id}")
    return {
        "source_id": source_id,
        "locator": locator,
        "excerpt_sha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
        "source_blob_sha": blob_sha,
        "char_start": start,
        "char_end": end,
    }


def _verify_factory_candidate_refs(root: Path, source_cache_dir: Path,
                                   refs: Any, allowed_source_pool: set[str]) -> None:
    if not isinstance(refs, list) or not refs:
        raise ValueError("factory candidate requires non-empty source_refs")
    for ref in refs:
        if not isinstance(ref, dict):
            raise ValueError("factory candidate source_ref must be an object")
        sid = ref.get("source_id")
        locator = ref.get("locator")
        excerpt = ref.get("excerpt")
        if sid not in allowed_source_pool:
            raise ValueError(f"factory candidate source escapes partition: {sid}")
        if not isinstance(excerpt, str) or not excerpt:
            raise ValueError(f"factory candidate excerpt missing: {sid}")
        _verify_factory_locator(root, source_cache_dir, str(sid), locator, excerpt)


def _verify_supports(root: Path, source_cache_dir: Path, supports: Any, allowed_source_pool: set[str]) -> list[dict[str, Any]]:
    if not isinstance(supports, list) or not supports:
        raise ValueError("verifier answer requires non-empty supports")
    registry = source_map(load_source_registry(root))
    verified: list[dict[str, Any]] = []
    for support in supports:
        if not isinstance(support, dict):
            raise ValueError("verifier support must be an object")
        sid = support.get("source_id")
        excerpt = support.get("excerpt")
        support_text = support.get("support_text")
        locator = support.get("locator")
        if sid not in allowed_source_pool:
            raise ValueError(f"verifier support source escapes partition: {sid}")
        if not isinstance(excerpt, str) or not excerpt:
            raise ValueError(f"verifier excerpt missing: {sid}")
        if not isinstance(support_text, str) or not support_text or support_text not in excerpt:
            raise ValueError(f"verifier support_text not found inside excerpt: {sid}")
        located = _verify_factory_locator(
            root, source_cache_dir, str(sid), locator, excerpt
        )
        verified.append({
            **located,
            "support_text_sha256": hashlib.sha256(support_text.encode("utf-8")).hexdigest(),
        })
    return verified


def reconcile_factory(
    root: Path,
    tasks_path: Path,
    curator_responses_path: Path,
    verifier_responses_path: Path,
    source_cache_dir: Path,
    reviewed_dir: Path,
    adjudication_path: Path,
    ledger_path: Path,
    custodian_mode: bool = False,
    partition: str = "non_holdout",
    reserve_activation_path: Path | None = None,
    capacity_extension_path: Path | None = None,
) -> dict[str, Any]:
    if partition not in {"holdout", "non_holdout"}:
        raise ValueError("partition must be holdout or non_holdout")
    if partition == "holdout":
        for p in (
            tasks_path, curator_responses_path, verifier_responses_path, source_cache_dir,
            reviewed_dir, adjudication_path, ledger_path,
        ):
            enforce_partition_boundary(root, "holdout", p, custodian_mode)
    task_rows = _task_rows(tasks_path)
    actual_partition = _task_partition(task_rows)
    if actual_partition != partition:
        raise ValueError(f"factory task partition {actual_partition} does not match requested {partition}")
    _validate_tasks_against_frozen_plan(
        root,
        task_rows,
        capacity_extension_path=capacity_extension_path,
        require_capacity_execution=capacity_extension_path is not None,
    )
    reserve_tasks = [
        task for task in task_rows
        if task.get("candidate_slot_kind") == "reserve"
    ]
    reserve_activation: dict[str, Any] | None = None
    reserve_activation_sha256: str | None = None
    capacity_extension: dict[str, Any] | None = None
    capacity_extension_sha256: str | None = None
    if reserve_tasks:
        if len(reserve_tasks) != len(task_rows):
            raise ValueError("do not mix primary and reserve tasks in one reconciliation")
        if partition != "non_holdout":
            raise ValueError("reserve reconciliation currently supports non_holdout only")
        attempts = {task.get("reserve_attempt") for task in reserve_tasks}
        if attempts == {1}:
            if capacity_extension_path is not None:
                raise ValueError(
                    "schema-26 reserve:01 reconciliation must not supply capacity extension"
                )
            if reserve_activation_path is None:
                raise ValueError(
                    "reserve:01 reconciliation requires a reviewed activation manifest"
                )
            from .post_consolidation import validate_reserve_activation

            reserve_activation = validate_reserve_activation(
                root, reserve_activation_path, task_rows
            )
            reserve_activation_sha256 = sha256_file(reserve_activation_path)
        elif attempts == {2}:
            if reserve_activation_path is not None:
                raise ValueError(
                    "reserve:02 reconciliation must not use schema-26 reserve activation"
                )
            if capacity_extension_path is None:
                raise ValueError(
                    "reserve:02 reconciliation requires the frozen capacity extension"
                )
            from .capacity_extension import validate_frozen_capacity_extension

            capacity_extension = validate_frozen_capacity_extension(
                root,
                capacity_extension_path,
                task_rows,
                require_execution_enabled=True,
            )
            capacity_extension_sha256 = sha256_file(capacity_extension_path)
        else:
            raise ValueError("reserve reconciliation requires one supported reserve attempt")
    elif reserve_activation_path is not None or capacity_extension_path is not None:
        raise ValueError("reserve authorization supplied for primary-only reconciliation")
    tasks = {str(t["task_id"]): t for t in task_rows}

    curators = {str(r["task_id"]): r for r in load_jsonl(curator_responses_path)}
    verifiers = {str(r["task_id"]): r for r in load_jsonl(verifier_responses_path)}
    if len(curators) != len(load_jsonl(curator_responses_path)):
        raise ValueError("duplicate curator task IDs")
    if len(verifiers) != len(load_jsonl(verifier_responses_path)):
        raise ValueError("duplicate verifier task IDs")

    promoted: list[dict[str, Any]] = []
    adjudication: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    skipped = 0

    def log(tid: str, outcome: str, curator: dict[str, Any] | None = None,
            verifier: dict[str, Any] | None = None, reason: str | None = None,
            case_id: str | None = None) -> None:
        ledger.append({
            "task_id": tid,
            "task_fingerprint": tasks[tid]["task_fingerprint"],
            "benchmark_id": tasks[tid]["benchmark_id"],
            "partition": tasks[tid]["partition"],
            "outcome": outcome,
            "reason": reason,
            "case_id": case_id,
            "curator_response_sha256": (
                sha256_bytes(canonical_json_bytes(curator)) if isinstance(curator, dict) else None
            ),
            "verifier_response_sha256": (
                sha256_bytes(canonical_json_bytes(verifier)) if isinstance(verifier, dict) else None
            ),
            "curator_model_family": curator.get("model_family") if isinstance(curator, dict) else None,
            "verifier_model_family": verifier.get("model_family") if isinstance(verifier, dict) else None,
        })

    for tid, task in tasks.items():
        curator = curators.get(tid)
        if curator is None or curator.get("status") != "candidate":
            skipped += 1
            log(tid, "skipped", curator=curator, reason="no_curator_candidate")
            continue

        _validate_response_identity(curator, task, "curator")
        candidate = curator.get("candidate")
        if not isinstance(candidate, dict):
            adjudication.append({"task_id": tid, "reason": "malformed_candidate_or_verifier_answer"})
            log(tid, "adjudication", curator=curator, reason="malformed_candidate_or_verifier_answer")
            continue

        provenance = candidate.get("answer_provenance")
        if (
            task.get("auto_promotion") is True
            and isinstance(provenance, dict)
            and provenance.get("mode") == "adjudication_required"
        ):
            adjudication.append({
                "task_id": tid,
                "reason": "curator_requested_adjudication",
            })
            log(tid, "adjudication", curator=curator, reason="curator_requested_adjudication")
            continue

        verifier = verifiers.get(tid)
        if verifier is None:
            adjudication.append({"task_id": tid, "reason": "missing_verifier_response"})
            log(tid, "adjudication", curator=curator, reason="missing_verifier_response")
            continue
        _validate_response_identity(verifier, task, "verifier")
        if _canonical_model_family(curator["model_family"]) == _canonical_model_family(verifier["model_family"]):
            adjudication.append({"task_id": tid, "reason": "model_family_not_independent"})
            log(tid, "adjudication", curator, verifier, "model_family_not_independent")
            continue
        if verifier.get("status") != "candidate":
            adjudication.append({"task_id": tid, "reason": "verifier_no_candidate"})
            log(tid, "adjudication", curator, verifier, "verifier_no_candidate")
            continue

        answer = verifier.get("answer")
        if not isinstance(answer, dict):
            adjudication.append({"task_id": tid, "reason": "malformed_candidate_or_verifier_answer"})
            log(tid, "adjudication", curator, verifier, "malformed_candidate_or_verifier_answer")
            continue
        try:
            _verify_factory_candidate_refs(
                root, source_cache_dir, candidate.get("source_refs"),
                set(task["allowed_source_pool"]),
            )
        except Exception as exc:
            adjudication.append({
                "task_id": tid,
                "reason": "curator_locator_invalid",
                "detail": str(exc),
            })
            log(tid, "adjudication", curator, verifier, "curator_locator_invalid")
            continue

        payload = candidate.get("payload")
        if not isinstance(payload, dict) or "gold" not in payload:
            adjudication.append({"task_id": tid, "reason": "curator_gold_missing"})
            log(tid, "adjudication", curator, verifier, "curator_gold_missing")
            continue
        curator_gold_error = _gold_contract_error(payload["gold"], task)
        if curator_gold_error is not None:
            reason = f"curator_gold_contract_invalid:{curator_gold_error}"
            adjudication.append({"task_id": tid, "reason": reason})
            log(tid, "adjudication", curator, verifier, reason)
            continue
        verifier_gold_error = _gold_contract_error(answer.get("gold"), task)
        if verifier_gold_error is not None:
            reason = f"verifier_gold_contract_invalid:{verifier_gold_error}"
            adjudication.append({"task_id": tid, "reason": reason})
            log(tid, "adjudication", curator, verifier, reason)
            continue
        if not _gold_agrees(payload["gold"], answer["gold"], task):
            adjudication.append({
                "task_id": tid,
                "reason": "gold_disagreement",
                "curator_model_family": curator["model_family"],
                "verifier_model_family": verifier["model_family"],
            })
            log(tid, "adjudication", curator, verifier, "gold_disagreement")
            continue

        try:
            verifier_supports = _verify_supports(
                root, source_cache_dir, answer.get("supports"), set(task["allowed_source_pool"])
            )
        except Exception as exc:
            adjudication.append({"task_id": tid, "reason": "verifier_support_invalid", "detail": str(exc)})
            log(tid, "adjudication", curator, verifier, "verifier_support_invalid")
            continue

        if task.get("auto_promotion") is not True:
            adjudication.append({
                "task_id": tid,
                "reason": "policy_requires_human_or_authority_gate",
                "curator_model_family": curator["model_family"],
                "verifier_model_family": verifier["model_family"],
            })
            log(tid, "adjudication", curator, verifier, "policy_requires_human_or_authority_gate")
            continue

        if candidate.get("gold_status") != "source_attributed":
            adjudication.append({"task_id": tid, "reason": "auto_promotion_requires_source_attributed"})
            log(tid, "adjudication", curator, verifier, "auto_promotion_requires_source_attributed")
            continue

        if candidate.get("benchmark_id") != task["benchmark_id"]:
            adjudication.append({"task_id": tid, "reason": "benchmark_id_mismatch"})
            log(tid, "adjudication", curator, verifier, "benchmark_id_mismatch")
            continue
        if candidate.get("anchor_source_id") != task["anchor_source_id"]:
            adjudication.append({"task_id": tid, "reason": "anchor_source_id_mismatch"})
            log(tid, "adjudication", curator, verifier, "anchor_source_id_mismatch")
            continue

        source_ids = {
            str(r.get("source_id")) for r in candidate.get("source_refs", [])
            if isinstance(r, dict) and isinstance(r.get("source_id"), str)
        }
        if not source_ids or not source_ids.issubset(set(task["allowed_source_pool"])):
            adjudication.append({"task_id": tid, "reason": "curator_source_partition_violation"})
            log(tid, "adjudication", curator, verifier, "curator_source_partition_violation")
            continue
        verifier_source_ids = {
            str(s.get("source_id")) for s in verifier_supports
            if isinstance(s, dict) and isinstance(s.get("source_id"), str)
        }
        if not verifier_source_ids.issubset(source_ids):
            adjudication.append({"task_id": tid, "reason": "verifier_support_not_in_curator_provenance"})
            log(tid, "adjudication", curator, verifier, "verifier_support_not_in_curator_provenance")
            continue

        candidate = json.loads(json.dumps(candidate, ensure_ascii=False))
        curator_response_sha256 = sha256_bytes(canonical_json_bytes(curator))
        verifier_response_sha256 = sha256_bytes(canonical_json_bytes(verifier))
        expected_slots = {
            str(s["slot_id"]): s for s in build_factory_plan(root)["slots"]
        }
        if capacity_extension is not None:
            for item in capacity_extension["extensions"]:
                slot = item["new_reserve_slot"]
                expected_slots[str(slot["slot_id"])] = slot
        expected_slot = expected_slots[task["slot_id"]]
        candidate["factory_verification"] = {
            "factory_version": int(_policy(root).get("factory_version", 0)),
            "risk_tier": int(task.get("risk_tier", 0)),
            "slot_binding_sha256": _slot_binding_sha256(expected_slot),
            "curator_model_family": curator["model_family"],
            "curator_model_ref": curator["model_ref"],
            "verifier_model_family": verifier["model_family"],
            "verifier_model_ref": verifier["model_ref"],
            "curator_response_sha256": curator_response_sha256,
            "verifier_response_sha256": verifier_response_sha256,
            "curator_execution_binding": curator.get("execution_binding"),
            "verifier_execution_binding": verifier.get("execution_binding"),
            "verifier_supports": verifier_supports,
            "agreement": "exact_gold_match",
            "task_fingerprint": task["task_fingerprint"],
        }
        if task.get("candidate_slot_kind") == "reserve":
            if task.get("reserve_attempt") == 1:
                assert reserve_activation is not None and reserve_activation_sha256 is not None
                candidate["factory_verification"]["reserve_activation"] = {
                    "activation_manifest_sha256": reserve_activation_sha256,
                    "cumulative_ledger_sha256": reserve_activation["cumulative_ledger_sha256"],
                    "replacement_eligibility_sha256": reserve_activation["replacement_eligibility_sha256"],
                    "replacement_for_slot_id": task["replacement_for_slot_id"],
                    "reserve_attempt": task["reserve_attempt"],
                }
            elif task.get("reserve_attempt") == 2:
                assert capacity_extension is not None and capacity_extension_sha256 is not None
                candidate["factory_verification"]["capacity_extension"] = {
                    "manifest_sha256": capacity_extension_sha256,
                    "protocol_freeze_schema": capacity_extension["protocol_freeze_schema"],
                    "base_factory_plan_sha256": capacity_extension["base_factory_plan_sha256"],
                    "reserve_ledger_sha256": capacity_extension["reserve_ledger_sha256"],
                    "exhausted_slots_sha256": capacity_extension["exhausted_slots_sha256"],
                    "replacement_for_slot_id": task["replacement_for_slot_id"],
                    "reserve_attempt": task["reserve_attempt"],
                }
            else:
                raise ValueError(f"unsupported reserve attempt: {task.get('reserve_attempt')}")
        try:
            sealed = seal_reviewed_record(root, candidate, source_cache_dir)
        except Exception as exc:
            adjudication.append({"task_id": tid, "reason": "curator_candidate_failed_qualification_contract", "detail": str(exc)})
            log(tid, "adjudication", curator, verifier, "curator_candidate_failed_qualification_contract")
            continue
        sealed["factory_task_id"] = tid
        sealed["factory_slot_id"] = task.get("slot_id", tid)
        sealed["factory_task_fingerprint"] = task["task_fingerprint"]
        promoted.append(sealed)
        log(tid, "promoted", curator, verifier, case_id=str(sealed.get("case_id")))

    by_benchmark: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in promoted:
        by_benchmark[str(row["benchmark_id"])].append(row)
    for bid, rows in by_benchmark.items():
        out = reviewed_dir / bid / "reviewed.jsonl"
        existing = load_jsonl(out)
        existing_ids = {str(r.get("case_id")) for r in existing}
        existing_slots = {
            str(r.get("factory_slot_id")) for r in existing
            if isinstance(r.get("factory_slot_id"), str)
        }
        for row in rows:
            cid = str(row.get("case_id"))
            slot_id = row.get("factory_slot_id")
            if cid in existing_ids:
                raise ValueError(f"duplicate promoted case_id: {cid}")
            if isinstance(slot_id, str) and slot_id in existing_slots:
                raise ValueError(f"factory slot already promoted: {slot_id}")
            existing.append(row)
            existing_ids.add(cid)
            if isinstance(slot_id, str):
                existing_slots.add(slot_id)
        dump_jsonl(out, existing)

    dump_jsonl(adjudication_path, adjudication)
    dump_jsonl(ledger_path, ledger)

    adjudication_reason_counts = Counter(
        str(row.get("reason"))
        for row in adjudication
        if isinstance(row.get("reason"), str) and row["reason"]
    )
    outcome_by_benchmark: dict[str, Counter[str]] = defaultdict(Counter)
    adjudication_reason_counts_by_benchmark: dict[str, Counter[str]] = defaultdict(Counter)
    for row in ledger:
        bid = str(row.get("benchmark_id", ""))
        outcome = str(row.get("outcome", ""))
        if bid and outcome:
            outcome_by_benchmark[bid][outcome] += 1
        reason = row.get("reason")
        if (
            bid
            and outcome == "adjudication"
            and isinstance(reason, str)
            and reason
        ):
            adjudication_reason_counts_by_benchmark[bid][reason] += 1

    return {
        "task_count": len(tasks),
        "promoted_count": len(promoted),
        "adjudication_count": len(adjudication),
        "skipped_count": skipped,
        "ledger_count": len(ledger),
        "promoted_by_benchmark": dict(sorted(Counter(str(r["benchmark_id"]) for r in promoted).items())),
        "adjudication_reason_counts": dict(sorted(adjudication_reason_counts.items())),
        "adjudication_reason_counts_by_benchmark": {
            bid: dict(sorted(counts.items()))
            for bid, counts in sorted(adjudication_reason_counts_by_benchmark.items())
        },
        "outcome_by_benchmark": {
            bid: dict(sorted(counts.items()))
            for bid, counts in sorted(outcome_by_benchmark.items())
        },
    }


def factory_status(plan_path: Path, curator_responses_path: Path | None = None,
                   verifier_responses_path: Path | None = None,
                   adjudication_path: Path | None = None,
                   reviewed_dir: Path | None = None) -> dict[str, Any]:
    plan = load_json(plan_path)
    curator = load_jsonl(curator_responses_path) if curator_responses_path and curator_responses_path.exists() else []
    verifier = load_jsonl(verifier_responses_path) if verifier_responses_path and verifier_responses_path.exists() else []
    adjudication = load_jsonl(adjudication_path) if adjudication_path and adjudication_path.exists() else []
    reviewed = 0
    if reviewed_dir and reviewed_dir.exists():
        for p in reviewed_dir.glob("*/reviewed.jsonl"):
            reviewed += len(load_jsonl(p))
    return {
        "target_total": plan["target_total"],
        "slot_count": plan["slot_count"],
        "primary_slot_count": plan.get("primary_slot_count", plan["target_total"]),
        "primary_non_holdout_slots": plan.get(
            "primary_non_holdout_slots", plan.get("non_holdout_slots")
        ),
        "primary_holdout_slots": plan.get(
            "primary_holdout_slots", plan.get("holdout_slots")
        ),
        "reserve_slot_count": plan.get("reserve_slot_count", 0),
        "candidate_non_holdout_slots": plan.get("candidate_non_holdout_slots"),
        "candidate_holdout_slots": plan.get("candidate_holdout_slots"),
        "curator_responses": len(curator),
        "verifier_responses": len(verifier),
        "reviewed_records": reviewed,
        "adjudication_records": len(adjudication),
        "remaining_to_target": max(0, int(plan["target_total"]) - reviewed),
    }
