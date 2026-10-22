"""U0.1 *synthetic-scope* exception assessments. Not external evidence discovery.

A verified P0 label or complete inspection of a DECLARED synthetic list cannot
prove no qarinah exists in scripture or in the real world. This helper only
materializes traceable positive/negative scenario assertions, never jurisprudence.
"""
from __future__ import annotations

from engines.usul.executor import ID


class ExceptionEvidenceError(ValueError):
    pass


MAX_ASSESSMENTS = 128
MAX_SCOPE_ITEMS = 64


def _require(condition, message):
    if not condition:
        raise ExceptionEvidenceError(message)


def _keys(item, expected, where):
    _require(isinstance(item, dict) and set(item) == set(expected),
             f"{where}: expected exactly {sorted(expected)}")


def _ids(values, label, allow_empty=False):
    _require(isinstance(values, list) and
             (allow_empty or len(values) > 0) and len(values) <= MAX_SCOPE_ITEMS,
             f"{label}: invalid identifier array")
    for value in values:
        _require(isinstance(value, str) and ID.fullmatch(value) is not None,
                 f"{label}: malformed identifier")
    _require(len(values) == len(set(values)), f"{label}: repeated identifier")


def materialize_exception_assessments(bundle, executable_specs, assessments,
                                       direct_facts):
    """Validate only synthetic scope assertions and return (facts, trace).

    For ABSENT_IN_DECLARED_SCOPE, checked items must cover the explicitly
    enumerated scope. It is NOT evidence of universal absence: a dishonest or
    incomplete DECLARED scope cannot be detected here. The accompanying
    P0 evidence IDs must resolve to internally 'verified' evidence records.
    """
    _require(isinstance(assessments, list) and len(assessments) <= MAX_ASSESSMENTS,
             "assessments must be a bounded array")
    accepted = {e["id"] for e in bundle["evidence"]
                if e["verification_status"] == "verified"}
    existing_atoms = {x["atom"] for x in direct_facts}
    seen_pairs = set()
    seen_atom_values = {}
    produced = []
    report = []
    for n, item in enumerate(assessments):
        where = f"assessments[{n}]"
        _keys(item, ("rule_id", "exception_atom", "finding",
                     "evidence_ids", "scope"), where)
        rule_id, atom = item["rule_id"], item["exception_atom"]
        _require(isinstance(rule_id, str) and rule_id in executable_specs,
                 f"{where}: unknown or nonexecutable rule")
        _require(isinstance(atom, str) and ID.fullmatch(atom) is not None,
                 f"{where}: invalid exception atom")
        exception_atoms = {x["atom"] for x in executable_specs[rule_id].get("unless_any", [])}
        _require(atom in exception_atoms, f"{where}: atom not an exception of the rule")
        _require((rule_id, atom) not in seen_pairs, f"{where}: duplicate assessment")
        seen_pairs.add((rule_id, atom))
        _require(atom not in existing_atoms, f"{where}: direct fact overrides an assessed exception")

        finding = item["finding"]
        _require(finding in ("PRESENT", "ABSENT_IN_DECLARED_SCOPE", "NOT_CHECKED"),
                 f"{where}: unsupported assessment state")
        evidence_ids = item["evidence_ids"]
        _ids(evidence_ids, f"{where}.evidence_ids", allow_empty=finding == "NOT_CHECKED")
        if finding == "NOT_CHECKED":
            _require(not evidence_ids, f"{where}: an unsearched assessment cannot cite detection evidence")
        else:
            _require(all(e in accepted for e in evidence_ids),
                     f"{where}: unknown or non-verified evidence reference")

        scope = item["scope"]
        _keys(scope, ("id", "kind", "declared_items", "checked_items"), f"{where}.scope")
        _require(isinstance(scope["id"], str) and ID.fullmatch(scope["id"]) is not None,
                 f"{where}: invalid scope identifier")
        _require(scope["kind"] == "synthetic_fixture",
                 f"{where}: real-world coverage cannot be certified by U0.1")
        declared, checked = scope["declared_items"], scope["checked_items"]
        _ids(declared, f"{where}.scope.declared_items")
        _ids(checked, f"{where}.scope.checked_items", allow_empty=True)
        _require(set(checked) <= set(declared),
                 f"{where}: checked items outside declared scope")
        if finding == "NOT_CHECKED":
            _require(not checked, f"{where}: NOT_CHECKED must have no inspected items")
        elif finding == "PRESENT":
            _require(bool(checked), f"{where}: positive observation must inspect an item")
        else:
            _require(set(checked) == set(declared),
                     f"{where}: negative observation requires complete declared-scope coverage")

        truth = "true" if finding == "PRESENT" else (
            "false" if finding == "ABSENT_IN_DECLARED_SCOPE" else None
        )
        if truth is not None:
            _require(atom not in seen_atom_values,
                     f"{where}: exception atom assessed more than once across rules")
            seen_atom_values[atom] = truth
            produced.append({"atom": atom, "truth": truth,
                             "source_evidence_ids": list(evidence_ids)})

        report.append({
            "rule_id": rule_id, "exception_atom": atom, "finding": finding,
            "scope_id": scope["id"],
            "scope_kind": scope["kind"],
            "declared_count": len(declared), "checked_count": len(checked),
            "declared_scope_coverage_complete": set(checked) == set(declared),
            "source_evidence_ids": list(evidence_ids),
            "real_world_absence_verified": False,
            "external_source_authentication_verified": False,
            "meaning": "SYNTHETIC_SCOPED_ASSERTION_NOT_UNIVERSAL_NEGATIVE",
        })
    return produced, report
