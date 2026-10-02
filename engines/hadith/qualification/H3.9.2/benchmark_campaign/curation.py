from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .core import dump_jsonl, load_jsonl
from .normalization import fingerprint_payload
from .source_cache import cache_filename, verify_cached_source
from .source_registry import load_source_registry, source_map


def _excerpt_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_cached_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="strict")


def seal_reviewed_record(root: Path, record: dict[str, Any], source_cache_dir: Path) -> dict[str, Any]:
    out = dict(record)
    refs = out.get("source_refs")
    if not isinstance(refs, list) or not refs:
        raise ValueError("source_refs must be a non-empty list")
    registry = source_map(load_source_registry(root))
    sealed_refs = []
    source_ids = []
    for ref in refs:
        if not isinstance(ref, dict):
            raise ValueError("each source_ref must be an object")
        source_id = ref.get("source_id")
        if source_id not in registry:
            raise ValueError(f"unregistered source: {source_id}")
        src = registry[source_id]
        if src.get("qualification_eligible") is not True:
            raise ValueError(f"source is candidate-only and cannot qualify: {source_id}")
        excerpt = ref.get("excerpt")
        locator = ref.get("locator")
        if not isinstance(excerpt, str) or not excerpt.strip():
            raise ValueError(f"exact source excerpt required: {source_id}")
        if not isinstance(locator, str) or not locator.strip():
            raise ValueError(f"source locator required: {source_id}")
        cache_path = source_cache_dir / cache_filename(source_id)
        if not cache_path.exists():
            raise FileNotFoundError(f"source cache missing for {source_id}: {cache_path}")
        cache_check = verify_cached_source(cache_path, src)
        if not cache_check["verified"]:
            raise ValueError(f"pinned source cache hash mismatch: {source_id}")
        cached_text = _load_cached_text(cache_path)
        if excerpt not in cached_text:
            raise ValueError(f"excerpt not found verbatim in pinned source cache: {source_id}")
        x = dict(ref)
        x["source_blob_sha"] = src["source_blob_sha"]
        x["excerpt_sha256"] = _excerpt_hash(excerpt)
        sealed_refs.append(x)
        source_ids.append(source_id)

    if len(set(source_ids)) != len(source_ids):
        raise ValueError("source_refs contain duplicate source IDs")
    payload = out.get("payload")
    if not isinstance(payload, dict) or "input" not in payload or "gold" not in payload:
        raise ValueError("payload must contain input and gold")
    if out.get("synthetic") is not False:
        raise ValueError("qualification curation requires synthetic=false")
    if out.get("gold_status") not in {"source_attributed", "reference_pilot", "expert_gold"}:
        raise ValueError("gold_status must be source_attributed, reference_pilot, or expert_gold")
    anchor_source_id = out.get("anchor_source_id")
    if anchor_source_id is None and len(source_ids) == 1:
        anchor_source_id = source_ids[0]
    if not isinstance(anchor_source_id, str) or anchor_source_id not in source_ids:
        raise ValueError("anchor_source_id must be explicitly supplied for multi-source cases and must be one of source_ids")
    out["anchor_source_id"] = anchor_source_id

    answer_provenance = out.get("answer_provenance")
    if out.get("gold_status") == "source_attributed":
        if not isinstance(answer_provenance, dict):
            raise ValueError("source_attributed requires answer_provenance")
        if answer_provenance.get("answer_origin") != "human_authored_source":
            raise ValueError("source_attributed answer_origin must be human_authored_source")
        if answer_provenance.get("extraction_method") not in {"ai", "human"}:
            raise ValueError("source_attributed extraction_method must be ai or human")
        if answer_provenance.get("source_verified") is not True:
            raise ValueError("source_attributed requires source_verified=true")
        if not isinstance(answer_provenance.get("human_reviewed"), bool):
            raise ValueError("source_attributed requires human_reviewed boolean")

    out["source_ids"] = source_ids
    out["source_refs"] = sealed_refs
    out["content_fingerprint"] = fingerprint_payload(payload)
    out.pop("source_id", None)
    out.pop("source_ref", None)
    out.pop("split", None)  # split is assigned only after the reviewed pool is sealed
    return out


def curate_reviewed_file(root: Path, benchmark_id: str, input_path: Path, output_path: Path,
                          source_cache_dir: Path) -> dict[str, Any]:
    rows = load_jsonl(input_path)
    sealed = []
    seen = set()
    for r in rows:
        x = dict(r)
        x["benchmark_id"] = benchmark_id
        x = seal_reviewed_record(root, x, source_cache_dir)
        cid = x.get("case_id")
        if not isinstance(cid, str) or not cid.strip():
            raise ValueError("case_id must be a non-empty string")
        if cid in seen:
            raise ValueError(f"duplicate case_id in reviewed input: {cid}")
        seen.add(cid)
        sealed.append(x)
    dump_jsonl(output_path, sealed)
    return {"benchmark_id": benchmark_id, "reviewed_count": len(sealed), "output": str(output_path)}
