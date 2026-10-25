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
from pathlib import Path

from qa import private_evidence_v01 as evidence

VERSION = "corpus-snapshot/v0.1.0"
CONTRACT = "mubin-corpus-snapshot-v0.1"
SNAPSHOTS_DIR = "snapshots"
LATEST_NAME = "LATEST.json"
REV_RE = re.compile(r"r[0-9a-f]{8}\Z")


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
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC |
                 getattr(os, "O_BINARY", 0), 0o600)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)


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
    manifest_path = revision_dir / "revision.json"
    _need(manifest_path.is_file(), "SNAPSHOT_MANIFEST_MISSING")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _need(manifest.get("revision_id") == revision_id,
          "SNAPSHOT_MANIFEST_MISMATCH")
    corpus_path = revision_dir / "corpus.sqlite3"
    sidecar_path = revision_dir / "sidecar.db"
    _need(corpus_path.is_file() and not corpus_path.is_symlink(),
          "SNAPSHOT_CORPUS_MISSING")
    _need(sidecar_path.is_file() and not sidecar_path.is_symlink(),
          "SNAPSHOT_SIDECAR_MISSING")
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


def publish_snapshot(vault: Path, corpus_db: Path, sidecar_db: Path, *,
                     campaign_receipt_sha256: str) -> dict:
    """Publish the current verified databases as a NEW immutable revision.

    corpus_db must be a verified, no-replace published file (R0.1a flow).
    sidecar_db must match the frozen sidecar pin. Both are hard-linked into
    the revision directory (never copied, never mutated); the revision
    manifest and the LATEST pointer are written atomically.
    """
    vault = Path(vault)
    corpus_db = Path(corpus_db)
    sidecar_db = Path(sidecar_db)
    for path in (corpus_db, sidecar_db):
        _need(path.is_file() and not path.is_symlink(),
              "SNAPSHOT_INPUT_MISSING_OR_SYMLINK")
    corpus_sha = _sha_file(corpus_db)
    sidecar_sha = _sha_file(sidecar_db)
    _need(sidecar_sha == __import__(
        "qa.tafsircenter_sidecar_v01", fromlist=["x"]).EXPECTED_SHA256,
        "SNAPSHOT_SIDECAR_PIN_MISMATCH")
    manifest_digest_source = corpus_sha + sidecar_sha + campaign_receipt_sha256
    revision_id = "r" + hashlib.sha256(
        manifest_digest_source.encode("utf-8")).hexdigest()[:8]
    revision_dir = snapshots_root(vault) / revision_id
    _need(not revision_dir.exists(), "SNAPSHOT_REVISION_ALREADY_PUBLISHED")
    revision_dir.mkdir(parents=True, exist_ok=True)
    os.link(corpus_db, revision_dir / "corpus.sqlite3")
    os.link(sidecar_db, revision_dir / "sidecar.db")
    manifest = {
        "contract": CONTRACT, "version": VERSION,
        "revision_id": revision_id,
        "corpus_sha256": corpus_sha, "sidecar_sha256": sidecar_sha,
        "campaign_receipt_sha256": campaign_receipt_sha256,
        "immutable": True, "text_included": False,
        "publication_allowed": False, "source_authenticated": False,
        "scholarly_verified": False, "rights_verified": False,
    }
    _write_atomic(revision_dir / "revision.json",
                  json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                             indent=2).encode("utf-8"))
    latest_body = {
        "revision_id": revision_id,
        "corpus_sha256": corpus_sha, "sidecar_sha256": sidecar_sha,
        "manifest_sha256": _sha_file(revision_dir / "revision.json"),
        "published_utc": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(),
    }
    _write_atomic(vault / LATEST_NAME,
                  json.dumps(latest_body, ensure_ascii=False, sort_keys=True,
                             indent=2).encode("utf-8"))
    return {"status": "SNAPSHOT_PUBLISHED", "revision_id": revision_id,
            "corpus_sha256": corpus_sha, "sidecar_sha256": sidecar_sha,
            "immutable": True, "supersedes_previous": True,
            "text_included": False, "publication_allowed": False,
            "scholarly_verified": False, "source_authenticated": False}
