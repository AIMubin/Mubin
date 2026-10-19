"""Acquire the independent official Tanzil Uthmani txt-2 witness.

Terms: preserve verbatim text and attribution; no modification of source bytes.
Output is staging-only until independently checked and approved.
"""
import argparse, hashlib, json, urllib.parse, urllib.request
from pathlib import Path
from corpus.verify_quran import verify

URL = "https://tanzil.net/pub/download/index.php"
PARAMS = {"quranType":"uthmani","outType":"txt-2","agree":"true",
          "marks":"true","sajdah":"true","rub":"true","stanween":"true"}

def fetch(destination: Path, manifest: Path):
    if destination.exists():
        raise FileExistsError(destination)
    address = URL + "?" + urllib.parse.urlencode(PARAMS)
    request = urllib.request.Request(address,headers={"User-Agent":"Mubin-corpus-audit/0.3"})
    with urllib.request.urlopen(request,timeout=90) as response:
        if urllib.parse.urlparse(response.url).hostname not in {"tanzil.net","www.tanzil.net"}:
            raise ValueError("Unexpected download host")
        raw = response.read(4_000_001)
    if len(raw) > 4_000_000:
        raise ValueError("Unexpectedly large witness")
    if raw[:100].lower().lstrip().startswith((b"<!doctype",b"<html")):
        raise ValueError("HTML response instead of text")
    # Reject accidental binary responses and invalid UTF-8.
    raw.decode("utf-8","strict")
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_bytes(raw)
    digest=hashlib.sha256(raw).hexdigest()
    check=verify(destination,digest) # Structural only; hash is self-calculated, not attestation.
    if not check["passed"]:
        destination.unlink(missing_ok=True)
        raise ValueError(f"Reference structure invalid: {check['errors']}")
    info={"source_url":address,"source":"Tanzil official downloader",
          "variant":"Uthmani txt-2","sha256":digest,"verses":check["verse_count"],
          "structurally_valid":True,"independently_attested_checksum":False,
          "canonical_authentication":False,
          "attribution":"Tanzil Project (https://tanzil.net), verbatim text, CC BY 3.0 subject to Tanzil terms"}
    manifest.parent.mkdir(parents=True,exist_ok=True)
    manifest.write_text(json.dumps(info,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return info

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,default=Path("corpus-data/reference/tanzil-uthmani.txt"))
    p.add_argument("--manifest",type=Path,default=Path("corpus-data/reference/tanzil-manifest.json"))
    a=p.parse_args()
    print(json.dumps(fetch(a.output,a.manifest),ensure_ascii=False,indent=2))
