"""Mubin U0.1: finite, deterministic *synthetic* methodology-scoped rule AST.

This is NOT Islamic law, a fatwa, formal verification of Usul rules, text
provenance, authority grading, or entitlement to ingest any real source.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

BASE = Path(__file__).resolve().parents[2]
SCHEMAS = BASE / "schemas"
MAX_BYTES = 1_048_576
MAX_OBJECT_DEPTH = 40
MAX_OBJECT_NODES = 8192
MAX_AST_DEPTH = 8
MAX_AST_NODES = 512
MAX_RULES_TOTAL = 64
SCOPE = "synthetic_logic_only"

_RULEBOOK_SCHEMA = json.loads((SCHEMAS / "usul-u01-rulebook.schema.json").read_text(encoding="utf-8"))
_CASE_SCHEMA = json.loads((SCHEMAS / "usul-u01-case.schema.json").read_text(encoding="utf-8"))
Draft202012Validator.check_schema(_RULEBOOK_SCHEMA)
Draft202012Validator.check_schema(_CASE_SCHEMA)
_RULEBOOK_VALIDATOR = Draft202012Validator(_RULEBOOK_SCHEMA)
_CASE_VALIDATOR = Draft202012Validator(_CASE_SCHEMA)


def _preflight(item: Any) -> list[str]:
    """Avoid cycles, recursion bombs, non-JSON objects, and huge diagnostics."""
    stack: list[tuple[Any, int]] = [(item, 0)]
    seen_container_ids: set[int] = set()
    nodes = 0
    while stack:
        node, depth = stack.pop()
        nodes += 1
        if nodes > MAX_OBJECT_NODES:
            return ["input_node_budget_exceeded"]
        if depth > MAX_OBJECT_DEPTH:
            return ["input_depth_exceeded"]
        if isinstance(node, (list, dict)):
            # Reject all shared/nested containers, even repeated without cycles:
            # JSON has a tree, not pointer aliases. This avoids exponential dumps.
            if id(node) in seen_container_ids:
                return ["aliased_or_cyclic_input"]
            seen_container_ids.add(id(node))
            if isinstance(node, dict):
                if len(node) > 128:
                    return ["object_member_budget_exceeded"]
                for k, v in node.items():
                    if type(k) is not str or len(k) > 80:
                        return ["invalid_object_key"]
                    stack.append((v, depth + 1))
                    stack.append((k, depth + 1))
            else:
                if len(node) > 1024:
                    return ["array_budget_exceeded"]
                for val in node:
                    stack.append((val, depth + 1))
        elif node is None or type(node) in (str, int, float, bool):
            if type(node) is str and len(node) > 8192:
                return ["string_budget_exceeded"]
        else:
            return ["not_a_json_value"]
    try:
        encoded = json.dumps(item, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode("utf-8", "strict")
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        return ["invalid_canonical_json"]
    if len(encoded) > MAX_BYTES:
        return ["input_byte_budget_exceeded"]
    return []


def _schema_errors(item: Any, validator: Draft202012Validator) -> list[str]:
    issues = []
    try:
        for e in validator.iter_errors(item):
            # Do not echo any untrusted value or potentially enormous schema error.
            path = "/".join(str(v) for v in e.absolute_path)[:180]
            issues.append(f"schema:{path}:{e.validator}")
            if len(issues) >= 30:
                break
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        return ["schema_validation_failed"]
    return sorted(set(issues))


def _ast_symbols(expr: Any, *, depth: int, budget: list[int]) -> tuple[set[str], list[str]]:
    budget[0] += 1
    if depth > MAX_AST_DEPTH or budget[0] > MAX_AST_NODES:
        return set(), ["invalid_rulebook:ast_budget_exceeded"]
    op = expr["op"]  # schema validated before traversal
    if op == "fact":
        return {expr["id"]}, []
    if op == "not":
        return _ast_symbols(expr["arg"], depth=depth+1, budget=budget)
    symbols: set[str] = set()
    for child in expr["args"]:
        found, errors = _ast_symbols(child, depth=depth+1, budget=budget)
        if errors:
            return set(), errors
        symbols |= found
    return symbols, []


def validate_rulebook(rulebook: Any) -> list[str]:
    issues = _preflight(rulebook)
    if issues:
        return ["invalid_rulebook:"+x for x in issues]
    issues = _schema_errors(rulebook, _RULEBOOK_VALIDATOR)
    if issues:
        return ["invalid_rulebook:"+x for x in issues]
    known = set(rulebook["symbols"])
    methods: set[str] = set()
    rule_count = 0
    budget = [0]
    for method in rulebook["methodologies"]:
        if method["id"] in methods:
            return ["invalid_rulebook:duplicate_methodology"]
        methods.add(method["id"])
        rule_ids: set[str] = set()
        for rule in method["rules"]:
            rule_count += 1
            if rule_count > MAX_RULES_TOTAL:
                return ["invalid_rulebook:rule_count_exceeded"]
            if rule["id"] in rule_ids:
                return ["invalid_rulebook:duplicate_rule"]
            rule_ids.add(rule["id"])
            for key in ("when", "unless"):
                if key in rule:
                    symbols, errors = _ast_symbols(rule[key], depth=1, budget=budget)
                    if errors:
                        return errors
                    if not symbols.issubset(known):
                        return ["invalid_rulebook:unknown_symbol"]
    return []


def validate_case(case: Any, rulebook: Any) -> list[str]:
    issues = _preflight(case)
    if issues:
        return ["invalid_case:"+x for x in issues]
    issues = _schema_errors(case, _CASE_VALIDATOR)
    if issues:
        return ["invalid_case:"+x for x in issues]
    if not isinstance(rulebook, dict) or not isinstance(rulebook.get("symbols"), list):
        return ["invalid_case:rulebook_symbols_unavailable"]
    if not set(case["facts"]).issubset(set(rulebook["symbols"])):
        return ["invalid_case:undeclared_fact"]
    return []


def _tri(expr: dict[str, Any], facts: dict[str, str]) -> tuple[bool | None, set[str]]:
    """Strong Kleene logic; unknown means missing/unsettled, never false.

    AND: any false => false; else if any unknown => unknown; else true.
    OR: any true => true; else if any unknown => unknown; else false.
    NOT: unknown stays unknown. Only unknowns relevant to result returned.
    """
    op = expr["op"]
    if op == "fact":
        key = expr["id"]
        state = facts.get(key, "unknown")
        if state == "unknown":
            return None, {key}
        return (state == "established"), set()
    if op == "not":
        value, unknown = _tri(expr["arg"], facts)
        return (None if value is None else not value), unknown
    children = [_tri(x, facts) for x in expr["args"]]
    values = [v for v, _ in children]
    if op == "all":
        if False in values:
            return False, set()
        if all(v is True for v in values):
            return True, set()
    else:  # op = any, schema-verified
        if True in values:
            return True, set()
        if all(v is False for v in values):
            return False, set()
    unknown: set[str] = set()
    for value, remaining in children:
        if value is None:
            unknown |= remaining
    return None, unknown


def _report(status: str, reason: str, *, case_id: str | None = None,
            method: str | None = None, question: str | None = None,
            active: tuple[str, ...] = (), pending: tuple[str, ...] = (),
            defeated: tuple[str, ...] = (), missing: tuple[str, ...] = (),
            conclusion: str | None = None, traces: tuple[dict[str, str], ...] = (),
            errors: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "status": status, "reason": reason, "case_id": case_id,
        "methodology_id": method, "question_id": question,
        "conclusion": conclusion, "active_rules": list(active),
        "pending_rules": list(pending), "defeated_rules": list(defeated),
        "missing_facts": list(missing), "rule_traces": list(traces),
        "errors": list(errors), "scope": SCOPE,
        "scholarly_authority_verified": False,
        "external_corpus_access": "none",
    }


def evaluate(rulebook: Any, case: Any) -> dict[str, Any]:
    """Evaluate a finite synthetic case. Never calls external tools or opens corpus."""
    errors = validate_rulebook(rulebook)
    if errors:
        return _report("invalid", "invalid_rulebook", errors=tuple(errors))
    errors = validate_case(case, rulebook)
    if errors:
        return _report("invalid", "invalid_case", errors=tuple(errors))
    selected = next((m for m in rulebook["methodologies"]
                     if m["id"] == case["methodology_id"]), None)
    if selected is None:
        return _report("invalid", "unknown_methodology", case_id=case["case_id"],
                       method=case["methodology_id"], question=case["question_id"])
    rules = [r for r in selected["rules"] if r["question_id"] == case["question_id"]]
    if not rules:
        return _report("invalid", "unknown_question", case_id=case["case_id"],
                       method=case["methodology_id"], question=case["question_id"])
    active: list[str] = []
    pending: list[str] = []
    defeated: list[str] = []
    missing: set[str] = set()
    traces: list[dict[str, str]] = []
    conclusions: set[str] = set()
    for rule in rules:
        premise, missing_premise = _tri(rule["when"], case["facts"])
        exception, missing_exception = (False, set()) if "unless" not in rule else _tri(rule["unless"], case["facts"])
        if exception is True:
            route = "defeated"
            defeated.append(rule["id"])
        elif premise is False:
            route = "inapplicable"
        elif premise is None or exception is None:
            route = "pending"
            pending.append(rule["id"])
            if premise is None:
                missing |= missing_premise
            if exception is None:
                missing |= missing_exception
        else:
            route = "active"
            active.append(rule["id"])
            conclusions.add(rule["conclusion"])
        traces.append({"rule_id":rule["id"],"state":route,
                       "conclusion_if_active":rule["conclusion"]})
    if len(conclusions) > 1:
        status, reason, conclusion = "conflict", "opposing_conclusions", None
    elif pending:
        status, reason, conclusion = "abstain", "insufficient_evidence", None
    elif len(conclusions) == 1:
        status, reason, conclusion = "supported", "method_local_derivation", next(iter(conclusions))
    else:
        status, reason, conclusion = "abstain", "no_applicable_rule", None
    return _report(status, reason, case_id=case["case_id"], method=case["methodology_id"],
                   question=case["question_id"], active=tuple(active),
                   pending=tuple(pending), defeated=tuple(defeated),
                   missing=tuple(sorted(missing)), conclusion=conclusion, traces=tuple(traces))
