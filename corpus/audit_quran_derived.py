"""Detect noncanonical reconstruction artifacts in derived Quran verse strings.

Diagnostic only: this never authenticates or edits the Quranic text.
"""
import argparse
import json
import sqlite3
from pathlib import Path
from corpus.verify_quran import EXPECTED_COUNTS

def audit(path: Path):
    if not path.is_file():
        raise FileNotFoundError(path)
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        rows = connection.execute("SELECT sura,aya,text FROM verses ORDER BY sura,aya").fetchall()
    finally:
        connection.close()
    expected = {(s,a) for s,count in enumerate(EXPECTED_COUNTS,1)
                for a in range(1,count+1)}
    if len(rows) != len(expected) or {(s,a) for s,a,_ in rows} != expected:
        raise ValueError("Incomplete Quran source coverage")
    flagged = [f"{sura}:{aya}" for sura,aya,text in rows
               if isinstance(text,str) and "/" in text]
    return {
        "dataset": "DERIVED_UNVERIFIED_QURAN",
        "verse_count": len(rows),
        "has_reconstruction_artifacts": bool(flagged),
        "quran_text_safe_to_display_as_canonical": False,
        "slash_marked_verse_count": len(flagged),
        "slash_marked_verse_ids": flagged,
        "note": "Diagnostic only. No correction or normalization of the verse text was performed."
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--database",type=Path,default=Path("corpus-data/linked/quran_tafsir.db"))
    p.add_argument("--report",type=Path,default=Path("corpus-data/linked/derived-quran-quality.json"))
    args=p.parse_args()
    result=audit(args.database)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+chr(10),encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="slash_marked_verse_ids"},
                     ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
