"""Detect possible cross-verse tafsir paragraph links in pinned linked SQLite.

This checks a narrowly scoped set of known Tabari markup-only entries. A
neighboring title containing the target ayah number is evidence of a shared
heading, NOT proof of exact paragraph bounds in a printed edition.
Original SQLite content is never modified.
"""
import argparse
import hashlib
import json
import re
import sqlite3
from pathlib import Path

FLAGGED_TABARY = (
    (4, 168), (26, 16), (26, 205), (37, 25),
    (37, 62), (37, 103), (50, 13),
)


def heading_numbers(text):
    """Numbers within the first source <br>-delimited title (not its body)."""
    parts = text.split("<br>", 2)
    if len(parts) < 3:
        return []
    return [int(n) for n in re.findall(r"\(([0-9]{1,3})\)", parts[1])]


def audit(path):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        entries = []
        for sura, aya in FLAGGED_TABARY:
            row = conn.execute(
                "SELECT text FROM tafsirs WHERE source='tabary' AND sura=? AND aya=?",
                (sura, aya)).fetchone()
            if row is None or row[0] != "<br>":
                raise ValueError(f"Expected original markup-only record: {sura}:{aya}")
            candidates = []
            for adjacent in (aya - 1, aya + 1):
                if adjacent < 1:
                    continue
                neighbor = conn.execute(
                    "SELECT text FROM tafsirs WHERE source='tabary' AND sura=? AND aya=?",
                    (sura, adjacent)).fetchone()
                if neighbor is None:
                    continue
                nums = heading_numbers(neighbor[0])
                if aya in nums:
                    candidates.append({
                        "neighbor_verse_id": f"{sura}:{adjacent}",
                        "heading_verse_numbers": nums,
                        "neighbor_text_sha256": hashlib.sha256(
                            neighbor[0].encode("utf-8")).hexdigest(),
                    })
            entries.append({
                "verse_id": f"{sura}:{aya}",
                "source_entry": "MARKUP_ONLY",
                "adjacent_shared_heading_candidates": candidates,
                "candidate_status": "ONE_ADJACENT_HEADING_MATCH" if len(candidates) == 1
                else "AMBIGUOUS_OR_NOT_FOUND",
                "printed_edition_verified": False,
            })
        return {
            "status": "DIAGNOSTIC_ONLY",
            "rows_examined": len(entries),
            "rows_with_unique_adjacent_heading": sum(
                e["candidate_status"] == "ONE_ADJACENT_HEADING_MATCH" for e in entries),
            "source_text_mutated": False,
            "records": entries,
            "note": "Shared headings support cross-verse linkage candidates; printed-edition passage boundaries require independent verification.",
        }
    finally:
        conn.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--database", type=Path, default=Path("corpus-data/linked/quran_tafsir.db"))
    p.add_argument("--report", type=Path, default=Path("corpus-data/linked/tabary-crossverse-candidates.json"))
    args = p.parse_args()
    result = audit(args.database)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
