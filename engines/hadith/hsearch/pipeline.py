"""H-Search-01: source-attested Tafsir mentions -> Hadith witnesses.

No use of H3.9.2 holdout or gold records, no canonical hadith identity
inference, no autonomous hadith grading, no raw text in report/HTTP.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from engines.hadith.hsearch.mention import detect_all
from engines.hadith.hsearch.matching import match_mentions
from engines.hadith.hsearch import sources as hs_sources
from engines.hadith.hsearch.commentary import find_commentary
from engines.hadith.hsearch.contracts import (
    CONTRACT, VERSION, _need, make_link, make_witness,
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _base(passages, mentions) -> dict:
    return {
        "contract": CONTRACT, "version": VERSION,
        "passages_processed": len(passages),
        "mentions_total": len(mentions),
        "holdout_read": False, "text_included": False,
        "scholarly_verified": False, "rights_verified": False,
        "publication_allowed": False, "juristic_inference_allowed": False,
        "public_fatwa_authorized": False, "p1_admitted": False,
    }


def run_hsearch(passages: list[dict], cache_dir: Path, *,
                allow_network: bool = False) -> dict:
    """Local research-only. A partial source cache never means NO_MATCH."""
    _need(type(passages) is list, "HS_PASSAGES_INVALID")
    # Mention detector validates each T0.2 source-bound passage.
    mentions = detect_all(passages)
    base = _base(passages, mentions)
    # Obtain the exact mentioned substring only from its validated T0.2
    # parent, never from unrelated or whole-passage text.
    by_passage = {p["interpretation_id"]: p for p in passages}
    _need(len(by_passage) == len(passages), "HS_DUPLICATE_PASSAGE")
    for m in mentions:
        p = by_passage.get(m["passage_id"])
        _need(p is not None, "HS_PARENT_PASSAGE_MISSING")
        a, b = m["passage_relative_span"]
        snippet = p["interpretation_statement"][a:b]
        _need(m["raw_source_span"] ==
              [p["evidence_span"][0] + a, p["evidence_span"][0] + b]
              and _sha(snippet) == m["evidence_sha256"],
              "HS_MENTION_RAW_SPAN_MISMATCH")
        m["_mention_text"] = snippet
    try:
        acquired = hs_sources.acquire(cache_dir, allow_network=allow_network)
    except Exception:
        return {
            **base, "status": "REFUSED", "code": "HS_ACQUIRE_OR_PIN_FAILED",
        }
    available = sorted(sid for sid, info in acquired.items()
                       if info.get("verified"))
    unavailable = sorted(sid for sid, info in acquired.items()
                         if not info.get("verified"))
    redacted_mentions = [
        {k: v for k, v in m.items() if not k.startswith("_")}
        for m in mentions
    ]
    if unavailable:
        # Scope is incomplete. A missing book is NOT evidence of no match
        # among all four mandated books. Do not mix partial NO_MATCH results.
        links = [make_link(
            mention=m, witness=None, match_status="SOURCE_UNAVAILABLE",
            match_method="incomplete_pinned_local_source_set")
            for m in mentions]
        return {
            **base, "status": "OK", "mentions": redacted_mentions,
            "witnesses_total": 0, "witnesses_sample": [],
            "links_total": len(links),
            "links_by_status": {"SOURCE_UNAVAILABLE": len(links)},
            "links": links, "sources_used": available,
            "sources_unavailable": unavailable,
            "commentary": {"records_total": 0, "presence": {},
                           "note": "No source-complete search performed"},
        }
    witnesses = []
    source_texts = {}
    source_meta = hs_sources.authorized_sources()
    for sid in available:
        src = source_meta[sid]
        text = hs_sources.load_text(src, Path(acquired[sid]["path"]))
        source_texts[sid] = text
        for a, b, locator in hs_sources.witness_candidate_spans(text):
            witnesses.append(make_witness(
                source_id=sid, work_id=src["work_id"],
                version_id=src["version_id"],
                source_blob_sha=src["source_blob_sha"],
                locator=locator, raw_text=text,
                span=(a, b),
            ))
    links = match_mentions(mentions, witnesses, source_texts=source_texts)
    witness_map = {w["witness_id"]: w for w in witnesses}
    _need(len(witness_map) == len(witnesses), "HS_DUPLICATE_WITNESS")
    commentary_records = []
    for link in links:
        wid = link.get("witness_id")
        if wid is None:
            continue
        w = witness_map[wid]
        raw = source_texts[w["source_id"]]
        a, b = w["raw_source_span"]
        block = raw[a:b]
        # Critical-word discovery is not a confirmed scholar's judgment.
        commentary_records.append(find_commentary(
            block, w["locator"], source_id=w["source_id"],
            work_id=w["work_id"], version_id=w["source_version_id"],
            blob_sha=w["source_blob_sha"],
        ))
    statuses = {}
    for link in links:
        st = link["match_status"]
        statuses[st] = statuses.get(st, 0) + 1
    presence = {}
    for item in commentary_records:
        p = item["presence"]
        presence[p] = presence.get(p, 0) + 1
    return {
        **base, "status": "OK",
        "mentions": redacted_mentions,
        "witnesses_total": len(witnesses),
        "witnesses_sample": witnesses[:5],
        "links_total": len(links),
        "links_by_status": statuses,
        "links": links,
        "sources_used": available,
        "sources_unavailable": [],
        "commentary": {
            "records_total": len(commentary_records),
            "presence": presence,
            "note": ("Lexical critique cues are UNVERIFIED source annotations; "
                     "no automatically attributable scholar judgment or grade"),
        },
    }
