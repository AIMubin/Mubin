"""Check that imported tafsir text matches the pinned Tafsir Center SQLite bytes.

Neither matching an upstream dataset nor identifying apparent truncation proves
editorial authenticity or correctness relative to a printed book edition.
"""
import argparse
from itertools import zip_longest
import hashlib
import json
from pathlib import Path
import sqlite3

from corpus.import_tafsircenter import PIN, NAMES, sha

FLAGGED = {
    "tabary": {(4,168),(26,16),(26,205),(37,25),(37,62),(37,103),(50,13)},
    "baghawy": {(4,43),(17,4),(18,10),(33,9)},
}

def compare(original, linked, source_sha=PIN):
    if sha(original) != source_sha:
        raise ValueError("Upstream Tafsir Center SQLite SHA-256 mismatch")
    if not linked.is_file():
        raise FileNotFoundError(linked)
    src=sqlite3.connect(original.resolve().as_uri()+"?mode=ro",uri=True)
    dst=sqlite3.connect(linked.resolve().as_uri()+"?mode=ro",uri=True)
    try:
        src.execute("PRAGMA query_only=ON")
        dst.execute("PRAGMA query_only=ON")
        results, flags={}, []
        for name in NAMES:
            originals=src.execute(f"SELECT sura,aya,tafsir FROM tafsir_{name} ORDER BY sura,aya")
            derived=dst.execute("SELECT sura,aya,text FROM tafsirs WHERE source=? ORDER BY sura,aya",(name,))
            n=0
            for before, after in zip_longest(originals,derived):
                if before is None or after is None:
                    raise ValueError(f"Missing tafsir rows in {name}")
                if before != after:
                    raise ValueError(f"Text changed during import: {name}, {before[:2]}")
                n+=1
                if before[:2] in FLAGGED.get(name,set()):
                    data=before[2]
                    flags.append({
                        "source":name, "verse_id":f"{before[0]}:{before[1]}",
                        "source_characters":len(data),
                        "source_text_sha256":hashlib.sha256(data.encode("utf-8")).hexdigest(),
                        "identical_in_import":True,
                    })
            if n != 6236:
                raise ValueError(f"Unexpected tafsir coverage in {name}: {n}")
            results[name]={"identical_source_and_import_rows":n}
        if len(flags) != 11:
            raise ValueError(f"Expected eleven known quality flags; got {len(flags)}")
        return {
            "comparison":"ALL_SOURCE_ROWS_IDENTICAL_TO_IMPORTED_ROWS",
            "source_sha256":source_sha, "derived_db_sha256":sha(linked),
            "tafsir_sources":results,
            "flagged_source_records":sorted(flags,key=lambda x:(x["source"],x["verse_id"])),
            "source_edition_verified":False, "scholarly_verified":False,
            "note":"Matching proves no alteration by Mubin import, but cannot rule out defects or truncation already present upstream.",
        }
    finally:
        src.close()
        dst.close()


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,default=Path("corpus-data/source/tafsircenter-quran.db"))
    p.add_argument("--download",action="store_true")
    p.add_argument("--linked",type=Path,default=Path("corpus-data/linked/quran_tafsir.db"))
    p.add_argument("--report",type=Path,default=Path("corpus-data/linked/tafsir-upstream-comparison.json"))
    a=p.parse_args()
    source=a.source
    if not source.exists() and a.download:
        from huggingface_hub import hf_hub_download
        source=Path(hf_hub_download(repo_id="tafsircenter/tafsir-mcp-data",filename="quran.db",repo_type="dataset"))
    result=compare(source,a.linked)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="flagged_source_records"},ensure_ascii=False,indent=2))


if __name__=="__main__":main()
