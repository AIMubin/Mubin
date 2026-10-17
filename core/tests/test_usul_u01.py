"""U0.1 pre-registered synthetic Usul-like method evaluation.

This test set has NO fatwa, Qur'an/hadith corpus, source-holdout, or scholarly gold.
Cases were frozen as a JSON fixture before evaluator implementation.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from core.usul.engine import evaluate, validate_rulebook, validate_case

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "research" / "usul"
BOOK = json.loads((FIXTURES / "rulebook-synthetic.json").read_text(encoding="utf-8"))
SUITE = json.loads((FIXTURES / "test-cases-synthetic.json").read_text(encoding="utf-8"))


def tamper(rulebook, name):
    result = copy.deepcopy(rulebook)
    methods = result['methodologies']
    if name == 'duplicate_rule':
        methods[0]['rules'][1]['id'] = methods[0]['rules'][0]['id']
    elif name == 'unknown_symbol':
        methods[0]['rules'][0]['when']['args'][0]['id'] = 'unregistered_atom'
    elif name == 'too_deep':
        node = {'op':'fact','id':'a'}
        for _ in range(20):
            node={'op':'not','arg':node}
        methods[0]['rules'][0]['when']=node
    elif name == 'duplicate_methodology':
        methods[1]['id'] = methods[0]['id']
    elif name == 'unknown_op':
        methods[0]['rules'][0]['when']={'op':'eval','code':'True'}
    else:
        raise AssertionError('undeclared test tamper')
    return result


class TestUsulU01(unittest.TestCase):
    def test_fixture_is_frozen_pre_registered_contract(self):
        self.assertEqual('pre_registered_before_engine_implementation',SUITE['status'])
        self.assertEqual(40, len(SUITE['cases']))
        self.assertEqual(15, sum(x['case']['case_id'].startswith('p') for x in SUITE['cases']))
        self.assertEqual(25, sum(x['case']['case_id'].startswith('n') for x in SUITE['cases']))
        self.assertEqual(40,len({x['case']['case_id'] for x in SUITE['cases']}))
        self.assertEqual([],validate_rulebook(BOOK))

    def test_15_positives_and_25_adversarial_cases(self):
        for sample in SUITE['cases']:
            with self.subTest(case_id=sample['case']['case_id']):
                book=tamper(BOOK,sample['tamper_rulebook']) if 'tamper_rulebook' in sample else BOOK
                actual=evaluate(book,sample['case'])
                self.assertEqual(sample['expect']['status'],actual['status'],actual)
                if 'reason' in sample['expect']:
                    self.assertEqual(sample['expect']['reason'],actual['reason'],actual)
                self.assertFalse(actual['scholarly_authority_verified'])
                self.assertEqual('synthetic_logic_only',actual['scope'])
                if actual['status']=='supported':
                    self.assertIn(actual['conclusion'],('track_north','track_south'))
                    self.assertTrue(actual['active_rules'])
                    self.assertFalse(actual['pending_rules'])
                else:
                    self.assertIsNone(actual['conclusion'])

    def test_case_and_rulebook_never_mutated(self):
        origbook=copy.deepcopy(BOOK)
        original=copy.deepcopy(SUITE['cases'][0]['case'])
        first=evaluate(BOOK,original)
        second=evaluate(BOOK,original)
        self.assertEqual(first,second)
        self.assertEqual(origbook,BOOK)
        self.assertEqual(SUITE['cases'][0]['case'],original)

    def test_methods_are_isolated_with_opposing_policy(self):
        x=copy.deepcopy(SUITE['cases'][0]['case'])
        north=evaluate(BOOK,x)
        x['methodology_id']='method_b'
        south=evaluate(BOOK,x)
        self.assertEqual('supported',north['status'])
        self.assertEqual('supported',south['status'])
        self.assertEqual('track_north',north['conclusion'])
        self.assertEqual('track_south',south['conclusion'])
        self.assertTrue(all(z.startswith('a') for z in north['active_rules']))
        self.assertTrue(all(z.startswith('b') for z in south['active_rules']))

    def test_missing_premise_must_not_default_to_false(self):
        case=copy.deepcopy(SUITE['cases'][0]['case'])
        case['facts'].pop('c')
        result=evaluate(BOOK,case)
        self.assertEqual('abstain',result['status'])
        self.assertEqual('insufficient_evidence',result['reason'])
        self.assertIn('c',result['missing_facts'])

    def test_not_of_unknown_does_not_become_true(self):
        case=copy.deepcopy(SUITE['cases'][2]['case'])
        case['facts']['e']='unknown'
        result=evaluate(BOOK,case)
        self.assertEqual('abstain',result['status'])
        self.assertIn('e',result['missing_facts'])

    def test_exception_defeats_without_silent_conclusion(self):
        case=copy.deepcopy(SUITE['cases'][0]['case'])
        case['facts']['ex']='established'
        result=evaluate(BOOK,case)
        self.assertEqual('abstain',result['status'])
        self.assertIn('a1',result['defeated_rules'])
        self.assertEqual('no_applicable_rule',result['reason'])

    def test_positive_provenance_is_rule_ids_not_external_authenticity(self):
        result=evaluate(BOOK,SUITE['cases'][0]['case'])
        self.assertEqual(['a1'],result['active_rules'])
        self.assertTrue(result['rule_traces'])
        self.assertTrue(all('rule_id' in x for x in result['rule_traces']))
        self.assertNotIn('fatwa',str(result).lower())

    def test_rejects_question_or_methodology_auto_fallback(self):
        case=copy.deepcopy(SUITE['cases'][0]['case'])
        for idname, bad in [('methodology_id','Method_A'),('methodology_id',''),('question_id','bogus')]:
            with self.subTest(field=idname,value=bad):
                probe=copy.deepcopy(case);probe[idname]=bad
                self.assertEqual('invalid',evaluate(BOOK,probe)['status'])

    def test_truth_and_unknowns_are_never_inferred_from_extra_symbols(self):
        c=copy.deepcopy(SUITE['cases'][0]['case'])
        c['facts']['invented']='established'
        self.assertTrue(validate_case(c,BOOK))
        self.assertEqual('invalid',evaluate(BOOK,c)['status'])

    def test_nonjson_and_recursive_programmatic_input_fail_closed(self):
        strange=copy.deepcopy(BOOK)
        nest=[]
        for _ in range(1500):nest=[nest]
        strange['injected']=nest
        self.assertEqual('invalid',evaluate(strange,SUITE['cases'][0]['case'])['status'])
        self.assertEqual('invalid',evaluate(BOOK,{'facts':float('nan')})['status'])
        self.assertEqual('invalid',evaluate({'contract':'x'},SUITE['cases'][0]['case'])['status'])
        self.assertEqual('invalid',evaluate([],SUITE['cases'][0]['case'])['status'])

    def test_payload_bounds_and_duplicate_rule_rejected(self):
        big=copy.deepcopy(BOOK)
        big['methodologies'][0]['rules'] *= 33
        self.assertEqual('invalid',evaluate(big,SUITE['cases'][0]['case'])['status'])
        same=copy.deepcopy(BOOK)
        same['symbols'].append('a')
        self.assertTrue(validate_rulebook(same))

    def test_independent_oracle_exact_conclusions_all_15_positives(self):
        # Independently adjudicated from the declared synthetic rulebook,
        # NOT inferred from whatever the engine happened to return.
        oracle = {
            'p01':'track_north', 'p02':'track_south',
            'p03':'track_north', 'p04':'track_north',
            'p05':'track_north', 'p06':'track_north',
            'p07':'track_north', 'p08':'track_north',
            'p09':'track_south', 'p10':'track_north',
            'p11':'track_south', 'p12':'track_south',
            'p13':'track_north', 'p14':'track_north',
            'p15':'track_south',
        }
        self.assertEqual(15, len(oracle))
        for sample in SUITE['cases']:
            case = sample['case']
            if case['case_id'] in oracle:
                with self.subTest(case=case['case_id']):
                    result = evaluate(BOOK,case)
                    self.assertEqual(oracle[case['case_id']],result['conclusion'])

    def test_rule_order_must_not_change_conclusion_or_conflict(self):
        for id_ in ['p01','p02','p03','p07','p10','p13','n09','n10','n11']:
            case=next(e['case'] for e in SUITE['cases'] if e['case']['case_id']==id_)
            reordered=copy.deepcopy(BOOK)
            for method in reordered['methodologies']:
                method['rules'].reverse()
            a=evaluate(BOOK,case)
            b=evaluate(reordered,case)
            with self.subTest(case=id_):
                self.assertEqual((a['status'],a['reason'],a['conclusion'],a['missing_facts']),
                                 (b['status'],b['reason'],b['conclusion'],b['missing_facts']))

    def test_commutative_boolean_operators_and_reordering_facts(self):
        case=copy.deepcopy(SUITE['cases'][6]['case'])
        swapped=copy.deepcopy(BOOK)
        for method in swapped['methodologies']:
            for rule in method['rules']:
                expr=rule['when']
                if expr['op'] in ('all','any'):
                    expr['args'].reverse()
        baseline=evaluate(BOOK,case)
        result=evaluate(swapped,case)
        self.assertEqual((baseline['status'],baseline['conclusion']),
                         (result['status'],result['conclusion']))
        case['facts']=dict(reversed(list(case['facts'].items())))
        self.assertEqual(baseline,evaluate(BOOK,case))

    def test_false_and_unknown_and_true_or_unknown_short_circuit_correctly(self):
        a=copy.deepcopy(SUITE['cases'][0]['case'])
        a['facts']['a']='refuted'
        a['facts']['b']='unknown'
        r=evaluate(BOOK,a)
        self.assertEqual('no_applicable_rule',r['reason'])
        self.assertNotIn('b',r['missing_facts'])
        b=copy.deepcopy(SUITE['cases'][3]['case'])
        b['facts']['g']='unknown'
        r=evaluate(BOOK,b)
        self.assertEqual('supported',r['status'])
        self.assertNotIn('g',r['missing_facts'])

    def test_schema_files_and_frozen_fixture_hashes_are_present(self):
        import hashlib
        from core.usul.benchmark import FROZEN_CASES_SHA256, FROZEN_RULEBOOK_SHA256
        self.assertEqual(FROZEN_CASES_SHA256,hashlib.sha256(
            (FIXTURES/'test-cases-synthetic.json').read_bytes()).hexdigest())
        self.assertEqual(FROZEN_RULEBOOK_SHA256,hashlib.sha256(
            (FIXTURES/'rulebook-synthetic.json').read_bytes()).hexdigest())
        self.assertTrue((ROOT/'schemas/usul-u01-rulebook.schema.json').is_file())
        self.assertTrue((ROOT/'schemas/usul-u01-case.schema.json').is_file())

    def test_frozen_runner_binds_executed_objects_to_original_bytes(self):
        from core.usul.benchmark import run_frozen_suite
        from pathlib import Path
        raw_book = (FIXTURES / 'rulebook-synthetic.json').read_bytes()
        raw_cases = (FIXTURES / 'test-cases-synthetic.json').read_bytes()
        # It is not sufficient to hash the original file and execute another object.
        alternate_book = copy.deepcopy(BOOK)
        alternate_book['methodologies'][0]['rules'].reverse()
        self.assertNotEqual(BOOK, alternate_book)
        self.assertEqual('UNRECOGNIZED_RULEBOOK', run_frozen_suite(
            alternate_book, SUITE, raw_book, raw_cases)['code'])
        alternate_cases = copy.deepcopy(SUITE)
        alternate_cases['cases'].reverse()
        self.assertEqual('UNRECOGNIZED_FIXTURES', run_frozen_suite(
            BOOK, alternate_cases, raw_book, raw_cases)['code'])
        cyclic = copy.deepcopy(BOOK)
        cyclic['cycle'] = cyclic
        self.assertEqual('UNRECOGNIZED_RULEBOOK', run_frozen_suite(
            cyclic, SUITE, raw_book, raw_cases)['code'])

    def test_cli_good_and_malformed_json(self):
        normal=subprocess.run([sys.executable,'-m','core.usul',str(FIXTURES/'rulebook-synthetic.json'),str(FIXTURES/'test-cases-synthetic.json'),'--json'],cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(0,normal.returncode,(normal.stderr,normal.stdout))
        report=json.loads(normal.stdout)
        self.assertEqual(15,report['positive_passed'])
        self.assertEqual(25,report['adversarial_passed'])
        self.assertEqual(40,report['total'])
        self.assertTrue(report['passed'])
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'bad.json'
            for bad in ['{','{"contract":"x","contract":"y"}','{"x":NaN}','[[[[[[']:
                with self.subTest(input=bad):
                    path.write_text(bad,encoding='utf-8')
                    failed=subprocess.run([sys.executable,'-m','core.usul',str(path),str(FIXTURES/'test-cases-synthetic.json'),'--json'],cwd=ROOT,text=True,capture_output=True)
                    self.assertEqual(2,failed.returncode,(failed.stdout,failed.stderr))
                    self.assertEqual('INPUT_ERROR',json.loads(failed.stdout)['code'])

    def test_cli_rejects_symlinks_and_fifo_without_blocking(self):
        import os
        with tempfile.TemporaryDirectory() as td:
            directory=Path(td)
            link=directory/'link.json'
            try:
                link.symlink_to(FIXTURES/'rulebook-synthetic.json')
            except (OSError, NotImplementedError):
                pass
            else:
                failed=subprocess.run([sys.executable,'-m','core.usul',str(link),str(FIXTURES/'test-cases-synthetic.json'),'--json'],cwd=ROOT,text=True,capture_output=True,timeout=8)
                self.assertEqual(2,failed.returncode,(failed.stdout,failed.stderr))
            if hasattr(os,'mkfifo'):
                fifo=directory/'blocked.pipe'
                os.mkfifo(fifo)
                failed=subprocess.run([sys.executable,'-m','core.usul',str(fifo),str(FIXTURES/'test-cases-synthetic.json'),'--json'],cwd=ROOT,text=True,capture_output=True,timeout=8)
                self.assertEqual(2,failed.returncode,(failed.stdout,failed.stderr))

    def test_cli_rejects_lone_surrogate_and_changed_fixture_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'modified-fixtures.json'
            original=(FIXTURES/'test-cases-synthetic.json').read_text(encoding='utf-8')
            p.write_text(original+' ',encoding='utf-8')
            failed=subprocess.run([sys.executable,'-m','core.usul',str(FIXTURES/'rulebook-synthetic.json'),str(p),'--json'],cwd=ROOT,text=True,capture_output=True)
            self.assertEqual(1,failed.returncode)
            self.assertEqual('UNRECOGNIZED_FIXTURES',json.loads(failed.stdout)['code'])
            p.write_text('{"name":"\\ud800"}',encoding='utf-8')
            failed=subprocess.run([sys.executable,'-m','core.usul',str(p),str(FIXTURES/'test-cases-synthetic.json'),'--json'],cwd=ROOT,text=True,capture_output=True)
            self.assertEqual(2,failed.returncode, (failed.stdout,failed.stderr))
            self.assertEqual('INPUT_ERROR',json.loads(failed.stdout)['code'])

    def test_cli_input_cannot_claim_legitimate_juristic_verdict(self):
        bad=copy.deepcopy(SUITE['cases'][0]['case'])
        bad['facts']['copyrighted_quote']='claimed'
        self.assertEqual('invalid',evaluate(BOOK,bad)['status'])


if __name__=='__main__':unittest.main()
