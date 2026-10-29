"""Actual Chrome DOM smoke for optional UT-01.4 metadata panel (synthetic only).

The HTTP integration is separately tested against the loopback API. This
exercise runs the actual research.js in Chrome with an intercepted synthetic
response: it must render the correct tier, source spans and scientific cap.
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

from engines.quran.q01b.tanzil import load_raw
from engines.quran.q01c.reader import build_http_server
from qa.quran_browser_smoke import (
    MANIFEST, RAW, request, script, wait, check,
)


def main():
    chromedriver=shutil.which("chromedriver")
    if not chromedriver:
        p=Path(os.environ.get("CHROMEWEBDRIVER",""))/"chromedriver"
        chromedriver=str(p) if p.is_file() else None
    check(bool(chromedriver),"ChromeDriver required, no silent skip")
    index=load_raw(json.dumps(MANIFEST).encode("utf-8"),RAW)
    server=build_http_server(index,RAW,port=0)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        port=sock.getsockname()[1]
    process=subprocess.Popen([chromedriver,f"--port={port}"],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
    driver=f"http://127.0.0.1:{port}"
    sid=None
    try:
        for _ in range(100):
            if process.poll() is not None:
                raise AssertionError("ChromeDriver exited")
            try:
                if request(driver+"/status")["value"]["ready"]:
                    break
            except (OSError,KeyError,ValueError):
                pass
            time.sleep(.1)
        else:
            raise AssertionError("ChromeDriver not ready")
        r=request(driver+"/session","POST",{
            "capabilities":{"alwaysMatch":{"browserName":"chrome",
                "goog:chromeOptions":{"args":[
                    "--headless=new","--no-sandbox",
                    "--disable-dev-shm-usage","--window-size=1200,900"
                ]}}}})
        sid=r.get("sessionId") or r.get("value",{}).get("sessionId")
        check(bool(sid),"Chrome session absent")
        request(driver+f"/session/{sid}/url","POST",{
            "url":f"http://127.0.0.1:{server.server_port}/research"})
        check(script(driver,sid,"return document.documentElement.dir")=="rtl",
              "Research page lost RTL")
        fake={
            "tafsir_count":0,"quran_text":{"state":"SYNTHETIC_ONLY"},
            "tafsirs":[],"relations":[],
            "usul":{
                "contract":"mubin-usul-tafsir-presentation-v1",
                "section_title_ar":"القواعد الأصولية المرتبطة بالتفسير",
                "counts":{"matches_total":2,
                    "links_by_status":{"UNDETERMINED":2},
                    "ties_by_level":{"EXACT":1,"NONE":1}},
                "usul_rule_candidate_id":"candidate:amr-structural-hypothesis",
                "usul_research_pointer_id":"pilot:amr-rule-research-pointer",
                "usul_section_sha256":"a"*64,"catalog_sha256":"b"*64,
                "graph_sha256":"c"*64,
                "usul_link_level_cap":"AUTOMATED_CANDIDATE",
                "evidence_levels":["RETRIEVED_SOURCE_MATERIAL",
                    "GROUNDED_PASSAGE","AUTOMATED_CANDIDATE",
                    "TEXTUALLY_ATTRIBUTED","SCHOLARLY_VERIFIED"],
                "links_redacted":[
                    {"link_id":"utl:fake1","link_status":"UNDETERMINED",
                     "tafsir_candidate_id":"cand:fake1",
                     "usul_rule_candidate_id":"candidate:amr-structural-hypothesis",
                     "link_method":"EVIDENCE_CHAIN_VERIFICATION_ONLY",
                     "tie_level":"EXACT",
                     "evidence_level":"AUTOMATED_CANDIDATE",
                     "tafsir_tie_span":[20,24],
                     "tafsir_tie_sha256":"d"*64,
                     "usul_tie_span":[42,51],
                     "usul_tie_sha256":"e"*64,
                     "qarinah_status":"NOT_OBSERVED_IN_SCOPE",
                     "verification_status":"UNVERIFIED"},
                    {"link_id":"utl:fake2","link_status":"UNDETERMINED",
                     "tafsir_candidate_id":"cand:fake2",
                     "usul_rule_candidate_id":"candidate:amr-structural-hypothesis",
                     "link_method":"EVIDENCE_CHAIN_VERIFICATION_ONLY",
                     "tie_level":"NONE",
                     "evidence_level":"AUTOMATED_CANDIDATE",
                     "tafsir_tie_span":None,"tafsir_tie_sha256":None,
                     "usul_tie_span":None,"usul_tie_sha256":None,
                     "qarinah_status":"NOT_OBSERVED_IN_SCOPE",
                     "verification_status":"UNVERIFIED"}],
                "text_included":False,"scholarly_verified":False,
                "rule_application_verified":False,
            }}
        script(driver,sid,
               "window.__ut014 = "+json.dumps(fake,ensure_ascii=True)+";"
               "window.fetch = async () => ({ok:true,json:async()=>window.__ut014});")
        script(driver,sid,
               "document.querySelector('#ref').value='2:43';"
               "document.querySelector('#go').click();")
        wait(driver,sid,
             "return document.querySelector('#relations')?.textContent.includes('القواعد الأصولية المرتبطة بالتفسير')")
        check(script(driver,sid,
            "return document.querySelector('#relations').textContent.includes('بلا تطابق NONE')"),
            "NONE tier must not be described as a folded match")
        check(script(driver,sid,
            "return document.querySelector('#relations').textContent.includes('AUTOMATED_CANDIDATE')"),
            "Scientific level cap not shown")
        check(script(driver,sid,
            "return document.querySelector('#relations').textContent.includes('TEXTUALLY_ATTRIBUTED')"),
            "All five evidence levels must remain listed")
        check(script(driver,sid,
            "return document.querySelector('#relations').textContent.includes('42..51')"),
            "Raw UTF-8 span not rendered")
        check(script(driver,sid,
            "return document.querySelectorAll('#relations script, #relations img').length")==0,
            "Untrusted source data must be rendered as text only")
        request(driver+f"/session/{sid}/window/rect","POST",
                {"width":390,"height":840})
        mobile=script(driver,sid,
            "return {w:document.documentElement.clientWidth,"
            "s:document.documentElement.scrollWidth,"
            "dir:getComputedStyle(document.body).direction}")
        check(mobile["dir"]=="rtl" and mobile["s"]<=mobile["w"]+1,
              "Mobile RTL overflow")
        print(json.dumps({
            "result":"PASS","browser":"actual_headless_chrome",
            "usul_panel":True,"five_levels":True,
            "metadata_only":True,"scientific_cap":"AUTOMATED_CANDIDATE",
            "rights_verified":False,"scholarly_verified":False}))
    finally:
        if sid:
            try: request(driver+f"/session/{sid}","DELETE")
            except Exception: pass
        process.terminate()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired: process.kill()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


if __name__=="__main__":
    main()
