"""U0.1 experimental one-step propositional rule evaluator (NOT jurisprudence).

Inputs are explicit claims and evidence *identifiers*, not verified editions.
This does not implement usul al-fiqh, qiyas, tarjih or religious certification.
No rule chaining, implicit negatives, model-generated rule interpretation, or
user claims of external source authentication are permitted.
"""
from __future__ import annotations

import re
from collections import defaultdict

ID = re.compile(r"^[a-z][a-z0-9_.:-]{2,127}$")
MAX_FACTS = 256
MAX_RULES = 128
MAX_CONDITIONS = 16


class ContractError(ValueError):
    pass


def _record(obj, fields, required, path):
    if not isinstance(obj, dict):
        raise ContractError(f"{path}: expected object")
    unknown = set(obj) - set(fields)
    missing = set(required) - set(obj)
    if unknown or missing:
        raise ContractError(f"{path}: invalid fields (unknown={sorted(unknown)}, missing={sorted(missing)})")


def _id(value, path):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ContractError(f"{path}: invalid identifier")
    return value


def _ids(value, path):
    if not isinstance(value, list) or not value or len(value) > 64:
        raise ContractError(f"{path}: nonempty bounded source ID list required")
    for item in value:
        _id(item, path)
    if len(set(value)) != len(value):
        raise ContractError(f"{path}: duplicate identifiers")


def _predicate(value, path):
    _record(value, ("atom", "truth"), ("atom", "truth"), path)
    _id(value["atom"], path)
    if value["truth"] not in ("true", "false"):
        raise ContractError(f"{path}: truth must be true or false")


def _validated(model):
    _record(model, ("schema_version", "methodology_id", "facts", "rules", "objections"),
            ("schema_version", "methodology_id", "facts", "rules", "objections"),
            "model")
    if model["schema_version"] != "0.1.0":
        raise ContractError("unsupported schema version")
    _id(model["methodology_id"], "methodology_id")
    facts, rules, objections = model["facts"], model["rules"], model["objections"]
    if not isinstance(facts, list) or len(facts) > MAX_FACTS:
        raise ContractError("facts must be a bounded list")
    if not isinstance(rules, list) or len(rules) > MAX_RULES:
        raise ContractError("rules must be a bounded list")
    if not isinstance(objections, list) or len(objections) > MAX_RULES:
        raise ContractError("objections must be a bounded list")
    known = {}
    for i, fact in enumerate(facts):
        _record(fact, ("atom", "truth", "source_evidence_ids"),
                ("atom", "truth", "source_evidence_ids"), f"facts[{i}]")
        _predicate({"atom": fact["atom"], "truth": fact["truth"]}, f"facts[{i}]")
        _ids(fact["source_evidence_ids"], f"facts[{i}].source_evidence_ids")
        if fact["atom"] in known:
            raise ContractError(f"duplicate input fact: {fact['atom']}")
        known[fact["atom"]] = fact["truth"]
    identifiers = set()
    for i, rule in enumerate(rules):
        path = f"rules[{i}]"
        _record(rule,
                ("id", "methodology_id", "rule_kind", "if_all", "unless_any",
                 "then", "source_evidence_ids"),
                ("id", "methodology_id", "rule_kind", "if_all", "unless_any",
                 "then", "source_evidence_ids"), path)
        identifier = _id(rule["id"], path)
        if identifier in identifiers:
            raise ContractError(f"duplicate rule ID: {identifier}")
        identifiers.add(identifier)
        if rule["methodology_id"] != model["methodology_id"]:
            raise ContractError(f"{path}: methodology profile mismatch")
        if rule["rule_kind"] != "propositional_demo":
            raise ContractError(f"{path}: unsupported rule kind; no qiyas or fatwa execution")
        _ids(rule["source_evidence_ids"], path + ".source_evidence_ids")
        for field, minimum in (("if_all", 1), ("unless_any", 0)):
            items = rule[field]
            if not isinstance(items, list) or not minimum <= len(items) <= MAX_CONDITIONS:
                raise ContractError(f"{path}.{field}: invalid clause count")
            seen_atoms = set()
            for j, predicate in enumerate(items):
                _predicate(predicate, f"{path}.{field}[{j}]")
                if predicate["atom"] in seen_atoms:
                    raise ContractError(f"{path}.{field}: repeated atom")
                seen_atoms.add(predicate["atom"])
        _predicate(rule["then"], path + ".then")
        involved = {x["atom"] for x in rule["if_all"] + rule["unless_any"]}
        if rule["then"]["atom"] in involved:
            raise ContractError(f"{path}: direct conclusion/premise recursion not supported")
    seen_objections = set()
    for i, obj in enumerate(objections):
        path = f"objections[{i}]"
        _record(obj, ("id", "rule_id", "status", "source_evidence_ids"),
                ("id", "rule_id", "status", "source_evidence_ids"), path)
        key = _id(obj["id"], path)
        if key in seen_objections:
            raise ContractError(f"{path}: duplicate objection")
        seen_objections.add(key)
        if obj["rule_id"] not in identifiers:
            raise ContractError(f"{path}: objection targets unknown rule")
        if obj["status"] not in ("open", "sustained", "answered"):
            raise ContractError(f"{path}: unsupported objection status")
        _ids(obj["source_evidence_ids"], path + ".source_evidence_ids")
    return known


def evaluate(model):
    """Return descriptive simulation statuses without claiming scholarly validity.

    Each rule is evaluated ONLY against directly supplied factual assertions,
    never against other derived conclusions. Missing information is *unknown*,
    never False. If opposite conclusions are eligible, output is contested.
    """
    known = _validated(model)
    trace = []
    candidates = defaultdict(set)
    contested_by = defaultdict(set)
    objections = defaultdict(list)
    for obj in model["objections"]:
        objections[obj["rule_id"]].append(obj)

    def state(predicate):
        current = known.get(predicate["atom"])
        return "unknown" if current is None else (
            "satisfied" if current == predicate["truth"] else "not_satisfied"
        )

    for rule in model["rules"]:
        pre = [state(x) for x in rule["if_all"]]
        exceptions = [state(x) for x in rule["unless_any"]]
        unresolved = sorted(
            obj["id"] for obj in objections[rule["id"]]
            if obj["status"] in ("open", "sustained")
        )
        if "not_satisfied" in pre:
            status = "NOT_APPLICABLE"
        elif "satisfied" in exceptions:
            status = "BLOCKED_BY_EXCEPTION"
        elif unresolved:
            status = "BLOCKED_BY_OBJECTION"
        elif "unknown" in pre or "unknown" in exceptions:
            status = "UNDETERMINED"
        else:
            status = "CONDITIONALLY_SUPPORTED"
            candidates[rule["then"]["atom"]].add(rule["then"]["truth"])
            contested_by[rule["then"]["atom"]].add(rule["id"])
        trace.append({
            "rule_id": rule["id"], "status": status,
            "conclusion": dict(rule["then"]),
            "missing_premises": [x["atom"] for x, s in zip(rule["if_all"], pre) if s == "unknown"],
            "unresolved_exceptions": [x["atom"] for x, s in zip(rule["unless_any"], exceptions) if s == "unknown"],
            "unresolved_objections": unresolved,
            "rule_source_evidence_ids": list(rule["source_evidence_ids"]),
            "premise_source_evidence_ids": {
                x["atom"]: next(
                    (list(fact["source_evidence_ids"]) for fact in model["facts"]
                     if fact["atom"] == x["atom"]), [])
                for x in rule["if_all"]
            },
            "reasoning_scope": "one_step_synthetic_propositional_only",
        })
    # Only return conclusions for targeted rule outputs, never inferred facts.
    results = {}
    for atom in sorted({r["then"]["atom"] for r in model["rules"]}):
        supported = candidates.get(atom, set())
        conflicts_with_asserted_fact = bool(
            supported and atom in known and any(v != known[atom] for v in supported)
        )
        contested = len(supported) > 1 or conflicts_with_asserted_fact
        results[atom] = {
            "status": "CONTESTED" if contested else
                      "CONDITIONALLY_SUPPORTED" if supported else "UNDETERMINED",
            "supported_truth": next(iter(supported)) if len(supported) == 1 and not contested else None,
            "conflicts_with_explicit_input_fact": conflicts_with_asserted_fact,
            "supporting_rule_ids": sorted(contested_by.get(atom, set())),
        }
    return {
        "milestone": "U0.1_PROTOTYPE",
        "methodology_id": model["methodology_id"],
        "execution_scope": "ONE_STEP_PROPOSITIONAL_SIMULATION",
        "input_evidence_ids_externally_verified": False,
        "rules_scholarly_authenticated": False,
        "scholarly_verified": False,
        "valid_juristic_ruling": False,
        "public_fatwa_authorized": False,
        "conclusions": results,
        "trace": trace,
    }
