"""P1.1 Phase C: parent-pinned, explicitly derived byte windows.

This module never confuses a P1 local window receipt with authentication of
the full classical work. It does not make any rights or scholarly claims.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .hadith_bridge import (
    AUTHORITY, CHUNK_BYTES, DEFAULT_MAX_SOURCE_BYTES,
    cache_filename,
)
from .locators import verify_hadith_locator

WINDOW_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "schemas"
    / "parent-window-binding.schema.json"
)
# Small enough for P1 <=8 MiB snapshot and practical P0 <=5 MiB JSON bundles.
DEFAULT_MAX_WINDOW_BYTES = 1024 * 1024
ABSOLUTE_MAX_WINDOW_BYTES = 4 * 1024 * 1024


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(payload: Any) -> bytes:
    return json.dumps(
        payload, ensure_ascii=False, allow_nan=False, sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8", "strict")


def _identity_payload(binding: dict[str, Any]) -> dict[str, Any]:
    p, w = binding["parent"], binding["window"]
    return {
        "source_id": p["source_id"],
        "version_id": p["version_id"],
        "repo_ref": p["repo_ref"],
        "git_blob_sha1": p["git_blob_sha1"],
        "source_sha256": p["source_sha256"],
        "absolute_start_byte": w["absolute_start_byte"],
        "absolute_end_byte": w["absolute_end_byte"],
        "content_sha256": w["content_sha256"],
    }


def _binding_digest(binding: dict[str, Any]) -> str:
    unsigned = dict(binding)
    unsigned.pop("binding_sha256", None)
    return _sha(_canonical(unsigned))


def validate_parent_window_binding(
    binding: Any, window_bytes: bytes | bytearray | None,
) -> list[str]:
    """Check metadata/window self-consistency, NOT the parent or its authority.

    Only derive_parent_window independently reopens/re-hashes the parent.
    A forged binding rehashed by its author cannot establish source origin.
    """
    if not isinstance(binding, dict):
        return ["schema: binding must be a mapping"]
    if not isinstance(window_bytes, bytes):
        return ["window bytes must be immutable bytes"]
    if len(window_bytes) > ABSOLUTE_MAX_WINDOW_BYTES:
        return ["window exceeds binding size limit"]
    try:
        raw = _canonical(binding)
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        return [f"schema: invalid binding representation ({type(exc).__name__})"]
    if len(raw) > 5 * 1024 * 1024:
        return ["schema: binding JSON byte limit exceeded"]
    schema = json.loads(WINDOW_SCHEMA_PATH.read_text(encoding="utf-8"))
    errs = sorted({
        "schema: " + "/".join(map(str, e.absolute_path)) + ": " + e.message
        for e in Draft202012Validator(schema).iter_errors(binding)
    })
    if errs:
        return errs

    parent, window, quote = binding["parent"], binding["window"], binding["quote"]
    issues: list[str] = []
    # JSON hashes are self-asserted: validate actual bytes and source format too.
    # With the 4 MiB cap already enforced, decoding here is bounded.
    try:
        window_bytes.decode("utf-8", "strict")
    except UnicodeError:
        issues.append("window contains invalid UTF-8 bytes")
    if b"\r" in window_bytes:
        issues.append("window contains unsupported CR newline")
    if window["size_bytes"] > ABSOLUTE_MAX_WINDOW_BYTES:
        issues.append("window declared size exceeds maximum byte limit")
    if parent["quote_end_byte"] <= parent["quote_start_byte"]:
        issues.append("parent quote byte span is invalid")
    if not (
        0 <= window["absolute_start_byte"] <= parent["quote_start_byte"]
        < parent["quote_end_byte"] <= window["absolute_end_byte"] <= parent["size_bytes"]
    ):
        issues.append("window is not bounded to the parent quote span")
    if window["size_bytes"] != len(window_bytes):
        issues.append("window byte length mismatch")
    if window["size_bytes"] != window["absolute_end_byte"] - window["absolute_start_byte"]:
        issues.append("window absolute byte span/length mismatch")
    if _sha(window_bytes) != window["content_sha256"]:
        issues.append("window content digest mismatch")
    a, b = quote["start_in_window_byte"], quote["end_in_window_byte"]
    if a != parent["quote_start_byte"] - window["absolute_start_byte"]:
        issues.append("quote start offset differs from parent")
    if b != parent["quote_end_byte"] - window["absolute_start_byte"]:
        issues.append("quote end offset differs from parent")
    if not (0 <= a < b <= len(window_bytes)):
        issues.append("quote byte interval outside window")
    else:
        if _sha(window_bytes[a:b]) != quote["sha256"]:
            issues.append("quote digest mismatch")
        try:
            literal_quote = window_bytes[a:b].decode("utf-8", "strict")
        except UnicodeError:
            issues.append("quote splits a UTF-8 character boundary")
        else:
            if len(literal_quote) != quote["end_char"] - quote["start_char"]:
                issues.append("quote codepoint length inconsistent with character locator")
    if quote["end_char"] <= quote["start_char"]:
        issues.append("quote character span invalid")
    match = re.fullmatch(
        r"gitblob:([a-f0-9]{40})#char=(0|[1-9][0-9]{0,18}):(0|[1-9][0-9]{0,18})",
        quote["locator"],
    )
    if (
        match is None or int(match.group(2)) != quote["start_char"]
        or int(match.group(3)) != quote["end_char"]
    ):
        issues.append("quote character offsets differ from frozen locator")
    if not quote["locator"].startswith("gitblob:" + parent["git_blob_sha1"] + "#char="):
        issues.append("quote locator's parent blob pin mismatch")
    if window["id"] != "win." + _sha(_canonical(_identity_payload(binding))):
        issues.append("window identity digest mismatch")
    if binding["binding_sha256"] != _binding_digest(binding):
        issues.append("binding fingerprint mismatch")
    return sorted(set(issues))


def derive_parent_window(
    registry: dict[str, Any],
    cache_root: str | Path,
    source_id: str,
    locator: str,
    excerpt: str,
    *,
    left_context_bytes: int = 0,
    right_context_bytes: int = 0,
    max_source_bytes: int = DEFAULT_MAX_SOURCE_BYTES,
    max_window_bytes: int = DEFAULT_MAX_WINDOW_BYTES,
) -> tuple[dict[str, Any], bytes | None]:
    """Derive and return a metadata-only report plus separately held window bytes.

    Caller must explicitly stage bytes before any P1.0 call and provide an
    independently justified rights assertion. We never auto-assert clearance.
    """
    result: dict[str, Any] = {
        "valid": False, "scope": "parent_pinned_window_only",
        "authority": dict(AUTHORITY), "binding": None, "errors": [],
    }

    def fail(msg: str) -> tuple[dict[str, Any], None]:
        result["errors"].append(msg)
        return result, None

    if any(type(val) is not int for val in (
        left_context_bytes, right_context_bytes, max_source_bytes, max_window_bytes
    )):
        return fail("byte budgets/context must be plain integers")
    if left_context_bytes < 0 or right_context_bytes < 0:
        return fail("context byte counts cannot be negative")
    if max_source_bytes <= 0 or not 0 < max_window_bytes <= ABSOLUTE_MAX_WINDOW_BYTES:
        return fail("source/window byte limit is invalid")
    if left_context_bytes > max_window_bytes or right_context_bytes > max_window_bytes:
        return fail("context exceeds window byte limit")

    mapped = verify_hadith_locator(
        registry, cache_root, source_id, locator, excerpt,
        max_source_bytes=max_source_bytes, max_excerpt_bytes=max_window_bytes,
    )
    if not mapped["valid"]:
        result["errors"] = mapped["errors"]
        return result, None
    receipt = mapped["receipt"]
    quote_start, quote_end = receipt["start_byte"], receipt["end_byte"]
    entry = next(item for item in registry["sources"] if item["source_id"] == source_id)
    path = Path(cache_root) / cache_filename(source_id)

    if path.is_symlink() or Path(cache_root).is_symlink():
        return fail("unsafe parent cached file or cache root")

    fd: int | None = None
    try:
        fd = os.open(
            path, os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
        with os.fdopen(fd, "rb") as stream:
            fd = None
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode):
                return fail("unsafe parent file: not a regular file")
            size = before.st_size
            if size < 1 or size > max_source_bytes:
                return fail("parent file exceeds byte budget")
            start = max(0, quote_start - left_context_bytes)
            end = min(size, quote_end + right_context_bytes)
            if end <= start or end - start > max_window_bytes:
                return fail("derived window exceeds byte limit")

            sha1 = hashlib.sha1()
            sha1.update(f"blob {size}\0".encode("ascii"))
            sha256 = hashlib.sha256()
            read_bytes = 0
            while chunk := stream.read(CHUNK_BYTES):
                read_bytes += len(chunk)
                if read_bytes > size:
                    return fail("parent file changed size during read")
                sha1.update(chunk)
                sha256.update(chunk)
            if read_bytes != size:
                return fail("parent file truncated during read")
            if sha1.hexdigest() != entry["source_blob_sha"]:
                return fail("parent registry Git pin mismatch")
            if sha256.hexdigest() != receipt["source_sha256"]:
                return fail("parent source SHA-256 changed since locator verification")

            stream.seek(start)
            window_bytes = stream.read(end - start)
            after = os.fstat(stream.fileno())
            if (
                len(window_bytes) != end - start
                or before.st_dev != after.st_dev or before.st_ino != after.st_ino
                or before.st_size != after.st_size
                or before.st_mtime_ns != after.st_mtime_ns
                or before.st_ctime_ns != after.st_ctime_ns
            ):
                return fail("parent file changed during derivation")
    except OSError as exc:
        return fail(f"missing or unsafe parent cache file ({type(exc).__name__})")
    finally:
        if fd is not None:
            os.close(fd)

    # A derived window must be valid UTF-8 on its own: context cannot start or
    # stop in the middle of an Arabic/emoji multibyte codepoint.
    try:
        window_bytes.decode("utf-8", "strict")
    except UnicodeError:
        return fail("derived window splits a UTF-8 character boundary")

    relative_start = quote_start - start
    relative_end = quote_end - start
    quote_bytes = excerpt.encode("utf-8", "strict")
    if window_bytes[relative_start:relative_end] != quote_bytes:
        return fail("derived window does not include exact source excerpt")

    binding: dict[str, Any] = {
        "contract_version": "0.1.0",
        "scope": "parent_pinned_window_only",
        "parent": {
            "source_id": source_id,
            "work_id": entry["work_id"],
            "version_id": entry["version_id"],
            "repo_ref": entry["repo_ref"],
            "source_path": entry["source_path"],
            "git_blob_sha1": entry["source_blob_sha"],
            "source_sha256": receipt["source_sha256"],
            "size_bytes": size,
            "quote_start_byte": quote_start,
            "quote_end_byte": quote_end,
        },
        "window": {
            "id": "",
            "absolute_start_byte": start,
            "absolute_end_byte": end,
            "size_bytes": len(window_bytes),
            "content_sha256": _sha(window_bytes),
            "identity_scope": "derived_byte_window_not_parent_book",
        },
        "quote": {
            "locator": locator,
            "start_char": receipt["start_char"],
            "end_char": receipt["end_char"],
            "start_in_window_byte": relative_start,
            "end_in_window_byte": relative_end,
            "sha256": receipt["excerpt_sha256"],
        },
        "authority": dict(AUTHORITY),
    }
    binding["window"]["id"] = "win." + _sha(_canonical(_identity_payload(binding)))
    binding["binding_sha256"] = _binding_digest(binding)
    issues = validate_parent_window_binding(binding, window_bytes)
    if issues:
        result["errors"] = issues
        return result, None
    result["valid"] = True
    result["binding"] = binding
    return result, window_bytes


def check_linked_p1_receipt(
    binding: dict[str, Any],
    p1_result: dict[str, Any],
    window_bytes: bytes,
) -> list[str]:
    """Check a P1 *local* receipt matches precisely one derived quote window.

    Input should be the direct output of core.provenance.verify_bundle in a
    trusted pipeline. JSON metadata consistency is NOT an attestation of
    publisher identity, real permissions, or trustworthy remote execution.
    """
    if not isinstance(binding, dict) or not isinstance(p1_result, dict):
        return ["binding and P1 result must be objects"]
    # Re-validate the *actual* immutable derived bytes: a rehashed, impossible
    # size/UTF-8/CR claim must never be enough to link a P1 receipt.
    binding_issues = validate_parent_window_binding(binding, window_bytes)
    if binding_issues:
        return ["invalid parent-window binding: " + problem for problem in binding_issues]
    try:
        raw = _canonical(binding)
        if len(raw) > 5 * 1024 * 1024:
            return ["binding JSON byte limit exceeded"]
        schema = json.loads(WINDOW_SCHEMA_PATH.read_text(encoding="utf-8"))
        schema_errors = list(Draft202012Validator(schema).iter_errors(binding))
    except (TypeError, ValueError, RecursionError, UnicodeError) as exc:
        return [f"invalid binding JSON ({type(exc).__name__})"]
    if schema_errors:
        return ["binding schema invalid"]
    # Hashes are consistency checks, not signatures; nevertheless an ordinary
    # edited parent identity must never silently relink to an existing P1 receipt.
    if binding["binding_sha256"] != _binding_digest(binding):
        return ["parent-window binding fingerprint mismatch"]
    parent, window, quote = binding["parent"], binding["window"], binding["quote"]
    if window["id"] != "win." + _sha(_canonical(_identity_payload(binding))):
        return ["parent-window identity digest mismatch"]
    match = re.fullmatch(
        r"gitblob:([a-f0-9]{40})#char=(0|[1-9][0-9]{0,18}):(0|[1-9][0-9]{0,18})",
        quote["locator"],
    )
    if (
        match is None or match.group(1) != parent["git_blob_sha1"]
        or int(match.group(2)) != quote["start_char"]
        or int(match.group(3)) != quote["end_char"]
    ):
        return ["parent-window locator/character mapping mismatch"]
    if (
        window["absolute_start_byte"] + quote["start_in_window_byte"] != parent["quote_start_byte"]
        or window["absolute_start_byte"] + quote["end_in_window_byte"] != parent["quote_end_byte"]
        or window["absolute_end_byte"] > parent["size_bytes"]
    ):
        return ["parent-window absolute/relative byte binding mismatch"]

    if p1_result.get("valid") is not True:
        return ["P1 result is not valid"]
    if p1_result.get("scope") != "local_byte_exact_match_only":
        return ["P1 receipt assurance scope mismatch"]
    if p1_result.get("rights_assurance") != "operator_assertion_only":
        return ["P1 rights assurance scope mismatch"]
    receipts = p1_result.get("receipts")
    if not isinstance(receipts, list) or len(receipts) != 1:
        return ["expected exactly one P1 quote receipt for this derived window"]
    p1 = receipts[0]
    if not isinstance(p1, dict):
        return ["P1 quote receipt must be an object"]

    q = binding["quote"]
    w = binding["window"]
    expected = {
        "source_id": w["id"],
        "source_sha256": w["content_sha256"],
        "excerpt_sha256": q["sha256"],
        "start_byte": q["start_in_window_byte"],
        "end_byte": q["end_in_window_byte"],
        "verification_kind": "local_byte_exact_match",
    }
    issues = []
    for name, desired in expected.items():
        actual = p1.get(name)
        if type(actual) is not type(desired) or actual != desired:
            issues.append(f"P1 receipt {name} differs from parent-window binding")
    return issues
