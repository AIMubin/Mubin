"""T0.3.1: unified Quran-Tafsir research query contract.

Single query over the existing pinned pipeline (T0.1 lookup -> T0.2
byte-verified raw passages -> T0.2.3 candidates and relations).
Metadata-only always: statement text is never returned, even if a caller
requests the unsupported private-text mode. No new retrieval engine, no
second database, no scholarly claims, no consensus or preference inference.
"""
from __future__ import annotations

import json
from pathlib import Path

from engines.tafsir.t01 import lookup_verse
from engines.tafsir.t02_cli import extract_local_verse
from engines.tafsir.t023 import (
    build_relationships, identify_candidates, summarize_analysis,
)

CONTRACT = "mubin-tafsir-t03-unified-research-v1"
VERSION = "tafsir-t03/0.1.0"
_LEVELS = ("RETRIEVED_SOURCE_MATERIAL", "GROUNDED_PASSAGE",
           "AUTOMATED_CANDIDATE", "TEXTUALLY_ATTRIBUTED",
           "SCHOLARLY_VERIFIED")


def unified_research_query(db_path: Path, reference: str, *,
                           include_private_text: bool = False) -> dict:
    """One auditable research result for a verse reference.

    Metadata-only always; include_private_text=True is refused, not silently
    accepted. Reuses T0.1/T0.2/T0.2.3 without duplicate retrieval.
    """
    # T0.3 is strictly metadata-only, even on localhost. Private text is
    # exclusively available via the explicit T0.2/T0.2.3 operator CLIs.
    if include_private_text is not False:
        raise ValueError("T03_PRIVATE_TEXT_NOT_SUPPORTED")
    # Text is fetched in-process for the editorial-hold check and raw-byte
    # verification only; the returned payload is redacted regardless.
    lookup = lookup_verse(db_path, reference, include_private_text=True)
    passages = extract_local_verse(db_path, lookup)
    candidates = []
    for p in passages:
        candidates.extend(identify_candidates(p))
    relations = build_relationships(candidates)
    counts = summarize_analysis(passages, candidates, relations)

    per_work = []
    for t in lookup.get("tafsirs", []):
        work_id = t.get("work_id", "")
        work_candidates = [c for c in candidates if c["work_id"] == work_id]
        work_passages = [p for p in passages if p["work_id"] == work_id]
        per_work.append({
            "work_id": work_id,
            "work_title_ar": t.get("work_title_ar"),
            "author_ar": t.get("author_ar"),
            "display_status": t.get("display_status"),
            "edition_authenticated": t.get("edition_authenticated", False),
            "evidence_id": t.get("evidence_id"),
            "imported_record_sha256": t.get("imported_record_sha256"),
            "quality_flags": t.get("quality_flags", []),
            "passage_count": sum(1 for p in passages
                                 if p["work_id"] == work_id),
            "candidate_count": len(work_candidates),
            "passages_redacted": [
                {
                    "passage_id": p["interpretation_id"],
                    "source_record_id": p["source_record_id"],
                    "work_id": p["work_id"],
                    "raw_source_span": list(p["evidence_span"]),
                    "evidence_sha256": p["evidence_sha256"],
                    "verification_status": p["verification_status"],
                    "text_included": False,
                } for p in work_passages],
            "rights_verified": False,
            "source_authenticated": False,
            "scholarly_verified": False,
            "attribution_cues_named": sum(
                1 for c in work_candidates
                if c["attribution_type"] == "NAMED_REPORT"),
            "author_preference_cues": sum(
                1 for c in work_candidates
                if c["attribution_type"] == "AUTHOR_OWN_EXPLICIT"),
            "unidentified_speaker_candidates": sum(
                1 for c in work_candidates
                if c["speaker_identity_status"] == "UNKNOWN"),
            "candidates_redacted": [
                _redacted_candidate(c) for c in work_candidates],
        })
    return {
        "contract": CONTRACT,
        "version": VERSION,
        "status": "OK",
        "quran_reference": reference,
        "quran_text": {
            "included": False,
            "state": "DERIVED_DISPLAY_ONLY_NOT_AUTHENTICATED_MUSHAF",
            "note": "no Quranic text is served by this contract",
        },
        "tafsir_count": lookup.get("tafsir_count", len(per_work)),
        "tafsirs": per_work,
        "counts": counts,
        "relations": [_redacted_relation(r) for r in relations],
        "levels_of_evidence": list(_LEVELS),
        "count_semantics": counts.get(
            "count_semantics", "UNVERIFIED_LEXICAL_CANDIDATES"),
        "text_included": False,
        "scholarly_verified": False,
        "source_authenticated": False,
        "rights_verified": False,
        "interpretive_differences_assessed": False,
        "consensus_claimed": False,
        "publication_allowed": False,
        "juristic_inference_allowed": False,
        "public_fatwa_authorized": False,
        "p1_admitted": False,
    }


def _redacted_candidate(c: dict) -> dict:
    """Strip statement text; keep ids, spans, digests, and statuses."""
    return {
        "candidate_id": c["candidate_id"],
        "passage_id": c["passage_id"],
        "source_record_id": c["source_record_id"],
        "work_id": c["work_id"],
        "quran_reference": c["quran_reference"],
        "passage_span": c["passage_span"],
        "statement_start": c["statement_start"],
        "statement_end": c["statement_end"],
        "raw_source_span": list(c["raw_source_span"]),
        "attribution_evidence_span": c.get("attribution_evidence_span"),
        "evidence_sha256": c["evidence_sha256"],
        "source_sha256": c["source_sha256"],
        "interpretation_type": c["interpretation_type"],
        "speaker_name": c["speaker_name"],
        "speaker_identity_status": c["speaker_identity_status"],
        "attribution_type": c["attribution_type"],
        "author_endorsement": c["author_endorsement"],
        "attribution_confidence": c["attribution_confidence"],
        "verification_status": c["verification_status"],
        "rights_status": c["rights_status"],
        "scholarly_verified": False,
        "text_included": False,
    }


def _redacted_relation(r: dict) -> dict:
    return {
        "relation_id": r["relation_id"],
        "from_candidate_id": r["from_candidate_id"],
        "to_candidate_id": r["to_candidate_id"],
        "passage_id": r["passage_id"],
        "relation_type": r["relation_type"],
        "evidence_span": r.get("evidence_span"),
        "verification_status": r["verification_status"],
        "scholarly_verified": False,
        "consensus_claimed": False,
        "preference_by_system": False,
    }
