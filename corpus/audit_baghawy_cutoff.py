"""Read-only, non-authoritative alignment of a suspect tafsir cutoff to an edition witness.

The witness text is supplied locally by an authorized reviewer. This never
downloads, rewrites or publishes original tafsir or edited-edition passages.
Matching is a diagnostic aid only, not authentication of a printed edition.
"""
import argparse
import hashlib
import json
import sqlite3
import unicodedata
from pathlib import Path

FLAGGED_BAGHAWY = {(4, 43), (17, 4), (18, 10), (33, 9)}
ALLOWED_WITNESS_TYPES = {"independent_online_transcription", "printed_edition_transcription"}


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def diagnostic_letters(value):
    """Diagnostic equality only; do not transform stored tafsir or Quran text."""
    return "".join(
        char for char in unicodedata.normalize("NFC", value)
        if unicodedata.category(char)[0] in ("L", "N")
    )


def _count_and_position(haystack, needle):
    first = haystack.find(needle)
    if first == -1:
        return 0, -1
    second = haystack.find(needle, first + 1)
    return (1, first) if second == -1 else (2, first)


def inspect_cutoff(database, sura, aya, witness_text, witness_metadata,
                   min_anchor=48, min_continuation=24):
    if (sura, aya) not in FLAGGED_BAGHAWY:
        raise ValueError("Only the four known Baghawi cutoff candidates are in scope")
    if witness_metadata.get("source_type") not in ALLOWED_WITNESS_TYPES:
        raise ValueError("Witness source_type must be identified")
    if not witness_metadata.get("source_url") or not witness_metadata.get("work"):
        raise ValueError("Witness source URL and work title are required")
    if witness_metadata["source_type"] == "printed_edition_transcription":
        for key in ("edition", "publisher", "volume", "page"):
            if not witness_metadata.get(key):
                raise ValueError(f"Printed edition witness requires {key}")
    if min_anchor < 32 or min_continuation < 16:
        raise ValueError("Insufficient minimum diagnostic context")
    conn = sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        row = conn.execute(
            "SELECT text FROM tafsirs WHERE source=? AND sura=? AND aya=?",
            ("baghawy", sura, aya)).fetchone()
    finally:
        conn.close()
    if row is None or not isinstance(row[0], str) or len(row[0]) != 32767:
        raise ValueError("Expected original 32,767-character Baghawi record")
    original = row[0]
    normalized_source = diagnostic_letters(original)
    normalized_witness = diagnostic_letters(witness_text)
    best = None
    max_anchor = min(320, len(normalized_source))
    for n in range(max_anchor, min_anchor - 1, -1):
        needle = normalized_source[-n:]
        count, offset = _count_and_position(normalized_witness, needle)
        if count == 0:
            continue
        remaining = len(normalized_witness) - (offset + n)
        best = {
            "anchor_characters": n, "match_unique": count == 1,
            "minimum_continuation_met": remaining >= min_continuation,
            "continuation_characters_in_witness": remaining,
            "normalized_anchor_sha256": hashlib.sha256(needle.encode("utf-8")).hexdigest(),
        }
        break
    result_status = "NOT_ALIGNED"
    if best:
        if best["match_unique"] and best["minimum_continuation_met"]:
            result_status = "UNIQUE_CUTOFF_TAIL_WITH_LATER_TEXT_IN_WITNESS"
        else:
            result_status = "AMBIGUOUS_OR_INSUFFICIENT_CONTINUATION"
    return {
        "verse_id": f"{sura}:{aya}", "source": "baghawy",
        "source_text_sha256": hashlib.sha256(original.encode("utf-8")).hexdigest(),
        "source_character_count": len(original),
        "linked_database_sha256": file_hash(database),
        "witness_text_sha256": hashlib.sha256(witness_text.encode("utf-8")).hexdigest(),
        "witness_metadata": witness_metadata,
        "diagnostic_match": best,
        "status": result_status,
        "source_edition_identity_verified": False,
        "printed_page_verified_by_tool": False,
        "scholarly_verified": False,
        "approved_for_text_replacement": False,
        "note": "Character filtering discards diacritics and punctuation for diagnostics only. A continuation is not proof of edition identity, absence of variants, page numbering or publication rights.",
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--database", type=Path, required=True)
    p.add_argument("--sura", type=int, required=True)
    p.add_argument("--aya", type=int, required=True)
    p.add_argument("--witness-text-file", type=Path, required=True)
    p.add_argument("--witness-metadata", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    a = p.parse_args()
    witness = a.witness_text_file.read_text(encoding="utf-8")
    metadata = json.loads(a.witness_metadata.read_text(encoding="utf-8"))
    result = inspect_cutoff(a.database, a.sura, a.aya, witness, metadata)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "witness_metadata"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
