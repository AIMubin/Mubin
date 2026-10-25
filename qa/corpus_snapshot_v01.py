"""I0.1c — immutable, versioned evidence snapshots for the private vault.

Publishes a fully verified corpus database as an immutable, content-addressed
REVISION (never overwritten), advances an atomic LATEST pointer, and lets
operator sessions PIN the revision they resolved at: a session opened on
Revision A completes on Revision A even after Revision B is published.

Verification policy (per the I0.1c architecture decision):
  - import / new revision publication: FULL content verification;
  - normal queries: read from the pinned immutable snapshot — no re-hashing
    of the 223 MB sidecar or the corpus database per query;
  - qualification decisions remain bound to the evidence head that was
    current at review time; publishing a new revision yields a new evidence
    head, so stale approvals do not silently carry over.

Refusal codes never contain private paths or text.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import stat
from pathlib import Path

from qa import private_evidence_v01 as evidence

VERSION = "corpus-snapshot/v0.1.0"
CONTRACT = "mubin-corpus-snapshot-v0.1"
SNAPSHOTS_DIR = "snapshots"
LATEST_NAME = "LATEST.json"
REV_RE = re.compile(r"r[0-9a-f]{64}\Z")


class SnapshotError(ValueError):
    """Stable refusal codes; never contain private paths or text."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _need(ok, code):
    if not ok:
        raise SnapshotError(code)


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / (".tmp-" + str(os.getpid()) + "-" + path.name)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 getattr(os, "O_BINARY", 0), 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def snapshots_root(vault: Path) -> Path:
    return Path(vault) / SNAPSHOTS_DIR


def resolve_current_snapshot(vault: Path) -> dict:
    """Resolve the LATEST pointer to a fully consistent revision bundle.

    Refuses if the pointer, the revision manifest, or any pinned file is
    missing or altered: a session never silently upgrades, and a destroyed
    snapshot is reported rather than ignored.
    """
    vault = Path(vault)
    latest = vault / LATEST_NAME
    if latest.is_symlink() or not latest.is_file():
        raise SnapshotError("SNAPSHOT_LATEST_MISSING")
    body = json.loads(latest.read_text(encoding="utf-8"))
    _need(type(body) is dict and
          set(body) == {"revision_id", "corpus_sha256", "sidecar_sha256",
                        "published_utc", "manifest_sha256"},
          "SNAPSHOT_LATEST_INVALID")
    revision_id = body["revision_id"]
    _need(type(revision_id) is str and REV_RE.fullmatch(revision_id) is not None,
          "SNAPSHOT_REVISION_INVALID")
    revision_dir = snapshots_root(vault) / revision_id
    _need(revision_dir.is_dir() and not revision_dir.is_symlink(),
          "SNAPSHOT_REVISION_INVALID")
    manifest_path = revision_dir / "revision.json"
    _need(manifest_path.is_file() and not manifest_path.is_symlink(),
          "SNAPSHOT_MANIFEST_MISSING")
    _need(_sha_file(manifest_path) == body["manifest_sha256"],
          "SNAPSHOT_MANIFEST_DIGEST_MISMATCH")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _need(type(manifest) is dict and
          set(manifest) == {"contract", "version", "revision_id",
                            "corpus_sha256", "sidecar_sha256",
                            "campaign_receipt_sha256", "immutable",
                            "text_included", "publication_allowed",
                            "source_authenticated", "scholarly_verified",
                            "rights_verified"} and
          manifest["contract"] == CONTRACT and
          manifest["version"] == VERSION and
          manifest["revision_id"] == revision_id and
          manifest["immutable"] is True and
          all(manifest[k] is False for k in
              ("text_included", "publication_allowed",
               "source_authenticated", "scholarly_verified",
               "rights_verified")) and
          type(manifest["campaign_receipt_sha256"]) is str and
          re.fullmatch(r"[0-9a-f]{64}", manifest["campaign_receipt_sha256"]),
          "SNAPSHOT_MANIFEST_MISMATCH")
    corpus_path = revision_dir / "corpus.sqlite3"
    sidecar_path = revision_dir / "sidecar.db"
    _need(corpus_path.is_file() and not corpus_path.is_symlink(),
          "SNAPSHOT_CORPUS_MISSING")
    _need(sidecar_path.is_file() and not sidecar_path.is_symlink(),
          "SNAPSHOT_SIDECAR_MISSING")
    # Never claim an existing shared-inode revision is isolated.
    _need(corpus_path.stat().st_nlink == 1 and sidecar_path.stat().st_nlink == 1,
          "SNAPSHOT_SHARED_INODE_REFUSED")
    corpus_sha = _sha_file(corpus_path)
    sidecar_sha = _sha_file(sidecar_path)
    _need(corpus_sha == manifest.get("corpus_sha256") ==
          body.get("corpus_sha256"), "SNAPSHOT_CORPUS_DIGEST_MISMATCH")
    _need(sidecar_sha == manifest.get("sidecar_sha256") ==
          body.get("sidecar_sha256"), "SNAPSHOT_SIDECAR_DIGEST_MISMATCH")
    return {"revision_id": revision_id, "vault": vault,
            "corpus_db": corpus_path, "sidecar_db": sidecar_path,
            "corpus_sha256": corpus_sha, "sidecar_sha256": sidecar_sha,
            "manifest": manifest, "immutable": True,
            "text_included": False, "publication_allowed": False}


def _copy_verified(src: Path, dst: Path, expected_digest: str) -> None:
    """Create an inode-independent copy; never alias the mutable input."""
    before = src.stat()
    with src.open("rb") as stream_in, dst.open("xb") as stream_out:
        shutil.copyfileobj(stream_in, stream_out, 1024 * 1024)
        stream_out.flush()
        os.fsync(stream_out.fileno())
    after = src.stat()
    _need((before.st_dev, before.st_ino, before.st_size,
           before.st_mtime_ns, before.st_ctime_ns) ==
          (after.st_dev, after.st_ino, after.st_size,
           after.st_mtime_ns, after.st_ctime_ns),
          "SNAPSHOT_INPUT_CHANGED_DURING_COPY")
    _need(_sha_file(dst) == expected_digest,
          "SNAPSHOT_COPY_DIGEST_MISMATCH")
    # Best-effort read-only permissions: trusted operator storage is assumed,
    # since a user with write/owner rights can chmod/replace snapshots.
    dst.chmod(stat.S_IRUSR)
    _need(dst.stat().st_nlink == 1, "SNAPSHOT_SHARED_INODE_REFUSED")


def publish_snapshot(vault: Path, corpus_db: Path, sidecar_db: Path, *,
                     campaign_receipt_sha256: str) -> dict:
    """Copy-verify and atomically publish a physically isolated revision.

    This is a trusted single-operator filesystem model, not WORM storage.
    The caller is responsible for establishing authoritative source integrity
    and HMAC evidence linkage before publishing; digest checks here identify
    bytes, not the scientific/legal provenance of those bytes.
    """
    try:
        vault = evidence._guard_outside(Path(vault), None)
        corpus_db = evidence._guard_outside(Path(corpus_db), None)
        sidecar_db = evidence._guard_outside(Path(sidecar_db), None)
        _need(vault.is_dir(), "SNAPSHOT_VAULT_MISSING")
        _need(type(campaign_receipt_sha256) is str and
              re.fullmatch(r"[0-9a-f]{64}", campaign_receipt_sha256) is not None,
              "SNAPSHOT_RECEIPT_DIGEST_INVALID")
        for path in (corpus_db, sidecar_db):
            _need(path.is_file() and not path.is_symlink(),
                  "SNAPSHOT_INPUT_MISSING_OR_SYMLINK")
        corpus_sha = _sha_file(corpus_db)
        sidecar_sha = _sha_file(sidecar_db)
        from qa.tafsircenter_sidecar_v01 import EXPECTED_SHA256
        _need(sidecar_sha == EXPECTED_SHA256,
              "SNAPSHOT_SIDECAR_PIN_MISMATCH")
        seed = corpus_sha + sidecar_sha + campaign_receipt_sha256
        revision_id = "r" + hashlib.sha256(seed.encode("utf-8")).hexdigest()
        root = snapshots_root(vault)
        root.mkdir(parents=True, exist_ok=True)
        revision_dir = root / revision_id
        _need(not revision_dir.exists(), "SNAPSHOT_REVISION_ALREADY_PUBLISHED")
        stage_dir = root / (".stage-" + secrets.token_hex(16))
        stage_dir.mkdir(mode=0o700)
        try:
            _copy_verified(corpus_db, stage_dir / "corpus.sqlite3", corpus_sha)
            _copy_verified(sidecar_db, stage_dir / "sidecar.db", sidecar_sha)
            manifest = {
                "contract": CONTRACT, "version": VERSION,
                "revision_id": revision_id,
                "corpus_sha256": corpus_sha, "sidecar_sha256": sidecar_sha,
                "campaign_receipt_sha256": campaign_receipt_sha256,
                "immutable": True, "text_included": False,
                "publication_allowed": False, "source_authenticated": False,
                "scholarly_verified": False, "rights_verified": False,
            }
            _write_atomic(stage_dir / "revision.json",
                          json.dumps(manifest, ensure_ascii=False,
                                     sort_keys=True, indent=2).encode("utf-8"))
            # In the single-operator model, never replace an existing revision.
            _need(not revision_dir.exists(),
                  "SNAPSHOT_REVISION_ALREADY_PUBLISHED")
            stage_dir.rename(revision_dir)
        finally:
            if stage_dir.exists():
                shutil.rmtree(stage_dir)
        latest_body = {
            "revision_id": revision_id,
            "corpus_sha256": corpus_sha, "sidecar_sha256": sidecar_sha,
            "manifest_sha256": _sha_file(revision_dir / "revision.json"),
            "published_utc": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc).isoformat(),
        }
        _write_atomic(vault / LATEST_NAME,
                      json.dumps(latest_body, ensure_ascii=False,
                                 sort_keys=True, indent=2).encode("utf-8"))
        return {"status": "SNAPSHOT_PUBLISHED", "revision_id": revision_id,
                "corpus_sha256": corpus_sha, "sidecar_sha256": sidecar_sha,
                "immutable": True, "supersedes_previous": True,
                "text_included": False, "publication_allowed": False,
                "scholarly_verified": False, "source_authenticated": False}
    except (OSError, ValueError, TypeError, KeyError, UnicodeError,
            evidence.EvidenceError) as exc:
        if isinstance(exc, SnapshotError):
            raise
        raise SnapshotError("SNAPSHOT_FILESYSTEM_OR_FORMAT_ERROR") from exc
