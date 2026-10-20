"""Read-only Quran and tafsir lookup with explicit provenance and quality flags."""
import argparse
import json
import sqlite3
from pathlib import Path

from corpus.audit_tafsir_quality import plaintext
from corpus.quran_witness_analysis import read_witness, segment_first_verse, file_sha256
from corpus.triage_quran import REFERENCE_SHA256
from corpus.verify_quran import EXPECTED_COUNTS

SOURCES = ("tabary", "katheer", "baghawy", "saadi", "moyassar")
# Investigation flags are not permission to replace original text.
# Suppress suspect incomplete Tafsir Baghawi records in ordinary retrieval.
BAGHAWY_Q03_REVIEW_HOLD = {(4, 43), (17, 4), (18, 10), (33, 9)}


def get_ayah(db_path: Path, sura: int, aya: int, reference_path: Path | None = None,
             expected_reference_sha256: str = REFERENCE_SHA256,
             allow_unverified_derived_text: bool = False,
             allow_flagged_tafsir_text: bool = False):
    if type(sura) is not int or not 1 <= sura <= 114:
        raise ValueError("Invalid sura")
    if type(aya) is not int or not 1 <= aya <= EXPECTED_COUNTS[sura - 1]:
        raise ValueError("Invalid aya")
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    connection = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        raw = connection.execute("SELECT text FROM verses WHERE sura=? AND aya=?", (sura, aya)).fetchone()
        if raw is None:
            raise ValueError(f"Missing verse {sura}:{aya}")
        entries = connection.execute(
            "SELECT source,text FROM tafsirs WHERE sura=? AND aya=? ORDER BY source",
            (sura, aya)).fetchall()
    finally:
        connection.close()
    quran_text = None
    classification = "REFERENCE_REQUIRED_NO_QURAN_TEXT"
    reference_sha256 = None
    opening_basmala = None
    if reference_path is not None:
        verses = read_witness(reference_path, expected_reference_sha256)
        reference_sha256 = file_sha256(reference_path)
        expected = {(s, a) for s, n in enumerate(EXPECTED_COUNTS, 1) for a in range(1, n + 1)}
        if set(verses) != expected:
            raise ValueError("Independent Quran witness coverage mismatch")
        quran_text, opening_basmala = segment_first_verse(
            sura, aya, verses[(sura, aya)], verses[(1, 1)])
        classification = ("VERBATIM_TANZIL_VERSE_SEGMENT_NOT_SCHOLARLY_APPROVED"
                          if opening_basmala else "VERBATIM_TANZIL_WITNESS_NOT_SCHOLARLY_APPROVED")
    elif allow_unverified_derived_text:
        quran_text = raw[0]
        classification = "DERIVED_FROM_WORDS_NOT_CANONICALLY_VERIFIED"
    tafsirs = []
    for source, text in entries:
        if source not in SOURCES:
            continue
        flags = []
        value = text if isinstance(text, str) else ""
        display_text = plaintext(value)
        if not display_text:
            flags.append("NO_DISPLAYABLE_TEXT")
        if len(value) == 32767:
            flags.append("POSSIBLE_TRUNCATION_32767")
        editorial_hold = source == "baghawy" and (
            (sura, aya) in BAGHAWY_Q03_REVIEW_HOLD or len(value) == 32767
        )
        if editorial_hold:
            flags.append("EDITORIAL_HOLD_SUSPECTED_INCOMPLETE_UPSTREAM_TEXT")
        withheld = editorial_hold and not allow_flagged_tafsir_text
        tafsirs.append({
            "source_id": source,
            "verse_id": f"{sura}:{aya}",
            "text": value if display_text and not withheld else None,
            "display_text": display_text if display_text and not withheld else None,
            "displayable": bool(display_text) and not withheld,
            "render_as_plain_text": True,
            "quality_flags": flags,
            "editorial_review_required": editorial_hold,
            "display_status": (
                "WITHHELD_PENDING_EDITORIAL_VERIFICATION" if withheld else
                "DIAGNOSTIC_UNVERIFIED_SOURCE_TEXT" if editorial_hold else
                "NO_DISPLAYABLE_TEXT" if not display_text else
                "SOURCE_TEXT_UNVERIFIED_EDITION"
            ),
            "diagnostic_override_active": bool(editorial_hold and allow_flagged_tafsir_text),
            "edition_metadata": "NOT_YET_VERIFIED",
            "scholarly_verification": False,
        })
    return {
        "verse_id": f"{sura}:{aya}",
        "text": quran_text,
        "text_classification": classification,
        "reference_sha256": reference_sha256,
        "opening_basmala": opening_basmala,
        "reference_segment_is_literal_substring": bool(reference_sha256),
        "quran_text_attribution": "Tanzil Project (https://tanzil.net)" if reference_sha256 else (
            "Derived from Tafsir Center word data; internal diagnostics only" if allow_unverified_derived_text else None),
        "source_database": "tafsircenter/tafsir-mcp-data",
        "scholarly_verification": False,
        "tafsirs": tafsirs,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("sura", type=int)
    p.add_argument("aya", type=int)
    p.add_argument("--database", type=Path, default=Path("corpus-data/linked/quran_tafsir.db"))
    p.add_argument("--reference", type=Path)
    p.add_argument("--expected-reference-sha256", default=REFERENCE_SHA256)
    p.add_argument("--allow-unverified-derived-text", action="store_true")
    p.add_argument("--allow-flagged-tafsir-text", action="store_true",
                   help="LOCAL DIAGNOSTICS ONLY: return potentially truncated Tafsir Baghawi text")
    args = p.parse_args()
    print(json.dumps(get_ayah(args.database, args.sura, args.aya, args.reference,
                              args.expected_reference_sha256, args.allow_unverified_derived_text,
                              args.allow_flagged_tafsir_text),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
