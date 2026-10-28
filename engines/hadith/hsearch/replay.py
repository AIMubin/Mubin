"""Local-only H-Search-01 alignment replay and metadata-only evidence receipt.

Example:
 python -m engines.hadith.hsearch.replay 2:185 \
    --database corpus-data/linked/quran_tafsir.db \
    --hadith-cache "D:\MubinSources\hadith-sources"

No source text, local paths or arbitrary exceptions are printed.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from engines.tafsir.t01 import lookup_verse
from engines.tafsir.t02_cli import extract_local_verse
from engines.hadith.hsearch.pipeline import run_hsearch


def replay(reference: str, db_path: Path, cache_dir: Path) -> dict:
    # T0.1 and T0.2 enforce existing original-database and raw-source
    # integrity contracts before any Hadith evidence is produced.
    lookup = lookup_verse(db_path, reference, include_private_text=True)
    passages = extract_local_verse(db_path, lookup)
    report = run_hsearch(passages, cache_dir, allow_network=False)
    if report["status"] != "OK":
        return {
            "status": "REFUSED", "code": report.get("code", "HS_REPLAY_FAILED"),
            "text_included": False, "holdout_read": False,
        }
    links = report["links"]
    aligned = [link for link in links
               if link.get("textually_grounded_lexical_overlap") is True]
    return {
        "contract": "mubin-hsearch01-raw-alignment-replay-v1",
        "status": "OK", "reference": reference,
        "passages_processed": report["passages_processed"],
        "mention_cue_windows": report["mentions_total"],
        "pinned_source_blocks": report["witnesses_total"],
        "links_total": report["links_total"],
        "links_by_status": report["links_by_status"],
        "source_unavailable": report["sources_unavailable"],
        "aligned_candidate_links": aligned,
        "aligned_candidate_count": len(aligned),
        "lexical_overlap_verified": bool(aligned),
        "narration_identity_established": False,
        "hadith_grade_inferred": False,
        "scientific_gate_passed": False,
        "text_included": False,
        "holdout_read": False,
        "scholarly_verified": False,
        "rights_verified": False,
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Private-vault alignment replay, redacted metadata only")
    p.add_argument("reference", help="sura:ayah")
    p.add_argument("--database", type=Path, required=True)
    p.add_argument("--hadith-cache", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        result = replay(args.reference, args.database, args.hadith_cache)
    except Exception:
        # Never expose private paths, text or exceptions through the CLI.
        result = {"status": "REFUSED", "code": "HS_PRIVATE_REPLAY_FAILED",
                  "text_included": False, "holdout_read": False}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
