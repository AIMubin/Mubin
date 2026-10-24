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
)

VERSION = "quran-qualification-ledger/v0.1.0"
CONTRACT = "mubin-source-qualification-ledger-v0.1"
AXES = frozenset(("scholarly", "rights"))
SCHOLARLY_DECISIONS = frozenset((
    "SOURCE_TEXT_INTEGRITY_REVIEWED", "SOURCE_REJECTED",
    "RECORD_QUARANTINED", "EDITION_IDENTITY_UNCONFIRMED"))
RIGHTS_DECISIONS = frozenset((
    "INTERNAL_USE_CLEARED", "NOT_CLEARED", "RESTRICTED_USE_SCOPE"))
RECORD_DECISIONS = SCHOLARLY_DECISIONS & {"RECORD_QUARANTINED"}
ID = re.compile(r"[a-z][a-z0-9._:-]{2,127}\Z")
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
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries


def _verify_chain(entries: list[dict]) -> None:
    previous = "0" * 64
    for i, body in enumerate(entries, 1):
        recorded = body.get("entry_sha256")
        payload = {k: v for k, v in body.items() if k != "entry_sha256"}
        if recorded != _sha(_canonical(payload)) or body.get("prev_entry_sha256") != previous:
            raise QualificationError("LEDGER_CHAIN_INVALID")
        previous = recorded


def _anchor_path(anchor_dir: Path, ledger_path: Path) -> Path:
    return anchor_dir / (ledger_path.stem + ".qualification-head-anchor.json")


def read_head_anchor(anchor_dir: Path, ledger_path: Path, key: bytes) -> dict:
    path = _anchor_path(anchor_dir, ledger_path)
    if path.is_symlink() or not path.is_file():
        raise QualificationError("HEAD_ANCHOR_MISSING")
    body = json.loads(path.read_text(encoding="utf-8"))
    mac = body.pop("head_hmac", "")
    expected = hmac.new(key, _canonical(body), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mac, expected):
        raise QualificationError("HEAD_ANCHOR_MAC_INVALID")
    return body


def validate_decision(decision: dict) -> dict:
    """Contract validation; refuse self-review, text and auto-promotion."""
    _need(type(decision) is dict, "DECISION_SCHEMA_INVALID")
    required = {"decision_id", "axis", "source_id", "scope", "decision",
                "reviewer", "reviewed_at_utc", "evidence_head_sha256", "notes"}
    _need(set(decision) == required, "DECISION_SCHEMA_INVALID")
    _need(ID.fullmatch(decision["decision_id"]) is not None
          and ID.fullmatch(decision["source_id"]) is not None,
          "DECISION_ID_INVALID")
    _need(decision["axis"] in AXES, "AXIS_INVALID")
    axis, dec = decision["axis"], decision["decision"]
    allowed = SCHOLARLY_DECISIONS if axis == "scholarly" else RIGHTS_DECISIONS
    _need(dec in allowed, "DECISION_NOT_VALID_FOR_AXIS")
    _need(type(decision["reviewer"]) is str and 3 <= len(decision["reviewer"]) <= 80
          and decision["reviewer"].lower() not in ("system", "automation", "llm"),
          "REVIEWER_INVALID")
    _need(re.fullmatch(r"20[0-9]{2}-[01][0-9]-[0-3][0-9]T[0-2][0-9]:[0-5][0-9]:[0-5][0-9]Z",
                       decision["reviewed_at_utc"]) is not None,
          "REVIEW_DATE_INVALID")
    _need(SHA.fullmatch(decision["evidence_head_sha256"]) is not None,
          "EVIDENCE_HEAD_INVALID")
    _need(type(decision["notes"]) is str and len(decision["notes"]) <= MAX_NOTES,
          "NOTES_INVALID")
    scope = decision["scope"]
    _need(type(scope) is dict and set(scope) <= {"record_coordinates", "full_source"}
          and scope, "SCOPE_INVALID")
    if "record_coordinates" in scope:
        coords = scope["record_coordinates"]
        _need(type(coords) is list and 1 <= len(coords) <= 6236 and
              all(type(c) is str and re.fullmatch(
                  r"(?:[1-9]|[1-9][0-9]|1[01][0-9]|11[0-4]):[1-9][0-9]{0,2}\Z", c)
                  for c in coords), "SCOPE_COORDINATES_INVALID")
    # A cross-axis decision is refused: the axes are independent by contract.
    if axis == "rights" and dec in SCHOLARLY_DECISIONS - RIGHTS_DECISIONS:
        raise QualificationError("CROSS_AXIS_DECISION_REFUSED")
    return decision


def append_decision(ledger_path: Path, anchor_dir: Path, key_file: Path,
                    decision: dict, operator: str) -> dict:
    ledger_path = _guard_outside(ledger_path, None)
    anchor_dir = _guard_outside(anchor_dir, None)
    key = load_operator_key(_guard_outside(key_file, None))
    clean = validate_decision(decision)
    lock = _VaultLock(ledger_path.parent / LOCK_NAME, operator)
    with lock:
        entries = _load(ledger_path)
        _verify_chain(entries)
        _need(not any(e["payload"]["decision_id"] == clean["decision_id"]
                      for e in entries), "DECISION_ID_ALREADY_RECORDED")
        previous = entries[-1]["entry_sha256"] if entries else "0" * 64
        body = {
            "seq": len(entries) + 1, "prev_entry_sha256": previous,
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "operator": operator, "payload": clean,
        }
        entry_sha = _sha(_canonical(body))
        line = json.dumps({**body, "entry_sha256": entry_sha},
                          ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")) + "\n"
        prior = ledger_path.read_bytes() if ledger_path.exists() else b""
        temp = ledger_path.parent / (".qual-" + str(os.getpid()) + ".tmp")
        with open(temp, "wb") as handle:
            handle.write(prior)
            handle.write(line.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, ledger_path)
        anchor_path = _anchor_path(anchor_dir, ledger_path)
        anchor_path.parent.mkdir(parents=True, exist_ok=True)
        anchor_body = {"registry": ledger_path.name,
                       "head_entry_sha256": entry_sha,
                       "sequence": body["seq"]}
        mac = hmac.new(key, _canonical(anchor_body), hashlib.sha256).hexdigest()
        anchor_tmp = anchor_path.parent / (".qanchor-" + str(os.getpid()) + ".tmp")
        anchor_tmp.write_bytes(_canonical({**anchor_body, "head_hmac": mac}) + b"\n")
        os.replace(anchor_tmp, anchor_path)
    return {"status": "QUALIFICATION_DECISION_RECORDED",
            "decision_id": clean["decision_id"], "entry_sha256": entry_sha,
            "axis": clean["axis"], "decision": clean["decision"]}


def decisions_for(ledger_path: Path, source_id: str, axis: str | None = None) -> list[dict]:
    entries = _load(_guard_outside(ledger_path, None))
    _verify_chain(entries)
    out = []
    for body in entries:
        payload = body["payload"]
        if payload["source_id"] == source_id and axis in (None, payload["axis"]):
            out.append({"decision_id": payload["decision_id"],
                        "axis": payload["axis"], "decision": payload["decision"],
                        "scope": payload["scope"], "reviewer": payload["reviewer"],
                        "reviewed_at_utc": payload["reviewed_at_utc"],
                        "entry_sha256": body["entry_sha256"]})
    return out


def current_state(ledger_path: Path, source_id: str, axis: str) -> str:
    """Latest per-axis state; pending defaults when no decision exists."""
    _need(axis in AXES, "AXIS_INVALID")
    latest = None
    for body in _load(_guard_outside(ledger_path, None)):
        payload = body["payload"]
        if payload["source_id"] == source_id and payload["axis"] == axis:
            latest = payload
    if latest is None:
        return DEFAULT_SCHOLARLY if axis == "scholarly" else DEFAULT_RIGHTS
    return latest["decision"]


def verify_ledger(ledger_path: Path, anchor_dir: Path, key_file: Path) -> dict:
    ledger_path = _guard_outside(ledger_path, None)
    anchor_dir = _guard_outside(anchor_dir, None)
    key = load_operator_key(_guard_outside(key_file, None))
    entries = _load(ledger_path)
    _verify_chain(entries)
    head = entries[-1]["entry_sha256"] if entries else "0" * 64
    anchor = read_head_anchor(anchor_dir, ledger_path, key)
    if anchor.get("head_entry_sha256") != head:
        raise QualificationError("HEAD_ANCHOR_HEAD_MISMATCH")
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
