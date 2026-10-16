"""Bounded, offline Hadith registry pin verification; not source authentication.

Maps the frozen H3.9.2 registry's Git blob pins to locally computed SHA-256.
No file in the Hadith qualification tree is modified by this adapter.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any

MAX_REGISTRY_BYTES = 5 * 1024 * 1024
MAX_SOURCES = 256
DEFAULT_MAX_SOURCE_BYTES = 512 * 1024 * 1024
DEFAULT_MAX_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024
_SOURCE_ID = re.compile(r"[a-z][a-z0-9]*:[A-Za-z0-9][A-Za-z0-9_.:-]*\Z")
_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
_REPO = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*\Z")
_SAFE_SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")

AUTHORITY = {
    "edition": "not_authenticated",
    "rights": "not_reviewed",
    "entailment": "not_checked",
}
SCOPE = "registry_blob_match_only"


def cache_filename(source_id: str) -> str:
    """Mirror frozen H3.9.2 benchmark_campaign.source_cache.cache_filename."""
    if not isinstance(source_id, str) or _SOURCE_ID.fullmatch(source_id) is None:
        raise ValueError("unsafe source_id")
    return source_id.replace(":", "__") + ".source"


def _registry_digest(registry: dict[str, Any]) -> str:
    raw = json.dumps(
        registry, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8", "strict")
    return hashlib.sha256(raw).hexdigest()


def validate_hadith_registry(registry: Any) -> list[str]:
    """Check registry shape/pins; never authenticate the declared publisher."""
    if not isinstance(registry, dict):
        return ["registry must be a JSON object"]
    items = registry.get("sources")
    if not isinstance(items, list):
        return ["registry.sources must be an array"]
    if len(items) > MAX_SOURCES:
        return [f"registry exceeds {MAX_SOURCES} sources"]
    try:
        encoded = json.dumps(
            registry, ensure_ascii=False, allow_nan=False, separators=(",", ":"),
        ).encode("utf-8", "strict")
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        return [f"registry contains invalid JSON/UTF-8 ({type(exc).__name__})"]
    if len(encoded) > MAX_REGISTRY_BYTES:
        return [f"registry exceeds {MAX_REGISTRY_BYTES} bytes"]
    errors = []
    if registry.get("schema_version") != 2 or type(registry.get("schema_version")) is not int:
        errors.append("registry.schema_version must equal 2")
    if not isinstance(registry.get("registry_id"), str) or not registry["registry_id"].strip():
        errors.append("registry.registry_id must be non-empty")
    if not items:
        errors.append("registry.sources must not be empty")
    seen_ids: set[str] = set()
    seen_files: set[str] = set()
    for i, item in enumerate(items):
        ctx = f"registry.sources[{i}]"
        if not isinstance(item, dict):
            errors.append(f"{ctx} must be an object")
            continue
        sid = item.get("source_id")
        if not isinstance(sid, str) or _SOURCE_ID.fullmatch(sid) is None:
            errors.append(f"{ctx}.source_id is unsafe or malformed")
        else:
            if sid in seen_ids:
                errors.append(f"duplicate source_id: {sid}")
            seen_ids.add(sid)
            filename = cache_filename(sid).casefold()
            if filename in seen_files:
                errors.append(f"cache filename collision: {filename}")
            seen_files.add(filename)
        for field in ("work_id", "title_ar", "provider", "version_id", "format"):
            val = item.get(field)
            if not isinstance(val, str) or not val.strip():
                errors.append(f"{ctx}.{field} must be non-empty")
        if not isinstance(item.get("source_repo"), str) or _REPO.fullmatch(item["source_repo"]) is None:
            errors.append(f"{ctx}.source_repo is unsafe or malformed")
        path = item.get("source_path")
        if (
            not isinstance(path, str) or not path
            or any(_SAFE_SEGMENT.fullmatch(p) is None for p in path.split("/"))
        ):
            errors.append(f"{ctx}.source_path is unsafe or malformed")
        for field in ("repo_ref", "source_blob_sha"):
            val = item.get(field)
            if not isinstance(val, str) or _SHA1.fullmatch(val) is None:
                errors.append(f"{ctx}.{field} must be a pinned lowercase SHA-1")
        if type(item.get("qualification_eligible")) is not bool:
            errors.append(f"{ctx}.qualification_eligible must be boolean")
    return errors


def verify_hadith_cache(
    registry: dict[str, Any],
    cache_root: str | Path,
    *,
    max_source_bytes: int = DEFAULT_MAX_SOURCE_BYTES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
    eligible_only: bool = False,
    allowed_source_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Verify the bytes against the *declared frozen registry pin*, nothing more.

    Files are opened by descriptor with O_NOFOLLOW where available, read in
    bounded chunks, and checked for mutations during the open-file read. The
    SHA-256 covers actual cached bytes; the Git SHA-1 proves only consistency
    with the registry's declared blob digest. No network or rights validation.
    """
    result: dict[str, Any] = {
        "valid": False, "scope": SCOPE, "authority": dict(AUTHORITY),
        "registry_sha256": None, "sources": [], "errors": [],
    }
    errors = validate_hadith_registry(registry)
    if errors:
        result["errors"] = errors
        return result
    if (
        type(max_source_bytes) is not int or max_source_bytes <= 0
        or type(max_total_bytes) is not int or max_total_bytes <= 0
    ):
        result["errors"] = ["byte budgets must be positive integers"]
        return result

    if type(eligible_only) is not bool:
        result["errors"] = ["eligible_only must be a boolean"]
        return result
    if allowed_source_ids is not None:
        if not isinstance(allowed_source_ids, (set, frozenset)) or any(
            not isinstance(sid, str) for sid in allowed_source_ids
        ):
            result["errors"] = ["allowed_source_ids must be a set of strings"]
            return result
        available_ids = {entry["source_id"] for entry in registry["sources"]}
        unknown = sorted(allowed_source_ids - available_ids)
        if unknown:
            result["errors"] = [f"unknown source IDs: {', '.join(unknown[:10])}"]
            return result

    selected = [
        entry for entry in registry["sources"]
        if (not eligible_only or entry["qualification_eligible"])
        and (allowed_source_ids is None or entry["source_id"] in allowed_source_ids)
    ]
    result["selection"] = {
        "registry_source_count": len(registry["sources"]),
        "selected_source_count": len(selected),
        "eligible_only": eligible_only,
        "allowed_source_ids": sorted(allowed_source_ids) if allowed_source_ids is not None else None,
    }
    if not selected:
        result["errors"] = ["source selection is empty"]
        return result

    result["registry_sha256"] = _registry_digest(registry)
    root = Path(cache_root)
    if root.is_symlink() or not root.is_dir():
        result["errors"] = ["cache root must be a non-symlink directory"]
        return result

    consumed = 0
    for entry in sorted(selected, key=lambda x: x["source_id"]):
        name = cache_filename(entry["source_id"])
        record: dict[str, Any] = {
            "source_id": entry["source_id"],
            "work_id": entry["work_id"],
            "version_id": entry["version_id"],
            "title_ar": entry["title_ar"],
            "provider": entry["provider"],
            "source_repo": entry["source_repo"],
            "source_path": entry["source_path"],
            "repo_ref": entry["repo_ref"],
            "format": entry["format"],
            "qualification_eligible": entry["qualification_eligible"],
            "cache_filename": name,
            "expected_git_blob_sha1": entry["source_blob_sha"],
            "git_blob_sha1": None,
            "local_sha256": None,
            "size_bytes": None,
            "status": "not_checked",
        }
        result["sources"].append(record)
        path = root / name
        if path.is_symlink():
            record["status"] = "unsafe_cache_file"
            errors.append(f"{entry['source_id']}: symlinked cache file")
            continue
        try:
            flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(path, flags)
        except FileNotFoundError:
            record["status"] = "missing_cache_file"
            errors.append(f"{entry['source_id']}: missing cache file")
            continue
        except OSError as exc:
            record["status"] = "unsafe_cache_file"
            errors.append(f"{entry['source_id']}: unsafe or unreadable cache file ({type(exc).__name__})")
            continue

        try:
            with os.fdopen(fd, "rb") as stream:
                before = os.fstat(stream.fileno())
                if not stat.S_ISREG(before.st_mode):
                    record["status"] = "unsafe_cache_file"
                    errors.append(f"{entry['source_id']}: cache path is not a regular file")
                    continue
                size = before.st_size
                record["size_bytes"] = size
                if size > max_source_bytes or consumed + size > max_total_bytes:
                    record["status"] = "size_limit_exceeded"
                    errors.append(f"{entry['source_id']}: source or total byte budget exceeded")
                    continue
                sha1 = hashlib.sha1()
                sha1.update(f"blob {size}\0".encode("ascii"))
                sha256 = hashlib.sha256()
                count = 0
                while chunk := stream.read(CHUNK_BYTES):
                    count += len(chunk)
                    if count > size:
                        break
                    sha1.update(chunk)
                    sha256.update(chunk)
                after = os.fstat(stream.fileno())
                consumed += count
                if (
                    count != size or before.st_size != after.st_size
                    or before.st_mtime_ns != after.st_mtime_ns
                    or before.st_ctime_ns != after.st_ctime_ns
                ):
                    record["status"] = "cache_changed_during_read"
                    errors.append(f"{entry['source_id']}: cached bytes changed during read")
                    continue
                record["git_blob_sha1"] = sha1.hexdigest()
                record["local_sha256"] = sha256.hexdigest()
                if record["git_blob_sha1"] != entry["source_blob_sha"]:
                    record["status"] = "registry_blob_mismatch"
                    errors.append(f"{entry['source_id']}: Git blob SHA-1 does not match declared registry pin")
                else:
                    record["status"] = "registry_blob_matched"
        except OSError as exc:
            record["status"] = "unsafe_cache_file"
            errors.append(f"{entry['source_id']}: cache I/O failed ({type(exc).__name__})")
    result["errors"] = errors
    result["valid"] = not errors and len(result["sources"]) == len(selected)
    return result
