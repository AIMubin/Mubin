"""P0↔U0.1 typed rule bridge: structural, attribution and bounded execution layers.

Layer 1 structural: the P0 bundle must pass core.inference.validator (schema,
digests, reference integrity, cycles, methodology consistency).
Layer 2 attribution: every rule and fact evidence ID must EXIST in the bundle
and be verified; each rule's methodology must exist. Rules from more than one
methodology are refused: no cross-profile reconciliation contract exists yet.
Layer 3 execution: only deduction rules marked formalization_status
"machine_checkable" with an explicit bounded propositional spec run through
engines.usul.executor. Rule.expression free text is NEVER interpreted as
instructions. qiyas/tarjih are rejected outright - no analogical approximations.
Outputs remain engineering simulations: scholarly_verified stays False.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.inference.validator import validate_bundle
from engines.usul.executor import evaluate
from engines.usul.semantic_binding import BindingError, cited_sources, validate_binding

BRIDGE_VERSION = "p0-usul-u0.1/0.1.0"
EXECUTABLE_KINDS = {"deduction"}
REFUSED_KINDS = {"qiyas", "tarjih"}
STATUSES = {"open", "answered", "sustained"}


def _evidence_check(bundle, ids, label, rejected):
    for evidence_id in ids:
        entry = next((e for e in bundle["evidence"] if e["id"] == evidence_id), None)
        if entry is None:
            rejected.append({"target": label, "evidence_id": evidence_id,
                             "reason": "REJECTED_UNKNOWN_EVIDENCE"})
            return False
        if entry["verification_status"] != "verified":
            rejected.append({"target": label, "evidence_id": evidence_id,
                             "reason": "REJECTED_UNVERIFIED_EVIDENCE"})
            return False
    return True


def _spec_cycle(specs_by_id):
    graph = {}
    for rule_id, spec in specs_by_id.items():
        conclusions = {other for other in specs_by_id if other != rule_id
                       and specs_by_id[other]["then"]["atom"] in
                       {p["atom"] for p in spec["if_all"] + spec["unless_any"]}}
        graph[rule_id] = sorted(conclusions)
    seen, stack = set(), set()

    def visit(node):
        if node in stack:
            return True
        if node in seen:
            return False
        seen.add(node)
        stack.add(node)
        if any(visit(nxt) for nxt in graph.get(node, [])):
            return True
        stack.discard(node)
        return False

    return any(visit(node) for node in graph)


def build_and_run(bundle, specs, fact_assertions):
    """Return the full derivation record; never mutates the bundle."""
    structural_errors = validate_bundle(bundle)
    # Invalid bundles can omit rules entirely; do not dereference them before
    # returning the P0 structural rejection.
    rule_list = bundle.get("rules", []) if isinstance(bundle, dict) else []
    rule_list = rule_list if isinstance(rule_list, list) else []
    derivation = {
        "bridge": BRIDGE_VERSION,
        "structural_validation": {"passed": not structural_errors, "errors": structural_errors},
        "attribution": {"rules_executable": [], "rules_structural_only": [],
                        "rules_rejected": [], "facts_rejected": []},
        "methodology_isolation": {"methodologies_seen": sorted({r["methodology_id"] for r in rule_list if isinstance(r, dict) and isinstance(r.get("methodology_id"), str)}),
                                  "cross_methodology_reconciliation": "not_supported_in_u0.1"},
        "derivation_refused": None,
        "semantic_bindings": {},
        "source_citations": [],
        "citation_scope": "SOURCE_METADATA_ONLY_NO_TEXT_OR_RIGHTS_GRANTED",
        "semantic_equivalence_verified": False,
        "external_source_authentication_verified": False,
        "public_fatwa_authorized": False,
        "usul_result": None,
        "reproducible_offline": True,
        "scholarly_verified": False,
        "valid_juristic_ruling": False,
    }
    if structural_errors:
        derivation["derivation_refused"] = {"code": "STRUCTURAL_VALIDATION_FAILED",
                                            "errors": structural_errors}
        return derivation
    if not isinstance(specs, dict) or not isinstance(fact_assertions, list):
        derivation["derivation_refused"] = {"code": "INVALID_EXECUTION_INPUT",
                                            "detail": "specs must be an object and fact assertions an array"}
        return derivation

    methodologies = {m["id"]: m for m in bundle["methodologies"]}
    method_seen = derivation["methodology_isolation"]["methodologies_seen"]
    if len(method_seen) > 1:
        derivation["derivation_refused"] = {
            "code": "METHODOLOGY_MIXING_REFUSED",
            "detail": f"rules span {method_seen}; no audited reconciliation contract exists"}
        return derivation

    rejected = derivation["attribution"]["rules_rejected"]
    executable, structural_only = [], []
    specs_by_id = {}
    for rule in bundle["rules"]:
        label = rule["id"]
        if rule["rule_type"] in REFUSED_KINDS:
            rejected.append({"id": rule["id"], "reason": "REJECTED_UNSUPPORTED_RULE_KIND",
                             "detail": f"{rule['rule_type']} semantics are not defined in U0.1"})
            continue
        if rule["methodology_id"] not in methodologies:
            rejected.append({"id": rule["id"], "reason": "REJECTED_UNKNOWN_METHODOLOGY"})
            continue
        if not _evidence_check(bundle, rule["source_evidence_ids"], label, rejected):
            continue
        spec = specs.get(rule["id"])
        if (rule["rule_type"] not in EXECUTABLE_KINDS
                or rule["formalization_status"] != "machine_checkable"
                or spec is None):
            structural_only.append({"id": rule["id"],
                                    "reason": "REPRESENTATION_ONLY_NO_EXECUTABLE_SPEC"})
            continue
        try:
            binding_result = validate_binding(bundle, rule, spec)
            evaluate({"schema_version": "0.1.0", "methodology_id": rule["methodology_id"],
                      "facts": [], "rules": [{
                          "id": rule["id"], "methodology_id": rule["methodology_id"],
                          "rule_kind": "propositional_demo",
                          "if_all": spec["if_all"], "unless_any": spec.get("unless_any", []),
                          "then": spec["then"],
                          "source_evidence_ids": rule["source_evidence_ids"]}],
                      "objections": []})
        except (BindingError, ValueError, KeyError, TypeError) as exc:
            rejected.append({"id": rule["id"],
                             "reason": "REJECTED_INVALID_SEMANTIC_BINDING" if isinstance(exc, BindingError) else "REJECTED_INVALID_SPEC",
                             "detail": str(exc)})
            continue
        derivation["semantic_bindings"][rule["id"]] = binding_result
        specs_by_id[rule["id"]] = spec
        executable.append(rule)

    if _spec_cycle(specs_by_id):
        derivation["derivation_refused"] = {"code": "DERIVATION_CYCLE",
                                            "rules": sorted(specs_by_id)}
        return derivation

    facts, facts_rejected = [], derivation["attribution"]["facts_rejected"]
    for assertion in fact_assertions:
        if not _evidence_check(bundle, assertion["source_evidence_ids"],
                               f"facts[{assertion['atom']}]", facts_rejected):
            continue
        facts.append(assertion)

    objections = []
    for objection in bundle.get("objections", []):
        if objection["status"] not in STATUSES:
            continue
        targeted = set()
        for inference in bundle.get("inferences", []):
            if inference["id"] == objection["target_inference_id"]:
                targeted.update(inference["rule_ids"])
        for rule_id in sorted(targeted & set(specs_by_id)):
            objections.append({"id": f"{objection['id']}.on.{rule_id}", "rule_id": rule_id,
                               "status": objection["status"],
                               "source_evidence_ids": objection["evidence_ids"]})

    # Preserve a source reference trail for each executed rule and accepted fact.
    # Never copy evidence excerpts into the output or infer redistribution rights.
    used_evidence = set()
    for rule in executable:
        used_evidence.update(rule["source_evidence_ids"])
        binding = specs_by_id[rule["id"]].get("binding")
        if binding is not None:
            for clause in binding["preconditions"]:
                claim = next(c for c in bundle["claims"] if c["id"] == clause["claim_id"])
                used_evidence.update(claim["evidence_ids"])
            for clause in binding["exceptions"]:
                used_evidence.update(clause["source_evidence_ids"])
    for fact in facts:
        used_evidence.update(fact["source_evidence_ids"])
    for objection in objections:
        used_evidence.update(objection["source_evidence_ids"])
    derivation["source_citations"] = cited_sources(bundle, used_evidence)

    methodology = methodologies[bundle["rules"][0]["methodology_id"]] if bundle["rules"] else None
    derivation["attribution"]["rules_executable"] = sorted(specs_by_id)
    derivation["attribution"]["rules_structural_only"] = structural_only
    derivation["methodology_provenance"] = (
        {"id": methodology["id"], "label": methodology["label"], "version": methodology["version"]}
        if methodology else None)
    derivation["usul_result"] = evaluate({
        "schema_version": "0.1.0",
        "methodology_id": bundle["rules"][0]["methodology_id"],
        "facts": facts,
        "rules": [{"id": rule["id"], "methodology_id": rule["methodology_id"],
                   "rule_kind": "propositional_demo",
                   "if_all": specs_by_id[rule["id"]]["if_all"],
                   "unless_any": specs_by_id[rule["id"]].get("unless_any", []),
                   "then": specs_by_id[rule["id"]]["then"],
                   "source_evidence_ids": rule["source_evidence_ids"]}
                  for rule in executable],
        "objections": objections,
    })
    return derivation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("specs", type=Path)
    parser.add_argument("facts", type=Path)
    args = parser.parse_args()
    try:
        result = build_and_run(
            json.loads(args.bundle.read_text(encoding="utf-8")),
            json.loads(args.specs.read_text(encoding="utf-8")),
            json.loads(args.facts.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "INVALID_INPUT", "error_type": type(exc).__name__,
                          "scholarly_verified": False}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    # Never signal successful derivation to shell-based automation when any
    # policy denial or evidence rejection remains. Partial execution is not
    # an implicit authorization for the rejected inputs.
    has_rejection = bool(
        result["derivation_refused"]
        or result["attribution"]["rules_rejected"]
        or result["attribution"]["facts_rejected"]
    )
    return 1 if has_rejection else 0


if __name__ == "__main__":
    raise SystemExit(main())
