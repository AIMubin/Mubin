"""Private H-Search-01 coverage diagnostics: find exactly where 10-token hits fall out.

The diagnostic searches the *full pinned original verse rows*, not just
T0.2 segmentation or H-Search narration windows. It then tests in order:
T0.2 passage coverage, narration-window coverage, and source block coverage.
It is NOT the runtime matcher and never promotes narration identity.

Source strings must remain local. Only raw ranges and hashes are emitted.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict, deque
import hashlib
import json
import os
from pathlib import Path
import re

from engines.hadith.hsearch.alignment import align_shared_tokens
from engines.hadith.hsearch.matching import _fold
from engines.hadith.hsearch.mention import detect_all
from engines.hadith.hsearch import sources as hs_sources
from engines.tafsir.t01 import lookup_verse
from engines.tafsir.t02_cli import (
    extract_local_verse, verified_raw_verse_rows,
)

NGRAM = 10
_MAX_SAMPLES = 40
_MAX_TARGET_COPIES_PER_GRAM = 12


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _tokens(text: str):
    """Streaming raw character offsets; never build a full-file map."""
    for m in re.finditer(r"\S+", text):
        normalized = _fold(m.group())
        # A removed-diacritic-only token is not a word.
        for word in normalized.split():
            yield word, m.start(), m.end()


def _index_verse_rows(rows: list[dict]) -> tuple[dict, int]:
    index = defaultdict(list)
    dropped = 0
    for row in rows:
        window = deque(maxlen=NGRAM)
        for item in _tokens(row["raw_text"]):
            window.append(item)
            if len(window) != NGRAM:
                continue
            gram = tuple(token for token, _, _ in window)
            if len(index[gram]) >= _MAX_TARGET_COPIES_PER_GRAM:
                dropped += 1
                continue
            index[gram].append((
                row["work_id"], row["source_record_id"],
                window[0][1], window[-1][2],
            ))
    return index, dropped


def _covers(spans, start: int, end: int):
    # Small verse-scoped groups, never arbitrary whole-corpus scanning.
    return next((record for record in spans
                 if record[0] <= start and end <= record[1]), None)


def _block_of(spans, starts, a: int, b: int):
    if not spans:
        return None
    index = bisect_right(starts, a) - 1
    if index < 0:
        return None
    s, e, locator = spans[index]
    return (s, e, locator) if s <= a and b <= e else None


def diagnose_coverage(*, rows: list[dict], passages: list[dict],
                      mentions: list[dict], sources: dict[str, str],
                      source_blocks: dict[str, list]) -> dict:
    """Diagnose *complete-file* 10-word hits from already pinned texts.

    rows: dicts with work_id, source_record_id, raw_text, full original SHA.
    sources: keyed by previously allowed + git-blob-verified source IDs.
    Caller must authenticate rows, full source bytes and holdout exclusions.
    """
    if type(rows) is not list or type(passages) is not list or type(mentions) is not list:
        raise ValueError("HS_DIAG_INPUT_INVALID")
    if type(sources) is not dict or type(source_blocks) is not dict:
        raise ValueError("HS_DIAG_SOURCES_INVALID")
    if not set(sources).issubset(hs_sources.AUTHORIZED):
        raise ValueError("HS_DIAG_UNAUTHORIZED_SOURCE")
    for row in rows:
        if _sha(row["raw_text"]) != row["source_sha256"]:
            raise ValueError("HS_DIAG_TAFSIR_RAW_SHA_INVALID")
    lookup, dropped = _index_verse_rows(rows)
    passage_index = defaultdict(list)
    mention_index = defaultdict(list)
    for passage in passages:
        passage_index[passage["source_record_id"]].append((
            *passage["evidence_span"], passage["interpretation_id"]))
    for mention in mentions:
        mention_index[mention["tafsir_source_record_id"]].append((
            *mention["raw_source_span"], mention["mention_id"]))
    block_index = {}
    for source_id, text in sources.items():
        spans = source_blocks.get(source_id)
        if type(spans) is not list:
            raise ValueError("HS_DIAG_BLOCKS_MISSING")
        previous_end = 0
        for start, end, locator in spans:
            if not 0 <= start < end <= len(text) or start < previous_end:
                raise ValueError("HS_DIAG_BLOCKS_INVALID")
            previous_end = end
        block_index[source_id] = (spans, [x[0] for x in spans])

    counts = defaultdict(int)
    sample_groups = defaultdict(list)
    matched = 0
    seen = set()
    for source_id in sorted(sources):
        raw_source = sources[source_id]
        tokens = deque(maxlen=NGRAM)
        blocks, block_starts = block_index[source_id]
        for item in _tokens(raw_source):
            tokens.append(item)
            if len(tokens) != NGRAM:
                continue
            gram = tuple(token for token, _, _ in tokens)
            targets = lookup.get(gram)
            if not targets:
                continue
            source_start, source_end = tokens[0][1], tokens[-1][2]
            source_fragment = raw_source[source_start:source_end]
            block = _block_of(blocks, block_starts, source_start, source_end)
            for work_id, source_record_id, verse_start, verse_end in targets:
                key = (source_id, source_start, source_end,
                       source_record_id, verse_start, verse_end)
                if key in seen:
                    continue
                seen.add(key)
                target = next(row["raw_text"] for row in rows
                              if row["source_record_id"] == source_record_id)
                verse_fragment = target[verse_start:verse_end]
                aligned = align_shared_tokens(verse_fragment, source_fragment,
                                              min_words=NGRAM)
                passage, mention = None, None
                if aligned is None:
                    stage = "NORMALIZER_OR_TOKENIZATION_MISMATCH"
                else:
                    passage = _covers(passage_index[source_record_id],
                                      verse_start, verse_end)
                    mention = _covers(mention_index[source_record_id],
                                      verse_start, verse_end)
                    if passage is None:
                        stage = "OUTSIDE_T02_PASSAGE"
                    elif mention is None:
                        stage = "OUTSIDE_NARRATION_WINDOW"
                    elif block is None:
                        stage = "CROSSES_OR_OUTSIDE_SOURCE_BLOCK"
                    else:
                        stage = "INSIDE_ALL_PIPELINE_WINDOWS"
                counts[stage] += 1
                matched += 1
                if len(sample_groups[stage]) < 8:
                    sample_groups[stage].append({
                        "classification": stage,
                        "tafsir_work_id": work_id,
                        "tafsir_source_record_id": source_record_id,
                        "tafsir_raw_span": [verse_start, verse_end],
                        "tafsir_raw_sha256": _sha(verse_fragment),
                        "tafsir_original_source_sha256": next(
                            row["source_sha256"] for row in rows
                            if row["source_record_id"] == source_record_id),
                        "tafsir_passage_id": passage[2] if passage else None,
                        "mention_id": mention[2] if mention else None,
                        "hadith_source_id": source_id,
                        "hadith_raw_span": [source_start, source_end],
                        "hadith_raw_sha256": _sha(source_fragment),
                        "hadith_witness_locator": block[2] if block else None,
                        "hadith_witness_raw_span": (
                            [block[0], block[1]] if block else None),
                        "folded_phrase_sha256": _sha(" ".join(gram)),
                        "folded_word_count": NGRAM,
                        "is_narration_identity_proven": False,
                    })
    report = {
        "contract": "mubin-hsearch01-coverage-diagnostic-v1",
        "status": "OK",
        "normalization": "HSEARCH_FOLD_V1_WHOLE_WHITESPACE_TOKENS",
        "matched_full_source_10gram_occurrences": matched,
        "stage_counts": dict(sorted(counts.items())),
        "tafsir_index_grams": len(lookup),
        "truncated_tafsir_gram_occurrences": dropped,
        "stage_coverage_exhaustive": dropped == 0,
        "sample_limit_per_stage": 8,
        "samples": [entry for stage in sorted(sample_groups)
                    for entry in sample_groups[stage]],
        "text_included": False,
        "holdout_read": False,
        "scholarly_verified": False,
        "narration_identity_proven": False,
        "scientific_gate_passed": False,
    }
    report["evidence_payload_sha256"] = _sha(json.dumps(
        report, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")))
    return report


def diagnose_local(reference: str, database: Path, cache_dir: Path) -> dict:
    """Pinned private vault only; do not forward raw texts to web or CI."""
    lookup = lookup_verse(database, reference, include_private_text=True)
    passages = extract_local_verse(database, lookup)
    raw = verified_raw_verse_rows(database, lookup)
    eligible = [meta for meta in lookup["tafsirs"] if meta["text"] is not None]
    rows = [
        {
            "work_id": meta["work_id"],
            "source_record_id": meta["evidence_id"],
            "source_sha256": meta["imported_record_sha256"],
            "raw_text": raw[meta["dataset_source_key"]],
        }
        for meta in eligible
    ]
    acquired = hs_sources.acquire(cache_dir, allow_network=False)
    unavailable = sorted(sid for sid, info in acquired.items()
                         if not info["verified"])
    if unavailable:
        return {
            "status": "SOURCE_UNAVAILABLE", "sources_unavailable": unavailable,
            "text_included": False, "holdout_read": False,
        }
    metadata = hs_sources.authorized_sources()
    texts, blocks = {}, {}
    for sid in sorted(acquired):
        text = hs_sources.load_text(metadata[sid], Path(acquired[sid]["path"]))
        texts[sid] = text
        blocks[sid] = hs_sources.witness_candidate_spans(text)
    report = diagnose_coverage(
        rows=rows, passages=passages, mentions=detect_all(passages),
        sources=texts, source_blocks=blocks)
    report["quran_reference"] = reference
    report["passages_processed"] = len(passages)
    report["sources_checked"] = sorted(texts)
    report["tafsir_source_rows_checked"] = len(rows)
    # Receipt hash must describe the final, complete report.
    report.pop("evidence_payload_sha256")
    report["evidence_payload_sha256"] = _sha(json.dumps(
        report, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")))
    return report


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=(
        "Private original-source 10gram gap diagnostic; metadata only"))
    parser.add_argument("reference")
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--hadith-cache", required=True, type=Path)
    parser.add_argument("--receipt-path", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = diagnose_local(args.reference, args.database, args.hadith_cache)
        if report["status"] != "OK":
            print(json.dumps(report, ensure_ascii=False))
            return 2
        target = args.receipt_path
        if not target.parent.is_dir() or target.parent.is_symlink():
            raise ValueError("HS_DIAG_DEST_INVALID")
        output = (json.dumps(report, ensure_ascii=False, indent=2)
                  + "\n").encode("utf-8")
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as sink:
            sink.write(output)
            sink.flush()
            os.fsync(sink.fileno())
        # Display aggregate counts only; individual source spans stay local.
        print(json.dumps({
            "status": "OK",
            "quran_reference": args.reference,
            "stage_counts": report["stage_counts"],
            "full_source_hits": report["matched_full_source_10gram_occurrences"],
            "evidence_payload_sha256": report["evidence_payload_sha256"],
            "text_included": False,
        }, ensure_ascii=False))
        return 0
    except Exception:
        # Fail closed without publishing local paths, protected text, SQL or
        # Git source content. Never overwrite an existing evidence file.
        print(json.dumps({
            "status": "REFUSED", "code": "HS_DIAG_LOCAL_FAILED",
            "text_included": False,
        }))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
