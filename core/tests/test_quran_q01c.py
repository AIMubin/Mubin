"""Q0.1c red-first local reader tests; no certified Quran source."""
import hashlib
import http.client
import json
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from urllib.parse import quote
from engines.quran.q01b.tanzil import load_raw
from engines.quran.q01c.reader import build_http_server

ROOT=Path(__file__).resolve().parents[2]
RAW=('1|1|سَلَامٌ مختبر\n1|2|نَصٌّ تجريبي\n2|1|بَحْثٌ اصطناعي\n').encode('utf-8')
MANIFEST={'contract':'mubin-quran-q01b-verbatim-source-v1',
'source_kind':'synthetic_fixture','source_id':'synthetic:q01b',
'source_url':None,'source_commit':None,'source_git_blob_sha1':None,
'raw_sha256':hashlib.sha256(RAW).hexdigest(),'raw_byte_count':len(RAW),
'coverage':'partial','reading':'hafs_an_asim_kufan',
'rights_status':'requires_use_review','authority_status':'not_authenticated'}

class ReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        idx=load_raw(json.dumps(MANIFEST).encode(),RAW)
        cls.idx=idx
        cls.server=build_http_server(idx,RAW,port=0)
        cls.port=cls.server.server_port
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=4)
    def request(self,path,method='GET',headers=None):
        c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=5)
        try:
            c.request(method,path,headers=headers or {})
            r=c.getresponse()
            return r.status,dict(r.getheaders()),r.read()
        finally:c.close()
    def test_loopback_bound(self):
        self.assertEqual('127.0.0.1',self.server.server_address[0])
    def test_metadata_is_unverified(self):
        s,h,b=self.request('/api/status');self.assertEqual(200,s)
        j=json.loads(b)
        self.assertEqual(3,j['verse_count'])
        self.assertEqual('synthetic_fixture',j['source_kind'])
        for k in ('rights_verified','source_authenticated','eligible_for_religious_ruling'):
            self.assertFalse(j[k])
        self.assertNotIn('Access-Control-Allow-Origin',h)
    def test_reference_returns_verbatim(self):
        s,h,b=self.request('/api/get?ref=1%3A1')
        self.assertEqual(200,s);self.assertEqual('سَلَامٌ مختبر',json.loads(b)['result']['text'])
        self.assertEqual('application/json; charset=utf-8',h['Content-Type'])
    def test_absent_partial_ref_not_fabricated(self):
        s,_,b=self.request('/api/get?ref=1%3A7')
        self.assertEqual(200,s)
        self.assertEqual({'found':False,'reference':'1:7'},json.loads(b)['result'])
    def test_exact_vs_marks_fold_search(self):
        q=quote('سلام',safe='')
        s,_,b=self.request('/api/find?q='+q+'&mode=exact')
        self.assertEqual(200,s);self.assertEqual([],json.loads(b)['results'])
        s,_,b=self.request('/api/find?q='+q+'&mode=folded&limit=5')
        self.assertEqual(200,s)
        self.assertEqual('سَلَامٌ مختبر',json.loads(b)['results'][0]['text'])
    def test_only_marks_query_does_not_match_everything(self):
        s,_,b=self.request('/api/find?q='+quote('ً',safe='')+'&mode=folded')
        self.assertEqual(400,s)
        self.assertNotIn('سَلَامٌ',b.decode())
    def test_synthetic_source_notice_cannot_fake_copyright(self):
        s,_,b=self.request('/api/notice')
        self.assertEqual(200,s)
        j=json.loads(b);self.assertFalse(j['from_verified_publisher'])
        self.assertEqual('synthetic_fixture',j['source_kind'])
        self.assertNotIn('Tanzil Quran Text (Uthmani',j['notice'])
    def test_page_content_has_clear_attribution_and_safe_js(self):
        s,h,b=self.request('/');self.assertEqual(200,s)
        self.assertIn('https://tanzil.net',b.decode())
        self.assertIn('تجريبي',b.decode())
        self.assertIn('reader.js',b.decode())
        s,_,b=self.request('/reader.js');self.assertEqual(200,s)
        self.assertIn('textContent',b.decode())
        self.assertNotIn('innerHTML',b.decode())
        self.assertNotIn('eval(',b.decode())
        s,_,_=self.request('/reader.css');self.assertEqual(200,s)
    def test_security_headers_no_cors(self):
        for path in ('/','/reader.js','/api/get?ref=1%3A1'):
            with self.subTest(path=path):
                s,h,_=self.request(path);self.assertEqual(200,s)
                self.assertIn("default-src 'none'",h['Content-Security-Policy'])
                self.assertEqual('no-store',h['Cache-Control'])
                self.assertEqual('nosniff',h['X-Content-Type-Options'])
                self.assertEqual('no-referrer',h['Referrer-Policy'])
                self.assertNotIn('Access-Control-Allow-Origin',h)
    def test_dns_rebinding_host_rejected(self):
        for h in ('evil.example','127.0.0.2','0.0.0.0','127.0.0.1:9999','localhost.invalid'):
            with self.subTest(host=h):
                self.assertEqual(403,self.request('/api/status',headers={'Host':h})[0])
    def test_cross_site_origin_rejected(self):
        for origin in ('null','https://attacker.example','http://localhost:9999'):
            self.assertEqual(403,self.request('/api/status',headers={'Origin':origin})[0])
    def test_bad_and_duplicate_params(self):
        for path in ('/api/get?ref=1%3A1&ref=2%3A1','/api/get?ref=1%3A1&extra=1',
            '/api/status?x=1','/api/find?q=a&q=b','/api/find?q=x&mode=folded&mode=exact',
            '/api/get','/api/find','/api/get?ref=01%3A1','/?foo=bar',
            '/api/get?ref=1%3A1%0A','/api/get?ref=1%3A1%ZZ',
            '/api/find?q=%FF','/api/find?q=%ED%A0%80',
            '/api/find?q=x&limit=01','/api/find?q=x&limit=100000',
            '/api/find?q=x&mode=magic'):
            with self.subTest(path=path):
                self.assertEqual(400,self.request(path)[0])
    def test_route_404_no_source_dump(self):
        for p in ('/LICENSE','/../core/tests/test_quran_q01b.py','/api/other','/source'):
            s,_,b=self.request(p)
            self.assertEqual(404,s)
            self.assertNotIn(b'contract',b)
    def test_no_write_requests(self):
        for method in ('POST','PUT','PATCH','DELETE'):
            self.assertEqual(405,self.request('/api/get?ref=1%3A1',method=method)[0])
    def test_query_length_bound(self):
        self.assertEqual(414,self.request('/api/find?q='+'a'*2000)[0])
    def test_cli_cannot_bind_remote(self):
        r=subprocess.run([sys.executable,'-m','engines.quran.q01c','--bind','0.0.0.0'],
                         cwd=ROOT,capture_output=True,text=True,timeout=10)
        self.assertNotEqual(0,r.returncode)
    def test_workflow_contract(self):
        wf=(ROOT/'.github/workflows/mubin-quran-q01c.yml').read_text('utf8')
        self.assertIn('core/tests/test_quran_q01c.py',wf)
        self.assertIn('engines/quran/q01c/**',wf)
        self.assertIn('python -m unittest discover',wf)
        self.assertNotIn('git push',wf)

if __name__=='__main__':unittest.main()
