"""Read-only Quran/tafsir query API; never represents derived text as verified scripture."""
import argparse
import json
import sqlite3
from pathlib import Path
from corpus.verify_quran import EXPECTED_COUNTS

SOURCES = ("tabary", "katheer", "baghawy", "saadi", "moyassar")
def get_ayah(db_path: Path, sura: int, aya: int):
    if type(sura) is not int or not 1 <= sura <= 114:
        raise ValueError("Invalid sura")
    if type(aya) is not int or not 1 <= aya <= EXPECTED_COUNTS[sura-1]:
        raise ValueError("Invalid aya")
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    # Use read-only URI mode; query_only also prevents unintended writes.
    conn = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        row = conn.execute("SELECT text FROM verses WHERE sura=? AND aya=?", (sura, aya)).fetchone()
        if row is None:
            raise ValueError(f"Missing verse {sura}:{aya}")
        entries = conn.execute(
            "SELECT source,text FROM tafsirs WHERE sura=? AND aya=? ORDER BY source",
            (sura, aya)).fetchall()
        return {
            "verse_id": f"{sura}:{aya}",
            "text": row[0],
            "text_classification": "DERIVED_FROM_WORDS_NOT_CANONICALLY_VERIFIED",
            "source_database": "tafsircenter/tafsir-mcp-data",
            "scholarly_verification": False,
            "tafsirs": [
                {"source_id": source, "text": text, "verse_id": f"{sura}:{aya}",
                 "edition_metadata": "NOT_YET_VERIFIED", "scholarly_verification": False}
                for source, text in entries if source in SOURCES
            ],
        }
    finally:
        conn.close()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("sura", type=int)
    p.add_argument("aya", type=int)
    p.add_argument("--database", type=Path, default=Path("corpus-data/linked/quran_tafsir.db"))
    args = p.parse_args()
    print(json.dumps(get_ayah(args.database, args.sura, args.aya), ensure_ascii=False, indent=2))
if __name__ == "__main__":
    main()
