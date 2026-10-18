"""Actual Chrome E2E smoke test for the Mubin RTL localhost Quran reader.

Uses invented Arabic test strings ONLY; they are not Quranic verses.
Requires Chrome + ChromeDriver, uses Python stdlib and does not fetch any text.
Run explicitly with: python qa/quran_browser_smoke.py
"""
from __future__ import annotations
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request

from engines.quran.q01b.tanzil import load_raw
from engines.quran.q01c.reader import build_http_server

RAW = ('1|1|سَلَامٌ تجريبي <img src=x onerror=alert(1)>\n'
       '1|2|أَمَانَةٌ اصطناعية\n').encode('utf-8')
MANIFEST = {
    'contract':'mubin-quran-q01b-verbatim-source-v1',
    'source_kind':'synthetic_fixture',
    'source_id':'synthetic:q01b',
    'source_url':None, 'source_commit':None, 'source_git_blob_sha1':None,
    'raw_sha256':sha256(RAW).hexdigest(), 'raw_byte_count':len(RAW),
    'coverage':'partial', 'reading':'hafs_an_asim_kufan',
    'rights_status':'requires_use_review','authority_status':'not_authenticated',
}

def request(url, method='GET', payload=None, headers=None):
    body = None if payload is None else json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=body, method=method,
        headers={'Content-Type':'application/json', **(headers or {})})
    with urllib.request.urlopen(req,timeout=10) as res:
        b=res.read(262144)
        return json.loads(b) if b else None

def script(driver, sid, js):
    r=request(driver+'/session/'+sid+'/execute/sync','POST',
              {'script':js,'args':[]})
    if 'value' not in r:
        raise AssertionError('WebDriver evaluation failed: '+str(r)[:400])
    return r['value']

def wait(driver, sid, js):
    end=time.monotonic()+10
    while time.monotonic()<end:
        result=script(driver,sid,js)
        if result:
            return result
        time.sleep(.15)
    raise AssertionError('Browser UI timed out: '+js[:100])

def check(condition, message):
    if not condition:
        raise AssertionError(message)

def main():
    chromedriver=shutil.which('chromedriver')
    if not chromedriver:
        path=Path(os.environ.get('CHROMEWEBDRIVER',''))/'chromedriver'
        chromedriver=str(path) if path.is_file() else None
    check(chromedriver, 'FAIL: no ChromeDriver; do not silently skip browser tests')

    index=load_raw(json.dumps(MANIFEST,ensure_ascii=True).encode('utf-8'),RAW)
    webserver=build_http_server(index,RAW,port=0)
    serverthread=threading.Thread(target=webserver.serve_forever,daemon=True)
    serverthread.start()
    website='http://127.0.0.1:'+str(webserver.server_port)+'/'
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        driver_port=sock.getsockname()[1]
    process=subprocess.Popen([chromedriver,'--port='+str(driver_port)],
                             stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    driver='http://127.0.0.1:'+str(driver_port)
    sid=None
    try:
        for _ in range(100):
            check(process.poll() is None,'ChromeDriver exited unexpectedly')
            try:
                value=request(driver+'/status')
                if value['value']['ready']:
                    break
            except (OSError,KeyError,ValueError):
                pass
            time.sleep(.1)
        else:
            raise AssertionError('ChromeDriver did not become ready')
        response=request(driver+'/session','POST',{
            'capabilities':{'alwaysMatch':{'browserName':'chrome',
                'goog:chromeOptions':{'args':['--headless=new','--no-sandbox',
                     '--disable-dev-shm-usage','--window-size=1200,900']}}}})
        sid=response.get('sessionId') or response.get('value',{}).get('sessionId')
        check(sid, 'Chrome session creation failed: '+str(response)[:450])
        request(driver+'/session/'+sid+'/url','POST',{'url':website})
        wait(driver,sid,"return document.querySelector('#source-details')?.textContent.includes('synthetic:q01b')")
        check(script(driver,sid,"return document.documentElement.getAttribute('dir')")== 'rtl',
              'RTL document direction lost')
        check(script(driver,sid,"return document.documentElement.getAttribute('lang')")== 'ar',
              'Arabic document language lost')
        check(script(driver,sid,"return document.querySelector('#source-details').textContent.includes('اعتماد أصالة النص: لا')"),
              'Unverified-source disclosure missing')
        script(driver,sid,"document.querySelector('#reference').value='1:1'; document.querySelector('#lookup-form button').click();")
        displayed=wait(driver,sid,"return document.querySelector('article.ayah .verse')?.textContent")
        check(displayed==RAW.decode('utf-8').splitlines()[0].split('|',2)[2],
              'Lookup changed Unicode source text')
        check(script(driver,sid,"return document.querySelectorAll('article.ayah img').length")==0,
              'XSS: malicious HTML parsed instead of displayed as text')
        check(script(driver,sid,"return document.querySelector('article.ayah').textContent.includes('ليس آية قرآنية')"),
              'Invented text not flagged as synthetic')
        script(driver,sid,"document.querySelector('#query').value='سلام';document.querySelector('#fold-marks').click();document.querySelector('#search-form button').click();")
        wait(driver,sid,"return document.querySelector('#feedback').textContent.includes('1') && document.querySelectorAll('article.ayah').length===1")
        check(script(driver,sid,"return document.querySelector('article.ayah .verse').textContent")==displayed,
              'Diacritic-insensitive search returned modified text')
        script(driver,sid,"document.querySelector('#notice-details summary').click()")
        wait(driver,sid,"return document.querySelector('#source-notice').textContent.includes('اصطناعية')")
        request(driver+'/session/'+sid+'/window/rect','POST',{'width':390,'height':840})
        dims=script(driver,sid,"return {width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,dir:getComputedStyle(document.body).direction}")
        check(dims['dir']=='rtl' and dims['scroll']<=dims['width']+1,
              'Mobile RTL layout overflows horizontally: '+str(dims))
        try:
            request(website+'api/status',headers={'Host':'attacker.example'})
        except urllib.error.HTTPError as err:
            check(err.code==403,'Wrong status for hostile Host')
        else:
            raise AssertionError('Host spoofing not blocked')
        print(json.dumps({'result':'PASS','browser':'actual_headless_chrome',
              'source':'synthetic_only','rtl':True,'mobile_rtl':True,
              'exact_text_preserved':True,'html_injection_blocked':True,
              'github_corpus_downloaded':False,'source_authenticated':False,
              'rights_verified':False},sort_keys=True))
    finally:
        if sid:
            try:
                request(driver+'/session/'+sid,'DELETE')
            except Exception:
                pass
        process.terminate()
        try:
            process.wait(timeout=4)
        except subprocess.TimeoutExpired:
            process.kill()
        webserver.shutdown()
        webserver.server_close()
        serverthread.join(timeout=3)

if __name__=='__main__':
    main()
