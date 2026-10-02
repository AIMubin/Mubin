from __future__ import annotations

from pathlib import Path
from typing import Any

from .core import load_json


def default_registry_path(root: Path) -> Path:
    return root / "sources" / "source-registry.json"


def load_source_registry(root: Path, path: Path | None = None) -> dict[str, Any]:
    p = path or default_registry_path(root)
    if not p.exists():
        return {"schema_version": 1, "sources": []}
    return load_json(p)


def source_map(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for source in registry.get("sources", []):
        source_id = source["source_id"]
        if source_id in out:
            raise ValueError(f"duplicate source_id in source registry: {source_id}")
        out[source_id] = source
    return out
