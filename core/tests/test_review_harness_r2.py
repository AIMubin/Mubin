"""R2 test-first: live GitHub evidence is read-only; never equate claims with proof."""
from __future__ import annotations
import copy
import json
import unittest

from core.review_harness.github_live import (
    RemoteEvidenceError, fetch_pr_snapshot, assess_live_snapshot,
    _build_path, _safe_json_response, _trusted_run,
)

HEAD = 'a'*40
BASE = 'b'*40
REPO = 'AIMubin/Mubin'
WORKFLOW = '.github/workflows/mubin-inference-foundation.yml'

def api_response(pr=72, head=HEAD, base=BASE, draft=False):
    return {'number':pr, 'state':'open', 'draft':draft,
            'head':{'sha':head,'repo':{'full_name':REPO}},
            'base':{'sha':base,'repo':{'full_name':REPO}},
            'changed_files':2}

def file_item(name, status='modified'):
    return {'filename':name, 'status':status, 'changes':4, 'additions':2,'deletions':2}

def run(status='completed', conclusion='success', head=HEAD, path=WORKFLOW, event='pull_request'):
    return {'id':42, 'head_sha':head, 'name':'Mubin P0 inference foundation',
            'path':path,'status':status,'conclusion':conclusion, 'event':event,
            'repository':{'full_name':REPO}, 'head_repository':{'full_name':REPO},
            'html_url':'https://github.com/AIMubin/Mubin/actions/runs/42'}

class Stub:
    def __init__(self, pr=None, files=None, runs=None):
        self.pr = pr if pr is not None else api_response()
        self.files = files if files is not None else [file_item('core/inference/validator.py'),file_item('core/tests/test_inference_foundation.py')]
        self.runs = runs if runs is not None else [run()]
        if pr is None:
            self.pr["changed_files"] = len(self.files)
        self.calls=[]
    def __call__(self, path):
        self.calls.append(path)
        if path == '/repos/AIMubin/Mubin/pulls/72':return copy.deepcopy(self.pr)
        if path == '/repos/AIMubin/Mubin/pulls/72/files?per_page=100&page=1':return copy.deepcopy(self.files)
        if path == '/repos/AIMubin/Mubin/actions/runs?head_sha='+HEAD+'&per_page=100&page=1':
            return {'total_count':len(self.runs),'workflow_runs':copy.deepcopy(self.runs)}
        raise AssertionError('unexpected endpoint '+path)

class LiveGitHubReadTests(unittest.TestCase):
    def test_verified_sha_paths_and_successful_workflow(self):
        s=Stub()
        snapshot=fetch_pr_snapshot(72,s,expected_head_sha=HEAD)
        self.assertEqual(['core/inference/validator.py','core/tests/test_inference_foundation.py'],snapshot['changed_paths'])
        decision=assess_live_snapshot(snapshot,required_workflows={'Mubin P0 inference foundation':WORKFLOW})
        self.assertEqual('T1',decision['inferred_tier'])
        self.assertEqual('FAST_LANE_CANDIDATE',decision['engineering_lane'])
        self.assertEqual('injected_unverified',decision['metadata_provenance'])
        self.assertFalse(decision['ci_head_verified'])
        self.assertTrue(decision['workflow_metadata_consistent'])
        self.assertFalse(decision['eligible_for_auto_merge'])
        self.assertFalse(decision['independent_ai_review_verified'])
        self.assertEqual(0,decision['agent_invocations_performed'])
        self.assertEqual(3,len(s.calls))

    def test_documentation_fastlane_never_requires_unrelated_issues(self):
        s=Stub(files=[file_item('docs/research/experiment.md')])
        result=assess_live_snapshot(fetch_pr_snapshot(72,s),required_workflows={})
        self.assertEqual('T0',result['inferred_tier'])
        self.assertEqual('FAST_LANE_CANDIDATE',result['engineering_lane'])
        self.assertFalse(result['eligible_for_auto_merge'])

    def test_t2_t3_do_not_block_parallel_engineering(self):
        for path,tier in [('core/review_harness/github_live.py','T2'),
                          ('engines/hadith/qualification/H3.9.2/HOLDOUT-SEAL.md','T3')]:
            with self.subTest(path=path):
                d=assess_live_snapshot(fetch_pr_snapshot(72,Stub(files=[file_item(path)])),
                                       required_workflows={'Mubin P0 inference foundation':WORKFLOW})
                self.assertEqual(tier,d['inferred_tier'])
                self.assertEqual('PARALLEL_REVIEW_QUEUE',d['engineering_lane'])
                self.assertFalse(d['eligible_for_auto_merge'])
                self.assertTrue(d['engineering_can_continue'])

    def test_missing_or_failed_workflow_is_not_verified(self):
        for runs in ([],[run(status='in_progress',conclusion=None)],
                     [run(conclusion='failure')],[run(head=BASE)],
                     [run(path='.github/workflows/not-required.yml')],
                     [run(event='workflow_dispatch')],[run()|{'repository':{'full_name':'other/repo'}}]):
            with self.subTest(runs=runs):
                d=assess_live_snapshot(fetch_pr_snapshot(72,Stub(runs=runs)),
                                       required_workflows={'Mubin P0 inference foundation':WORKFLOW})
                self.assertFalse(d['ci_head_verified'])
                self.assertIn(d['engineering_lane'],['WAIT_FOR_CI','FAIL_REPORTED'])
                self.assertFalse(d['eligible_for_auto_merge'])

    def test_failures_take_priority_over_parallel_lane(self):
        d=assess_live_snapshot(fetch_pr_snapshot(72,Stub(runs=[run(conclusion='failure')],files=[file_item('core/review_harness/github_live.py')])),required_workflows={'Mubin P0 inference foundation':WORKFLOW})
        self.assertEqual('FAIL_REPORTED',d['engineering_lane'])

    def test_untrusted_pr_identity_never_trusted(self):
        for patch in ({'number':71}, {'state':'closed'}, {'head':{'sha':HEAD,'repo':{'full_name':'attacker/Mubin'}}},
                      {'base':{'sha':BASE,'repo':{'full_name':'attacker/Mubin'}}},
                      {'head':{'sha':BASE,'repo':{'full_name':REPO}}},
                      {'changed_files':500}, {'draft':'false'}):
            with self.subTest(patch=patch):
                with self.assertRaises(RemoteEvidenceError):
                    fetch_pr_snapshot(72,Stub(pr=api_response() | patch),expected_head_sha=HEAD)

    def test_stale_head_webhook_rejected(self):
        with self.assertRaises(RemoteEvidenceError):
            fetch_pr_snapshot(72,Stub(),expected_head_sha=BASE)

    def test_changed_paths_duplicates_and_injection_fail_closed(self):
        for paths in ([file_item('../secret')],[file_item('README.md'),file_item('README.md')],
                      [file_item('.github/workflows/a.yml',status='unexpected')],
                      [file_item('README.md\n evil')], [file_item('README.md',status='modified') | {'filename':'/root/.ssh'}]):
            with self.subTest(paths=paths):
                with self.assertRaises(RemoteEvidenceError):fetch_pr_snapshot(72,Stub(files=paths))

    def test_forged_provider_provenance_never_attests_workflow_success(self):
        # Attestation must be conferred by the live transport itself, never
        # by a mutable JSON key supplied through an injected fake client.
        snapshot=fetch_pr_snapshot(72,Stub())
        snapshot['metadata_provenance']='github_https_read_only'
        decision=assess_live_snapshot(snapshot,
                                      required_workflows={'Mubin P0 inference foundation':WORKFLOW})
        self.assertTrue(decision['workflow_metadata_consistent'])
        self.assertFalse(decision['ci_head_verified'])
        self.assertNotEqual('FAST_LANE_READY',decision['engineering_lane'])

    def test_sensitive_rename_source_controls_risk_tier(self):
        # Risk is assessed on BOTH sides; do not launder holdouts by rename.
        files=[file_item('docs/research/renamed.md',status='renamed') |
               {'previous_filename':'engines/hadith/qualification/H3.9.2/HOLDOUT-SEAL.md'}]
        report=assess_live_snapshot(fetch_pr_snapshot(72,Stub(files=files)),
                                    required_workflows={'Mubin P0 inference foundation':WORKFLOW})
        self.assertEqual('T3',report['inferred_tier'])
        self.assertIn('engines/hadith/qualification/H3.9.2/HOLDOUT-SEAL.md',
                      fetch_pr_snapshot(72,Stub(files=files))['changed_paths'])

    def test_workflow_pagination_truncation_never_green(self):
        s=Stub()
        original=s.__call__
        def listed(p):
            v=original(p)
            if '/actions/runs?' in p:v['total_count']=200
            return v
        result=assess_live_snapshot(fetch_pr_snapshot(72,listed),
                                    required_workflows={'Mubin P0 inference foundation':WORKFLOW})
        self.assertFalse(result['workflow_metadata_consistent'])
        self.assertEqual('WAIT_FOR_CI',result['engineering_lane'])

    def test_bad_rename_source_rejected(self):
        f=file_item('docs/renamed.md',status='renamed')|{'previous_filename':'../private'}
        with self.assertRaises(RemoteEvidenceError):fetch_pr_snapshot(72,Stub(files=[f]))

    def test_bounded_pagination_rejects_excessive_files(self):
        s=Stub(pr=api_response()|{'changed_files':101},files=[file_item('README.md')]*100)
        with self.assertRaises(RemoteEvidenceError):fetch_pr_snapshot(72,s)

    def test_no_external_url_or_github_redirect(self):
        for p in ('https://evil.com/anything','//evil.com','/repos/other/repo/pulls/1',
                  '/repos/AIMubin/Mubin/issues/1','/repos/AIMubin/Mubin/pulls/72#bad','/repos/AIMubin/Mubin/../secrets'):
            with self.subTest(path=p):
                with self.assertRaises(RemoteEvidenceError):_build_path(p)

    def test_duplicate_json_and_nonfinite_rejected(self):
        for b in (b'{"a":1,"a":2}',b'{"x":NaN}',b'{"x":Infinity}',b'[1,2]',b'\xff'):
            with self.subTest(raw=b):
                with self.assertRaises(RemoteEvidenceError):_safe_json_response(b)

    def test_successful_run_requires_correct_workflow_and_identity(self):
        self.assertTrue(_trusted_run(run(),HEAD,'Mubin P0 inference foundation',WORKFLOW))
        for patch in ({'head_sha':BASE},{'path':'workflow.yml'},{'status':'in_progress'},
                      {'conclusion':'neutral'},{'event':'workflow_dispatch'},
                      {'html_url':'https://evil.com/actions/runs/42'}):
            self.assertFalse(_trusted_run(run()|patch,HEAD,'Mubin P0 inference foundation',WORKFLOW))

    def test_draft_PR_can_continue_without_promoting_release(self):
        d=assess_live_snapshot(fetch_pr_snapshot(72,Stub(pr=api_response(draft=True))),required_workflows={'Mubin P0 inference foundation':WORKFLOW})
        self.assertEqual('FAST_LANE_CANDIDATE',d['engineering_lane'])
        self.assertFalse(d['eligible_for_release'])
        self.assertFalse(d['eligible_for_auto_merge'])

if __name__=='__main__':unittest.main()