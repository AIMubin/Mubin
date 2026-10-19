"""Audit linked SQLite coverage, content, and foreign keys. Not religious authentication."""
import argparse
import json
import sqlite3
from pathlib import Path
from corpus.verify_quran import EXPECTED_COUNTS
from corpus.import_tafsircenter import NAMES, sha

def audit(path: Path):
    if not path.is_file(): raise FileNotFoundError(path)
    db=sqlite3.connect(path.resolve().as_uri()+"?mode=ro",uri=True)
    try:
        db.execute("PRAGMA query_only=ON")
        expected={(s,a) for s,n in enumerate(EXPECTED_COUNTS,1) for a in range(1,n+1)}
        verses=db.execute("SELECT sura,aya,text FROM verses").fetchall()
        actual={(s,a) for s,a,t in verses}
        issues=[]
        if len(verses)!=6236 or actual!=expected:
            issues.append("Verse set incomplete or duplicated")
        if any(not isinstance(t,str) or not t.strip() for s,a,t in verses):
            issues.append("Empty verse text")
        counts={}
        for name in NAMES:
            rows=db.execute("SELECT sura,aya,text FROM tafsirs WHERE source=?",(name,)).fetchall()
            keys={(s,a) for s,a,t in rows}
            counts[name]=len(rows)
            if len(rows)!=6236 or keys!=expected or any(not isinstance(t,str) or not t.strip() for s,a,t in rows):
                issues.append(f"Incomplete/duplicate/blank tafsir: {name}")
        unexpected=db.execute("SELECT DISTINCT source FROM tafsirs WHERE source NOT IN (?,?,?,?,?)",NAMES).fetchall()
        if unexpected: issues.append("Unexpected tafsir source(s)")
        if db.execute("PRAGMA foreign_key_check").fetchall(): issues.append("Foreign key violations")
        integrity=db.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity!="ok": issues.append(f"SQLite integrity: {integrity}")
        return {"structural_audit_passed":not issues, "scholarly_verified":False,
                "canonical_quran_verified":False, "sha256":sha(path),
                "verse_count":len(verses),"tafsir_counts":counts,"issues":issues}
    finally: db.close()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--database",type=Path,default=Path("corpus-data/linked/quran_tafsir.db"))
    p.add_argument("--report",type=Path,default=Path("corpus-data/linked/audit-report.json"))
    a=p.parse_args()
    result=audit(a.database)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result["structural_audit_passed"] else 1)
if __name__=="__main__": main()
