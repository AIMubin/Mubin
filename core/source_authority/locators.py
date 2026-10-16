"""Strict H3.9.2 Factory char locator -> raw UTF-8 byte range bridge.

A valid mapping is bound to a complete cache-file Git blob pin, NOT to an
authenticated source edition, scholarly interpretation, or P1.0 receipt.
"""
from __future__ import annotations

import codecs
import hashlib
import os
import re
import stat
from pathlib import Path
from typing import Any

from .hadith_bridge import (
    AUTHORITY, DEFAULT_MAX_SOURCE_BYTES, CHUNK_BYTES,
    cache_filename, validate_hadith_registry,
)

MAX_EXCERPT_BYTES = 1024 * 1024
_LOCATOR = re.compile(r"gitblob:([0-9a-f]{40})#char=(0|[1-9][0-9]*):(0|[1-9][0-9]*)\Z")


def verify_hadith_locator(
    registry: dict[str, Any],
    cache_root: str | Path,
    source_id: str,
    locator: str,
    excerpt: str,
    *,
    max_source_bytes: int = DEFAULT_MAX_SOURCE_BYTES,
    max_excerpt_bytes: int = MAX_EXCERPT_BYTES,
) -> dict[str, Any]:
    """Resolve a Factory locator without loading the full source into memory.

    The old H3.9.2 Factory used Path.read_text(encoding='utf-8') and sliced
    Python *Unicode codepoints*. That read also applies universal-newline
    translation. Phase B rejects CR anywhere in the raw file: LF-only source
    bytes are a necessary condition for safely equating codepoint offsets with
    the original UTF-8 byte positions using this narrow adapter.

    A source digest is checked on the SAME opened file descriptor before
    emitting an excerpt byte receipt. Only hashes/locators are returned; never
    the source text or excerpt content.
    """
    result: dict[str, Any] = {
        "valid": False,
        "scope": "pinned_bytes_and_exact_excerpt_only",
        "authority": dict(AUTHORITY),
        "receipt": None,
        "errors": [],
    }

    def reject(reason: str) -> dict[str, Any]:
        result["errors"].append(reason)
        return result

    problems = validate_hadith_registry(registry)
    if problems:
        result["errors"] = problems
        return result
    if not isinstance(source_id, str):
        return reject("source_id must be a string")
    if not isinstance(locator, str):
        return reject("locator must be a string")
    if (
        type(max_source_bytes) is not int or max_source_bytes <= 0
        or type(max_excerpt_bytes) is not int or max_excerpt_bytes <= 0
    ):
        return reject("byte limits must be positive integers")
    if not isinstance(excerpt, str) or not excerpt:
        return reject("excerpt must be non-empty UTF-8 text")
    try:
        target = excerpt.encode("utf-8", "strict")
    except UnicodeError:
        return reject("excerpt contains invalid UTF-8 codepoints")
    if len(target) > max_excerpt_bytes:
        return reject("excerpt exceeds byte limit")
    match = _LOCATOR.fullmatch(locator)
    if match is None:
        return reject("locator must be canonical gitblob:<pin>#char=start:end")
    expected_pin, raw_a, raw_b = match.groups()
    a, b = int(raw_a), int(raw_b)
    if b <= a:
        return reject("locator character range must be strictly increasing")

    sources = {item["source_id"]: item for item in registry["sources"]}
    entry = sources.get(source_id)
    if entry is None:
        return reject("unknown source_id in frozen registry")
    if expected_pin != entry["source_blob_sha"]:
        return reject("locator pin differs from registry source pin")

    root = Path(cache_root)
    if root.is_symlink() or not root.is_dir():
        return reject("unsafe source cache root")
    path = root / cache_filename(source_id)
    if path.is_symlink():
        return reject("unsafe symlink cache file")
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0))
    except OSError as exc:
        return reject(f"missing or unsafe cache file ({type(exc).__name__})")

    try:
        with os.fdopen(fd, "rb") as stream:
            fd = None
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode):
                return reject("unsafe cache file: not a regular file")
            size = before.st_size
            if size > max_source_bytes:
                return reject("cached source exceeds byte limit")

            raw_sha1 = hashlib.sha1()
            raw_sha1.update(f"blob {size}\0".encode("ascii"))
            raw_sha256 = hashlib.sha256()
            decoder = codecs.getincrementaldecoder("utf-8")(errors="strict")
            char_pos = 0
            byte_pos = 0
            start_byte: int | None = None
            end_byte: int | None = None
            counted_bytes = 0

            def scan(decoded: str) -> None:
                nonlocal char_pos, byte_pos, start_byte, end_byte
                # Path.read_text in H3.9.2 normalizes CRLF/CR. Reject rather
                # than silently map Factory's normalized char offsets to raw
                # bytes with incompatible line endings.
                if "\r" in decoded:
                    raise ValueError("unsupported CR newline in raw source")
                chunk_chars = len(decoded)
                chunk_bytes = len(decoded.encode("utf-8"))
                for wanted, is_start in ((a, True), (b, False)):
                    if char_pos <= wanted <= char_pos + chunk_chars:
                        offset = len(decoded[:wanted - char_pos].encode("utf-8"))
                        if is_start:
                            start_byte = byte_pos + offset
                        else:
                            end_byte = byte_pos + offset
                char_pos += chunk_chars
                byte_pos += chunk_bytes

            while chunk := stream.read(CHUNK_BYTES):
                counted_bytes += len(chunk)
                if counted_bytes > size:
                    return reject("source grew during verification")
                raw_sha1.update(chunk)
                raw_sha256.update(chunk)
                scan(decoder.decode(chunk, final=False))
            scan(decoder.decode(b"", final=True))
            if counted_bytes != size or byte_pos != counted_bytes:
                return reject("source size or UTF-8 byte accounting changed during scan")
            if raw_sha1.hexdigest() != expected_pin:
                return reject("cached source does not match frozen registry pin")
            if start_byte is None or end_byte is None or end_byte <= start_byte:
                return reject("locator character span exceeds decoded source")
            if end_byte - start_byte != len(target):
                return reject("excerpt byte length differs from resolved raw span")
            stream.seek(start_byte)
            source_excerpt = stream.read(end_byte - start_byte)
            if source_excerpt != target:
                return reject("excerpt differs from exact pinned source byte span")
            after = os.fstat(stream.fileno())
            if (
                before.st_dev != after.st_dev or before.st_ino != after.st_ino
                or before.st_size != after.st_size
                or before.st_mtime_ns != after.st_mtime_ns
                or before.st_ctime_ns != after.st_ctime_ns
            ):
                return reject("cache source changed during locator verification")

            result["receipt"] = {
                "source_id": source_id,
                "work_id": entry["work_id"],
                "version_id": entry["version_id"],
                "repo_ref": entry["repo_ref"],
                "source_path": entry["source_path"],
                "locator": locator,
                "start_char": a,
                "end_char": b,
                "start_byte": start_byte,
                "end_byte": end_byte,
                "source_git_blob_sha1": raw_sha1.hexdigest(),
                "source_sha256": raw_sha256.hexdigest(),
                "excerpt_sha256": hashlib.sha256(target).hexdigest(),
                "verification_kind": "registry_pinned_bytes_and_exact_quote",
            }
            result["valid"] = True
            return result
    except UnicodeError:
        return reject("source is not valid strict UTF-8")
    except (OSError, ValueError) as exc:
        if isinstance(exc, ValueError) and "CR" in str(exc):
            return reject("unsupported CR newline in raw source")
        return reject(f"unsafe/unreadable cached source ({type(exc).__name__})")
    finally:
        if fd is not None:
            os.close(fd)
