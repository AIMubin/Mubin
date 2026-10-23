"""Q0.1b: synthetic-only unit tests and live mirror integration CI (separate)."""
from __future__ import annotations
import copy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from engines.quran.q01b.tanzil import (
    _BLOB,_COMMIT,_URL,MAX_RAW_BYTES,RawSourceError,
    load_raw,read_regular_file,assess_raw,
)
ROOT=Path(__file__).resolve().parents[2]
SRC=b'1|1|\xd8\xb3\xd9\x8e\xd9\x84\xd9\x8e\xd8\xa7\xd9\x85\xd9\x8c \xd9\x85\xd8\xaa\xd8\xad\xd8\xa7\xd9\x86\xd9\x8c\n1|2|\xd8\xa7\xd9\x84\xd9\x86\xd8\xb5 \xd8\xa7\xd9\x84\xd8\xa7\xd8\xb5\xd8\xb7\xd9\x86\xd8\xa7\xd8\xb9\xd9\x8a\n2|1|\xd8\xa8\xd8\xad\xd8\xab \xd8\xa7\xd8\xb5\xd8\xb7\xd9\x86\xd8\xa7\xd8\xb9\xd9\x8a\n2|2|\xd9\x85\xd8\xab\xd8\xa7\xd9\x84 \xd8\xa7\xd8\xae\xd8\xaa\xd8\xa8\xd8\xa7\xd8\xb1\xd9\x8a\n'

def fixture(raw=SRC):
    m={
        'contract':'mubin-quran-q01b-verbatim-source-v1',
        'source_kind':'synthetic_fixture',
        'source_id':'synthetic:q01b','source_url':None,'source_commit':None,
        'source_git_blob_sha1':None,'raw_sha256':sha256(raw).hexdigest(),
        'raw_byte_count':len(raw),'coverage':'partial',
        'reading':'hafs_an_asim_kufan',
        'rights_status':'requires_use_review','authority_status':'not_authenticated',
    }
    return m

def encoded(obj):
    return (json.dumps(obj,ensure_ascii=True,sort_keys=True,separators=(',',':'))+'\n').encode()

class Q01bSourceTests(unittest.TestCase):
    def setUp(self):
        self.m=fixture()
        self.idx=load_raw(encoded(self.m),SRC)

    def invalid(self,manifest=None,raw=SRC):
        x=assess_raw(encoded(self.m if manifest is None else manifest),raw)
        self.assertFalse(x['valid_metadata'],x)
        self.assertFalse(x['source_authenticated'])

    def test_synthetic_numbered_verses_and_source_provenance(self):
        r=self.idx.report()
        self.assertEqual(4,r['verse_count'])
        self.assertEqual(2,r['chapter_count'])
        self.assertEqual(sha256(SRC).hexdigest(),r['raw_sha256'])
        for k in ('rights_verified','source_authenticated','official_tanzil_bytes_independently_verified',
                  'eligible_for_religious_ruling'):
            self.assertFalse(r[k])
        self.assertEqual('سَلَامٌ متحانٌ',self.idx.get('1:1')['text'])
        self.assertEqual({'found':False,'reference':'114:6'},self.idx.get('114:6'))

    def test_search_keeps_verbatim_in_memory(self):
        self.assertEqual([],self.idx.find('سلام'))
        match=self.idx.find('سلام',fold_marks=True)
        self.assertEqual(1,len(match))
        self.assertEqual('سَلَامٌ متحانٌ',match[0]['text'])
        self.assertEqual(4,len(self.idx.verses))

    def test_reject_diacritic_only_query_and_invalid_options(self):
        for q in ('\u064e','\u06d6','\u064e\u0651'):
            with self.subTest(query=q),self.assertRaises(RawSourceError):
                self.idx.find(q,fold_marks=True)
        for q in ('',' ','a'*300,'\ud800'):
            with self.subTest(query=repr(q)),self.assertRaises(RawSourceError):self.idx.find(q)
        for opt in (True, '4', 0,101,1.5):
            with self.subTest(value=opt),self.assertRaises(RawSourceError):
                self.idx.find('سلام',limit=opt)

    def test_get_rejects_noncanonical_reference(self):
        for ref in ('01:1','1:01','115:1','1:8','1:1\n','2:0','-1:2',True,None):
            with self.subTest(ref=ref),self.assertRaises(RawSourceError):self.idx.get(ref)

    def test_byte_changes_break_digest_and_no_automatic_repair(self):
        for raw in (SRC+b' ',SRC.replace(b'\n',b'\r\n'),SRC[:-1],SRC.replace(b'1|1|',b'1|2|',1)):
            with self.subTest(tail=raw[-12:]):self.invalid(raw=raw)

    def test_changed_source_and_changed_self_hash_never_create_authority(self):
        raw=SRC.replace('متحان'.encode(), 'اختبار'.encode())
        m=fixture(raw)
        result=load_raw(encoded(m),raw).report()
        self.assertFalse(result['source_authenticated'])
        self.assertFalse(result['rights_verified'])

    def test_out_of_order_duplicate_invalid_records(self):
        lines=SRC.splitlines(keepends=True)
        for raw in (b''.join(reversed(lines)),lines[0]*2+b''.join(lines[1:]),
                    b'1|0|'+lines[0].split(b'|',2)[-1]+b''.join(lines[1:]),
                    b'115|1|'+lines[0].split(b'|',2)[-1]+b''.join(lines[1:]),
                    b'1|1|English\n'+b''.join(lines[1:])):
            m=fixture(raw)
            with self.subTest(raw=raw[:20]),self.assertRaises(RawSourceError):
                load_raw(encoded(m),raw)

    def test_reject_extra_comment_or_duplicate_with_recomputed_hash(self):
        for raw in (SRC+b'\\n', SRC+b'# external editorial text\\n',
                    SRC.replace(b'2|2|',b'2|1|',1)):
            with self.subTest(tail=raw[-40:]),self.assertRaises(RawSourceError):
                load_raw(encoded(fixture(raw)),raw)

    def test_partial_snapshot_can_grow_with_valid_coordinates_but_stays_unverified(self):
        expanded=SRC+'2|3|نص إضافي\n'.encode('utf-8')
        idx=load_raw(encoded(fixture(expanded)),expanded)
        self.assertEqual(5,idx.report()['verse_count'])
        self.assertFalse(idx.report()['source_authenticated'])
        self.assertFalse(idx.report()['rights_verified'])

    def test_attempt_source_authentication_or_rights_laundering(self):
        for key,value in [('rights_status','approved'),('authority_status','authenticated'),
                          ('source_authenticated',True),('source_kind','provider_verified'),
                          ('coverage','complete_hafs_kufan'),('source_id','external:quran'),
                          ('raw_byte_count',0),('raw_sha256','f'*64),('source_url','https://untrusted.example')]:
            m=copy.deepcopy(self.m);m[key]=value
            with self.subTest(key=key),self.assertRaises(RawSourceError):load_raw(encoded(m),SRC)

    def test_mirror_requires_both_pins_not_just_asserted_sha256(self):
        m=copy.deepcopy(self.m)
        m.update(source_kind='unverified_github_mirror',source_id='mirror:acfatah-tanzil-uthmani-v1.1',
                 coverage='complete_hafs_kufan',source_url=_URL,source_commit=_COMMIT,
                 source_git_blob_sha1=_BLOB)
        for key,value in [('source_commit','f'*40),('source_git_blob_sha1','f'*40),
                          ('source_url','https://example.com/x')]:
            altered=copy.deepcopy(m);altered[key]=value
            with self.subTest(key=key),self.assertRaises(RawSourceError):
                load_raw(encoded(altered),SRC)
        # Even an entirely self-consistent synthetic source cannot be relabeled
        # as the pinned 6236-verse GitHub mirror.
        with self.assertRaises(RawSourceError):load_raw(encoded(m),SRC)

    def test_manifest_unknown_fields_bom_nan_duplicate_keys(self):
        for raw in [b'\xef\xbb\xbf'+encoded(self.m),
                    encoded(self.m).replace(b'"reading":',b'"reading":"foo","reading":',1),
                    encoded(self.m).replace(b'"raw_byte_count":',b'"raw_byte_count":NaN,"_":',1),
                    b'[]',b'not json']:
            with self.subTest(prefix=raw[:20]),self.assertRaises(RawSourceError):load_raw(raw,SRC)

    def test_manifest_immutable(self):
        with self.assertRaises(TypeError):self.idx.manifest['source_id']='real'
        self.assertEqual('synthetic:q01b',self.idx.get('1:1')['source_id'])

    def test_read_regular_file_blocks_symlink_and_unreadable(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'corpus.txt';p.write_bytes(SRC)
            self.assertEqual(SRC,read_regular_file(p,1024))
            with self.assertRaises(RawSourceError):read_regular_file(p,3)
            link=Path(d)/'alias';link.symlink_to(p)
            with self.assertRaises(RawSourceError):read_regular_file(link,1024)
            with self.assertRaises(RawSourceError):read_regular_file(Path(d),1024)

    def test_cli_synthetic_verify_get_find_and_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            mp=Path(d)/'manifest.json';mp.write_bytes(encoded(self.m))
            cp=Path(d)/'corpus.txt';cp.write_bytes(SRC)
            base=[sys.executable,'-m','engines.quran.q01b','--manifest',str(mp),'--source',str(cp),'--json']
            for suffix in (['verify'],['get','1:1'],['find','سلام','--fold-marks']):
                p=subprocess.run(base+suffix,capture_output=True,text=True,cwd=ROOT,timeout=10)
                self.assertEqual(0,p.returncode,p.stderr+p.stdout)
                self.assertFalse(json.loads(p.stdout)['source_authenticated'])
            p=subprocess.run(base+['get','1:8'],capture_output=True,text=True,cwd=ROOT,timeout=10)
            self.assertEqual(1,p.returncode)
            mp.unlink()
            p=subprocess.run(base+['verify'],capture_output=True,text=True,cwd=ROOT,timeout=10)
            self.assertEqual(2,p.returncode)

    def test_mirror_manifest_preserves_pinned_head_git_blob_and_no_rights_assumption(self):
        src=ROOT/'engines/quran/q01b/sources/tanzil-mirror-v1.1.json'
        obj=json.loads(src.read_text(encoding='utf-8'))
        self.assertEqual(_COMMIT,obj['source_commit'])
        self.assertEqual(_BLOB,obj['source_git_blob_sha1'])
        self.assertEqual(_URL,obj['source_url'])
        self.assertEqual('not_authenticated',obj['authority_status'])
        self.assertEqual('requires_use_review',obj['rights_status'])
        self.assertEqual('complete_hafs_kufan',obj['coverage'])
        self.assertEqual('unverified_github_mirror',obj['source_kind'])

    def test_workflow_does_not_commit_raw_quran_text_and_restricts_source(self):
        text=(ROOT/'.github/workflows/mubin-quran-q01b.yml').read_text()
        self.assertIn('data/quran-uthmani.txt',text)
        self.assertIn(_COMMIT,text)
        self.assertIn('python -m engines.quran.q01b',text)
        self.assertIn('core/tests/test_quran_q01b.py',text)
        self.assertNotIn('git push',text)

if __name__=='__main__':unittest.main()
