"""R2: read-only, tightly scoped GitHub PR+workflow observation.

Transport-bound data, if live, are GitHub-observed metadata, NOT proofs of
reviewer independence, source rights, text authenticity or safe auto-merge.
Injected transports remain explicitly *untrusted fixtures* even when shaped
like valid responses. No PR body, diff text, workflow logs or secrets are
printed. Tests remain offline.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import weakref
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .validator import _path_tier, _safe_path, _safe_plain_tree

REPO = 'AIMubin/Mubin'
API = 'https://api.github.com'
SHA = re.compile(r'[0-9a-f]{40}\Z')
PR_NUMBER = re.compile(r'[1-9][0-9]{0,6}\Z')
WHITELIST = (
    re.compile(r'/repos/AIMubin/Mubin/pulls/[1-9][0-9]{0,6}\Z'),
    re.compile(r'/repos/AIMubin/Mubin/pulls/[1-9][0-9]{0,6}/files\?per_page=100&page=1\Z'),
    re.compile(r'/repos/AIMubin/Mubin/actions/runs\?head_sha=[0-9a-f]{40}&per_page=100&page=1\Z'),
)
RUN_URL = re.compile(r'https://github[.]com/AIMubin/Mubin/actions/runs/[1-9][0-9]*\Z')
STATUS = frozenset({'added','modified','removed','renamed','copied','changed'})
MAX_BYTES = 1024*1024
MAX_FILES = 100
MAX_RUNS = 100

class _AuthenticatedLiveSnapshot(dict):
    """Ephemeral in-process capability; NEVER serializable as a trust claim.

    The only ordinary constructor path is the built-in GitHub HTTPS reader.
    Copying its JSON fields, including the apparent provenance string, does
    not transfer the capability to an injected/untrusted snapshot.
    """
    __slots__ = ("_cap", "__weakref__")


_LIVE_SNAPSHOTS = weakref.WeakValueDictionary()


def _observed_live(snapshot: Any) -> bool:
    return (type(snapshot) is _AuthenticatedLiveSnapshot
            and type(snapshot._cap) is str
            and _LIVE_SNAPSHOTS.get(snapshot._cap) is snapshot)


class RemoteEvidenceError(ValueError):
    """Unsafe, ambiguous, stale or unavailable provider fact: fail closed."""


def _build_path(path: str) -> str:
    if type(path) is not str or not any(p.fullmatch(path) for p in WHITELIST):
        raise RemoteEvidenceError('GitHub API path is not allowlisted')
    return API + path


def _safe_json_response(raw: bytes, *, allow_list: bool = False) -> Any:
    if type(raw) is not bytes or len(raw) > MAX_BYTES:
        raise RemoteEvidenceError('provider response is not bounded bytes')
    def pairs(a: list[tuple[str, Any]]) -> dict[str, Any]:
        obj: dict[str, Any] = {}
        for k,v in a:
            if k in obj:raise RemoteEvidenceError('duplicate provider JSON member')
            obj[k]=v
        return obj
    def bad_constant(_: str) -> None:
        raise RemoteEvidenceError('nonfinite provider JSON number')
    try:
        obj=json.loads(raw.decode('utf-8','strict'),object_pairs_hook=pairs,
                       parse_constant=bad_constant)
    except (ValueError,TypeError,UnicodeError,RecursionError) as exc:
        raise RemoteEvidenceError('invalid provider JSON') from exc
    expected_type = list if allow_list else dict
    if type(obj) is not expected_type:
        raise RemoteEvidenceError('wrong top-level provider response type')
    if not _safe_plain_tree(obj):
        raise RemoteEvidenceError('unsafe provider JSON tree')
    return obj


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RemoteEvidenceError('provider redirect forbidden')


class GitHubReadOnly:
    """Construct only repository-fixed HTTPS GET, with bounded body and timeout."""
    def __init__(self, token: str | None = None):
        self._token = token or ''
        self._opener = build_opener(_NoRedirect())
    def __call__(self, path: str) -> Any:
        url = _build_path(path)
        headers = {'Accept':'application/vnd.github+json',
                   'X-GitHub-Api-Version':'2022-11-28',
                   'User-Agent':'Mubin-R2-ReadOnly/0.2'}
        if self._token:headers['Authorization']='Bearer '+self._token
        try:
            request=Request(url, headers=headers, method='GET')
            with self._opener.open(request, timeout=8) as response:
                raw=response.read(MAX_BYTES+1)
        except (HTTPError, URLError, OSError, TimeoutError) as exc:
            # Never include error bodies, URL query strings, or tokens.
            raise RemoteEvidenceError('GitHub read-only metadata request failed') from exc
        return _safe_json_response(raw,allow_list='/files?' in path)


def _sha(s: Any) -> bool:
    return type(s) is str and SHA.fullmatch(s) is not None


def _real_id(v: Any) -> bool:
    return type(v) is int and 0 < v < 1_000_000_000_000


def _repo_object(obj: Any) -> bool:
    return type(obj) is dict and obj.get('full_name') == REPO


def _run_identity(item: Any, head: str, name: str, path: str) -> bool:
    if type(item) is not dict or not _real_id(item.get('id')):
        return False
    return (item.get('head_sha') == head and item.get('name') == name
            and item.get('path') == path and item.get('event') == 'pull_request'
            and _repo_object(item.get('repository'))
            and _repo_object(item.get('head_repository'))
            and item.get('html_url') == f'https://github.com/{REPO}/actions/runs/{item["id"]}'
            and RUN_URL.fullmatch(item.get('html_url','')) is not None)


def _trusted_run(item: Any, head: str, name: str, path: str) -> bool:
    return (_run_identity(item,head,name,path) and
            item.get('status') == 'completed' and item.get('conclusion') == 'success')


def fetch_pr_snapshot(pr_number: int, get_json: Callable[[str], Any] | None = None,
                      *, expected_head_sha: str | None = None) -> dict[str, Any]:
    """Bound PR facts + exact-head workflow runs. Injected get_json is never trusted.

    Does not fetch the diff, invoke agents, merge PRs or validate CI job semantics.
    Oversized (>100 changed GitHub files) PRs need a separate paginated R3 path.
    """
    if type(pr_number) is not int or PR_NUMBER.fullmatch(str(pr_number)) is None:
        raise RemoteEvidenceError('invalid PR identity')
    if expected_head_sha is not None and not _sha(expected_head_sha):
        raise RemoteEvidenceError('invalid expected HEAD SHA')
    live = get_json is None
    fetch: Callable[[str],Any] = GitHubReadOnly(os.environ.get('GITHUB_TOKEN')) if live else get_json
    try:
        pr = fetch(f'/repos/{REPO}/pulls/{pr_number}')
        if (type(pr) is not dict or not _safe_plain_tree(pr)
                or type(pr.get('number')) is not int or pr['number'] != pr_number
                or pr.get('state') != 'open' or type(pr.get('draft')) is not bool
                or type(pr.get('changed_files')) is not int
                or not 1 <= pr['changed_files'] <= MAX_FILES):
            raise RemoteEvidenceError('PR is closed, ambiguous or file-list exceeds R2 bound')
        head_obj = pr.get('head'); base_obj=pr.get('base')
        if not (type(head_obj) is dict and type(base_obj) is dict
                and _sha(head_obj.get('sha')) and _sha(base_obj.get('sha'))
                and head_obj['sha'] != base_obj['sha']
                and _repo_object(head_obj.get('repo')) and _repo_object(base_obj.get('repo'))):
            raise RemoteEvidenceError('PR head/base not pinned to this repository')
        head = head_obj['sha']
        if expected_head_sha is not None and head != expected_head_sha:
            raise RemoteEvidenceError('stale PR webhook/event HEAD')
        files = fetch(f'/repos/{REPO}/pulls/{pr_number}/files?per_page=100&page=1')
        if (type(files) is not list or not _safe_plain_tree(files) or
                len(files) != pr['changed_files']):
            raise RemoteEvidenceError('incomplete or unsafe changed-file list')
        paths: list[str] = []
        file_names = set()
        for f in files:
            if (type(f) is not dict or type(f.get('filename')) is not str
                    or f['status'] not in STATUS or not _safe_path(f['filename'])
                    or f['filename'] in file_names):
                raise RemoteEvidenceError('unsafe or duplicate changed-file path')
            file_names.add(f['filename'])
            paths.append(f['filename'])
            if f['status'] == 'renamed':
                prior=f.get('previous_filename')
                if not _safe_path(prior):
                    raise RemoteEvidenceError('unsafe rename source path')
                paths.append(prior)
        rr = fetch(f'/repos/{REPO}/actions/runs?head_sha={head}&per_page=100&page=1')
        if (type(rr) is not dict or not _safe_plain_tree(rr)
                or type(rr.get('workflow_runs')) is not list
                or len(rr['workflow_runs']) > MAX_RUNS
                or type(rr.get('total_count')) is not int
                or rr['total_count'] < len(rr['workflow_runs'])):
            raise RemoteEvidenceError('malformed workflow run list')
        # Each entry is explicitly selected from an exact-head provider call.
        data={'repository':REPO,'pr_number':pr_number, 'draft':pr['draft'],
              'head_sha':head,'base_sha':base_obj['sha'],
              'changed_paths':sorted(set(paths)),
              'workflow_runs':rr['workflow_runs'],
              'workflow_runs_truncated':rr['total_count'] > MAX_RUNS,
              'metadata_provenance':'github_https_read_only' if live else 'injected_unverified'}
        if live:
            snap = _AuthenticatedLiveSnapshot(data)
            snap._cap = secrets.token_hex(24)
            _LIVE_SNAPSHOTS[snap._cap] = snap
            return snap
        return data
    except (TypeError,KeyError,IndexError,RecursionError) as exc:
        raise RemoteEvidenceError('invalid or incomplete GitHub provider structure') from exc


def assess_live_snapshot(snapshot: dict[str,Any], *,
                         required_workflows: dict[str,str] | None = None) -> dict[str,Any]:
    """Engineering advisory only. No auto merge or scholarly decisions.

    Failed reported CI overrides fast/parallel review. Pending CI does not
    prevent working on independent engineering branches.
    """
    # Built-in HTTPS snapshots carry an unforgeable-for-JSON process-local
    # capability. A caller can change `metadata_provenance` but cannot mint
    # that capability simply by constructing the same data dictionary.
    plain = dict(snapshot) if type(snapshot) is _AuthenticatedLiveSnapshot else snapshot
    if (type(plain) is not dict or not _safe_plain_tree(plain)
            or not _sha(snapshot.get('head_sha'))
            or snapshot.get('repository') != REPO
            or type(snapshot.get('changed_paths')) is not list
            or not snapshot['changed_paths']
            or any(not _safe_path(p) for p in snapshot['changed_paths'])
            or type(snapshot.get('workflow_runs')) is not list
            or type(snapshot.get('workflow_runs_truncated')) is not bool):
        raise RemoteEvidenceError('invalid snapshot input')
    required = {} if required_workflows is None else required_workflows
    if (type(required) is not dict or len(required) > 8
            or any(type(k) is not str or type(v) is not str or
                   len(k) > 120 or len(v) > 200 or not v.startswith('.github/workflows/')
                   for k,v in required.items())):
        raise RemoteEvidenceError('invalid required workflow contract')
    head=snapshot['head_sha']
    tier=max(_path_tier(p) for p in snapshot['changed_paths'])
    outcomes = {}
    for name,path in sorted(required.items()):
        matching=[r for r in snapshot['workflow_runs'] if _run_identity(r,head,name,path)]
        if not matching:
            outcomes[name]='missing'
        else:
            # GitHub workflow re-runs reuse run IDs; the GET response returns
            # latest attempt's conclusion for a given run.
            last=max(matching,key=lambda r:r['id'])
            outcomes[name] = ('success' if _trusted_run(last,head,name,path)
                              else 'failure' if last.get('status')=='completed' and last.get('conclusion')=='failure'
                              else 'pending_or_inconclusive')
    consistent = bool(required) and not snapshot['workflow_runs_truncated'] and all(v=='success' for v in outcomes.values())
    live=_observed_live(snapshot)
    failing=any(v=='failure' for v in outcomes.values())
    missing=bool(required) and not consistent
    if failing:lane='FAIL_REPORTED'
    elif missing:lane='WAIT_FOR_CI'
    elif tier>=2:lane='PARALLEL_REVIEW_QUEUE'
    else:lane='FAST_LANE_READY' if live else 'FAST_LANE_CANDIDATE'
    return {
        'repository':REPO,'pr_number':snapshot.get('pr_number'),
        'head_sha':head,'metadata_provenance':'github_https_read_only' if live else 'injected_unverified',
        'inferred_tier':f'T{tier}', 'engineering_lane':lane,
        'engineering_can_continue':True,'workflow_outcomes':outcomes,
        'workflow_metadata_consistent':consistent,
        'ci_head_verified':live and consistent,
        'pending_or_missing_checks':sorted(k for k,v in outcomes.items() if v != 'success'),
        'eligible_for_auto_merge':False,'eligible_for_release':False,
        'independent_ai_review_verified':False,'human_review_performed':False,
        'scholarly_authority_verified':False,'rights_verified':False,
        'h392_gold_eligible':False,'agent_invocations_performed':0,
        'notice':'GitHub live workflow metadata only, not job-test semantics, model review, rights or scholarly approval.'
    }