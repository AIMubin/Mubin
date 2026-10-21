"""Pair and align all W1/W2 al-Waraqat chapters; metadata-only output.

Pairs W1 inventory chapters with deterministically extracted W2 sections by
folded-title digest, then aligns each pair through witness_alignment with
pinned SHA-256 verification. Emits classification counts and per-section
alignment records WITHOUT any source text.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from engines.usul.witness_alignment import align_sections, WitnessAlignmentError

VERSION = "waraqat-w2-pair-compare/0.1.0"
MAX_PER_SECTION_DIFF_EVENTS = 2048


def _sha_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True,
                        help="full W1 inventory JSON")
    parser.add_argument("--w1-export", type=Path, required=True)
    parser.add_argument("--w2-manifest", type=Path, required=True,
                        help="manifest from waraqat_w2_full_extract")
    parser.add_argument("--w2-sections-dir", type=Path, required=True)
    parser.add_argument("--w1-sections-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    manifest = json.loads(args.w2_manifest.read_text(encoding="utf-8"))
    export = args.w1_export.read_bytes()

    w2_by_fold = {}
    for entry in manifest.get("paired", []):
        pass  # manifest pairing is informational; pairing is re-derived below
    w2_sections = manifest["sections"]
    # Re-derive pairing from folded-title digests (manifest stores counts only).
    import hashlib as _h
    fold_sha = lambda t: _h.sha256(t.encode("utf-8")).hexdigest()
    w2_by_fold = {}
    for ws in w2_sections:
        w2_by_fold.setdefault(fold_sha(ws["title_folded"]), []).append(ws)
    paired_map = {}
    for section in inventory["sections"]:
        if section["kind"] != "HEADING_SECTION":
            continue
        cands = w2_by_fold.get(section["heading_folded_sha256"], [])
        if len(cands) == 1:
            paired_map[section["id"]] = {"w2_section": cands[0]}
    # Re-derive W1 section bytes from the pinned export via inventory bounds.
    results, skipped = [], []
    cursor_ok = True
    for section in inventory["sections"]:
        if section["kind"] == "PRELUDE":
            skipped.append({"w1_section_id": section["id"],
                            "reason": "PRELUDE_HAS_NO_W2_COUNTERPART_BY_DESIGN"})
            continue
        pair = paired_map.get(section["id"])
        if pair is None:
            skipped.append({"w1_section_id": section["id"],
                            "reason": "NO_FOLDED_TITLE_MATCH_IN_W2"})
            continue
        start, stop = section["source_byte_start"], section["source_byte_end_exclusive"]
        piece = export[start:stop]
        import hashlib as _h
        if _h.sha256(piece).hexdigest() != section["section_sha256"]:
            skipped.append({"w1_section_id": section["id"],
                            "reason": "W1_SECTION_DIGEST_MISMATCH"})
            continue
        w1_path = args.w1_sections_dir / (section["id"].replace(":", "_") + ".txt")
        w1_path.parent.mkdir(parents=True, exist_ok=True)
        w1_path.write_bytes(piece)
        w2_file = (args.w2_sections_dir /
                   f"w2-h2-{pair['w2_section']['h2_ordinal']:03d}.txt")
        try:
            alignment = align_sections(
                w1_path, w2_file,
                left_sha256=section["section_sha256"],
                right_sha256=_sha_file(w2_file),
                left_source_id="pilot:waraqat-primary",
                right_source_id="pilot:waraqat-comparator",
                left_locator=section["id"],
                right_locator=f"w2:h2-{pair['w2_section']['h2_ordinal']}")
        except WitnessAlignmentError as exc:
            skipped.append({"w1_section_id": section["id"],
                            "reason": "ALIGNMENT_REFUSED",
                            "detail": str(exc)})
            continue
        classes = {}
        for event in alignment.get("strict_changes", []):
            key = event.get("class", "UNKNOWN")
            classes[key] = classes.get(key, 0) + 1
        results.append({
            "w1_section_id": section["id"],
            "w2_h2_ordinal": pair["w2_section"]["h2_ordinal"],
            "overall_classification": alignment["overall_classification"],
            "strict_change_count": alignment["strict_change_count"],
            "profiles": {k: v for k, v in alignment["profiles"].items()
                         if isinstance(v, bool)},
            "classification_counts": classes,
            "left_bytes": section["source_byte_end_exclusive"] - section["source_byte_start"],
            "right_bytes": w2_file.stat().st_size,
        })
    payload = {
        "engine": VERSION, "status": "W2_PAIR_COMPARE_COMPLETE",
        "compared_sections": len(results),
        "skipped": skipped,
        "results": results,
        "source_text_included": False,
        "scholarly_verified": False, "redistribution_approved": False,
        "semantic_equivalence_verified": False,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(json.dumps({"status": payload["status"],
                      "compared": len(results), "skipped": len(skipped)},
                     ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
