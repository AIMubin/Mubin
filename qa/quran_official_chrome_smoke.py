"""Actual Chrome verification of the domain-reader code path.

Default: artificial full-size 6,236-row text, with injected test-only SHA pin.
Optional --live: authentic network bytes as observed (NOT publisher-attested).

Do not echo scripture in logs or screenshots; browser is localhost only.
This verifies software behavior, never publisher signature, rights or ruling.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
from unittest.mock import patch
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import threading
import time
import urllib.error

from engines.quran.q01e import official
from engines.quran.q01.engine import _VERSE_COUNTS
from engines.quran.q01c.reader import build_http_server
from qa.quran_browser_smoke import request, script, wait, check


def synthetic_full_candidate():
    """An artificial full-size document; NEVER represent this as an authentic Quran."""
    rows=[f"{s}|{a}|مِثَالٌ اصْطِنَاعِيٌّ لِلِاخْتِبَارِ\n"
          for s,n in enumerate(_VERSE_COUNTS,1) for a in range(1,n+1)]
    rows.extend(["\n","# PLEASE DO NOT REMOVE OR CHANGE THIS COPYRIGHT BLOCK\n",
                 "# TEST-ONLY invented Arabic sentences; no edition assertions\n"])
    return "".join(rows).encode("utf-8")


def main(argv=None):
    parser=argparse.ArgumentParser(description="Chrome E2E for offline artificial or advisory live domain reader")
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument("--fixture",action="store_true",help="default: full-size artificial candidate")
    mode.add_argument("--live",action="store_true",help="ADVISORY: fetch fixed Tanzil HTTPS candidate")
    args=parser.parse_args(argv)
    chromedriver=shutil.which("chromedriver")
    if not chromedriver:
        candidate=Path(os.environ.get("CHROMEWEBDRIVER","")) / "chromedriver"
        chromedriver=str(candidate) if candidate.is_file() else None
    check(chromedriver, "ChromeDriver missing: do not treat this as a pass")
    if args.live:
        index,raw=official.obtain_official_index()
    else:
        raw=synthetic_full_candidate()
        # Injection is scoped to tests: the real code continues to use its
        # historical immutable digest and will not accept this artificial file.
        with patch.object(official,"PINNED_OFFICIAL_DOMAIN_SHA256",sha256(raw).hexdigest()):
            index=official.load_official_candidate(raw)
            server=build_http_server(index,raw,port=0)
    if args.live:
        server=build_http_server(index,raw,port=0)
    worker=threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    site=f"http://127.0.0.1:{server.server_port}/"
    with socket.socket() as s:
        s.bind(("127.0.0.1",0))
        port=s.getsockname()[1]
    process=subprocess.Popen([chromedriver,f"--port={port}"],
                             stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    driver=f"http://127.0.0.1:{port}"
    sid=None
    try:
        for _ in range(100):
            check(process.poll() is None,"driver exited before session")
            try:
                if request(driver+"/status")["value"]["ready"]:
                    break
            except (OSError,KeyError,ValueError):
                pass
            time.sleep(0.1)
        else:
            raise AssertionError("driver did not become ready")
        response=request(driver+"/session","POST",{
          "capabilities":{"alwaysMatch":{"browserName":"chrome",
              "goog:chromeOptions":{"args":["--headless=new","--no-sandbox",
                  "--disable-dev-shm-usage","--window-size=1200,900"]}}}})
        sid=response.get("sessionId") or response.get("value",{}).get("sessionId")
        check(bool(sid),"no Chrome session")
        request(driver+f"/session/{sid}/url","POST",{"url":site})
        wait(driver,sid,
            "return document.querySelector('#source-details')?.textContent.includes('tanzil-domain:')")
        check(script(driver,sid,"return document.documentElement.dir")=="rtl",
              "Quran page lost RTL direction")
        check(script(driver,sid,"return document.documentElement.lang")=="ar",
              "Quran page lost Arabic language")
        check(script(driver,sid,
            "return document.querySelector('#source-details').textContent.includes('اعتماد أصالة النص: لا')"),
            "missing research/unattested source disclosure")
        # Retrieve an actual verse and compare Unicode exactly with the index
        # already parsed from the original pinned bytes, without logging its text.
        script(driver,sid,
            "document.querySelector('#reference').value='2:1';document.querySelector('#lookup-form button').click()")
        displayed=wait(driver,sid,"return document.querySelector('article.ayah .verse')?.textContent")
        check(displayed==index.get("2:1")["text"],"reader changed original source text")
        check(script(driver,sid,
            "return document.querySelector('article.ayah').textContent.includes('استجابة Tanzil المثبتة')"),
            "mislabels a domain-source code path as a GitHub mirror")
        tafsir_links=script(driver,sid,
            "return Array.from(document.querySelectorAll('article.ayah .tafsir-links a')).map(a=>({href:a.href,target:a.target,rel:a.rel,policy:a.referrerPolicy}))")
        check(len(tafsir_links)==2,"Expected two external Ayat citation links, not copied tafsir text")
        check(tafsir_links[0]["href"] ==
            "https://quran.ksu.edu.sa/index.php#aya=2_1&m=hafs&qaree=husary&trans=ar_mu",
            "Wrong Quran verse-to-Ayat al-Muyassar deep link")
        check(tafsir_links[1]["href"] ==
            "https://quran.ksu.edu.sa/index.php#aya=2_1&m=hafs",
            "Other tafsir navigation must not claim a selected commentary source")
        for item in tafsir_links:
            check(item["target"]=="_blank" and "noopener" in item["rel"] and
                  "noreferrer" in item["rel"] and item["policy"]=="no-referrer",
                  "External tafsir link missing browser privacy boundaries")
        wait(driver,sid,
            "return document.querySelectorAll('article.ayah .tafsir-bibliography li').length===6")
        check(script(driver,sid,
            "return document.querySelector('article.ayah .tafsir-bibliography').textContent.includes('الطبعة غير محددة')"),
            "Unknown tafsir edition cannot be silently promoted")
        check(script(driver,sid,
            "return document.querySelector('article.ayah .tafsir-bibliography').textContent.includes('الحقوق غير متحقق منها')"),
            "Tafsir rights must remain explicitly unverified")
        check(script(driver,sid,
            "return document.querySelectorAll('article.ayah .tafsir-bibliography a').length")==0,
            "Unverified tafsir books cannot silently acquire unlicensed per-book links")
        check(script(driver,sid,
            "return document.querySelector('article.ayah .ai-explanation')?.textContent.includes('غير مفعّل')"),
            "AI interpretation has to remain disabled and separate")
        check(script(driver,sid,
            "return document.querySelectorAll('article.ayah .tafsir-links iframe').length")==0,
            "Must never embed or fetch KSU tafsir as if licensed locally")
        script(driver,sid,"document.querySelector('#notice-details summary').click()")
        wait(driver,sid,
            "return document.querySelector('#source-notice').textContent.includes('PLEASE DO NOT REMOVE')")
        request(driver+f"/session/{sid}/window/rect","POST",{"width":390,"height":840})
        viewport=script(driver,sid,
            "return {w:document.documentElement.clientWidth, sw:document.documentElement.scrollWidth, dir:getComputedStyle(document.body).direction}")
        check(viewport["dir"]=="rtl" and viewport["sw"]<=viewport["w"]+1,
              "mobile RTL overflow in official-source reader")
        print(json.dumps({
            "result":"PASS", "browser":"actual_headless_chrome",
            "source":("pinned_tanzil_domain_export_unattested" if args.live
                       else "artificial_6236_domain_source_simulation"),
            "verse_count":len(index.verses), "exact_unicode_source":True,
            "mobile_rtl":True,"copyright_notice_visible":True,
            "scripture_text_logged":False,
            "publisher_authenticated":False,
            "source_authenticated":False,"rights_verified":False,
        },sort_keys=True))
    finally:
        if sid:
            try:request(driver+f"/session/{sid}","DELETE")
            except Exception:pass
        process.terminate()
        try:process.wait(timeout=4)
        except subprocess.TimeoutExpired:process.kill()
        server.shutdown();server.server_close()
        worker.join(timeout=3)


if __name__=="__main__":
    main()
