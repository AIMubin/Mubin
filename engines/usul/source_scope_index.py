"""Pinned synthetic *indexed-source* inspection for U0.1 research.

The local fixture's complete manifest is frozen by a code-side SHA256, with
per-item UTF-8 hashes. We scan bytes/text ourselves, not a caller's 'checked'
list, and refuse changed/omitted/duplicated documents. This does not establish
that all relevant qur'anic or juridical sources were searched or that an Arabic
qarinah has been semantically identified. Only a synthetic literal token works.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engines.usul.exception_evidence import ExceptionEvidenceError

FIXTURE_ROOT = Path(__file__).resolve().parent / "pilots" / "data"
INDEXES = {
    "absent": ("absent-index.json",
               "4d62de6db9e16290da6bc30ee0685f0c9a726dbe99ad7f45ce5dd23c96822cd7",
               "pilot:absent-index"),
    "present": ("present-index.json",
                "eb6b0ef8af58197783095786e554272318334299ac2313d6db43ef79fc92a332",
                "pilot:present-index"),
}
RULE_ID = "pilot:rule-amr-default"
EXCEPTION_ATOM = "pilot:diverting-indicator"
EVIDENCE_ID = "pilot:ev-indicator"
TOKEN = "[[QARINAH]]"
MAX_INDEX_BYTES = 16384


def _check(value, note):
    if not value:
        raise ExceptionEvidenceError("Pinned scope index: " + note)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def load_index(index_key, *, root=FIXTURE_ROOT):
    """Load only allowlisted index keys and pinned bytes; no caller-supplied SHA."""
    _check(type(index_key) is str and index_key in INDEXES,
           "unknown index selection")
    name, expected_hash, expected_id = INDEXES[index_key]
    path = Path(root) / name
    data = path.read_bytes()
    _check(len(data) <= MAX_INDEX_BYTES, "oversize index")
    _check(_sha(data) == expected_hash, "index SHA-256 mismatch")
    try:
        index = json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ExceptionEvidenceError("Pinned scope index: malformed JSON") from exc
    _check(type(index) is dict and set(index) == {
        "schema_version", "index_id", "index_kind",
        "related_p0_source_id", "related_p0_source_sha256",
        "marker", "items",
    }, "unexpected index schema")
    _check(index["schema_version"] == "0.1.0"
           and index["index_id"] == expected_id
           and index["index_kind"] == "synthetic_fixture"
           and index["marker"] == TOKEN, "unexpected index identity")
    items = index["items"]
    _check(type(items) is list and len(items) == 2,
           "pinned synthetic index must have exactly two entries")
    seen = set()
    for entry in items:
        _check(type(entry) is dict and set(entry) ==
               {"id", "locator", "text", "text_sha256"},
               "invalid item schema")
        _check(type(entry["id"]) is str and entry["id"] not in seen,
               "duplicate/invalid index item")
        _check(entry["id"] in {"pilot:case-part1", "pilot:case-part2"},
               "unexpected source item")
        _check(type(entry["text"]) is str and type(entry["locator"]) is str
               and type(entry["text_sha256"]) is str
               and _sha(entry["text"].encode("utf-8")) == entry["text_sha256"],
               "item content integrity mismatch")
        seen.add(entry["id"])
    _check(seen == {"pilot:case-part1", "pilot:case-part2"},
           "incomplete index")
    return index, expected_hash


def examine(bundle, index_key):
    """Compute inspection and assessment directly from pinned fixture bytes.

    'not_checked' records no search; it checks index identity only and yields
    no negative observation. No real-source or universal absence inference.
    """
    no_scan = index_key == "not_checked"
    resolved = "absent" if no_scan else index_key
    index, digest = load_index(resolved)
    sources = {item["id"]: item for item in bundle["sources"]}
    source = sources.get(index["related_p0_source_id"])
    _check(source is not None and source["kind"] == "other"
           and source["content_sha256"] == index["related_p0_source_sha256"],
           "index not tied to the expected P0 synthetic source metadata")
    ev = {item["id"]: item for item in bundle["evidence"]}
    cited = ev.get(EVIDENCE_ID)
    _check(cited is not None
           and cited["source_id"] == index["related_p0_source_id"]
           and cited["verification_status"] == "verified",
           "index evidence reference invalid")
    scanned = []
    found = []
    if not no_scan:
        # Full scan even for a positive match; report every pinned document.
        for entry in index["items"]:
            scanned.append(entry["id"])
            if TOKEN in entry["text"]:
                found.append(entry["id"])
    ids = [entry["id"] for entry in index["items"]]
    finding = ("NOT_CHECKED" if no_scan else
               "PRESENT" if found else "ABSENT_IN_DECLARED_SCOPE")
    assessment = [{
        "rule_id": RULE_ID, "exception_atom": EXCEPTION_ATOM,
        "finding": finding,
        "evidence_ids": [] if no_scan else [EVIDENCE_ID],
        "scope": {
            "id": index["index_id"], "kind": "synthetic_fixture",
            "declared_items": ids, "checked_items": scanned,
        },
    }]
    proof = {
        "index_id": index["index_id"],
        "index_sha256": digest,
        "index_bytes_authenticated": True,
        "index_kind": index["index_kind"],
        "p0_synthetic_source_id": index["related_p0_source_id"],
        "p0_synthetic_source_sha256": index["related_p0_source_sha256"],
        "query_literal": TOKEN,
        "scan_performed": not no_scan,
        "enumerated_items": len(ids), "checked_items": len(scanned),
        "matching_item_ids": found,
        "item_sha256": {item["id"]: item["text_sha256"] for item in index["items"]},
        "index_completeness_scope": "PINNED_SYNTHETIC_FIXTURE_ONLY",
        "real_world_absence_verified": False,
        "scripture_coverage_verified": False,
        "external_source_authentication_verified": False,
        "semantic_qarinah_detection_verified": False,
    }
    return assessment, proof
