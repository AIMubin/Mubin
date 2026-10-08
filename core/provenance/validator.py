"""P1 offline, byte-exact provenance checks. No external-source authority or fatwa."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator

from core.inference import validate_bundle

MANIFEST_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "schemas"
    / "source-snapshot-manifest.schema.json"
)
MAX_SNAPSHOT_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_SOURCES = 16
PATH_PART = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _digest_object(value: Any) -> str:
    """Canonical local-input fingerprint, NOT a digital signature."""
    return _sha(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8"))


def _safe_snapshot_path(root: Path, relative: str) -> Path:
    """Restrict local snapshots to plain files under corpus root, without symlinks."""
    posix = PurePosixPath(relative)
    if (
        posix.is_absolute()
        or not relative
        or "\\" in relative
        or ":" in relative
        or "//" in relative
        or any(not PATH_PART.fullmatch(part) for part in relative.split("/"))
        or relative.split("/")[-1].startswith(".")
    ):
        raise ValueError("unsafe relative snapshot path")
    if root.is_symlink() or not root.is_dir():
        raise ValueError("corpus root must be an existing non-symlink directory")
    path = root
    for segment in posix.parts:
        path = path / segment
        if path.is_symlink():
            raise ValueError("source paths must not contain symbolic links")
    if not path.is_file():
        raise ValueError("source snapshot is not an existing regular file")
    if not path.resolve(strict=True).is_relative_to(root.resolve(strict=True)):
        raise ValueError("source snapshot escapes corpus root")
    return path


def verify_bundle(
    bundle: dict[str, Any],
    manifest: dict[str, Any],
    corpus_root: str | Path,
) -> dict[str, Any]:
    """Return {valid, errors, receipts}. Fail-closed and never mutate the inputs.

    A receipt proves a byte-exact match to an *operator-supplied local snapshot*.
    It does not prove publication origin, lawful licensing or textual entailment.
    """
    errors = ["P0: " + error for error in validate_bundle(bundle)]
    schema = json.loads(MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    errors.extend(
        "manifest: " + "/".join(map(str, issue.absolute_path)) + ": " + issue.message
        for issue in Draft202012Validator(schema).iter_errors(manifest)
    )
    if errors:
        return {"valid": False, "errors": sorted(set(errors)), "receipts": []}

    sources = manifest["sources"]
    if len(sources) > MAX_SOURCES:
        return {"valid": False, "errors": [
            f"manifest: exceeds P1 snapshot cap of {MAX_SOURCES} sources"
        ], "receipts": []}

    indexed: dict[str, dict[str, Any]] = {}
    for entry in sources:
        if entry["id"] in indexed:
            errors.append(f"manifest: duplicate source {entry['id']}")
        indexed[entry["id"]] = entry
    p0_sources = {entry["id"]: entry for entry in bundle["sources"]}
    if indexed.keys() != p0_sources.keys():
        errors.append("manifest source IDs do not match P0 bundle source IDs")

    raw_snapshots: dict[str, bytes] = {}
    spans: dict[tuple[str, str], tuple[int, int]] = {}
    consumed = 0
    root = Path(corpus_root)
    for entry in sources:
        key = entry["id"]
        base = p0_sources.get(key)
        if base is None:
            continue
        for field, mapped in (
            ("work_title", "work_title"), ("edition", "edition"),
            ("scope_locator", "locator"), ("content_sha256", "content_sha256")
        ):
            if entry[field] != base[mapped]:
                errors.append(f"source {key}: mismatched {field}")
        rights = entry["rights"]
        if rights["status"] != "operator_cleared":
            errors.append(f"source {key}: rights not operator-cleared")
        try:
            path = _safe_snapshot_path(root, entry["relative_path"])
            with path.open("rb") as fp:
                raw = fp.read(MAX_SNAPSHOT_BYTES + 1)
            if len(raw) > MAX_SNAPSHOT_BYTES:
                errors.append(f"source {key}: snapshot exceeds {MAX_SNAPSHOT_BYTES} bytes")
                continue
            consumed += len(raw)
            if consumed > MAX_TOTAL_BYTES:
                errors.append("snapshots exceed total P1 byte limit")
                break
            raw.decode("utf-8", errors="strict")
        except (OSError, ValueError, UnicodeError) as exc:
            errors.append(f"source {key}: unreadable or unsafe UTF-8 snapshot: {exc}")
            continue
        if _sha(raw) != entry["content_sha256"]:
            errors.append(f"source {key}: full snapshot SHA-256 mismatch")
            continue
        raw_snapshots[key] = raw
        intervals: list[tuple[int, int]] = []
        for span in entry["spans"]:
            locator = span["locator"]
            skey = (key, locator)
            if skey in spans:
                errors.append(f"source {key}: duplicate locator {locator}")
                continue
            a, b = span["start_byte"], span["end_byte"]
            if b <= a or b > len(raw):
                errors.append(f"source {key}: invalid byte span for {locator}")
                continue
            try:
                raw[a:b].decode("utf-8", errors="strict")
            except UnicodeError:
                errors.append(f"source {key}: span splits UTF-8 character at {locator}")
                continue
            spans[skey] = (a, b)
            intervals.append((a, b))
        intervals.sort()
        if any(left[1] > right[0] for left, right in zip(intervals, intervals[1:])):
            errors.append(f"source {key}: overlapping locator spans")

    receipts: list[dict[str, Any]] = []
    for evidence in bundle["evidence"]:
        eid, sid, locator = evidence["id"], evidence["source_id"], evidence["locator"]
        if evidence["verification_status"] != "verified":
            errors.append(f"evidence {eid}: P1 cannot certify unverified or rejected claim")
            continue
        if evidence["verification_method"] != "exact_source_match":
            errors.append(f"evidence {eid}: P1 requires exact_source_match method")
        span = spans.get((sid, locator))
        raw = raw_snapshots.get(sid)
        if span is None or raw is None:
            errors.append(f"evidence {eid}: missing verified snapshot locator {sid}/{locator}")
            continue
        start, end = span
        excerpt = evidence["excerpt"].encode("utf-8")
        if excerpt != raw[start:end]:
            errors.append(f"evidence {eid}: byte-exact excerpt mismatch at {locator}")
            continue
        if _sha(excerpt) != evidence["excerpt_sha256"]:
            errors.append(f"evidence {eid}: excerpt SHA-256 mismatch")
            continue
        receipts.append({
            "evidence_id": eid,
            "source_id": sid,
            "locator": locator,
            "start_byte": start,
            "end_byte": end,
            "excerpt_sha256": evidence["excerpt_sha256"],
            "source_sha256": _sha(raw),
            "verification_kind": "local_byte_exact_match",
        })

    if errors:
        return {"valid": False, "errors": sorted(set(errors)), "receipts": []}
    receipts.sort(key=lambda item: item["evidence_id"])
    return {
        "valid": True, "errors": [], "scope": "local_byte_exact_match_only",
        "rights_assurance": "operator_assertion_only",
        "bundle_sha256": _digest_object(bundle),
        "manifest_sha256": _digest_object(manifest),
        "receipts": receipts,
    }
