"""Development-first internal-research ingestion bridge (fail-closed).

Links core.internal_source_use.assess_internal_source_use into
corpus.import_local.ingest with an explicit internal-research admission mode
and a hash-chained append-only usage register kept OUTSIDE Git.

Admission of a source requires ALL of:
  - the gate returning INTERNAL_DEVELOPMENT_RESEARCH_ELIGIBLE
  - a content-addressed object + internal_only manifest in the corpus root
  - a hash-chained usage-register entry referencing that manifest

A crash at any point leaves the source NOT admitted (fail-closed). Refusals
raise InternalSourceRefusal carrying a stable code only - never source text,
paths or secrets. This module performs NO legal or scholarly clearance: the
attestations are operator-declared and must be independently retained.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile

from core.internal_source_use import assess_internal_source_use
from corpus.import_local import ingest

VERSION = "internal-research-ingest/0.1.0"
ADMISSION_ELIGIBLE = "INTERNAL_DEVELOPMENT_RESEARCH_ELIGIBLE"


class InternalSourceRefusal(ValueError):
    """Stable-code refusal; the code never carries source text or paths."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _need(ok: bool, code: str):
    if not ok:
        raise InternalSourceRefusal(code)


def _is_regular_file(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        raise InternalSourceRefusal("SOURCE_PATH_MISSING") from None
    return stat.S_ISREG(info.st_mode)


def _reject_symlink(path: Path):
    if path.is_symlink():
        raise InternalSourceRefusal("SOURCE_IS_SYMLINK")


def _refuse_private_root_inside_git(corpus_root: Path):
    root = corpus_root.resolve()
    for parent in (root, *root.parents):
        if (parent / ".git").exists():
            raise InternalSourceRefusal("PRIVATE_STORAGE_INSIDE_GIT_REFUSED")


def append_usage_register(register_path: Path, entry: dict) -> str:
    """Append one hash-chained entry; verify the whole chain first.

    Chain rule: entry_sha256 = sha256(canonical({seq, prev_entry_sha256,
    recorded_at_utc, payload})). Tampering with any earlier entry breaks the
    chain and refuses the append.
    """
    _refuse_private_root_inside_git(register_path.parent)
    _reject_symlink(register_path)
    if not verify_usage_register(register_path)["chain_valid"]:
        raise InternalSourceRefusal("USAGE_REGISTER_CHAIN_INVALID")
    entries = []
    if register_path.exists():
        _reject_symlink(register_path)
        for line in register_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entries.append(json.loads(line))
    previous = entries[-1]["entry_sha256"] if entries else "0" * 64
    seq = len(entries) + 1
    from datetime import datetime, timezone
    body = {
        "seq": seq, "prev_entry_sha256": previous,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "payload": entry,
    }
    entry_sha = _sha(_canonical(body))
    line = json.dumps({**body, "entry_sha256": entry_sha},
                      ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")) + "\n"
    register_path.parent.mkdir(parents=True, exist_ok=True)
    prior_bytes = register_path.read_bytes() if register_path.exists() else b""
    handle = tempfile.NamedTemporaryFile("wb", delete=False,
                                         dir=str(register_path.parent),
                                         prefix=".register-", suffix=".tmp")
    try:
        handle.file.write(prior_bytes)
        handle.file.write(line.encode("utf-8"))
        handle.file.flush()
        os.fsync(handle.file.fileno())
    finally:
        handle.close()
    os.replace(handle.name, register_path)
    return entry_sha


def verify_usage_register(register_path: Path) -> dict:
    """Re-walk the hash chain; metadata-only integrity report."""
    _reject_symlink(register_path)
    if not register_path.exists():
        return {"status": "REGISTER_EMPTY", "entries": 0, "chain_valid": True}
    try:
        entries = []
        for line in register_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                entries.append(json.loads(line))
        previous, broken = "0" * 64, []
        expected_keys = {"seq", "prev_entry_sha256", "recorded_at_utc",
                         "payload", "entry_sha256"}
        for i, entry in enumerate(entries, 1):
            if (type(entry) is not dict or set(entry) != expected_keys or
                    type(entry["seq"]) is not int or entry["seq"] != i or
                    type(entry["payload"]) is not dict or
                    type(entry["prev_entry_sha256"]) is not str or
                    type(entry["entry_sha256"]) is not str or
                    type(entry["recorded_at_utc"]) is not str):
                broken.append(i)
                break
            recorded = entry["entry_sha256"]
            computed = _sha(_canonical({k: v for k, v in entry.items()
                                         if k != "entry_sha256"}))
            if computed != recorded or entry["prev_entry_sha256"] != previous:
                broken.append(i)
                break
            previous = recorded
    except (OSError, UnicodeError, ValueError, TypeError, KeyError,
            RecursionError, OverflowError):
        return {"status": "REGISTER_CHAIN_BROKEN", "entries": 0,
                "broken_at": [], "chain_valid": False}
    return {"status": "REGISTER_CHAIN_VALID" if not broken else "REGISTER_CHAIN_BROKEN",
            "entries": len(entries), "broken_at": broken, "chain_valid": not broken}


def ingest_internal_research(source_path: Path, corpus_root: Path,
                             register_path: Path, *, source_meta: dict,
                             attestation: dict, use_record: dict,
                             independently_pinned_sha256: str) -> dict:
    """Gate, then content-address, then register one internal-research source."""
    _need(type(source_meta) is dict, "INVALID_SOURCE_META_SCHEMA")
    source_path = Path(source_path)
    _reject_symlink(source_path)
    if not source_path.exists():
        raise InternalSourceRefusal("SOURCE_PATH_MISSING")
    if not _is_regular_file(source_path):
        raise InternalSourceRefusal("SOURCE_NOT_REGULAR_FILE")
    _refuse_private_root_inside_git(source_path.parent)
    corpus_root = Path(corpus_root)
    _refuse_private_root_inside_git(corpus_root)
    _refuse_private_root_inside_git(Path(register_path).parent)
    _reject_symlink(corpus_root)
    _reject_symlink(Path(register_path))
    _need(set(source_meta) == {
        "source_id", "source_kind", "work_id", "edition_id",
        "redistribution_status", "source_url", "acquisition_evidence"
    }, "INVALID_SOURCE_META_SCHEMA")
    _need(all(type(value) is str for value in source_meta.values()),
          "INVALID_SOURCE_META_SCHEMA")
    data = source_path.read_bytes()
    digest = _sha(data)

    source = {
        "source_id": source_meta["source_id"],
        "source_kind": source_meta["source_kind"],
        "work_id": source_meta["work_id"],
        "edition_id": source_meta["edition_id"],
        "source_sha256": digest,
        "verification_scope": "PINNED_SOURCE_BYTES_MATCHED",
        "redistribution_status": source_meta["redistribution_status"],
    }
    gate = assess_internal_source_use(
        source, attestation, use_record=use_record,
        independently_pinned_sha256=independently_pinned_sha256)
    if not gate["internal_development_eligible"]:
        raise InternalSourceRefusal(gate["status"])

    record = ingest(source_path, corpus_root, source_id=source["source_id"],
                    edition=source["edition_id"], rights=source["redistribution_status"],
                    source_url=source_meta["source_url"],
                    visibility="internal_only")
    _need(record.get("sha256") == digest,
          "SOURCE_CHANGED_DURING_IMPORT")
    written_object = corpus_root / record["object_path"]
    _need(written_object.is_file() and not written_object.is_symlink() and
          _sha(written_object.read_bytes()) == digest,
          "SOURCE_OBJECT_DIGEST_MISMATCH")
    admitted_manifest = dict(record)
    admitted_manifest.update({
        "admission_status": gate["status"],
        "admission_legal_basis": attestation["basis"],
        "use_date": use_record["use_date"],
        "purpose_code": use_record["purpose_code"],
        "verification_scope": source["verification_scope"],
        "independently_pinned_sha256": independently_pinned_sha256,
        "usage_register": str(register_path.name),
    })
    manifest_path = (corpus_root / "manifests" /
                     (source["source_id"] + "-" + digest[:16] + ".json"))
    tmp = manifest_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(admitted_manifest, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    os.replace(tmp, manifest_path)

    register_entry = {
        "source_id": source["source_id"], "work_id": source["work_id"],
        "edition_id": source["edition_id"], "source_sha256": digest,
        "source_kind": source["source_kind"],
        "purpose_code": use_record["purpose_code"],
        "use_date": use_record["use_date"], "legal_basis": attestation["basis"],
        "acquisition_evidence": source_meta["acquisition_evidence"],
        "verification_scope": source["verification_scope"],
        "redistribution_status": source["redistribution_status"],
        "admission_status": gate["status"],
        "manifest_sha256": _sha(manifest_path.read_bytes()),
        "object_sha256": digest,
    }
    entry_sha = append_usage_register(register_path, register_entry)
    return {"status": gate["status"], "manifest": admitted_manifest,
            "register_entry_sha256": entry_sha,
            "object_sha256": digest, "manifest_sha256": _sha(manifest_path.read_bytes())}


def is_admitted(manifest_path: Path, register_path: Path) -> bool:
    """A source is admitted only when the manifest says ELIGIBLE AND the
    usage register contains an entry referencing that exact manifest digest."""
    if not manifest_path.exists() or not register_path.exists():
        return False
    if not verify_usage_register(register_path)["chain_valid"]:
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, TypeError):
        return False
    if manifest.get("admission_status") != ADMISSION_ELIGIBLE:
        return False
    manifest_digest = _sha(manifest_path.read_bytes())
    if (manifest.get("sha256") != manifest.get("independently_pinned_sha256") or
            not isinstance(manifest.get("object_path"), str)):
        return False
    try:
        root = manifest_path.parent.parent.resolve()
        candidate = root / manifest["object_path"]
        object_path = candidate.resolve()
        if (not object_path.is_relative_to(root) or not object_path.is_file() or
                candidate.is_symlink() or
                _sha(object_path.read_bytes()) != manifest["sha256"]):
            return False
    except (OSError, RuntimeError, TypeError, ValueError):
        return False
    for line in register_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        body = json.loads(line)
        payload = body.get("payload", {})
        if payload.get("admission_status") == ADMISSION_ELIGIBLE and \
                payload.get("source_sha256") == manifest["sha256"] and \
                payload.get("manifest_sha256") == manifest_digest:
            return True
    return False
