"""R0.1b: metadata-first, read-only adapters over separately verified private SQLite.

A restricted private-text query requires an independently signed local use
permit, scoped to the exact R0.1a evidence head and source. It is not a licence
or scientific attestation. No public HTTP interface or logging is provided.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
import re
import sqlite3

from engines.quran.q01.engine import _VERSE_COUNTS
from qa import private_evidence_v01 as evidence
from qa.corpus_ingest_v01 import PIN_QURAN_ID, VALID_IDS, load_manifest
from qa.tafsircenter_sidecar_v01 import TABLES_AR, SOURCE_ID as SIDECAR_SOURCE_ID

CONTRACT = "mubin-private-research-adapters-v0.1"
PERMIT_CONTRACT = "mubin-local-private-text-permit-v0.1"
SIDE_TABLES = tuple(TABLES_AR) + ("QuranTafseer",)
TEXT_COLUMNS = {**{table: "tafsir" for table in TABLES_AR},
                "QuranTafseer": "Mukhtasarar"}
HEX = re.compile(r"[0-9a-f]{64}\Z")
REF = re.compile(r"(?:[1-9]|[1-9][0-9]|1[01][0-9]|11[0-4]):[1-9][0-9]{0,2}\Z")
MAX_TEXT = 128 * 1024
# An independently approved issuer fingerprint must be pinned in a SEPARATE
# governance change before any private text can be served by this library.
# Neither a caller-provided key nor an unsigned config can grant authority.
TRUSTED_PERMIT_SIGNER_SHA256: str | None = None


class ResearchAdapterError(ValueError):
    """Stable refusal codes; never contain private text, paths or permit data."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _deny(code: str):
    raise ResearchAdapterError(code)


def _reference(ref: str) -> tuple[int, int]:
    if type(ref) is not str or not REF.fullmatch(ref):
        _deny("REFERENCE_INVALID")
    s, a = (int(n) for n in ref.split(":"))
    if not 1 <= s <= len(_VERSE_COUNTS) or a > _VERSE_COUNTS[s - 1]:
        _deny("REFERENCE_INVALID")
    return s, a


def _source_id(source_id: str, *, sidecar: bool) -> str:
    allowed = SIDE_TABLES if sidecar else VALID_IDS
    if type(source_id) is not str or source_id not in allowed:
        _deny("SOURCE_NOT_ALLOWLISTED")
    return source_id


def _db(path: Path) -> sqlite3.Connection:
    # Existing R0.1a path guard also blocks Git-checkout storage, parent
    # symlinks and Windows junctions; the database may not be created here.
    try:
        candidate = evidence._guard_outside(path, None)
        if not candidate.is_file() or candidate.is_symlink():
            _deny("PRIVATE_DATABASE_MISSING")
        con = sqlite3.connect(candidate.as_uri() + "?mode=ro&immutable=1",
                              uri=True, timeout=3)
        con.execute("PRAGMA query_only=ON")
        return con
    except (OSError, sqlite3.Error, evidence.EvidenceError) as exc:
        raise ResearchAdapterError("PRIVATE_DATABASE_UNAVAILABLE") from exc


def _no_text(value: dict) -> dict:
    # The only public-like output of these adapters: no raw scripture,
    # commentary, footnotes, private file paths or signed permission bytes.
    return {
        **value, "text_included": False, "source_authenticated": False,
        "rights_status": "legal_review_pending", "rights_verified": False,
        "scholarly_verified": False, "p1_admitted": False,
        "publication_allowed": False, "redistribution_approved": False,
        "juristic_inference_allowed": False, "public_fatwa_authorized": False,
    }


def _private_permit(permit_path: Path | None, key_path: Path | None,
                    vault: Path, head: str, source_id: str) -> None:
    """Verify independently held, source-specific HMAC; no minting function.

    An operator-signed permit is a restricted access decision, not an
    attestation of publisher custody, edition identity or rights clearance.
    """
    if permit_path is None or key_path is None:
        _deny("LOCAL_TEXT_PERMIT_REQUIRED")
    if TRUSTED_PERMIT_SIGNER_SHA256 is None:
        _deny("LOCAL_TEXT_ISSUER_NOT_CONFIGURED")
    if (type(TRUSTED_PERMIT_SIGNER_SHA256) is not str
            or not HEX.fullmatch(TRUSTED_PERMIT_SIGNER_SHA256)):
        _deny("LOCAL_TEXT_ISSUER_NOT_CONFIGURED")
    try:
        p = evidence._guard_secret_location(permit_path, vault)
        k = evidence._guard_secret_location(key_path, vault)
        if not p.is_file() or not k.is_file():
            _deny("LOCAL_TEXT_PERMIT_MISSING")
        if p.stat().st_size > 8192:
            _deny("LOCAL_TEXT_PERMIT_INVALID")
        key = k.read_bytes()
        if len(key) < 32:
            _deny("LOCAL_TEXT_PERMIT_INVALID")
        if hashlib.sha256(key).hexdigest() != TRUSTED_PERMIT_SIGNER_SHA256:
            _deny("LOCAL_TEXT_ISSUER_MISMATCH")
        raw = json.loads(p.read_bytes().decode("utf-8", "strict"))
        if type(raw) is not dict or set(raw) != {
            "contract", "evidence_head_sha256", "source_ids", "purpose",
            "expires_utc", "authorization_id", "text_access_allowed",
            "publication_allowed", "p1_admitted", "mac"}:
            _deny("LOCAL_TEXT_PERMIT_INVALID")
        mac = raw.pop("mac")
        if type(mac) is not str or not HEX.fullmatch(mac):
            _deny("LOCAL_TEXT_PERMIT_INVALID")
        actual = hmac.new(key, evidence._canonical(raw), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(mac, actual):
            _deny("LOCAL_TEXT_PERMIT_SIGNATURE_INVALID")
        if (raw["contract"] != PERMIT_CONTRACT or
                raw["evidence_head_sha256"] != head or
                raw["purpose"] != "restricted_internal_research" or
                raw["text_access_allowed"] is not True or
                raw["publication_allowed"] is not False or
                raw["p1_admitted"] is not False or
                type(raw["source_ids"]) is not list or
                len(set(map(str, raw["source_ids"]))) != len(raw["source_ids"]) or
                source_id not in raw["source_ids"] or
                any(type(s) is not str for s in raw["source_ids"]) or
                type(raw["authorization_id"]) is not str or
                not re.fullmatch(r"[a-z0-9][a-z0-9_-]{5,79}",raw["authorization_id"])):
            _deny("LOCAL_TEXT_PERMIT_SCOPE_DENIED")
        if type(raw["expires_utc"]) is not str or not re.fullmatch(
                r"20[0-9]{2}-[01][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-5][0-9]Z",
                raw["expires_utc"]):
            _deny("LOCAL_TEXT_PERMIT_INVALID")
        expiry = datetime.fromisoformat(raw["expires_utc"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if expiry <= now or (expiry - now).total_seconds() > 86400:
            _deny("LOCAL_TEXT_PERMIT_EXPIRED_OR_EXCESSIVE")
    except ResearchAdapterError:
        raise
    except (OSError, ValueError, UnicodeError, TypeError, KeyError,
            evidence.EvidenceError) as exc:
        raise ResearchAdapterError("LOCAL_TEXT_PERMIT_INVALID") from exc


class PrivateResearchAdapters:
    """No stateful connection or web endpoint; one audited local read/request."""

    def __init__(self, *, vault: Path, corpus_db: Path, sidecar_db: Path,
                 registry: Path, anchor_dir: Path, evidence_key: Path,
                 permit_path: Path | None = None, permit_key: Path | None = None):
        self.vault = Path(vault)
        self.corpus_db = Path(corpus_db)
        self.sidecar_db = Path(sidecar_db)
        self.registry = Path(registry)
        self.anchor_dir = Path(anchor_dir)
        self.evidence_key = Path(evidence_key)
        self.permit_path = Path(permit_path) if permit_path is not None else None
        self.permit_key = Path(permit_key) if permit_key is not None else None
        # External evidence is ALWAYS checked again on lookup; callers cannot
        # supply their own "verified=True" booleans or forged evidence report.

    def _evidence(self) -> dict:
        try:
            report = evidence.verify_evidence(
                self.registry, self.anchor_dir, self.evidence_key,
                self.vault, self.sidecar_db)
            if (report.get("status") != "EVIDENCE_REGISTRY_VERIFIED"
                    or report.get("byte_integrity_verified") is not True
                    or report.get("source_authenticated") is not False
                    or report.get("scholarly_verified") is not False
                    or report.get("rights_status") != "legal_review_pending"
                    or report.get("text_included") is not False):
                _deny("EVIDENCE_NOT_QUALIFIED")
            # verify_evidence uses the hard-pinned private corpus filename.
            corpus = evidence._guard_outside(self.corpus_db, None)
            canonical = evidence._guard_outside(
                self.vault / evidence.CORPUS_DB_NAME, None)
            if corpus != canonical:
                _deny("CORPUS_PATH_NOT_ANCHORED")
            if (type(report.get("head_entry_sha256")) is not str or
                    not HEX.fullmatch(report["head_entry_sha256"])):
                _deny("EVIDENCE_NOT_QUALIFIED")
            return report
        except ResearchAdapterError:
            raise
        except (evidence.EvidenceError, OSError, sqlite3.Error, ValueError) as exc:
            raise ResearchAdapterError("EVIDENCE_VERIFICATION_FAILED") from exc

    def corpus_sources(self) -> list[dict]:
        self._evidence()
        manifest = load_manifest()
        expected = {s["id"]: s for s in manifest["sources"]}
        db = _db(self.corpus_db)
        try:
            rows = db.execute(
                "SELECT source_id,source_kind,version,raw_sha256,rights_status,"
                "publication_enabled,source_authenticated,p1_admitted "
                "FROM corpus_sources ORDER BY source_id").fetchall()
            if len(rows) != len(expected):
                _deny("CORPUS_SOURCE_SET_MISMATCH")
            found = []
            for sid, kind, version, rawsha, rights, pub, auth, p1 in rows:
                if (sid not in expected or kind != expected[sid]["kind"]
                        or version != expected[sid]["version"]
                        or rawsha != expected[sid]["sha256"]
                        or rights != "legal_review_pending"
                        or pub != 0 or auth != 0 or p1 != 0):
                    _deny("CORPUS_SOURCE_SET_MISMATCH")
                found.append(_no_text({
                    "source_id": sid, "source_kind": kind,
                    "source_version": version, "source_sha256": rawsha,
                    "adapter": "quranenc_corpus", "records": 6236}))
            if set(s["source_id"] for s in found) != set(expected):
                _deny("CORPUS_SOURCE_SET_MISMATCH")
            return found
        except sqlite3.Error as exc:
            raise ResearchAdapterError("CORPUS_METADATA_QUERY_FAILED") from exc
        finally:
            db.close()

    def sidecar_sources(self) -> list[dict]:
        self._evidence()
        db = _db(self.sidecar_db)
        try:
            names = {t[0] for t in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            if not set(SIDE_TABLES).issubset(names):
                _deny("SIDECAR_TABLE_SET_MISMATCH")
            return [_no_text({
                "source_id": table, "source_kind": "tafsir",
                "parent_source_id": SIDECAR_SOURCE_ID,
                "adapter": "tafsircenter_sidecar", "records": 6236})
                    for table in SIDE_TABLES]
        except sqlite3.Error as exc:
            raise ResearchAdapterError("SIDECAR_METADATA_QUERY_FAILED") from exc
        finally:
            db.close()

    def lookup(self, reference: str, source_id: str, *,
               adapter: str = "corpus", include_text: bool = False) -> dict:
        sura, aya = _reference(reference)
        if type(include_text) is not bool:
            _deny("TEXT_MODE_INVALID")
        if adapter not in ("corpus", "sidecar"):
            _deny("ADAPTER_NOT_ALLOWLISTED")
        sid = _source_id(source_id, sidecar=(adapter == "sidecar"))
        report = self._evidence()
        if adapter == "corpus":
            if sid not in {row["source_id"] for row in self.corpus_sources()}:
                _deny("CORPUS_SOURCE_SET_MISMATCH")
        else:
            if sid not in {row["source_id"] for row in self.sidecar_sources()}:
                _deny("SIDECAR_TABLE_SET_MISMATCH")
        if include_text:
            _private_permit(self.permit_path, self.permit_key, self.vault,
                            report["head_entry_sha256"],sid)
        db = _db(self.corpus_db if adapter == "corpus" else self.sidecar_db)
        try:
            if adapter == "corpus":
                if include_text:
                    row = db.execute(
                        "SELECT text,footnotes FROM corpus_entries "
                        "WHERE source_id=? AND sura=? AND aya=?",
                        (sid,sura,aya)).fetchone()
                else:
                    row = db.execute(
                        "SELECT 1 FROM corpus_entries "
                        "WHERE source_id=? AND sura=? AND aya=?",
                        (sid,sura,aya)).fetchone()
            else:
                # Only hard-coded tables/columns may be interpolated in SQL.
                # All user-supplied verse coordinates are parameterized.
                s_col, a_col = ("surahNo", "ayahNo") if sid == "QuranTafseer" else ("sura", "aya")
                if include_text:
                    col = TEXT_COLUMNS[sid]
                    row = db.execute(
                        f'SELECT "{col}" FROM "{sid}" WHERE "{s_col}"=? '
                        f'AND "{a_col}"=?', (sura,aya)).fetchone()
                else:
                    row = db.execute(
                        f'SELECT 1 FROM "{sid}" WHERE "{s_col}"=? '
                        f'AND "{a_col}"=?', (sura,aya)).fetchone()
            if row is None:
                _deny("REFERENCE_NOT_PRESENT")
            result = _no_text({
                "contract": CONTRACT, "reference": reference,
                "adapter": adapter, "source_id": sid,
                "evidence_head_sha256": report["head_entry_sha256"],
                "coordinate_present": True})
            if include_text:
                fields = row[:2] if adapter == "corpus" else row[:1]
                if any(type(field) is not str or len(field.encode("utf-8")) > MAX_TEXT
                       for field in fields):
                    _deny("PRIVATE_TEXT_INVALID")
                result["text"] = fields[0]
                if adapter == "corpus":
                    result["footnotes"] = fields[1]
                result["text_included"] = True
                result["restricted_local_use_only"] = True
            return result
        except sqlite3.Error as exc:
            raise ResearchAdapterError("PRIVATE_LOOKUP_FAILED") from exc
        finally:
            db.close()
