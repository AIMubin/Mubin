"""E2E-01.4b.4: fail-closed byte-pin preflight before local AI dispatch.

A repository-scoped digest receipt is NOT publisher custody or a model result.
The production CLI loads a fixed tracked metadata manifest. No source text is
committed, logged or emitted by this preflight.
"""
from __future__ import annotations

import re
from pathlib import Path

from engines.e2e.witness_science import (
    TrialError, _local_json, _require, _witness_packet,
)

CONTRACT = "mubin-e2e-014b4-frozen-local-preflight-v0.1"
_MANIFEST = (Path(__file__).resolve().parents[2]
             / "evaluation/evidence/amr_2_43_local_excerpt_digests_v01.json")
_SHA256 = re.compile(r"[a-f0-9]{64}\Z")
_ROLES = frozenset(("verse", "tafsir", "usul"))
_PIN_FIELDS = ("id", "role", "url", "family", "local_excerpt_sha256")
_LOCKED_FALSE = (
    "upstream_source_byte_attested",
    "original_quran_edition_authenticated",
    "original_tafsir_edition_authenticated",
    "independent_model_pair_executed",
    "source_authenticated",
    "scholarly_verified",
    "publication_allowed",
    "juristic_inference_allowed",
    "public_fatwa_authorized",
    "p1_admitted",
)


def _load_manifest() -> dict:
    """Only the fixed repo manifest; the production CLI has no override."""
    try:
        return _local_json(_MANIFEST)
    except TrialError as exc:
        raise TrialError("LOCAL_PIN_MANIFEST_UNAVAILABLE") from exc


def _verify_manifest(packet: dict, digest: str, manifest: dict) -> None:
    """Compare exact local witness bytes, identity and canonical packet hash.

    The digest is not a signature. A compromised repository manifest or
    inaccurate original online excerpt remains beyond this check's scope.
    """
    _require(
        type(manifest) is dict
        and manifest.get("contract") ==
            "mubin-e2e-014b3-cited-excerpt-digests-v0.1"
        and manifest.get("case_id") == "AMR-01-P"
        and manifest.get("reference") == "2:43"
        and manifest.get("candidate_word") == "أَقِيمُوا"
        and type(manifest.get("packet_canonical_sha256")) is str
        and _SHA256.fullmatch(manifest["packet_canonical_sha256"]) is not None
        and type(manifest.get("witness_records")) is list
        and len(manifest["witness_records"]) == 3
        and all(manifest.get(key) is False for key in _LOCKED_FALSE)
        and manifest.get("scientific_gold_label") is None
        and manifest.get("rights_status") == "legal_review_pending",
        "LOCAL_PIN_MANIFEST_INVALID",
    )
    rows = manifest["witness_records"]
    _require(
        all(type(r) is dict and set(r) == set(_PIN_FIELDS)
            and type(r["local_excerpt_sha256"]) is str
            and _SHA256.fullmatch(r["local_excerpt_sha256"]) is not None
            for r in rows),
        "LOCAL_PIN_MANIFEST_INVALID",
    )
    _require(
        {r["role"] for r in rows} == _ROLES
        and len({r["id"] for r in rows}) == 3
        and packet["case_id"] == manifest["case_id"]
        and packet["reference"] == manifest["reference"],
        "LOCAL_PIN_MANIFEST_INVALID",
    )
    observed = {
        r["role"]: {
            "id": r["id"], "role": r["role"], "url": r["url"],
            "family": r["family"], "local_excerpt_sha256": r["sha256"],
        }
        for r in packet["witnesses"]
    }
    expected = {r["role"]: r for r in rows}
    _require(observed == expected, "LOCAL_WITNESS_PIN_MISMATCH")
    _require(digest == manifest["packet_canonical_sha256"],
             "LOCAL_PACKET_PIN_MISMATCH")


def preflight_frozen_packet(*, casebook: dict, packet: dict,
                            case_id: str) -> dict:
    """No HTTP call: full format, source-local hash and frozen-byte checks."""
    _require(case_id == "AMR-01-P", "LOCAL_CASE_NOT_ADMITTED")
    matches = [case for case in casebook["cases"]
               if case["id"] == case_id
               and case["category"] == "POSITIVE_CANDIDATE"]
    _require(len(matches) == 1, "LOCAL_CASE_NOT_ADMITTED")
    digest, _, state = _witness_packet(matches[0], packet)
    _require(
        state["three_witness_roles_present"]
        and state["exact_candidate_substring_in_verse_bytes"]
        and state["family_labels_distinct"],
        "LOCAL_EVIDENCE_INSUFFICIENT",
    )
    _verify_manifest(packet, digest, _load_manifest())
    return {
        "contract": CONTRACT,
        "case_id": case_id,
        "status": "LOCAL_FROZEN_EXCERPT_BYTE_PIN_MATCH",
        "evidence_packet_sha256": digest,
        "frozen_repository_excerpt_manifest_matched": True,
        "local_utf8_hashes_self_consistent": True,
        "upstream_source_byte_attested": False,
        "independent_model_pair_executed": False,
        "source_authenticated": False,
        "scholarly_verified": False,
        "publication_allowed": False,
        "juristic_inference_allowed": False,
        "public_fatwa_authorized": False,
        "p1_admitted": False,
        "source_text_included": False,
    }
