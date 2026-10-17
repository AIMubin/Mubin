"""Frozen *synthetic* U0.1 benchmark runner: controlled mutation tests only."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from .engine import evaluate, _preflight

# Created BEFORE evaluator implementation, then saved with the red test transcript.
# These hashes are not independent signing authority; they stop accidental edits.
FROZEN_CASES_SHA256 = '658e8278d7b7addf6dc56d81a6703bc55c95d19d7550e456bd3094016c368de9'
FROZEN_RULEBOOK_SHA256 = 'a551b35678d6dc182f2e4cbab5e25cea8eb4b6392ee66eabc7a5cdc5611a02ea'
# Secondary, independent truth-table oracle for ALL fifteen positives;
# protects against a "PASS" consisting of incorrect but nonempty conclusions.
_POSITIVE_ORACLE = {
    'p01': 'track_north', 'p02': 'track_south', 'p03': 'track_north',
    'p04': 'track_north', 'p05': 'track_north', 'p06': 'track_north',
    'p07': 'track_north', 'p08': 'track_north', 'p09': 'track_south',
    'p10': 'track_north', 'p11': 'track_south', 'p12': 'track_south',
    'p13': 'track_north', 'p14': 'track_north', 'p15': 'track_south',
}

_ALLOWED_MUTATIONS = frozenset({
    'duplicate_rule', 'unknown_symbol', 'too_deep',
    'duplicate_methodology', 'unknown_op',
})


def _alter(rulebook: dict[str, Any], key: str | None) -> dict[str, Any]:
    changed = deepcopy(rulebook)
    if key is None:
        return changed
    methods = changed['methodologies']
    if key == 'duplicate_rule':
        methods[0]['rules'][1]['id'] = methods[0]['rules'][0]['id']
    elif key == 'unknown_symbol':
        methods[0]['rules'][0]['when']['args'][0]['id'] = 'unregistered_atom'
    elif key == 'too_deep':
        node = {'op': 'fact', 'id': 'a'}
        for _ in range(20):
            node = {'op': 'not', 'arg': node}
        methods[0]['rules'][0]['when'] = node
    elif key == 'duplicate_methodology':
        methods[1]['id'] = methods[0]['id']
    elif key == 'unknown_op':
        methods[0]['rules'][0]['when'] = {'op': 'eval', 'code': 'True'}
    else:
        raise ValueError('unrecognized frozen mutation')
    return changed


def _invalid_report(code: str, failures: list[str] | None = None) -> dict[str, Any]:
    return {'passed': False, 'scope': 'synthetic_benchmark_only', 'code': code,
            'total': 0, 'positive_passed': 0, 'adversarial_passed': 0,
            'frozen_rulebook_sha256': FROZEN_RULEBOOK_SHA256,
            'frozen_cases_sha256': FROZEN_CASES_SHA256,
            'failures': failures or []}


def run_frozen_suite(rulebook: Any, suite: Any, raw_rulebook: bytes, raw_suite: bytes) -> dict[str, Any]:
    """No caller can claim U0.1 benchmark pass with substituted fixtures."""
    if sha256(raw_rulebook).hexdigest() != FROZEN_RULEBOOK_SHA256:
        return _invalid_report('UNRECOGNIZED_RULEBOOK')
    if sha256(raw_suite).hexdigest() != FROZEN_CASES_SHA256:
        return _invalid_report('UNRECOGNIZED_FIXTURES')
    # Exact raw hashes must bind the *objects actually executed* as well.
    # This public runner accepts already-parsed objects from programmatic callers,
    # which may otherwise swap or mutate them after source bytes are pinned.
    if _preflight(rulebook):
        return _invalid_report('UNRECOGNIZED_RULEBOOK')
    if _preflight(suite):
        return _invalid_report('UNRECOGNIZED_FIXTURES')
    try:
        decoded_rulebook = json.loads(raw_rulebook.decode('utf-8', 'strict'))
        decoded_suite = json.loads(raw_suite.decode('utf-8', 'strict'))
        if rulebook != decoded_rulebook:
            return _invalid_report('UNRECOGNIZED_RULEBOOK')
        if suite != decoded_suite:
            return _invalid_report('UNRECOGNIZED_FIXTURES')
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        return _invalid_report('INVALID_SUITE')
    if not isinstance(suite, dict) or set(suite) != {'contract','status','cases'}:
        return _invalid_report('INVALID_SUITE')
    if suite['contract'] != 'mubin-usul-synthetic-eval-set-v1' or suite['status'] != 'pre_registered_before_engine_implementation':
        return _invalid_report('INVALID_SUITE')
    entries = suite['cases']
    if not isinstance(entries, list) or len(entries) != 40:
        return _invalid_report('INVALID_SUITE')
    seen: set[str] = set()
    positive = adversarial = 0
    failures: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict) or not {'case', 'expect'}.issubset(entry) or set(entry) - {'case', 'expect', 'tamper_rulebook'}:
            return _invalid_report('INVALID_SUITE')
        case = entry['case']
        expected = entry['expect']
        if not isinstance(case, dict) or not isinstance(expected, dict) or not {'status'}.issubset(expected) or set(expected) - {'status','reason'}:
            return _invalid_report('INVALID_SUITE')
        identifier = case.get('case_id')
        if not isinstance(identifier, str) or identifier in seen or not (identifier.startswith('p') or identifier.startswith('n')):
            return _invalid_report('INVALID_SUITE')
        seen.add(identifier)
        modification = entry.get('tamper_rulebook')
        if modification is not None and modification not in _ALLOWED_MUTATIONS:
            return _invalid_report('INVALID_SUITE')
        candidate_rulebook = _alter(rulebook, modification)
        result = evaluate(candidate_rulebook, case)
        ok = result['status'] == expected['status'] and (
            'reason' not in expected or result['reason'] == expected['reason']
        )
        if identifier.startswith('p'):
            ok = ok and result['conclusion'] == _POSITIVE_ORACLE.get(identifier)
        else:
            ok = ok and result['conclusion'] is None
        if ok:
            if identifier.startswith('p'):
                positive += 1
            else:
                adversarial += 1
        else:
            failures.append(identifier)
    passed = len(seen) == 40 and positive == 15 and adversarial == 25 and not failures
    return {'passed':passed, 'scope':'synthetic_benchmark_only',
            'code':'PASS' if passed else 'TEST_FAILURE',
            'total':len(seen),'positive_passed':positive,'adversarial_passed':adversarial,
            'frozen_rulebook_sha256':FROZEN_RULEBOOK_SHA256,
            'frozen_cases_sha256':FROZEN_CASES_SHA256,
            'failures':failures}
