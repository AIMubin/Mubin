"""H-Search-01.1: pinned hadith source retrieval (non-holdout only).

Reads the frozen H3.9.2 source registry as DATA (read-only). Only the four
operator-authorized non-holdout sources are ever acquired or read. Every
cached file is verified against the registry git-blob SHA before use.
Holdout sources are never read, listed, or acquired by this module.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from pathlib import Path
from typing import Any

from engines.hadith.hsearch.contracts import _need


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

REGISTRY_PATH = (Path(__file__).resolve().parents[3]
                 / "engines" / "hadith" / "qualification" / "H3.9.2"
                 / "sources" / "source-registry.json")
AUTHORIZED = frozenset((
    "openiti:0279Tirmidhi.Sunan",
    "openiti:0458Bayhaqi.SunanKubra",
    "openiti:0762IbnYusufZaylaci.NasbRaya",
    "openiti:1353IbnCabdRahimMubarakfuri.TuhfatAhwadhi"))
NO_HOLDOUT_NOTE = "holdout sources are out of scope and never read"


def load_registry() -> dict:
    reg = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    _need(reg.get("schema_version") == 2, "HS_REGISTRY_SCHEMA_UNSUPPORTED")
    return reg


def authorized_sources() -> dict[str, dict]:
    reg = load_registry()
    out = {}
    for s in reg.get("sources", []):
        if s.get("source_id") in AUTHORIZED:
            out[s["source_id"]] = s
    missing = AUTHORIZED - set(out)
    _need(not missing, "HS_AUTHORIZED_SOURCE_MISSING_FROM_REGISTRY")
    return out


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def cache_filename(source_id: str) -> str:
    return source_id.replace(":", "__").replace("/", "_") + ".source"


def raw_url(source: dict) -> str:
    repo, ref, path = source["source_repo"], source.get("repo_ref"), source["source_path"]
    _need(bool(ref), "HS_SOURCE_UNPINNED")
    return f"https://raw.githubusercontent.com/{repo}/{ref}/{path}"


def acquire(cache_dir: Path, *, allow_network: bool = False) -> dict[str, dict]:
    """Acquire (or reuse) and verify the authorized sources. Returns
    {source_id: {path, verified, blob_sha, size}}."""
    _need(cache_dir is not None and not cache_dir.is_symlink(),
          "HS_CACHE_DIR_INVALID")
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = {}
    for sid, src in authorized_sources().items():
        path = cache_dir / cache_filename(sid)
        if path.is_file():
            data = path.read_bytes()
        elif allow_network:
            req = urllib.request.Request(raw_url(src),
                                         headers={"User-Agent": "mubin-hsearch01"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
            path.write_bytes(data)
        else:
            out[sid] = {"path": str(path), "verified": False,
                        "SOURCE_UNAVAILABLE": True}
            continue
        actual = git_blob_sha(data)
        verified = actual == src.get("source_blob_sha")
        _need(verified, "HS_SOURCE_BLOB_MISMATCH")
        out[sid] = {"path": str(path), "verified": True,
                    "blob_sha": actual,
                    "sha256": _sha256(data), "size": len(data)}
    return out


# --- minimal OpenITI parsing: paragraph blocks as witness candidate spans ---
_HEADING = re.compile(r"^#{1,6} ", re.M)


def load_text(meta: dict, path: Path) -> str:
    data = path.read_bytes()
    _need(git_blob_sha(data) == meta.get("source_blob_sha"),
          "HS_SOURCE_BLOB_MISMATCH")
    return data.decode("utf-8", "strict")


def witness_candidate_spans(text: str, *, min_len: int = 40,
                            max_len: int = 6000) -> list[tuple[int, int, str]]:
    """Conservative segmentation of an OpenITI text into block spans.

    Blocks are split on blank lines / headings. Each block is a CANDIDATE
    location; no claim is made that a block is a complete independent hadith
    (a source may contain isnad, matn, commentary, grading, or commentary).
    Returns (start, end, locator) triples; locator is a line-based hint.
    """
    _need(type(text) is str and text, "HS_TEXT_EMPTY")
    spans = []
    line_starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            line_starts.append(i + 1)
    def line_of(off: int) -> int:
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= off:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1
    # Line-merged blocks: consecutive non-empty lines merged up to max_len.
    # OpenITI mARkdown/CEX texts use single newlines; blank-line splitting
    # alone produced giant unusable blocks. A block is still only a
    # CANDIDATE location, never a claim of an independent hadith.
    n = len(text)
    i = 0
    while i < n:
        s0 = i
        e1 = i
        while i < n:
            nl = text.find("\n", i)
            line_end = n if nl < 0 else nl + 1
            line = text[i:line_end].strip()
            if not line or line.startswith("#"):
                if e1 > s0:
                    break
                i = line_end
                continue
            if e1 > s0 and line_end - s0 > max_len:
                break
            e1 = line_end
            i = line_end
        if e1 - s0 >= min_len:
            while e1 > s0 and text[e1 - 1] in " \t\u200f\u200e":
                e1 -= 1
            if e1 - s0 >= min_len:
                spans.append((s0, e1, f"L{line_of(s0)}"))
        if i <= s0:
            i = s0 + 1
    return spans
