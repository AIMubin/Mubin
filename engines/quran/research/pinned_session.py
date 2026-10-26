"""I0.1c.1: opt-in, process-lifetime pinned operator workspace snapshot.

A full R0.1a vault/HMAC verification and two full snapshot digests happen ONCE
at startup. Metadata HTTP requests perform only cheap identity/stat guards,
re-authenticate the small registry and HMAC anchor, and independently verify
the signed R0.1d qualification ledger through the existing operator APIs.

This is NOT multioperator, WORM, public access or permission to read text.
Changing the authenticated evidence head fails closed until restart/re-pin.
"""
from __future__ import annotations

from pathlib import Path

from engines.quran.research.private_adapters import (
    PrivateResearchAdapters, ResearchAdapterError,
)
from qa import private_evidence_v01 as ev
from qa.corpus_snapshot_v01 import resolve_current_snapshot, SnapshotError

_UNVERIFIED = ("source_authenticated", "scholarly_verified", "text_included")
_SHA_KEYS = ("corpus_database_sha256", "sidecar_source_sha256")


class PinnedSessionError(ValueError):
    """Stable refusal codes; never expose local paths or evidence material."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _need(value, reason: str) -> None:
    if not value:
        raise PinnedSessionError(reason)


def _fingerprint(path: Path):
    """Reject replacement, mutation, symlink and hardlink addition.

    Not a malicious-admin/WORM defense: the local trusted operator could
    modify or restore timestamps and bypass filesystem metadata checks.
    """
    guarded = ev._guard_outside(path, None)
    _need(guarded == path and guarded.is_file(),
          "PINNED_FILE_UNAVAILABLE")
    s = guarded.stat()
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns,
            s.st_ctime_ns, s.st_nlink)


class PinnedSnapshotSession:
    def __init__(self, *, vault: Path, corpus_db: Path, sidecar_db: Path,
                 registry: Path, anchor_dir: Path, evidence_key: Path):
        self.vault = ev._guard_outside(Path(vault), None)
        self.registry = ev._guard_outside(Path(registry), None)
        self.anchor_dir = ev._guard_secret_location(Path(anchor_dir), self.vault)
        self.evidence_key = ev._guard_secret_location(Path(evidence_key), self.vault)
        original_corpus = ev._guard_outside(Path(corpus_db), None)
        original_sidecar = ev._guard_outside(Path(sidecar_db), None)
        _need(original_corpus == ev._guard_outside(
            self.vault / ev.CORPUS_DB_NAME, None),
            "PINNED_ORIGINAL_CORPUS_NOT_CANONICAL")
        _need(self.vault.is_dir(), "PINNED_VAULT_MISSING")

        # These two expensive operations occur before any HTTP listener is
        # started. Never call them from the steady-state request path.
        report = ev.verify_evidence(
            self.registry, self.anchor_dir, self.evidence_key,
            self.vault, original_sidecar)
        _need(report.get("status") == "EVIDENCE_REGISTRY_VERIFIED" and
              report.get("byte_integrity_verified") is True and
              report.get("rights_status") == "legal_review_pending" and
              all(report.get(k) is False for k in _UNVERIFIED) and
              isinstance(report.get("head_entry_sha256"), str) and
              len(report["head_entry_sha256"]) == 64,
              "PINNED_EVIDENCE_NOT_VERIFIED")
        snapshot = resolve_current_snapshot(self.vault)
        self.head = report["head_entry_sha256"]
        self.revision = snapshot["revision_id"]
        self.corpus_db = ev._guard_outside(snapshot["corpus_db"], None)
        self.sidecar_db = ev._guard_outside(snapshot["sidecar_db"], None)
        self._report = dict(report)
        self._expected_digests = {
            "corpus_database_sha256": snapshot["corpus_sha256"],
            "sidecar_source_sha256": snapshot["sidecar_sha256"],
            # Receipt identity also participates in content-addressed
            # revision identity. Without this check, unrelated campaign
            # provenance could be silently attached to an otherwise valid
            # corpus/sidecar byte pair.
            "campaign_receipt_sha256": snapshot["manifest"]["campaign_receipt_sha256"],
        }
        self._watched = (
            original_corpus, original_sidecar,
            self.vault / ev.RECEIPT_NAME,
            self.corpus_db, self.sidecar_db,
            self.vault / "snapshots" / self.revision / "revision.json",
        )
        self._stats = tuple(_fingerprint(p) for p in self._watched)
        self.verify_live()
        self.adapters = PinnedResearchAdapters(self)

    def _authenticated_head(self):
        entries = ev._load_registry(self.registry)
        _need(bool(entries), "PINNED_REGISTRY_EMPTY")
        ev._verify_chain(entries)  # _load_registry alone is NOT authenticated
        key = ev.load_operator_key(self.evidence_key, create=False)
        witness = ev.read_head_anchor(self.anchor_dir, self.registry, key)
        _need(witness["head_entry_sha256"] == entries[-1]["entry_sha256"] and
              witness["sequence"] == len(entries),
              "PINNED_REGISTRY_ANCHOR_MISMATCH")
        return entries[-1]

    def verify_live(self):
        """No large-file hashes per request; refuse visible changes + stale HMAC.

        Qualified decisions are reverified separately by operator_lookup and
        workspace._per_source_states on EVERY request.
        """
        try:
            current = tuple(_fingerprint(p) for p in self._watched)
            _need(current == self._stats, "PINNED_FILES_CHANGED")
            head = self._authenticated_head()
            _need(head["entry_sha256"] == self.head,
                  "PINNED_EVIDENCE_HEAD_CHANGED")
            _need(all(head["payload"].get(k) == digest
                      for k, digest in self._expected_digests.items()),
                  "PINNED_EVIDENCE_DIGEST_CHANGED")
            _need(tuple(_fingerprint(p) for p in self._watched) == current,
                  "PINNED_FILES_CHANGED_DURING_REQUEST")
        except PinnedSessionError:
            raise
        except (ev.EvidenceError, OSError, ValueError, TypeError, KeyError,
                UnicodeError) as exc:
            raise PinnedSessionError("PINNED_SESSION_VERIFICATION_FAILED") from exc

    def evidence_report(self):
        self.verify_live()
        return dict(self._report)


class PinnedResearchAdapters(PrivateResearchAdapters):
    def __init__(self, session: PinnedSnapshotSession):
        super().__init__(
            vault=session.vault, corpus_db=session.corpus_db,
            sidecar_db=session.sidecar_db, registry=session.registry,
            anchor_dir=session.anchor_dir, evidence_key=session.evidence_key)
        self._pinned_session = session

    def _evidence(self) -> dict:
        try:
            return self._pinned_session.evidence_report()
        except PinnedSessionError as exc:
            raise ResearchAdapterError(exc.code) from exc
