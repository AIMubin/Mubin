"""H-Search-01 pipeline: tafsir passages -> mentions -> witness candidates
-> careful links -> reported commentary. Metadata-only outputs.
"""
from __future__ import annotations

from pathlib import Path

from engines.hadith.hsearch.mention import detect_all
from engines.hadith.hsearch.matching import match_mentions
from engines.hadith.hsearch import sources as hs_sources
from engines.hadith.hsearch.commentary import find_commentary
from engines.hadith.hsearch.contracts import CONTRACT, VERSION, _need


def _sha_hex(s: str) -> str:
    import hashlib
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def run_hsearch(passages: list[dict], cache_dir: Path, *,
                allow_network: bool = False) -> dict:
    """Run the full hadith-evidence pipeline for tafsir passages.

    Returns counts, redacted mentions, links, and commentary presence only.
    SOURCE_UNAVAILABLE is returned when the pinned sources are not cached
    locally (distinct from NO_MATCH).
    """
    _need(type(passages) is list, "HS_PASSAGES_INVALID")
    mentions = detect_all(passages)
    try:
        acquired = hs_sources.acquire(cache_dir, allow_network=allow_network)
    except Exception as exc:
        code = str(exc.args[0]) if exc.args else "HS_ACQUIRE_FAILED"
        return {"contract": CONTRACT, "version": VERSION, "status": "REFUSED",
                "code": code, "mentions_total": len(mentions),
                "text_included": False, "scholarly_verified": False,
                "rights_verified": False}
    unavailable = [sid for sid, info in acquired.items()
                   if info.get("SOURCE_UNAVAILABLE")]
    witnesses = []
    witness_texts = {}
    commentary_records = []
    if not unavailable:
        for sid, info in acquired.items():
            src = hs_sources.authorized_sources()[sid]
            text = hs_sources.load_text(src, Path(info["path"]))
            for s0, s1, locator in hs_sources.witness_candidate_spans(text):
                w = {
                    "witness_id": "hw:" + hs_sources.cache_filename(sid),
                    "source_id": sid, "work_id": src["work_id"],
                    "source_version_id": src["version_id"],
                    "source_blob_sha": src["source_blob_sha"],
                    "locator": locator,
                    "raw_source_span": [s0, s1],
                    "evidence_sha256": None,  # set by matcher on upgrade
                    "witness_status": "UNVERIFIED",
                    "_text": text,
                }
                # per-block digest pin
                snippet = text[s0:s1]
                import hashlib
                w["evidence_sha256"] = hashlib.sha256(
                    snippet.encode("utf-8")).hexdigest()
                witnesses.append(w)
                witness_texts[w["witness_id"]] = text
    # matcher needs mention text; pass via parallel structure
    mention_texts = {id(m): p for m, p in zip(mentions, [None] * len(mentions))}
    # bind actual passage texts for matching (in-process only)
    for m in mentions:
        for p in passages:
            span = m["raw_source_span"]
            t = p.get("interpretation_statement") or ""
            if span[1] <= len(t) and t[span[0]:span[1]] and \
               _sha_hex(t[span[0]:span[1]]) == m["evidence_sha256"]:
                pass  # handled below via helper defined at module bottom
                m["_mention_text"] = t
                break
    for w in witnesses:
        w["_text"] = witness_texts.get(w["witness_id"], "")
    links = match_mentions(mentions, witnesses,
                           source_texts=witness_texts)
    # commentary scan: only for linked witnesses with a locator
    for l in links:
        if l["witness_id"] and l["witness_locator"]:
            wid = l["witness_id"]
            text = witness_texts.get(wid)
            if text:
                span = None
                for w in witnesses:
                    if w["witness_id"] == wid:
                        span = w["raw_source_span"]
                        break
                if span:
                    block = text[span[0]:span[1]]
                    commentary_records.append(find_commentary(
                        block, l["witness_locator"],
                        source_id=l["witness_source_id"],
                        work_id="", version_id="", blob_sha=""))
    redacted_mentions = [{k: v for k, v in m.items() if not k.startswith("_")}
                         for m in mentions]
    redacted_witnesses = [{k: v for k, v in w.items()
                           if not k.startswith("_")} for w in witnesses]
    by_status = {}
    for l in links:
        by_status[l["match_status"]] = by_status.get(l["match_status"], 0) + 1
    judgment_presence = {}
    for c in commentary_records:
        judgment_presence[c["presence"]] = \
            judgment_presence.get(c["presence"], 0) + 1
    return {
        "contract": CONTRACT, "version": VERSION, "status": "OK",
        "passages_processed": len(passages),
        "mentions_total": len(mentions),
        "mentions": redacted_mentions,
        "witnesses_total": len(redacted_witnesses),
        "witnesses_sample": redacted_witnesses[:5],
        "links_total": len(links),
        "links_by_status": by_status,
        "links": links,
        "commentary": {
            "records_total": len(commentary_records),
            "presence": judgment_presence,
            "note": "reported judgments only; scope limited to exact "
                    "source text; mubin issues no hadith judgments"},
        "sources_used": sorted(a for a in acquired
                               if not acquired[a].get("SOURCE_UNAVAILABLE")),
        "sources_unavailable": unavailable,
        "holdout_read": False,
        "text_included": False,
        "scholarly_verified": False,
        "rights_verified": False,
        "publication_allowed": False,
        "juristic_inference_allowed": False,
        "public_fatwa_authorized": False,
        "p1_admitted": False,
    }


