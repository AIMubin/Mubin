"""Fail-closed Q0.1 prototype: a reader of pinned snapshot bytes, not a mushaf authority."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from engines.quran.q01.engine import (SnapshotError, load_snapshot, verse_counts, assess_snapshot)

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / 'engines/quran/fixtures'
M = (FIX/'q01-manifest-synthetic.json').read_bytes()
C = (FIX/'q01-verses-synthetic.json').read_bytes()

def encode(v):
    return (json.dumps(v, ensure_ascii=True, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')

def update_manifest(manifest, corpus):
    x=copy.deepcopy(manifest)
    x['raw_sha256']=hashlib.sha256(corpus).hexdigest()
    x['declared_verse_count']=len(json.loads(corpus)['verses'])
    return encode(x)

class Q01Tests(unittest.TestCase):
    def setUp(self):
        self.manifest=json.loads(M)
        self.corpus=json.loads(C)
        self.index=load_snapshot(M,C)

    def test_snapshot_structural_and_authenticity_boundaries(self):
        x=assess_snapshot(M,C)
        self.assertTrue(x['valid_metadata'],x)
        self.assertEqual(4,x['loaded_verse_count'])
        self.assertEqual('synthetic_fixture_only',x['scope'])
        for k in ('source_authenticated','rights_verified','canonical_corpus_qualified','eligible_for_religious_ruling'):
            self.assertFalse(x[k],k)
        self.assertEqual(hashlib.sha256(C).hexdigest(),x['raw_sha256'])

    def test_exact_reference_returns_original_text_and_source_id(self):
        r=self.index.get('1:1')
        self.assertTrue(r['found'])
        self.assertEqual(self.corpus['verses'][0]['text'],r['text'])
        self.assertEqual('synthetic:q01',r['source_id'])
        self.assertFalse(r['source_authenticated'])

    def test_unknown_reference_returns_not_found_not_fabrication(self):
        self.assertEqual({'found':False,'reference':'1:7'},self.index.get('1:7'))
        self.assertEqual({'found':False,'reference':'114:6'},self.index.get('114:6'))
        for key in ('0:1','1:0','115:1','01:1','1:01','1:1\n','1:-1','1: 1','1:9999'):
            with self.subTest(key=repr(key)):
                with self.assertRaises(SnapshotError):self.index.get(key)

    def test_search_verbatim_and_diacritic_insensitive_query_only(self):
        raw=self.corpus['verses'][0]['text']
        exact=self.index.find('سَلَامٌ',match='exact',limit=10)
        self.assertEqual(1,len(exact))
        self.assertEqual(raw,exact[0]['text'])
        self.assertEqual([],self.index.find('سلام',match='exact',limit=10))
        no_marks=self.index.find('سلام',match='arabic_marks_insensitive',limit=10)
        self.assertEqual(1,len(no_marks))
        self.assertEqual(raw,no_marks[0]['text'])
        self.assertFalse(no_marks[0]['source_authenticated'])

    def test_search_keeps_hamza_and_source_script(self):
        self.assertEqual([],self.index.find('امانة',match='arabic_marks_insensitive',limit=10))
        self.assertEqual(1,len(self.index.find('أمانة',match='arabic_marks_insensitive',limit=10)))
        for key in ('','  ','\ud800','a'*2048):
            with self.subTest(key=repr(key)):
                with self.assertRaises(SnapshotError):self.index.find(key)
        for m in ('fold_all','NFKC','root'):
            with self.assertRaises(SnapshotError):self.index.find('سلام',match=m)
        for lim in (0,101,True,'1',1.5):
            with self.assertRaises(SnapshotError):self.index.find('سلام',limit=lim)

    def test_tamper_text_or_whitespace_breaks_raw_pin(self):
        for b in (C.replace('تجريبي'.encode(), 'اختباري'.encode(),1), C+b' ',C.replace(b'\n',b'\r\n')):
            with self.subTest(b=b[-35:]):
                with self.assertRaises(SnapshotError):load_snapshot(M,b)

    def test_manually_updated_hash_does_not_grant_authority(self):
        c=copy.deepcopy(self.corpus)
        c['verses'][0]['text']='نص معدل غير مصدّق'
        new=encode(c)
        idx=load_snapshot(update_manifest(self.manifest,new),new)
        self.assertEqual('نص معدل غير مصدّق',idx.get('1:1')['text'])
        self.assertFalse(idx.get('1:1')['source_authenticated'])

    def test_duplicate_out_of_order_and_invalid_ayahs_fail(self):
        for change in ('dup','reverse','zero','out_of_range','wrongtype','surah_bool','text_empty','text_english'):
            c=copy.deepcopy(self.corpus)
            if change=='dup':c['verses'][1]['surah'],c['verses'][1]['ayah']=1,1
            if change=='reverse':c['verses'].reverse()
            if change=='zero':c['verses'][0]['ayah']=0
            if change=='out_of_range':c['verses'][0]['surah']=115
            if change=='wrongtype':c['verses'][0]['ayah']='1'
            if change=='surah_bool':c['verses'][0]['surah']=True
            if change=='text_empty':c['verses'][0]['text']=''
            if change=='text_english':c['verses'][0]['text']='not quran'
            b=encode(c)
            with self.subTest(change=change),self.assertRaises(SnapshotError):
                load_snapshot(update_manifest(self.manifest,b),b)

    def test_forbid_extra_fields_and_claiming_authority(self):
        changes=[('manifest','source_authenticated',True),('manifest','rights_status','verified'),
                 ('manifest','authority_status','verified'),('manifest','root_sha256','a'*64),
                 ('corpus','editorial_note','hidden payload')]
        for kind,key,value in changes:
            m,c=copy.deepcopy(self.manifest),copy.deepcopy(self.corpus)
            (m if kind=='manifest' else c)[key]=value
            cb=encode(c)
            with self.subTest(kind=kind,key=key),self.assertRaises(SnapshotError):
                load_snapshot(update_manifest(m,cb),cb)

    def test_duplicate_members_and_nonfinite_rejected(self):
        samples=[C.replace(b'"verses":',b'"verses":[],"verses":',1),
                 C.replace(b'"ayah":1',b'"ayah":NaN',1),
                 C.replace(b'"ayah":1',b'"ayah":Infinity',1)]
        for b in samples:
            with self.assertRaises(SnapshotError):load_snapshot(update_manifest(self.manifest,b),b)

    def test_unicode_surrogates_and_control_characters_are_rejected(self):
        for val in ('\ud800','سطر\nغير صحيح','ص\u202e\u202c','\u0000'):
            c=copy.deepcopy(self.corpus);c['verses'][0]['text']=val
            b=encode(c)
            with self.subTest(val=repr(val)),self.assertRaises(SnapshotError):
                load_snapshot(update_manifest(self.manifest,b),b)

    def test_non_plain_containers_not_accepted(self):
        class Spoof(dict):
            def __eq__(self,other):return True
        # Programmatic interface must also reject untrusted subclasses (no JSON parser involved).
        from engines.quran.q01.engine import validate_parsed
        with self.assertRaises(SnapshotError):validate_parsed(Spoof(self.manifest),self.corpus)
        with self.assertRaises(SnapshotError):validate_parsed(self.manifest, Spoof(self.corpus))
        c=copy.deepcopy(self.corpus);c['verses'][0]=Spoof(c['verses'][0])
        with self.assertRaises(SnapshotError):validate_parsed(self.manifest,c)

    def test_manifest_declared_count_and_full_corpus_requirements(self):
        m=copy.deepcopy(self.manifest);m['declared_verse_count']=5
        with self.assertRaises(SnapshotError):load_snapshot(encode(m),C)
        m=copy.deepcopy(self.manifest);m['coverage']='complete_hafs_kufan'
        with self.assertRaises(SnapshotError):load_snapshot(encode(m),C)
        self.assertEqual(114,len(verse_counts()))
        self.assertEqual(6236,sum(verse_counts()))

    def test_cannot_mix_tafsir_or_readings_in_corpus(self):
        for key,value in [('tafsir','model explanation'),('translation','English'),('reading','warsh'),('page_number',1)]:
            c=copy.deepcopy(self.corpus);c['verses'][0][key]=value;b=encode(c)
            with self.subTest(key=key),self.assertRaises(SnapshotError):load_snapshot(update_manifest(self.manifest,b),b)
        m=copy.deepcopy(self.manifest);m['reading']='warsh'
        with self.assertRaises(SnapshotError):load_snapshot(encode(m),C)

    def test_report_never_infers_authenticity(self):
        m=copy.deepcopy(self.manifest);m['source_kind']='external_unverified'
        m['source_id']='external:unverified:fixture'
        m['provider_url']='https://example.org/source'
        loaded=load_snapshot(encode(m),C)
        self.assertEqual('external_unverified_snapshot',loaded.report()['scope'])
        self.assertFalse(loaded.report()['source_authenticated'])
        self.assertFalse(loaded.report()['rights_verified'])

    def test_cli_verify_get_and_find_json(self):
        for suffix in (['verify'],['get','1:1'],['find','سلام','--match','arabic_marks_insensitive']):
            cmd=[sys.executable,'-m','engines.quran.q01','--manifest',str(FIX/'q01-manifest-synthetic.json'),
                 '--corpus',str(FIX/'q01-verses-synthetic.json'),'--json']+suffix
            p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=15)
            self.assertEqual(0,p.returncode,p.stderr+p.stdout)
            a=json.loads(p.stdout)
            self.assertFalse(a.get('source_authenticated',False))

    def test_cli_bad_metadata_exit_one(self):
        with tempfile.TemporaryDirectory() as d:
            c=Path(d)/'corpus.json';c.write_bytes(C+b' ')
            p=subprocess.run([sys.executable,'-m','engines.quran.q01','--manifest',str(FIX/'q01-manifest-synthetic.json'),
                 '--corpus',str(c),'--json','verify'],cwd=ROOT,capture_output=True,text=True,timeout=15)
            self.assertEqual(1,p.returncode,p.stderr+p.stdout)

    def test_cli_unsafe_input_exit_two(self):
        with tempfile.TemporaryDirectory() as d:
            link=Path(d)/'symlink.json';link.symlink_to(FIX/'q01-verses-synthetic.json')
            p=subprocess.run([sys.executable,'-m','engines.quran.q01','--manifest',str(FIX/'q01-manifest-synthetic.json'),
                 '--corpus',str(link),'--json','verify'],cwd=ROOT,capture_output=True,text=True,timeout=15)
            self.assertEqual(2,p.returncode,p.stderr+p.stdout)
            p=subprocess.run([sys.executable,'-m','engines.quran.q01','--manifest',str(FIX/'missing.json'),
                 '--corpus',str(FIX/'q01-verses-synthetic.json'),'--json','verify'],cwd=ROOT,capture_output=True,text=True,timeout=15)
            self.assertEqual(2,p.returncode,p.stderr+p.stdout)

    def test_schema_matches_static_fixture_and_blocks_rogue_fields(self):
        from jsonschema import Draft202012Validator
        schema=json.loads((ROOT/'schemas/quran-q01-snapshot.schema.json').read_text(encoding='utf-8'))
        Draft202012Validator.check_schema(schema)
        for name,object in [('manifest',self.manifest),('corpus',self.corpus)]:
            self.assertEqual([],list(Draft202012Validator(schema['$defs'][name]).iter_errors(object)))
            bad=copy.deepcopy(object);bad['pretend_scholar_approval']=True
            self.assertTrue(list(Draft202012Validator(schema['$defs'][name]).iter_errors(bad)))

    def test_diacritic_only_search_must_not_match_all_verses(self):
        for query in ("\u064b", "\u064b\u0651", "\u06d6"):
            with self.subTest(query=repr(query)),self.assertRaises(SnapshotError):
                self.index.find(query,match='arabic_marks_insensitive')

    def test_loaded_provenance_cannot_be_mutated_after_validation(self):
        with self.assertRaises(TypeError):
            self.index.manifest['source_id']='external:forged-after-verification'
        self.assertEqual('synthetic:q01',self.index.get('1:1')['source_id'])

    def test_workflow_runs_scope_and_quran_cli(self):
        wf=(ROOT/'.github/workflows/mubin-quran-q01.yml').read_text(encoding='utf-8')
        self.assertIn('core/tests/test_quran_q01.py',wf)
        self.assertIn('engines/quran/**',wf)
        self.assertIn('python -m engines.quran.q01',wf)

if __name__ == '__main__':unittest.main()