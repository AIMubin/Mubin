"""Q0.1d: compare Q0.1b byte-pinned mirror to a caller-provided, UNTRUSTED candidate.

No official Tanzil bytes or independent publisher attestation in these tests.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from engines.quran.q01d.compare import compare_raw, CandidateError, parse_numbered_candidate
from engines.quran.q01b.tanzil import load_raw

ROOT=Path(__file__).resolve().parents[2]
MIRROR = '1|1|سَلَامٌ صنْعي\n1|2|نص تجريبي\n2|1|مثال تعليمي\n'.encode('utf8')

def manifest(raw=MIRROR):
    return json.dumps({'contract':'mubin-quran-q01b-verbatim-source-v1',
        'source_kind':'synthetic_fixture','source_id':'synthetic:q01b',
        'source_url':None,'source_commit':None,'source_git_blob_sha1':None,
        'raw_sha256':hashlib.sha256(raw).hexdigest(),'raw_byte_count':len(raw),
        'coverage':'partial','reading':'hafs_an_asim_kufan',
        'rights_status':'requires_use_review','authority_status':'not_authenticated'},
        ensure_ascii=False).encode('utf8')

class Q01dCandidateTests(unittest.TestCase):
    def test_byte_identical_still_not_authenticated(self):
        x=compare_raw(manifest(),MIRROR,MIRROR)
        self.assertEqual('byte_identical',x['comparison'])
        self.assertTrue(x['byte_equal'])
        self.assertTrue(x['verse_text_equal'])
        self.assertEqual(3,x['candidate_verse_count'])
        self.assertEqual([],x['differing_refs'])
        for k in ('source_authenticated','official_candidate_attested','rights_verified','candidate_publisher_provenance_verified','eligible_for_religious_ruling'):
            self.assertFalse(x[k],k)

    def test_changed_one_verse_is_recorded_not_silently_fixed(self):
        changed=MIRROR.replace('مثال تعليمي'.encode(),'نص مختلف'.encode())
        x=compare_raw(manifest(),MIRROR,changed)
        self.assertEqual('verse_text_differs',x['comparison'])
        self.assertFalse(x['verse_text_equal'])
        self.assertFalse(x['byte_equal'])
        self.assertEqual(1,x['differing_verse_count'])
        self.assertEqual(['2:1'],x['differing_refs'])
        self.assertNotIn('نص مختلف',repr(x))
        self.assertEqual(changed,changed) # candidate bytes stay caller-owned; no correction

    def test_different_footer_same_verses_not_promoted(self):
        with_footer=MIRROR+b'\n# provenance sample\n'
        x=compare_raw(manifest(),MIRROR,with_footer)
        self.assertEqual('verse_equal_bytes_different',x['comparison'])
        self.assertTrue(x['verse_text_equal'])
        self.assertFalse(x['byte_equal'])
        self.assertFalse(x['official_candidate_attested'])

    def test_excess_and_missing_verses_are_rejected(self):
        for candidate in (MIRROR.replace(b'2|1|',b'2|2|'),MIRROR.splitlines(keepends=True)[0],
                          MIRROR+MIRROR.splitlines(keepends=True)[-1],
                          MIRROR.replace(b'1|2|',b'1|1|'),
                          MIRROR.replace(b'1|2|',b'3|999|')):
            with self.subTest(candidate=candidate[-30:]),self.assertRaises(CandidateError):
                compare_raw(manifest(),MIRROR,candidate)

    def test_surrogate_bom_crlf_and_unsigned_comment_rejected(self):
        for candidate in (b'\xef\xbb\xbf'+MIRROR,MIRROR.replace(b'\n',b'\r\n'),
                          MIRROR.replace('مثال تعليمي'.encode(),b'\\ud800'),
                          MIRROR+b'bad footer\n',MIRROR+b'#bad footer\n2|2|bad\n',
                          MIRROR.rstrip(b'\n'),
                          MIRROR+b'\n# foo\n\n# bar\n\n\n\n\n'):
            with self.subTest(candidate=candidate[-60:]),self.assertRaises(CandidateError):
                compare_raw(manifest(),MIRROR,candidate)

    def test_unknown_both_sides_no_external_authentication(self):
        bad=bytearray(MIRROR);bad[-3]=32
        with self.assertRaises(CandidateError):compare_raw(manifest(),bytes(bad),MIRROR)
        with self.assertRaises(CandidateError):compare_raw(manifest(),MIRROR.decode(),MIRROR)
        with self.assertRaises(CandidateError):compare_raw(manifest(),MIRROR,[])

    def test_bounded_mismatch_list_but_total_count_exact(self):
        changed=MIRROR.replace('سَلَامٌ صنْعي'.encode(),'لغة تجريبية'.encode()).replace('مثال تعليمي'.encode(),'نص مختلف'.encode())
        x=compare_raw(manifest(),MIRROR,changed,limit_refs=1)
        self.assertEqual(2,x['differing_verse_count'])
        self.assertEqual(1,len(x['differing_refs']))
        self.assertTrue(x['refs_truncated'])
        for val in (0,True,101,'1',1.2):
            with self.subTest(limit=val),self.assertRaises(CandidateError):
                compare_raw(manifest(),MIRROR,MIRROR,limit_refs=val)

    def test_cli_untrusted_comparison_json_and_no_stdout_verses(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            (d/'m.json').write_bytes(manifest())
            (d/'mirror.txt').write_bytes(MIRROR)
            (d/'candidate.txt').write_bytes(MIRROR)
            args=[sys.executable,'-m','engines.quran.q01d','--manifest',str(d/'m.json'),
                '--mirror',str(d/'mirror.txt'),'--candidate',str(d/'candidate.txt'),'--json']
            run=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,timeout=15)
            self.assertEqual(0,run.returncode,run.stdout+run.stderr)
            self.assertNotIn('سَلَامٌ',run.stdout)
            x=json.loads(run.stdout)
            self.assertEqual('byte_identical',x['comparison'])
            self.assertFalse(x['candidate_publisher_provenance_verified'])
            (d/'candidate.txt').write_bytes(MIRROR+b'2|2|hi\n')
            invalid=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,timeout=15)
            self.assertEqual(1,invalid.returncode,invalid.stdout+invalid.stderr)
            (d/'candidate.txt').unlink()
            missing=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,timeout=15)
            self.assertEqual(2,missing.returncode,missing.stdout+missing.stderr)

    def test_metadata_does_not_have_authority_override(self):
        x=compare_raw(manifest(),MIRROR,MIRROR)
        for prohibited in ('official_source_verified','publisher_authentication','approve','human_verified'):
            self.assertNotIn(prohibited,x)
        self.assertEqual('operator_supplied_unverified',x['candidate_provenance'])

    def test_no_online_fetch_or_write_to_corpus_in_adapter(self):
        doc=(ROOT/'engines/quran/q01d/compare.py').read_text(encoding='utf-8')
        for token in ('requests.get(', 'urllib.request.urlopen(', 'subprocess.run(', 'os.system('):
            self.assertNotIn(token,doc)
        self.assertIn('Tanzil', (ROOT/'docs/research/QURAN-Q01D-COMPARISON.md').read_text(encoding='utf-8'))

if __name__=='__main__':unittest.main()