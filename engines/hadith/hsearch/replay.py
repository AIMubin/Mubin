"""Local-only H-Search-01 alignment replay and metadata-only evidence receipt.

Example:
 python -m engines.hadith.hsearch.replay 2:185 \
    --database corpus-data/linked/quran_tafsir.db \
    --hadith-cache "D:\MubinSources\hadith-sources"

No source text, local paths or arbitrary exceptions are printed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
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
    # Explicit allowlist prevents accidental forwarding of private text
    # if the upstream link schema gains private fields in the future.
    public_link_keys = frozenset((
        "contract", "link_id", "mention_id", "witness_id",
        "witness_source_id", "witness_locator", "match_status",
        "match_method", "verification_status", "scholarly_verified",
        "folded_phrase_sha256", "folded_word_count",
        "tafsir_shared_raw_span", "hadith_shared_raw_span",
        "tafsir_shared_raw_sha256", "hadith_shared_raw_sha256",
        "tafsir_source_record_id", "hadith_source_blob_sha",
        "hadith_source_version_id", "shared_span_unit",
        "textually_grounded_lexical_overlap",
        "identity_of_narration_confirmed",
    ))
    aligned = [
        {k: v for k, v in link.items() if k in public_link_keys}
        for link in links
        if link.get("textually_grounded_lexical_overlap") is True
    ]
    receipt = {
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
    frozen_bytes = json.dumps(receipt, ensure_ascii=False,
                              sort_keys=True, separators=(",", ":")).encode("utf-8")
    receipt["evidence_payload_sha256"] = hashlib.sha256(frozen_bytes).hexdigest()
    return receipt


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Private-vault alignment replay, redacted metadata only")
    p.add_argument("reference", help="sura:ayah")
    p.add_argument("--database", type=Path, required=True)
    p.add_argument("--hadith-cache", type=Path, required=True)
    p.add_argument("--receipt-path", type=Path,
                   help="Optional local immutable JSON receipt; refuses overwrite")
    args = p.parse_args(argv)
    try:
        result = replay(args.reference, args.database, args.hadith_cache)
        if args.receipt_path is not None and result["status"] == "OK":
            dest = args.receipt_path
            if not dest.parent.is_dir() or dest.parent.is_symlink():
                raise ValueError("HS_RECEIPT_DIR_INVALID")
            output = (json.dumps(result, ensure_ascii=False, indent=2)
                      + "\n").encode("utf-8")
            fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(output)
                stream.flush()
                os.fsync(stream.fileno())
    except Exception:
        # Never expose private paths, text or exceptions through the CLI.
        result = {"status": "REFUSED", "code": "HS_PRIVATE_REPLAY_FAILED",
                  "text_included": False, "holdout_read": False}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
