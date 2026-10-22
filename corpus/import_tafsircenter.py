#!/usr/bin/env python3
"""Import Tafsir Center's Quran/tafsir SQLite release, preserving provenance."""
import argparse, hashlib, json, sqlite3
from pathlib import Path
REPO="tafsircenter/tafsir-mcp-data"
PIN="10e61f615ab5e6a3440e8ecc8ba1dc2273d12cd9048752760fe53a44d191cc27"
NAMES=("tabary","katheer","baghawy","saadi","moyassar")
from corpus.verify_quran import EXPECTED_COUNTS

def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()

def import_db(source, output, expected_hash=PIN):
    if not source.is_file(): raise FileNotFoundError(source)
    actual=sha(source)
    if actual!=expected_hash: raise ValueError("Untrusted source SHA-256")
    if output.exists(): raise FileExistsError(output)
    expected={(s,a) for s,n in enumerate(EXPECTED_COUNTS,1) for a in range(1,n+1)}
    src=sqlite3.connect(f"file:{source.resolve()}?mode=ro",uri=True)
    src.execute("PRAGMA query_only=ON")
    output.parent.mkdir(parents=True,exist_ok=True)
    dst=sqlite3.connect(output)
    try:
        tables={x[0] for x in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required={"word_content_rasm",*(f"tafsir_{n}" for n in NAMES)}
        if not required<=tables: raise ValueError(f"Missing tables: {required-tables}")
        dst.executescript("""CREATE TABLE verses(sura INTEGER,aya INTEGER,text TEXT NOT NULL,PRIMARY KEY(sura,aya));
CREATE TABLE tafsirs(source TEXT NOT NULL,sura INTEGER,aya INTEGER,text TEXT NOT NULL,
PRIMARY KEY(source,sura,aya),FOREIGN KEY(sura,aya) REFERENCES verses(sura,aya));
CREATE INDEX tafsir_verse ON tafsirs(sura,aya);""")
        dst.execute("PRAGMA foreign_keys=ON")
        words={}
        for s,a,w,t in src.execute("SELECT surahNo,ayahNo,wordNo,word FROM word_content_rasm ORDER BY surahNo,ayahNo,wordNo"):
            if (s,a) not in expected or not isinstance(t,str) or not t.strip():
                raise ValueError(f"Invalid word at {s}:{a}")
            words.setdefault((s,a),[]).append(t)
        if set(words)!=expected: raise ValueError("Quran verse coverage mismatch")
        dst.executemany("INSERT INTO verses VALUES(?,?,?)",((s,a," ".join(words[s,a])) for s,a in sorted(expected)))
        coverage={}
        for name in NAMES:
            keys=set()
            for s,a,t in src.execute(f"SELECT sura,aya,tafsir FROM tafsir_{name}"):
                if (s,a) not in expected or (s,a) in keys: raise ValueError(f"Invalid tafsir {name}: {s}:{a}")
                keys.add((s,a))
                if isinstance(t,str) and t.strip():
                    dst.execute("INSERT INTO tafsirs VALUES(?,?,?,?)",(name,s,a,t))
            coverage[name]={"source_keys":len(keys),"nonempty":dst.execute("SELECT COUNT(*) FROM tafsirs WHERE source=?",(name,)).fetchone()[0]}
        if dst.execute("PRAGMA foreign_key_check").fetchall(): raise ValueError("Broken foreign key")
        dst.commit()
        return {"status":"IMPORTED_NOT_SCHOLARLY_VERIFIED","source":REPO,"source_sha256":actual,
                "verses":len(words),"tafsirs":coverage,"output_sha256":sha(output),
                "text_note":"Verse text joined from word tokens: derived, not canonical publisher bytes",
                "rights":"CC BY 4.0 claimed in LICENSE-DATA; DATA_SOURCES.md requests commercial permissions; review pending"}
    except BaseException:
        dst.close()
        output.unlink(missing_ok=True)
        raise
    finally:
        src.close()
        dst.close()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,default=Path("corpus-data/source/tafsircenter-quran.db"))
    p.add_argument("--download",action="store_true")
    p.add_argument("--output",type=Path,default=Path("corpus-data/linked/quran_tafsir.db"))
    p.add_argument("--manifest",type=Path,default=Path("corpus-data/linked/import-manifest.json"))
    a=p.parse_args()
    source=a.source
    if not source.exists() and a.download:
        from huggingface_hub import hf_hub_download
        source=Path(hf_hub_download(repo_id=REPO,filename="quran.db",repo_type="dataset"))
    result=import_db(source,a.output)
    a.manifest.parent.mkdir(parents=True,exist_ok=True)
    a.manifest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
