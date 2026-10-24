"""R0.1d: two-axis source qualification ledger (scholarly + rights).

Decisions are independent, scoped, explicitly recorded and hash-chained with
an out-of-band HMAC head anchor. By construction:
  - a SCHOLARLY decision can never move a RIGHTS state and vice versa;
  - absent decisions leave a source in its pending default state;
  - record-level quarantine is recorded without touching other records,
    other sources, or any original text;
  - no decision in this ledger grants publication, rule execution or fatwa
    authority, and none is an automatic promotion.

Reviewers record decisions; this module only stores, chains and reports them.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from qa.private_evidence_v01 import (
    _VaultLock, _canonical, _guard_outside, load_operator_key,
    EvidenceError,
)
from engines.quran.q01.engine import _VERSE_COUNTS
from qa.corpus_ingest_v01 import VALID_IDS
from qa.tafsircenter_sidecar_v01 import TABLES_AR

VERSION = "quran-qualification-ledger/v0.1.0"
CONTRACT = "mubin-source-qualification-ledger-v0.1"
AXES = frozenset(("scholarly", "rights"))
SCHOLARLY_DECISIONS = frozenset((
    "SOURCE_TEXT_INTEGRITY_REVIEWED", "SOURCE_REJECTED",
    "RECORD_QUARANTINED", "EDITION_IDENTITY_UNCONFIRMED"))
RIGHTS_DECISIONS = frozenset((
    "INTERNAL_USE_CLEARED", "NOT_CLEARED", "RESTRICTED_USE_SCOPE"))
RECORD_DECISIONS = SCHOLARLY_DECISIONS & {"RECORD_QUARANTINED"}
ID = re.compile(r"[A-Za-z][A-Za-z0-9._:-]{2,127}\Z")
SOURCE_IDS = frozenset(VALID_IDS) | frozenset(TABLES_AR) | {"QuranTafseer"}
SHA = re.compile(r"[0-9a-f]{64}\Z")
DEFAULT_SCHOLARLY = "UNREVIEWED"
DEFAULT_RIGHTS = "legal_review_pending"
LOCK_NAME = ".qualification-ledger.lock"
MAX_NOTES = 400


class QualificationError(ValueError):
    """Stable refusal codes; never contain source text or private paths."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _need(ok, code):
    if not ok:
        raise QualificationError(code)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load(path: Path) -> list[dict]:
    if path.is_symlink():
        raise QualificationError("LEDGER_SYMLINK_REFUSED")
    if not path.exists():
        return []
    try:
        raw = path.read_bytes()
        lines = raw.decode("utf-8", "strict").split(chr(10))
        entries = [json.loads(line) for line in lines if line]
    except (OSError, ValueError, UnicodeError, TypeError, RecursionError) as exc:
        raise QualificationError("LEDGER_FORMAT_INVALID") from exc
    if not all(type(entry) is dict for entry in entries):
        raise QualificationError("LEDGER_FORMAT_INVALID")
    if raw != b"".join(_canonical(entry) + bytes([10]) for entry in entries):
        raise QualificationError("LEDGER_NONCANONICAL_BYTES")
    return entries


def _verify_chain(entries: list[dict]) -> None:
    previous = "0" * 64
    for i, body in enumerate(entries, 1):
        keys = {"seq", "prev_entry_sha256", "recorded_at_utc",
                "operator", "payload", "entry_sha256"}
        if (type(body) is not dict or set(body) != keys
                or type(body["seq"]) is not int or body["seq"] != i
                or type(body["prev_entry_sha256"]) is not str
                or type(body["entry_sha256"]) is not str
                or type(body["operator"]) is not str
                or type(body["recorded_at_utc"]) is not str
                or type(body["payload"]) is not dict):
            raise QualificationError("LEDGER_CHAIN_INVALID")
        validate_decision(body["payload"])
        recorded = body["entry_sha256"]
        payload = {k: v for k, v in body.items() if k != "entry_sha256"}
        if (not SHA.fullmatch(recorded)
                or recorded != _sha(_canonical(payload))
                or body["prev_entry_sha256"] != previous):
            raise QualificationError("LEDGER_CHAIN_INVALID")
        previous = recorded


def _anchor_path(anchor_dir: Path, ledger_path: Path) -> Path:
    return anchor_dir / (ledger_path.stem + ".qualification-head-anchor.json")


def read_head_anchor(anchor_dir: Path, ledger_path: Path, key: bytes) -> dict:
    path = _anchor_path(_guard_outside(anchor_dir, None), ledger_path)
    if path.is_symlink() or not path.is_file():
        raise QualificationError("HEAD_ANCHOR_MISSING")
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError, OSError, RecursionError) as exc:
        raise QualificationError("HEAD_ANCHOR_FORMAT_INVALID") from exc
    if type(body) is not dict or set(body) != {
            "registry", "head_entry_sha256", "sequence", "head_hmac"}:
        raise QualificationError("HEAD_ANCHOR_FORMAT_INVALID")
    mac = body.pop("head_hmac")
    if type(mac) is not str or not SHA.fullmatch(mac):
        raise QualificationError("HEAD_ANCHOR_FORMAT_INVALID")
    expected = hmac.new(key, _canonical(body), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mac, expected):
        raise QualificationError("HEAD_ANCHOR_MAC_INVALID")
    if (body["registry"] != ledger_path.name
            or type(body["head_entry_sha256"]) is not str
            or not SHA.fullmatch(body["head_entry_sha256"])
            or type(body["sequence"]) is not int
            or body["sequence"] < 1):
        raise QualificationError("HEAD_ANCHOR_FORMAT_INVALID")
    return body


def _attested_entries(ledger_path: Path, anchor_dir: Path,
                      key_file: Path, *, allow_initial=False) -> tuple[list[dict], str]:
    """Trust a ledger only when its entire chain equals its signed anchor."""
    ledger = _guard_outside(ledger_path, None)
    anchor = _guard_outside(anchor_dir, None)
    key_path = _guard_outside(key_file, None)
    entries = _load(ledger)
    _verify_chain(entries)
    anchor_path = _anchor_path(anchor, ledger)
    if not entries:
        if allow_initial and not ledger.exists() and not anchor_path.exists():
            return [], "0" * 64
        raise QualificationError("LEDGER_UNPAIRED_OR_EMPTY")
    try:
        key = load_operator_key(key_path, create=False)
    except EvidenceError as exc:
        raise QualificationError("LEDGER_KEY_UNAVAILABLE") from exc
    body = read_head_anchor(anchor, ledger, key)
    head = entries[-1]["entry_sha256"]
    if body["head_entry_sha256"] != head or body["sequence"] != len(entries):
        raise QualificationError("HEAD_ANCHOR_HEAD_MISMATCH")
    return entries, head


def validate_decision(decision: dict) -> dict:
    """Schema, scope and disjoint-axis validation; NOT reviewer attestation."""
    _need(type(decision) is dict, "DECISION_SCHEMA_INVALID")
    required = {"decision_id", "axis", "source_id", "scope", "decision",
                "reviewer", "reviewed_at_utc", "evidence_head_sha256", "notes"}
    _need(set(decision) == required, "DECISION_SCHEMA_INVALID")
    for name in ("decision_id", "source_id", "axis", "decision", "reviewer",
                 "reviewed_at_utc", "evidence_head_sha256", "notes"):
        _need(type(decision[name]) is str, "DECISION_SCHEMA_INVALID")
    _need(ID.fullmatch(decision["decision_id"]) is not None, "DECISION_ID_INVALID")
    _need(decision["source_id"] in SOURCE_IDS, "SOURCE_NOT_ALLOWLISTED")
    axis, dec = decision["axis"], decision["decision"]
    _need(axis in AXES, "AXIS_INVALID")
    other = RIGHTS_DECISIONS if axis == "scholarly" else SCHOLARLY_DECISIONS
    if dec in other:
        raise QualificationError("CROSS_AXIS_DECISION_REFUSED")
    _need(dec in (SCHOLARLY_DECISIONS if axis == "scholarly"
                  else RIGHTS_DECISIONS), "DECISION_NOT_VALID_FOR_AXIS")
    reviewer = decision["reviewer"]
    normalized = reviewer.strip().casefold()
    _need(3 <= len(reviewer) <= 80 and normalized == reviewer.casefold()
          and not any(ord(ch) < 32 or ord(ch) == 127 for ch in reviewer)
          and normalized not in {"system", "automation", "llm", "ai", "bot", "codex",
                                 "gpt", "model", "auto"},
          "REVIEWER_INVALID")
    stamp = decision["reviewed_at_utc"]
    try:
        instant = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        _need(instant <= datetime.now(timezone.utc), "REVIEW_DATE_INVALID")
    except ValueError as exc:
        raise QualificationError("REVIEW_DATE_INVALID") from exc
    _need(SHA.fullmatch(decision["evidence_head_sha256"]) is not None
          and decision["evidence_head_sha256"] != "0" * 64,
          "EVIDENCE_HEAD_INVALID")
    notes = decision["notes"]
    _need(len(notes) <= MAX_NOTES and not any(ord(c) < 32 for c in notes),
          "NOTES_INVALID")
    scope = decision["scope"]
    _need(type(scope) is dict, "SCOPE_INVALID")
    if dec == "RECORD_QUARANTINED":
        _need(set(scope) == {"record_coordinates"}, "SCOPE_INVALID")
        coords = scope["record_coordinates"]
        _need(type(coords) is list and 1 <= len(coords) <= 6236
              and all(type(c) is str for c in coords), "SCOPE_COORDINATES_INVALID")
        parsed = []
        for coordinate in coords:
            try:
                sv, av = coordinate.split(":")
                sura, aya = int(sv), int(av)
                canonical = f"{sura}:{aya}" == coordinate
            except (ValueError, AttributeError):
                raise QualificationError("SCOPE_COORDINATES_INVALID") from None
            _need(canonical and 1 <= sura <= len(_VERSE_COUNTS)
                  and 1 <= aya <= _VERSE_COUNTS[sura-1], "SCOPE_COORDINATES_INVALID")
            parsed.append(coordinate)
        _need(len(set(parsed)) == len(parsed), "SCOPE_COORDINATES_INVALID")
    else:
        _need(scope == {"full_source": True}, "SCOPE_INVALID")
    return decision


def append_decision(ledger_path: Path, anchor_dir: Path, key_file: Path,
                    decision: dict, operator: str) -> dict:
    """Record exactly one human-provided decision; never grant public authority."""
    ledger_path = _guard_outside(ledger_path, None)
    anchor_dir = _guard_outside(anchor_dir, None)
    key_file = _guard_outside(key_file, None)
    clean = validate_decision(decision)
    _need(type(operator) is str and operator.strip().casefold() != clean["reviewer"].strip().casefold(),
          "SELF_REVIEW_REFUSED")
    with _VaultLock(ledger_path.parent / LOCK_NAME, operator):
        entries, previous = _attested_entries(ledger_path, anchor_dir, key_file,
                                               allow_initial=True)
        try:
            key = load_operator_key(key_file, create=not entries)
        except EvidenceError as exc:
            raise QualificationError("LEDGER_KEY_UNAVAILABLE") from exc
        _need(not any(e["payload"]["decision_id"] == clean["decision_id"]
                      for e in entries), "DECISION_ID_ALREADY_RECORDED")
        body = {
            "seq": len(entries) + 1, "prev_entry_sha256": previous,
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "operator": operator, "payload": clean,
        }
        entry_sha = _sha(_canonical(body))
        record = {**body, "entry_sha256": entry_sha}
        raw = b"".join(_canonical(entry) + bytes([10]) for entry in [*entries, record])
        # Single process-local lock; both files must remain on operator-owned
        # storage. A crash between two replacements MUST fail closed thereafter.
        temp = ledger_path.parent / (".qual-" + str(os.getpid()) + ".tmp")
        anchor_path = _anchor_path(anchor_dir, ledger_path)
        anchor_path.parent.mkdir(parents=True, exist_ok=True)
        anchor_body = {"registry": ledger_path.name,
                       "head_entry_sha256": entry_sha,
                       "sequence": body["seq"]}
        mac = hmac.new(key, _canonical(anchor_body), hashlib.sha256).hexdigest()
        anchor_tmp = anchor_path.parent / (".qanchor-" + str(os.getpid()) + ".tmp")
        try:
            for dst, data in ((temp, raw),
                              (anchor_tmp, _canonical({**anchor_body, "head_hmac": mac}) + bytes([10]))):
                fd = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                             getattr(os, "O_BINARY", 0), 0o600)
                with os.fdopen(fd, "wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
            os.replace(temp, ledger_path)
            os.replace(anchor_tmp, anchor_path)
        finally:
            temp.unlink(missing_ok=True)
            anchor_tmp.unlink(missing_ok=True)
    return {"status": "QUALIFICATION_DECISION_RECORDED",
            "decision_id": clean["decision_id"], "entry_sha256": entry_sha,
            "axis": clean["axis"], "decision": clean["decision"],
            "publication_granted": False, "juristic_inference_allowed": False,
            "public_fatwa_authorized": False}


def decisions_for(ledger_path: Path, source_id: str, axis: str | None = None,
                  *, anchor_dir: Path, key_file: Path,
                  reference: str | None = None) -> list[dict]:
    _need(type(source_id) is str and source_id in SOURCE_IDS, "SOURCE_NOT_ALLOWLISTED")
    _need(axis is None or axis in AXES, "AXIS_INVALID")
    if reference is not None:
        _valid_reference(reference)
    entries, _ = _attested_entries(ledger_path, anchor_dir, key_file)
    out = []
    for body in entries:
        payload = body["payload"]
        if payload["source_id"] != source_id or axis not in (None, payload["axis"]):
            continue
        scope = payload["scope"]
        if reference is not None and "record_coordinates" in scope and reference not in scope["record_coordinates"]:
            continue
        out.append({"decision_id": payload["decision_id"],
                    "axis": payload["axis"], "decision": payload["decision"],
                    "scope": scope, "reviewer": payload["reviewer"],
                    "reviewed_at_utc": payload["reviewed_at_utc"],
                    "evidence_head_sha256": payload["evidence_head_sha256"],
                    "entry_sha256": body["entry_sha256"],
                    "publication_granted": False})
    return out


def _valid_reference(reference: str) -> None:
    if type(reference) is not str:
        raise QualificationError("SCOPE_COORDINATES_INVALID")
    try:
        sv, av = reference.split(":")
        sura, aya = int(sv), int(av)
    except (ValueError, TypeError):
        raise QualificationError("SCOPE_COORDINATES_INVALID") from None
    _need(reference == f"{sura}:{aya}" and 1 <= sura <= len(_VERSE_COUNTS)
          and 1 <= aya <= _VERSE_COUNTS[sura-1], "SCOPE_COORDINATES_INVALID")


def current_state(ledger_path: Path, source_id: str, axis: str, *,
                  anchor_dir: Path, key_file: Path,
                  reference: str | None = None) -> str:
    """Full-source decisions remain global; quarantines affect only matching coordinates."""
    _need(axis in AXES, "AXIS_INVALID")
    items = decisions_for(ledger_path, source_id, axis, anchor_dir=anchor_dir,
                          key_file=key_file, reference=reference)
    latest_full = DEFAULT_SCHOLARLY if axis == "scholarly" else DEFAULT_RIGHTS
    quarantined = False
    for item in items:
        if item["scope"] == {"full_source": True}:
            latest_full = item["decision"]
        elif (reference is not None and axis == "scholarly"
              and item["decision"] == "RECORD_QUARANTINED"):
            quarantined = True
    return "RECORD_QUARANTINED" if quarantined else latest_full


def verify_ledger(ledger_path: Path, anchor_dir: Path, key_file: Path) -> dict:
    entries, head = _attested_entries(ledger_path, anchor_dir, key_file)
    return {"contract": CONTRACT, "status": "QUALIFICATION_LEDGER_VERIFIED",
            "entries": len(entries), "head_entry_sha256": head,
            "axes": sorted(AXES), "publication_granted": False,
            "scholarly_verified_globally": False,
            "juristic_inference_allowed": False,
            "public_fatwa_authorized": False, "text_included": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    record = sub.add_parser("record")
    record.add_argument("--ledger", required=True)
    record.add_argument("--anchor-dir", required=True)
    record.add_argument("--key-file", required=True)
    record.add_argument("--decision-json", required=True)
    record.add_argument("--operator", required=True)
    state = sub.add_parser("state")
    state.add_argument("--ledger", required=True)
    state.add_argument("--source-id", required=True)
    state.add_argument("--axis", choices=tuple(AXES), required=True)
    check = sub.add_parser("verify")
    check.add_argument("--ledger", required=True)
    check.add_argument("--anchor-dir", required=True)
    check.add_argument("--key-file", required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == "record":
            decision = json.loads(Path(args.decision_json).read_text(encoding="utf-8"))
            report = append_decision(args.ledger, args.anchor_dir,
                                     args.key_file, decision, args.operator)
            code = 0
        elif args.action == "state":
            report = {"source_id": args.source_id, "axis": args.axis,
                      "state": current_state(args.ledger, args.source_id, args.axis),
                      "decisions": decisions_for(args.ledger, args.source_id, args.axis)}
            code = 0
        else:
            report = verify_ledger(args.ledger, args.anchor_dir, args.key_file)
            code = 0
    except QualificationError as exc:
        report, code = {"status": "REFUSED", "reason_code": exc.code,
                        "text_included": False}, 1
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        report, code = {"status": "REFUSED", "reason_code": "LEDGER_INTERNAL_ERROR",
                        "text_included": False}, 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
