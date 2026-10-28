"""H-Search-01 data contracts: HadithMention, HadithSourceWitness,
HadithEvidenceLink. Stable ids derived from source identity + span + digest.
No canonical hadith numbers are invented; no judgments are issued.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

CONTRACT = "mubin-hsearch01-v1"
VERSION = "hsearch/0.1.0"

MENTION_TYPES = frozenset((
    "MARFU",        # raised to the Prophet
    "MAWQUF",       # stopped at a Companion
    "MAQTU",        # cut at a Follower
    "NARRATIVE_EVIDENCE",
    "UNDETERMINED"))
ATTRIBUTION = frozenset(("EXPLICIT_IN_TEXT", "IMPLIED_BY_MARKER", "UNKNOWN"))
MATCH_STATUSES = frozenset((
    "NO_MATCH", "CANDIDATE_MATCH", "TEXTUALLY_SUPPORTED",
    "REVIEW_REQUIRED", "REJECTED", "SOURCE_UNAVAILABLE"))
JUDGMENT_PRESENCE = frozenset((
    "SOURCE_REPORTED_JUDGMENT", "UNVERIFIED_CRITICAL_ATTRIBUTION",
    "NO_CRITICAL_JUDGMENT_FOUND"))
_SHA = re.compile(r"[0-9a-f]{64}")


def _need(ok, code):
    if not ok:
        raise ValueError(code)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sid(*parts) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def _common(meta: dict) -> dict:
    return {
        "contract": CONTRACT,
        "quran_reference": meta["quran_reference"],
        "tafsir_work_id": meta["tafsir_work_id"],
        "tafsir_source_record_id": meta["tafsir_source_record_id"],
        "verification_status": "UNVERIFIED",
        "scholarly_verified": False,
        "rights_verified": False,
        "text_included": False,
        "publication_allowed": False,
        "juristic_inference_allowed": False,
        "public_fatwa_authorized": False,
        "p1_admitted": False,
    }


def make_mention(*, meta: dict, raw_text: str, span: tuple[int, int],
                 mention_type: str, attribution_status: str) -> dict:
    """One narration mention inside a grounded tafsir passage.

    span indexes into raw_text; evidence_sha256 pins the exact substring.
    """
    _need(type(raw_text) is str and raw_text, "HS_TEXT_EMPTY")
    _need(type(span) is tuple and len(span) == 2 and 0 <= span[0] < span[1]
          <= len(raw_text), "HS_SPAN_INVALID")
    _need(mention_type in MENTION_TYPES, "HS_MENTION_TYPE_INVALID")
    _need(attribution_status in ATTRIBUTION, "HS_ATTRIBUTION_INVALID")
    snippet = raw_text[span[0]:span[1]]
    base = meta.get("passage_char_start", 0)
    _need(type(base) is int and base >= 0, "HS_PASSAGE_BASE_INVALID")
    absolute = (base + span[0], base + span[1])
    m = _common(meta)
    mention_id = "hm:" + _sid(meta["tafsir_source_record_id"],
                                absolute, _sha(snippet.encode("utf-8")))[:40]
    return {**m,
            "mention_id": mention_id,
            "passage_id": meta.get("passage_id"),
            "raw_source_span": [absolute[0], absolute[1]],
            "passage_relative_span": [span[0], span[1]],
            "evidence_sha256": _sha(snippet.encode("utf-8")),
            "mention_type": mention_type,
            "attribution_status": attribution_status,
            "evidence_text_sha256": _sha((meta["tafsir_source_record_id"]
                                          + "|" + snippet).encode("utf-8")),
            }


def make_witness(*, source_id: str, work_id: str, version_id: str,
                 source_blob_sha: str, locator: str, raw_text: str,
                 span: tuple[int, int], narration_identifier=None,
                 edition=None) -> dict:
    _need(type(raw_text) is str and raw_text, "HS_TEXT_EMPTY")
    _need(type(span) is tuple and len(span) == 2 and 0 <= span[0] < span[1]
          <= len(raw_text), "HS_SPAN_INVALID")
    _need(re.fullmatch(r"[0-9a-f]{40}", source_blob_sha or "") is not None,
          "HS_BLOB_SHA_INVALID")
    snippet = raw_text[span[0]:span[1]]
    witness_id = "hw:" + _sid(source_id, version_id, locator, span, snippet)[:40]
    return {
        "contract": CONTRACT,
        "witness_id": witness_id,
        "source_id": source_id,
        "work_id": work_id,
        "source_version_id": version_id,
        "source_blob_sha": source_blob_sha,
        "locator": locator,
        "raw_source_span": [span[0], span[1]],
        "evidence_sha256": _sha(snippet.encode("utf-8")),
        "narration_identifier": narration_identifier,
        "edition": edition,
        "witness_status": "UNVERIFIED",
        "scholarly_verified": False,
        "text_included": False,
    }


def make_link(*, mention: dict, witness, match_status: str,
              match_method: str, supporting_evidence_ids=None,
              critical_commentary_refs=None) -> dict:
    _need(match_status in MATCH_STATUSES, "HS_MATCH_STATUS_INVALID")
    _need(witness is None or type(witness) is dict, "HS_WITNESS_INVALID")
    _need(not (match_status in ("TEXTUALLY_SUPPORTED", "CANDIDATE_MATCH")
               and witness is None), "HS_LINK_NEEDS_WITNESS")
    link_id = "hl:" + _sid(mention["mention_id"],
                           (witness or {}).get("witness_id", "none"),
                           match_status)[:40]
    return {
        "contract": CONTRACT,
        "link_id": link_id,
        "mention_id": mention["mention_id"],
        "witness_id": (witness or {}).get("witness_id"),
        "witness_source_id": (witness or {}).get("source_id"),
        "witness_locator": (witness or {}).get("locator"),
        "match_status": match_status,
        "match_method": match_method,
        "supporting_evidence_ids": supporting_evidence_ids or [],
        "critical_commentary_refs": critical_commentary_refs or [],
        "verification_status": "UNVERIFIED",
        "scholarly_verified": False,
        "rights_verified": False,
        "text_included": False,
    }
