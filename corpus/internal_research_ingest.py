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
        for line in register_path.read_text(encoding="utf-8").split("\n"):
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
        # A valid JSONL chain may omit its final newline. Preserve the
        # previous entry bytes while adding the required record separator.
        if prior_bytes and not prior_bytes.endswith(b"\n"):
            handle.file.write(b"\n")
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
        for line in register_path.read_text(encoding="utf-8").split("\n"):
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



def _is_windows_reparse_point(path: Path) -> bool:
    """Compatible with Python 3.11, where Path.is_junction does not exist."""
    if os.name != "nt" or not path.exists():
        return False
    # Junctions carry FILE_ATTRIBUTE_REPARSE_POINT (0x400). Reject other
    # reparse points too: the vault needs ordinary local directories.
    attrs = getattr(path.lstat(), "st_file_attributes", 0)
    return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _guard_private_path(path: Path, *, container: bool = False):
    """Fail closed on existing symlink/junction components before any writes.

    The workflow assumes one trusted writer; do not allow a separate process
    to mutate directory entries while an admission is running.
    """
    try:
        candidate = Path(os.path.abspath(os.fspath(path)))
        for part in (candidate, *candidate.parents):
            if part.is_symlink() or _is_windows_reparse_point(part):
                raise InternalSourceRefusal("PRIVATE_STORAGE_SYMLINK_REFUSED")
            if (part / ".git").exists() or (part / ".git").is_symlink():
                raise InternalSourceRefusal("PRIVATE_STORAGE_INSIDE_GIT_REFUSED")
            if part != candidate and part.exists() and not part.is_dir():
                raise InternalSourceRefusal("PRIVATE_STORAGE_PATH_INVALID")
        # Windows resolve() also normalizes unrelated system path aliases,
        # case and short names. That alone is not evidence of a link.
        resolved = candidate.resolve()
        if os.name != "nt" and resolved != candidate:
            raise InternalSourceRefusal("PRIVATE_STORAGE_SYMLINK_REFUSED")
        for parent in (resolved, *resolved.parents):
            if (parent / ".git").exists() or (parent / ".git").is_symlink():
                raise InternalSourceRefusal("PRIVATE_STORAGE_INSIDE_GIT_REFUSED")
        if container and candidate.exists() and not candidate.is_dir():
            raise InternalSourceRefusal("PRIVATE_STORAGE_PATH_INVALID")
        return candidate
    except InternalSourceRefusal:
        raise
    except (OSError, RuntimeError, ValueError, TypeError):
        raise InternalSourceRefusal("PRIVATE_STORAGE_PATH_INVALID") from None


def _ingest_internal_research(source_path: Path, corpus_root: Path,
                              register_path: Path, *, source_meta: dict,
                              attestation: dict, use_record: dict,
                              independently_pinned_sha256: str) -> dict:
    _need(type(source_meta) is dict, "INVALID_SOURCE_META_SCHEMA")
    _need(set(source_meta) == {
        "source_id", "source_kind", "work_id", "edition_id",
        "redistribution_status", "source_url", "acquisition_evidence"
    }, "INVALID_SOURCE_META_SCHEMA")
    _need(all(type(value) is str for value in source_meta.values()),
          "INVALID_SOURCE_META_SCHEMA")
    source_path = Path(source_path)
    _reject_symlink(source_path)
    if not source_path.exists():
        raise InternalSourceRefusal("SOURCE_PATH_MISSING")
    if not _is_regular_file(source_path):
        raise InternalSourceRefusal("SOURCE_NOT_REGULAR_FILE")
    _guard_private_path(source_path)
    corpus_root = _guard_private_path(Path(corpus_root), container=True)
    register_path = _guard_private_path(Path(register_path))
    _guard_private_path(register_path.parent, container=True)

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
    _need(source_meta["source_id"] and all(
        char.isascii() and (char.isalnum() or char in "-_")
        for char in source_meta["source_id"]), "SOURCE_ID_INVALID")
    manifest_path = corpus_root / "manifests" / (
        source["source_id"] + "-" + digest[:16] + ".json")
    obj_path = corpus_root / "objects" / digest[:2] / digest
    # These checks happen BEFORE calling the legacy importer.
    for target in (corpus_root / "objects", corpus_root / "manifests",
                   obj_path.parent, obj_path, manifest_path,
                   register_path, register_path.parent):
        _guard_private_path(target, container=(
            target == corpus_root / "objects" or
            target == corpus_root / "manifests" or
            target == obj_path.parent or
            target == register_path.parent))
    if register_path.exists() and not verify_usage_register(register_path)["chain_valid"]:
        raise InternalSourceRefusal("USAGE_REGISTER_CHAIN_INVALID")

    old_admission = manifest_path.exists()
    if old_admission:
        if not is_admitted(manifest_path, register_path):
            raise InternalSourceRefusal("EXISTING_MANIFEST_UNADMITTED")
        admitted_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        _need(
            admitted_manifest.get("edition") == source["edition_id"] and
            admitted_manifest.get("rights_statement") == source["redistribution_status"] and
            admitted_manifest.get("source_url") == source_meta["source_url"] and
            admitted_manifest.get("source_id") == source["source_id"] and
            admitted_manifest.get("sha256") == digest,
            "EXISTING_MANIFEST_METADATA_CONFLICT")
        manifest_digest = _sha(manifest_path.read_bytes())
    else:
        corpus_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".internal-stage-",
                                         dir=corpus_root) as temporary:
            stage_root = Path(temporary)
            # The legacy importer may write a manifest; it only writes inside
            # this private staging root, never at the final manifest path.
            record = ingest(
                source_path, stage_root, source_id=source["source_id"],
                edition=source["edition_id"],
                rights=source["redistribution_status"],
                source_url=source_meta["source_url"], visibility="internal_only")
            _need(record.get("sha256") == digest,
                  "SOURCE_CHANGED_DURING_IMPORT")
            staged_obj = stage_root / record["object_path"]
            _need(staged_obj.is_file() and _sha(staged_obj.read_bytes()) == digest,
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
            obj_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            # Fail closed if an untrusted replacement appeared since preflight.
            _guard_private_path(obj_path)
            _guard_private_path(manifest_path)
            _guard_private_path(register_path)
            if obj_path.exists():
                _need(obj_path.is_file() and
                      _sha(obj_path.read_bytes()) == digest,
                      "SOURCE_OBJECT_DIGEST_MISMATCH")
            else:
                os.replace(staged_obj, obj_path)
            payload_bytes = (json.dumps(admitted_manifest, ensure_ascii=False,
                                        indent=2) + "\n").encode("utf-8")
            staged_manifest = stage_root / "admission.json"
            staged_manifest.write_bytes(payload_bytes)
            manifest_digest = _sha(payload_bytes)
            _need(not manifest_path.exists(), "EXISTING_MANIFEST_UNADMITTED")
            os.replace(staged_manifest, manifest_path)

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
        "manifest_sha256": manifest_digest,
        "object_sha256": digest,
    }
    try:
        entry_sha = append_usage_register(register_path, register_entry)
    except BaseException:
        # The register may have been durably appended before a subsequent
        # error; preserve a committed admission. Otherwise remove ONLY the
        # new manifest. An existing admission must never be overwritten.
        if not old_admission and not is_admitted(manifest_path, register_path):
            manifest_path.unlink(missing_ok=True)
        raise
    return {"status": gate["status"], "manifest": admitted_manifest,
            "register_entry_sha256": entry_sha,
            "object_sha256": digest, "manifest_sha256": manifest_digest}


def ingest_internal_research(source_path: Path, corpus_root: Path,
                             register_path: Path, *, source_meta: dict,
                             attestation: dict, use_record: dict,
                             independently_pinned_sha256: str) -> dict:
    """Non-disclosing public boundary: only stable refusal codes escape."""
    try:
        return _ingest_internal_research(
            source_path, corpus_root, register_path,
            source_meta=source_meta, attestation=attestation,
            use_record=use_record,
            independently_pinned_sha256=independently_pinned_sha256)
    except InternalSourceRefusal:
        raise
    except (OSError, RuntimeError, UnicodeError, ValueError, TypeError,
            KeyError, RecursionError, OverflowError):
        raise InternalSourceRefusal("INTERNAL_INGEST_COMMIT_FAILED") from None


def is_admitted(manifest_path: Path, register_path: Path) -> bool:
    """Total fail-closed predicate: corrupt/inaccessible intake is never admitted."""
    try:
        if (not manifest_path.is_file() or not register_path.is_file() or
                manifest_path.is_symlink() or register_path.is_symlink()):
            return False
        if not verify_usage_register(register_path)["chain_valid"]:
            return False
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        if type(manifest) is not dict:
            return False
        if manifest.get("admission_status") != ADMISSION_ELIGIBLE:
            return False
        manifest_digest = _sha(manifest_bytes)
        if (manifest.get("sha256") != manifest.get("independently_pinned_sha256") or
                not isinstance(manifest.get("object_path"), str)):
            return False
        root = manifest_path.parent.parent.resolve()
        candidate = root / manifest["object_path"]
        object_path = candidate.resolve()
        if (not object_path.is_relative_to(root) or not object_path.is_file() or
                candidate.is_symlink() or
                _sha(object_path.read_bytes()) != manifest["sha256"]):
            return False
        # splitlines() also splits U+0085/U+2028/U+2029 inside valid JSON
        # strings. Only ASCII LF terminates a JSONL record.
        for line in register_path.read_text(encoding="utf-8").split("\n"):
            if not line.strip():
                continue
            body = json.loads(line)
            payload = body.get("payload", {})
            if payload.get("admission_status") == ADMISSION_ELIGIBLE and \
                    payload.get("source_sha256") == manifest["sha256"] and \
                    payload.get("manifest_sha256") == manifest_digest:
                return True
        return False
    except (OSError, RuntimeError, UnicodeError, ValueError, TypeError,
            AttributeError, RecursionError, OverflowError):
        return False
