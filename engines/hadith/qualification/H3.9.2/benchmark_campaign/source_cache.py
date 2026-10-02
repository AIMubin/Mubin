from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path
from typing import Any

from .core import sha256_file, write_json
from .source_registry import load_source_registry


def cache_filename(source_id: str) -> str:
    safe = source_id.replace(":", "__").replace("/", "_")
    return f"{safe}.source"


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def raw_url(source: dict[str, Any]) -> str:
    repo = source["source_repo"]
    ref = source.get("repo_ref")
    path = source["source_path"]
    if not ref:
        raise ValueError(f"source has no repo_ref pin: {source['source_id']}")
    return f"https://raw.githubusercontent.com/{repo}/{ref}/{path}"


def verify_cached_source(path: Path, source: dict[str, Any]) -> dict[str, Any]:
    data = path.read_bytes()
    actual_blob = git_blob_sha(data)
    expected_blob = source.get("source_blob_sha")
    return {
        "source_id": source["source_id"],
        "path": str(path),
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "git_blob_sha": actual_blob,
        "expected_git_blob_sha": expected_blob,
        "verified": actual_blob == expected_blob,
    }


def acquire_sources(root: Path, cache_dir: Path, include_ineligible: bool = False,
                    allowed_source_ids: set[str] | None = None) -> dict[str, Any]:
    registry = load_source_registry(root)
    cache_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for source in registry.get("sources", []):
        if source.get("qualification_eligible") is not True and not include_ineligible:
            continue
        if allowed_source_ids is not None and source.get("source_id") not in allowed_source_ids:
            continue
        path = cache_dir / cache_filename(source["source_id"])
        if path.exists():
            check = verify_cached_source(path, source)
            if not check["verified"]:
                raise ValueError(f"cached source hash mismatch: {source['source_id']}")
            check["downloaded"] = False
            results.append(check)
            continue
        url = raw_url(source)
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            with urllib.request.urlopen(url, timeout=120) as response, tmp.open("wb") as f:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
            check = verify_cached_source(tmp, source)
            if not check["verified"]:
                tmp.unlink(missing_ok=True)
                check.update({"downloaded": True, "url": url, "reason": "git_blob_sha_mismatch"})
                results.append(check)
                continue
            tmp.replace(path)
            check["path"] = str(path)
            check["downloaded"] = True
            check["url"] = url
            results.append(check)
        except Exception as exc:
            tmp.unlink(missing_ok=True)
            results.append({
                "source_id": source["source_id"],
                "path": str(path),
                "url": url,
                "downloaded": False,
                "verified": False,
                "reason": "download_error",
                "error": f"{type(exc).__name__}: {exc}",
            })

    manifest = {
        "registry_id": registry.get("registry_id"),
        "source_count": len(results),
        "all_verified": all(x["verified"] for x in results),
        "sources": results,
    }
    write_json(cache_dir / "SOURCE_CACHE_MANIFEST.json", manifest)
    return manifest


def verify_source_cache(root: Path, cache_dir: Path, include_ineligible: bool = False,
                        allowed_source_ids: set[str] | None = None) -> dict[str, Any]:
    registry = load_source_registry(root)
    results = []
    for source in registry.get("sources", []):
        if source.get("qualification_eligible") is not True and not include_ineligible:
            continue
        if allowed_source_ids is not None and source.get("source_id") not in allowed_source_ids:
            continue
        path = cache_dir / cache_filename(source["source_id"])
        if not path.exists():
            results.append({"source_id": source["source_id"], "path": str(path), "verified": False, "reason": "missing"})
            continue
        results.append(verify_cached_source(path, source))
    return {
        "registry_id": registry.get("registry_id"),
        "source_count": len(results),
        "all_verified": bool(results) and all(x["verified"] for x in results),
        "sources": results,
    }
