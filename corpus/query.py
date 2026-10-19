"""Read-only Quran and tafsir lookup with explicit provenance and quality flags."""
import argparse
import json
import sqlite3
from pathlib import Path

from corpus.audit_tafsir_quality import plaintext
from corpus.compare_quran import witness
from corpus.triage_quran import REFERENCE_SHA256
from corpus.verify_quran import EXPECTED_COUNTS

SOURCES = ("tabary", "katheer", "baghawy", "saadi", "moyassar")


def get_ayah(db_path: Path, sura: int, aya: int, reference_path: Path | None = None,
             expected_reference_sha256: str = REFERENCE_SHA256,
             allow_unverified_derived_text: bool = False):
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
    if reference_path is not None:
        verses, reference_sha256 = witness(reference_path)
        if reference_sha256.lower() != expected_reference_sha256.lower():
            raise ValueError("Independent Quran witness hash mismatch")
        expected = {(s, a) for s, n in enumerate(EXPECTED_COUNTS, 1) for a in range(1, n + 1)}
        if set(verses) != expected:
            raise ValueError("Independent Quran witness coverage mismatch")
        quran_text = verses[(sura, aya)]
        classification = "VERBATIM_TANZIL_WITNESS_NOT_SCHOLARLY_APPROVED"
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
        tafsirs.append({
            "source_id": source,
            "verse_id": f"{sura}:{aya}",
            "text": value if display_text else None,
            "display_text": display_text or None,
            "displayable": bool(display_text),
            "render_as_plain_text": True,
            "quality_flags": flags,
            "edition_metadata": "NOT_YET_VERIFIED",
            "scholarly_verification": False,
        })
    return {
        "verse_id": f"{sura}:{aya}",
        "text": quran_text,
        "text_classification": classification,
        "reference_sha256": reference_sha256,
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
    args = p.parse_args()
    print(json.dumps(get_ayah(args.database, args.sura, args.aya, args.reference,
                              args.expected_reference_sha256, args.allow_unverified_derived_text),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
