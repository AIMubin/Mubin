"""Actual Chrome verification of 6,236-verse pinned Tanzil-domain candidate.

Do not echo scripture in logs or screenshots; browser is localhost only.
This verifies software behavior, never publisher signature, rights or ruling.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import threading
import time
import urllib.error

from engines.quran.q01e.official import obtain_official_index
from engines.quran.q01c.reader import build_http_server
from qa.quran_browser_smoke import request, script, wait, check


def main():
    chromedriver=shutil.which("chromedriver")
    if not chromedriver:
        candidate=Path(os.environ.get("CHROMEWEBDRIVER","")) / "chromedriver"
        chromedriver=str(candidate) if candidate.is_file() else None
    check(chromedriver, "ChromeDriver missing: do not treat this as a pass")
    index,raw=obtain_official_index()
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
            "return document.querySelector('article.ayah').textContent.includes('استجابة نطاق Tanzil')"),
            "mislabels an official-domain export as a GitHub mirror")
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
            "return document.querySelector('article.ayah .tafsir-bibliography').textContent.includes('الطبعة: غير محددة')"),
            "Unknown tafsir edition cannot be silently promoted")
        check(script(driver,sid,
            "return document.querySelector('article.ayah .tafsir-bibliography').textContent.includes('الحقوق: غير متحقق منها')"),
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
            "source":"pinned_tanzil_domain_export_unattested",
            "verse_count":len(index.verses), "exact_unicode_source":True,
            "mobile_rtl":True,"copyright_notice_visible":True,
            "scripture_text_logged":False,
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
