from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
import hashlib
import json
import re

from .core import canonical_json_bytes, dump_jsonl, load_json, load_jsonl, sha256_bytes, write_json
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


def _validate_tasks_against_frozen_plan(root: Path, rows: list[dict[str, Any]]) -> None:
    expected_plan = build_factory_plan(root)
    slots = {str(s["slot_id"]): s for s in expected_plan["slots"]}
    cplan = _curation_plan(root)
    registry = source_map(load_source_registry(root))
    policy_fields = (
        "benchmark_id", "partition", "anchor_source_id", "task_type",
        "allowed_labels", "auto_promotion", "risk_tier", "visibility",
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
        bid = expected["benchmark_id"]
        partition = expected["partition"]
        bp = cplan.get("benchmarks", {}).get(bid, {})
        pool_key = "holdout_source_pool" if partition == "holdout" else "non_holdout_source_pool"
        other_key = "non_holdout_source_pool" if partition == "holdout" else "holdout_source_pool"
        if task.get("allowed_source_pool") != bp.get(pool_key):
            raise ValueError(f"factory task allowed_source_pool differs from frozen plan: {slot_id}")
        if task.get("forbidden_source_pool") != bp.get(other_key):
            raise ValueError(f"factory task forbidden_source_pool differs from frozen plan: {slot_id}")
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
    slots: list[dict[str, Any]] = []
    for q in quotas["benchmarks"]:
        bid = q["benchmark_id"]
        bp = policy["benchmarks"][bid]
        sb = bspec[bid]
        for partition_key, partition_name in (("non_holdout", "non_holdout"), ("holdout", "holdout")):
            for anchor in q[partition_key]["anchor_quotas"]:
                sid = anchor["anchor_source_id"]
                for ordinal in range(1, int(anchor["target_cases"]) + 1):
                    slot_id = f"{bid}:{partition_name}:{sid}:{ordinal:04d}"
                    slots.append({
                        "slot_id": slot_id,
                        "benchmark_id": bid,
                        "partition": partition_name,
                        "anchor_source_id": sid,
                        "ordinal": ordinal,
                        "task_type": sb["evaluation"]["task_type"],
                        "allowed_labels": sb["evaluation"]["labels"],
                        "auto_promotion": bp["auto_promotion"],
                        "risk_tier": bp["risk_tier"],
                        "visibility": "custodian_only" if partition_name == "holdout" else "development_safe",
                    })
    plan = {
        "campaign_id": spec["campaign_id"],
        "factory_version": 1,
        "slot_count": len(slots),
        "target_total": quotas["total_target"],
        "holdout_slots": sum(1 for s in slots if s["partition"] == "holdout"),
        "non_holdout_slots": sum(1 for s in slots if s["partition"] == "non_holdout"),
        "slots": slots,
    }
    if plan["slot_count"] != int(quotas["total_target"]):
        raise ValueError("factory slot count does not match frozen curation target")
    if out_path is not None:
        write_json(out_path, plan)
    return plan


def _segment_score(text: str, keywords: list[str]) -> int:
    return sum(text.count(k) for k in keywords if k)


def build_factory_tasks(root: Path, plan_path: Path, index_dir: Path, out_path: Path,
                        partition: str = "non_holdout", custodian_mode: bool = False) -> dict[str, Any]:
    if partition not in {"holdout", "non_holdout"}:
        raise ValueError("factory tasks are built one partition at a time")
    enforce_partition_boundary(root, partition, index_dir, custodian_mode)
    enforce_partition_boundary(root, partition, out_path, custodian_mode)
    plan = load_json(plan_path)
    expected_plan = build_factory_plan(root)
    if canonical_json_bytes(plan) != canonical_json_bytes(expected_plan):
        raise ValueError("factory plan does not match the frozen quotas/spec/policy")
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
        seg = ranked[usage[anchor] % len(ranked)]
        usage[anchor] += 1
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


def prepare_verifier_tasks(root: Path, tasks_path: Path, curator_responses_path: Path, out_path: Path,
                           partition: str = "non_holdout", custodian_mode: bool = False) -> dict[str, Any]:
    if partition not in {"holdout", "non_holdout"}:
        raise ValueError("partition must be holdout or non_holdout")
    if partition == "holdout":
        for p in (tasks_path, curator_responses_path, out_path):
            enforce_partition_boundary(root, "holdout", p, custodian_mode)
    task_rows = _task_rows(tasks_path)
    actual_partition = _task_partition(task_rows)
    if actual_partition != partition:
        raise ValueError(f"factory task partition {actual_partition} does not match requested {partition}")
    _validate_tasks_against_frozen_plan(root, task_rows)
    tasks = {str(t["task_id"]): t for t in task_rows}
    responses = load_jsonl(curator_responses_path)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
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
        candidate = response.get("candidate")
        if not isinstance(candidate, dict):
            raise ValueError(f"candidate payload missing: {tid}")
        payload = candidate.get("payload")
        if not isinstance(payload, dict) or "input" not in payload:
            raise ValueError(f"candidate payload.input missing: {tid}")
        blind_error = _blind_input_error(payload["input"], task)
        if blind_error is not None:
            raise ValueError(f"candidate payload.input violates verifier blindness: {tid}: {blind_error}")
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
        verifier_task["task_fingerprint"] = task["task_fingerprint"]
        out.append(verifier_task)
    dump_jsonl(out_path, out)
    return {
        "input_candidates": len(out),
        "verifier_tasks": len(out),
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
        normalized = [str(x) for x in labels]
        if len(normalized) != len(set(normalized)):
            return "multilabel_labels_must_be_unique"
        if not set(normalized).issubset(allowed):
            return "multilabel_label_outside_contract"
        return None
    return "unsupported_task_type"


def _validate_response_identity(response: dict[str, Any], task: dict[str, Any], role: str) -> None:
    if response.get("task_fingerprint") != task.get("task_fingerprint"):
        raise ValueError(f"{role} task fingerprint mismatch: {task['task_id']}")
    for field in ("model_family", "model_ref"):
        if not isinstance(response.get(field), str) or not response[field].strip():
            raise ValueError(f"{role} response requires {field}: {task['task_id']}")


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


def reconcile_factory(root: Path, tasks_path: Path, curator_responses_path: Path,
                      verifier_responses_path: Path, source_cache_dir: Path,
                      reviewed_dir: Path, adjudication_path: Path, ledger_path: Path,
                      custodian_mode: bool = False, partition: str = "non_holdout") -> dict[str, Any]:
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
    _validate_tasks_against_frozen_plan(root, task_rows)
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
        verifier = verifiers.get(tid)
        if verifier is None:
            adjudication.append({"task_id": tid, "reason": "missing_verifier_response"})
            log(tid, "adjudication", curator=curator, reason="missing_verifier_response")
            continue
        _validate_response_identity(curator, task, "curator")
        _validate_response_identity(verifier, task, "verifier")
        if _canonical_model_family(curator["model_family"]) == _canonical_model_family(verifier["model_family"]):
            adjudication.append({"task_id": tid, "reason": "model_family_not_independent"})
            log(tid, "adjudication", curator, verifier, "model_family_not_independent")
            continue
        if verifier.get("status") != "candidate":
            adjudication.append({"task_id": tid, "reason": "verifier_no_candidate"})
            log(tid, "adjudication", curator, verifier, "verifier_no_candidate")
            continue

        candidate = curator.get("candidate")
        answer = verifier.get("answer")
        if not isinstance(candidate, dict) or not isinstance(answer, dict):
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
        if canonical_json_bytes(payload["gold"]) != canonical_json_bytes(answer.get("gold")):
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
            "verifier_supports": verifier_supports,
            "agreement": "exact_gold_match",
            "task_fingerprint": task["task_fingerprint"],
        }
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
    return {
        "task_count": len(tasks),
        "promoted_count": len(promoted),
        "adjudication_count": len(adjudication),
        "skipped_count": skipped,
        "ledger_count": len(ledger),
        "promoted_by_benchmark": dict(sorted(Counter(str(r["benchmark_id"]) for r in promoted).items())),
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
        "curator_responses": len(curator),
        "verifier_responses": len(verifier),
        "reviewed_records": reviewed,
        "adjudication_records": len(adjudication),
        "remaining_to_target": max(0, int(plan["target_total"]) - reviewed),
    }
