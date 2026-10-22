"""Compare two Quran witnesses without erasing differences in rasm or diacritics.

Reference file must use sura|ayah|text (Tanzil txt-2). This is a diagnostic
comparison; neither witness is silently promoted to canonical status.
"""
import argparse, hashlib, json, sqlite3
from pathlib import Path
from corpus.verify_quran import EXPECTED_COUNTS

def witness(path):
    data=path.read_bytes()
    text=data.decode("utf-8",errors="strict")
    out={}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"): continue
        bits=line.split("|",2)
        if len(bits)!=3: raise ValueError("Expected sura|ayah|text")
        s,a,t=bits
        key=(int(s),int(a))
        if key in out: raise ValueError(f"Duplicate reference: {key}")
        if not t.strip(): raise ValueError(f"Empty reference: {key}")
        out[key]=t
    return out,hashlib.sha256(data).hexdigest()

def compare(dbpath, refpath):
    ref,hashvalue=witness(refpath)
    expected={(s,a) for s,n in enumerate(EXPECTED_COUNTS,1) for a in range(1,n+1)}
    db=sqlite3.connect(dbpath.resolve().as_uri()+"?mode=ro",uri=True)
    try:
        src={(s,a):t for s,a,t in db.execute("SELECT sura,aya,text FROM verses")}
        if len(src)!=6236 or set(src)!=expected: raise ValueError("Imported verse coverage invalid")
    finally: db.close()
    if set(ref)!=expected: raise ValueError("Independent witness coverage invalid")
    differences=[]
    for key in sorted(expected):
        if src[key]!=ref[key]:
            differences.append({"verse_id":f"{key[0]}:{key[1]}",
                                "imported_text":src[key], "reference_text":ref[key]})
    return {"comparison_status":"IDENTICAL" if not differences else "DIFFERENCES_REQUIRE_REVIEW",
            "scholarly_verified":False,"reference_sha256":hashvalue,
            "total":6236,"exact_matches":6236-len(differences),
            "differences_count":len(differences),
            "differences":differences}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--database",type=Path,default=Path("corpus-data/linked/quran_tafsir.db"))
    p.add_argument("--reference",type=Path,required=True)
    p.add_argument("--report",type=Path,default=Path("corpus-data/linked/quran-comparison.json"))
    a=p.parse_args()
    result=compare(a.database,a.reference)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="differences"},ensure_ascii=False,indent=2))
    raise SystemExit(0 if not result["differences_count"] else 2)
if __name__=="__main__":main()
