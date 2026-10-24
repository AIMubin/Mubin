"""R0.1a — private evidence registry over the operator research vault.

Builds and verifies a metadata-only evidence registry for the private
research corpus vault: source digests, database digests, record counts and
campaign linkage. NO Quranic or tafsir text is ever read into the registry
or any report.

Integrity model (single trusted operator):
  1. Hash-chained append-only registry (reuse of the internal-research
     chain construction with inter-process lock hardening).
  2. HMAC-SHA256 head anchor stored OUTSIDE the vault: recomputing the
     whole chain without the operator key cannot forge a consistent head.
  3. Every append re-verifies: vault bytes vs pinned digests, SQLite
     integrity + record counts, campaign receipt digest, chain, and head
     anchor. Any single-byte change in the database, the campaign receipt
     or the registry is refused.

This module performs no legal clearance and no scholarly verification.
All authority flags in reports are fixed to false.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import sqlite3
import time
from pathlib import Path

from qa.tafsircenter_sidecar_v01 import verify_sidecar as _verify_tafsircenter

VERSION = "private-evidence-registry/v0.1.0"
CONTRACT = "mubin-private-evidence-registry-v0.1"
RECEIPT_NAME = "receipts/operator-import-campaign-v01.json"
SIDECAR_PIN = "10e61f615ab5e6a3440e8ecc8ba1dc2273d12cd9048752760fe53a44d191cc27"
CORPUS_DB_NAME = "mubin-private-corpus-v01.sqlite3"
SIDECAR_DB_NAME = "tafsircenter-quran.db"
REGISTRY_NAME = "evidence-registry.jsonl"
ANCHOR_NAME = "evidence-registry-head-anchor.json"
LOCK_NAME = ".evidence-registry.lock"
CORPUS_SOURCES = 5
CORPUS_ENTRIES = 31180
CORPUS_VERSES_PER_SOURCE = 6236


class EvidenceError(ValueError):
    """Stable, non-disclosing refusal codes only."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _need(ok, code):
    if not ok:
        raise EvidenceError(code)


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _guard_outside(path: Path, vault: Path) -> Path:
    """Refuse symlinks and anything resolving inside the public checkout."""
    candidate = Path(os.path.abspath(os.fspath(path)))
    for component in (candidate, *candidate.parents):
        if component.is_symlink() or (hasattr(component, "is_junction") and component.is_junction()):
            raise EvidenceError("PRIVATE_PATH_SYMLINK_REFUSED")
    repo = Path(__file__).resolve().parents[1]
    resolved = candidate.resolve()
    if resolved == repo or repo in resolved.parents:
        raise EvidenceError("PRIVATE_STORAGE_INSIDE_GIT_REFUSED")
    if vault is not None:
        vault_resolved = Path(vault).resolve()
        if resolved == vault_resolved:
            raise EvidenceError("ANCHOR_INSIDE_VAULT_REFUSED")
    return resolved


def _guard_secret_location(path: Path, vault: Path) -> Path:
    """Keys and MAC anchors must not be stored anywhere within the vault."""
    candidate = _guard_outside(path, vault)
    vault_resolved = Path(vault).resolve()
    if vault_resolved in candidate.parents:
        raise EvidenceError("SECRET_OR_ANCHOR_INSIDE_VAULT_REFUSED")
    return candidate


def load_operator_key(key_file: Path, *, create: bool = True) -> bytes:
    """Load (or create with 0600) the operator HMAC key OUTSIDE the vault."""
    path = Path(os.path.abspath(os.fspath(key_file)))
    if path.is_symlink():
        raise EvidenceError("OPERATOR_KEY_SYMLINK_REFUSED")
    if path.exists():
        key = path.read_bytes()
        if len(key) < 32:
            raise EvidenceError("OPERATOR_KEY_TOO_SHORT")
        return key
    if not create:
        raise EvidenceError("OPERATOR_KEY_MISSING")
    import secrets
    key = secrets.token_bytes(48)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    try:
        os.write(fd, key)
    finally:
        os.close(fd)
    return key


class _VaultLock:
    """Single-writer lock for registry appends (single-operator model).

    An O_EXCL lock file with live-owner information; a stale lock from a
    crashed process older than STALE_SECONDS is broken on the next run.
    """

    STALE_SECONDS = 600

    def __init__(self, lock_path: Path, operator: str):
        self.path = lock_path
        self.operator = operator
        self.fd = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                self.fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                os.write(self.fd, (self.operator + " " + str(int(time.time()))).encode("ascii"))
                return self
            except FileExistsError:
                age = time.time() - self.path.stat().st_mtime
                # Never break a lock purely by age: a legitimate operator
                # may have paused, and stale deletion admits two writers.
                # Manual recovery requires checking the holder first.
                raise EvidenceError("REGISTRY_BUSY_ANOTHER_OPERATOR") from None

    def __exit__(self, *_):
        if self.fd is not None:
            os.close(self.fd)
            self.path.unlink(missing_ok=True)
        return False


def verify_vault(vault_dir: Path, sidecar_db: Path,
                 campaign_receipt: dict | None = None) -> dict:
    """Byte/integrity/counts verification of both vault databases.

    The TafsirCenter sidecar lives wherever the operator keeps it (it is a
    separately licensed original), so its path is supplied explicitly and
    only its bytes and structure are read. Reads structure and digests
    only; no verse or commentary text is returned or logged. Refuses on
    any single-byte mismatch.
    """
    vault = _guard_outside(vault_dir, None)
    sidecar_db = _guard_outside(sidecar_db, None)
    receipt_path = vault / RECEIPT_NAME
    if receipt_path.is_symlink() or not receipt_path.is_file():
        raise EvidenceError("CAMPAIGN_RECEIPT_MISSING")
    receipt_raw = receipt_path.read_bytes()
    receipt = json.loads(receipt_raw.decode("utf-8"))
    if type(receipt) is not dict or receipt.get("campaign") != "operator-local-private-corpus-import-v01":
        raise EvidenceError("CAMPAIGN_RECEIPT_INVALID")
    if (type(receipt.get("limits")) is not dict or
            receipt["limits"].get("scholarly_verified") is not False or
            type(receipt.get("steps")) is not list or
            not all(type(step) is dict for step in receipt["steps"])):
        raise EvidenceError("CAMPAIGN_RECEIPT_INVALID")
    steps = {step.get("step"): step for step in receipt["steps"]}
    corpus_step = steps.get("permanent_private_corpus_import")
    if not corpus_step:
        raise EvidenceError("CAMPAIGN_RECEIPT_INVALID")

    # Sidecar: byte-verify against the frozen module pin, then structure.
    sidecar_path = sidecar_db
    if sidecar_path.is_symlink():
        raise EvidenceError("PRIVATE_PATH_SYMLINK_REFUSED")
    if not sidecar_path.is_file():
        raise EvidenceError("SIDECAR_DB_MISSING")
    sidecar_sha = _sha_file(sidecar_path)
    if sidecar_sha != SIDECAR_PIN:
        raise EvidenceError("SIDECAR_DIGEST_MISMATCH")
    sidecar_report = _verify_tafsircenter(sidecar_path, deep=True)

    # Corpus vault DB: byte digest, sqlite integrity, exact record counts.
    corpus_path = vault / CORPUS_DB_NAME
    if corpus_path.is_symlink():
        raise EvidenceError("PRIVATE_PATH_SYMLINK_REFUSED")
    if not corpus_path.is_file():
        raise EvidenceError("CORPUS_DB_MISSING")
    corpus_sha = _sha_file(corpus_path)
    con = sqlite3.connect(corpus_path.as_uri() + "?mode=ro&immutable=1", uri=True)
    try:
        con.execute("PRAGMA query_only=ON")
        if con.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise EvidenceError("CORPUS_DB_INTEGRITY_FAILURE")
        sources = con.execute(
            "SELECT source_id, source_kind, raw_sha256 FROM corpus_sources ORDER BY source_id"
        ).fetchall()
        if len(sources) != CORPUS_SOURCES:
            raise EvidenceError("CORPUS_SOURCE_COUNT_CHANGED")
        per_source = {}
        total = 0
        for source_id, source_kind, raw_sha in sources:
            count = con.execute(
                "SELECT COUNT(*) FROM corpus_entries WHERE source_id=?",
                (source_id,)).fetchone()[0]
            if count != CORPUS_VERSES_PER_SOURCE:
                raise EvidenceError("CORPUS_RECORD_COUNT_CHANGED")
            if con.execute(
                    "SELECT COUNT(DISTINCT sura || ':' || aya) FROM corpus_entries "
                    "WHERE source_id=?", (source_id,)).fetchone()[0] != count:
                raise EvidenceError("CORPUS_COORDINATE_CHANGED")
            per_source[source_id] = {"kind": source_kind, "records": count,
                                     "sha256": raw_sha}
            total += count
        if total != CORPUS_ENTRIES:
            raise EvidenceError("CORPUS_RECORD_COUNT_CHANGED")
    except sqlite3.Error as exc:
        raise EvidenceError("CORPUS_DB_NOT_READABLE") from exc
    finally:
        con.close()

    # Campaign receipt must reference exactly these digests and counts.
    listed = corpus_step.get("sources", [])
    if (type(listed) is not list or
            not all(type(item) is dict and type(item.get("id")) is str for item in listed)):
        raise EvidenceError("CAMPAIGN_RECEIPT_INVALID")
    imported = {item["id"]: item for item in listed}
    if len(imported) != CORPUS_SOURCES or len(listed) != CORPUS_SOURCES:
        raise EvidenceError("CAMPAIGN_RECEIPT_INVALID")
    for source_id, meta in per_source.items():
        item = imported.get(source_id)
        if item is None or item.get("sha256") != meta["sha256"] or \
                item.get("verses") != meta["records"]:
            raise EvidenceError("CAMPAIGN_RECEIPT_INVALID")
    if corpus_step.get("records") != CORPUS_ENTRIES:
        raise EvidenceError("CAMPAIGN_RECEIPT_INVALID")

    return {
        "sidecar": {"sha256": sidecar_sha, "tables": sidecar_report["table_counts"],
                    "tafsir_sources": sidecar_report["tafsir_sources"]},
        "corpus_db": {"sha256": corpus_sha, "records": total,
                      "sources": per_source},
        "campaign_receipt_sha256": _sha(receipt_raw),
        "byte_integrity_verified": True,
        "source_authenticated": False,
        "rights_status": "legal_review_pending",
        "scholarly_verified": False,
        "p1_admitted": False,
    }


def build_registry_entry(vault_dir: Path, sidecar_db: Path,
                         campaign_id: str) -> tuple[dict, dict]:
    """One metadata-only registry entry describing the verified vault."""
    observation = verify_vault(vault_dir, sidecar_db)
    entry = {
        "campaign_id": campaign_id,
        "sidecar_source_sha256": observation["sidecar"]["sha256"],
        "corpus_database_sha256": observation["corpus_db"]["sha256"],
        "campaign_receipt_sha256": observation["campaign_receipt_sha256"],
        "corpus_records": observation["corpus_db"]["records"],
        "corpus_sources": observation["corpus_db"]["sources"],
        "sidecar_table_counts": observation["sidecar"]["tables"],
        "byte_integrity_verified": True,
        "source_version": "tanzil-uthmani-1.1/2026-10-18-preset + quranenc@pinned + tafsircenter-sidecar-v01",
    }
    entry.update({
        "source_authenticated": False,
        "rights_status": "legal_review_pending",
        "rights_verified": False,
        "scholarly_verified": False,
        "p1_admitted": False,
        "juristic_inference_allowed": False,
        "public_fatwa_authorized": False,
        "text_included": False,
    })
    return entry, observation


def _load_registry(registry_path: Path) -> list[dict]:
    if registry_path.is_symlink():
        raise EvidenceError("REGISTRY_SYMLINK_REFUSED")
    if not registry_path.exists():
        return []
    entries = []
    try:
        existing = registry_path.read_bytes()
        lines = existing.decode("utf-8", "strict").split(chr(10))
    except (OSError, UnicodeError) as exc:
        raise EvidenceError("REGISTRY_JSON_INVALID") from exc
    for line in lines:
        if line.strip():
            try:
                value = json.loads(line)
            except (ValueError, TypeError, RecursionError) as exc:
                raise EvidenceError("REGISTRY_JSON_INVALID") from exc
            if type(value) is not dict:
                raise EvidenceError("REGISTRY_CHAIN_INVALID")
            entries.append(value)
    # The MAC authenticates the parsed chain. Without this extra byte-level
    # check an attacker can alter separators/whitespace without changing
    # the hashes, and an append might bless a malformed JSONL log.
    if existing != b"".join(_canonical(entry) + bytes([10]) for entry in entries):
        raise EvidenceError("REGISTRY_NONCANONICAL_BYTES")
    return entries


def _verify_chain(entries: list[dict]) -> None:
    previous = "0" * 64
    for i, body in enumerate(entries, 1):
        expected_keys = {"seq", "prev_entry_sha256", "recorded_at_utc",
                         "operator", "payload", "entry_sha256"}
        if (type(body) is not dict or set(body) != expected_keys or
                type(body["seq"]) is not int or body["seq"] != i or
                type(body["payload"]) is not dict or
                type(body["operator"]) is not str or
                type(body["recorded_at_utc"]) is not str or
                type(body["prev_entry_sha256"]) is not str or
                type(body["entry_sha256"]) is not str):
            raise EvidenceError("REGISTRY_CHAIN_INVALID")
        flags = body["payload"]
        if (flags.get("source_authenticated") is not False or
                flags.get("rights_status") != "legal_review_pending" or
                flags.get("rights_verified") is not False or
                flags.get("scholarly_verified") is not False or
                flags.get("p1_admitted") is not False or
                flags.get("juristic_inference_allowed") is not False or
                flags.get("public_fatwa_authorized") is not False or
                flags.get("text_included") is not False):
            raise EvidenceError("REGISTRY_AUTHORITY_FLAGS_INVALID")
        recorded = body["entry_sha256"]
        payload = {k: v for k, v in body.items() if k != "entry_sha256"}
        if recorded != _sha(_canonical(payload)) or body["prev_entry_sha256"] != previous:
            raise EvidenceError("REGISTRY_CHAIN_INVALID")
        previous = recorded


def _head_anchor_path(anchor_dir: Path, registry_path: Path) -> Path:
    return anchor_dir / (registry_path.stem + "." + ANCHOR_NAME)


def read_head_anchor(anchor_dir: Path, registry_path: Path, key: bytes) -> dict:
    path = _head_anchor_path(_guard_outside(anchor_dir, None), registry_path)
    if path.is_symlink() or not path.is_file():
        raise EvidenceError("HEAD_ANCHOR_MISSING")
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise EvidenceError("HEAD_ANCHOR_FORMAT_INVALID") from exc
    if type(body) is not dict:
        raise EvidenceError("HEAD_ANCHOR_FORMAT_INVALID")
    mac = body.pop("head_hmac", "")
    if type(mac) is not str or not re.fullmatch(r"[0-9a-f]{64}", mac):
        raise EvidenceError("HEAD_ANCHOR_FORMAT_INVALID")
    expected = hmac.new(key, _canonical(body), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mac, expected):
        raise EvidenceError("HEAD_ANCHOR_MAC_INVALID")
    if (set(body) != {"registry", "head_entry_sha256", "sequence"}
            or body["registry"] != registry_path.name
            or type(body["sequence"]) is not int
            or body["sequence"] < 1
            or type(body["head_entry_sha256"]) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", body["head_entry_sha256"])):
        raise EvidenceError("HEAD_ANCHOR_FORMAT_INVALID")
    return body


def _assert_anchored_head(entries: list[dict], registry_path: Path,
                          anchor_dir: Path, key: bytes) -> str:
    """Reject rehashed/rolled-back history BEFORE signing a new append."""
    anchor_path = _head_anchor_path(anchor_dir, registry_path)
    if not entries:
        if registry_path.exists() or anchor_path.exists():
            raise EvidenceError("UNPAIRED_INITIAL_REGISTRY_OR_ANCHOR")
        return "0" * 64
    anchor = read_head_anchor(anchor_dir, registry_path, key)
    head = entries[-1]["entry_sha256"]
    if anchor["head_entry_sha256"] != head or anchor["sequence"] != len(entries):
        raise EvidenceError("HEAD_ANCHOR_HEAD_MISMATCH")
    return head


def _assert_unchanged_vault(latest_payload: dict, observation: dict) -> None:
    """Reject changed source bytes / receipts before a new anchored append."""
    if (latest_payload.get("corpus_database_sha256") != observation["corpus_db"]["sha256"]
            or latest_payload.get("sidecar_source_sha256") != observation["sidecar"]["sha256"]
            or latest_payload.get("campaign_receipt_sha256") != observation["campaign_receipt_sha256"]
            or latest_payload.get("corpus_sources") != observation["corpus_db"]["sources"]
            or latest_payload.get("corpus_records") != observation["corpus_db"]["records"]
            or latest_payload.get("sidecar_table_counts") != observation["sidecar"]["tables"]):
        raise EvidenceError("VAULT_CHANGED_SINCE_LAST_ENTRY")


def append_evidence(registry_path: Path, anchor_dir: Path, key_file: Path,
                    vault_dir: Path, sidecar_db: Path, campaign_id: str,
                    operator: str) -> dict:
    """Verify the vault, then atomically append one anchored entry."""
    registry_path = _guard_outside(registry_path, Path(vault_dir))
    anchor_dir = _guard_secret_location(anchor_dir, Path(vault_dir))
    guarded_key_file = _guard_secret_location(key_file, Path(vault_dir))
    with _VaultLock(registry_path.parent / LOCK_NAME, operator):
        # Never silently rotate an existing registry's lost HMAC key.
        initial = not registry_path.exists() and not _head_anchor_path(anchor_dir, registry_path).exists()
        key = load_operator_key(guarded_key_file, create=initial)
        entries = _load_registry(registry_path)
        _verify_chain(entries)
        previous = _assert_anchored_head(entries, registry_path, anchor_dir, key)
        entry, observation = build_registry_entry(vault_dir, sidecar_db, campaign_id)
        if entries:
            _assert_unchanged_vault(entries[-1]["payload"], observation)
        from datetime import datetime, timezone
        body = {
            "seq": len(entries) + 1, "prev_entry_sha256": previous,
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "operator": operator,
            "payload": entry,
        }
        entry_sha = _sha(_canonical(body))
        line = json.dumps({**body, "entry_sha256": entry_sha},
                          ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")) + "\n"
        prior = registry_path.read_bytes() if registry_path.exists() else b""
        temp = registry_path.parent / (".registry-" + str(os.getpid()) + ".tmp")
        with open(temp, "wb") as handle:
            handle.write(prior)
            handle.write(line.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, registry_path)
        # Advance the OUT-OF-VAULT HMAC head anchor.
        anchor_path = _head_anchor_path(anchor_dir, registry_path)
        anchor_body = {
            "registry": registry_path.name, "head_entry_sha256": entry_sha,
            "sequence": body["seq"],
        }
        mac = hmac.new(key, _canonical(anchor_body), hashlib.sha256).hexdigest()
        anchor = {**anchor_body, "head_hmac": mac}
        anchor_path.parent.mkdir(parents=True, exist_ok=True)
        anchor_temp = anchor_path.parent / (".anchor-" + str(os.getpid()) + ".tmp")
        anchor_temp.write_bytes(_canonical(anchor) + b"\n")
        os.replace(anchor_temp, anchor_path)
    return {"status": "REGISTRY_ENTRY_APPENDED", "entry_sha256": entry_sha,
            "observation_summary": {
                "corpus_records": observation["corpus_db"]["records"],
                "sidecar_sha256": observation["sidecar"]["sha256"],
                "corpus_db_sha256": observation["corpus_db"]["sha256"]}}


def verify_evidence(registry_path: Path, anchor_dir: Path, key_file: Path,
                    vault_dir: Path, sidecar_db: Path) -> dict:
    """Full verification: vault bytes + chain + HMAC anchor, no writes."""
    registry_path = _guard_outside(registry_path, Path(vault_dir))
    anchor_dir = _guard_secret_location(anchor_dir, Path(vault_dir))
    key = load_operator_key(_guard_secret_location(key_file, Path(vault_dir)), create=False)
    observation = verify_vault(vault_dir, sidecar_db)
    entries = _load_registry(registry_path)
    if not entries:
        raise EvidenceError("REGISTRY_EMPTY")
    _verify_chain(entries)
    head = _assert_anchored_head(entries, registry_path, anchor_dir, key)
    # Latest entry must still describe the CURRENT vault bytes exactly.
    _assert_unchanged_vault(entries[-1]["payload"], observation)
    return {"status": "EVIDENCE_REGISTRY_VERIFIED",
            "entries": len(entries), "head_entry_sha256": head,
            "byte_integrity_verified": True,
            "corpus_records": observation["corpus_db"]["records"],
            "source_authenticated": False, "rights_status": "legal_review_pending",
            "scholarly_verified": False, "text_included": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--anchor-dir", type=Path, required=True)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--sidecar-db", type=Path, required=True)
    parser.add_argument("--campaign-id", default="operator-local-private-corpus-import-v01")
    parser.add_argument("--operator", default="local-operator")
    parser.add_argument("--check", action="store_true",
                        help="verify only; do not append a new entry")
    args = parser.parse_args(argv)
    try:
        if args.check:
            report = verify_evidence(args.registry, args.anchor_dir,
                                     args.key_file, args.vault, args.sidecar_db)
        else:
            report = append_evidence(args.registry, args.anchor_dir,
                                     args.key_file, args.vault, args.sidecar_db,
                                     args.campaign_id, args.operator)
        code = 0
    except EvidenceError as exc:
        report, code = {"status": "REFUSED", "reason_code": exc.code,
                        "text_included": False}, 1
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        report, code = {"status": "REFUSED", "reason_code": "EVIDENCE_INTERNAL_ERROR",
                        "text_included": False}, 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
