"""U0.1 source-attributed structural semantic binding (NOT semantic certification).

Binds each machine predicate to a specific P0 rule clause and anchored P0
claim, pins the exact P0 rule bytes, and emits traceable source references.
Human language equivalence is NOT established by this structural mapping.
"""
from __future__ import annotations

import hashlib
import json


class BindingError(ValueError):
    pass


def rule_fingerprint(rule):
    """Commit to every field of one P0 rule, including free explanatory text."""
    data = json.dumps(rule, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _exact_keys(obj, expected, where):
    if not isinstance(obj, dict) or set(obj) != set(expected):
        raise BindingError(f"{where}: expected exactly {sorted(expected)}")


def _predicate(obj, where):
    _exact_keys(obj, ("atom", "truth"), where)
    if not isinstance(obj["atom"], str) or not obj["atom"].strip():
        raise BindingError(f"{where}: invalid atom")
    if obj["truth"] not in ("true", "false"):
        raise BindingError(f"{where}: invalid truth")


def validate_binding(bundle, rule, spec):
    """Check *structural correspondence*, not soundness of rule or premises.

    A missing binding remains legacy/unbound; a supplied invalid binding
    is refused, never silently downgraded to legacy evaluation.
    """
    binding = spec.get("binding")
    if binding is None:
        return {"status": "LEGACY_UNBOUND", "rule_sha256": rule_fingerprint(rule),
                "semantic_equivalence_verified": False}
    _exact_keys(binding, ("version", "rule_sha256", "preconditions",
                          "exceptions", "conclusion"), "binding")
    if binding["version"] != "0.1.0":
        raise BindingError("binding: unsupported version")
    digest = rule_fingerprint(rule)
    if binding["rule_sha256"] != digest:
        raise BindingError("binding: P0 rule SHA-256 mismatch (stale formalization)")
    indexed_claims = {c["id"]: c for c in bundle["claims"]}
    indexed_evidence = {e["id"]: e for e in bundle["evidence"]}
    if not isinstance(binding["preconditions"], list) or not isinstance(binding["exceptions"], list):
        raise BindingError("binding: clauses must be arrays")
    if not isinstance(spec.get("if_all"), list) or not isinstance(spec.get("unless_any", []), list):
        raise BindingError("binding: executable clauses must be arrays")
    if not isinstance(rule["preconditions"], list) or not isinstance(rule["exceptions"], list):
        raise BindingError("binding: invalid P0 rule clause containers")
    matching = [i for i in bundle["inferences"] if rule["id"] in i["rule_ids"]]
    if not matching:
        raise BindingError("binding: rule has no P0 inference applying it")

    def correspondence(labels, mappings, predicates, kind):
        if len(labels) != len(set(labels)):
            raise BindingError(f"binding: duplicate P0 {kind} labels")
        if len(labels) != len(mappings) or len(mappings) != len(predicates):
            raise BindingError(f"binding: {kind} clause count mismatch")
        seen = set()
        for i, (expected_label, item, executable) in enumerate(zip(labels, mappings, predicates)):
            where = f"binding.{kind}[{i}]"
            if kind == "preconditions":
                _exact_keys(item, ("label", "claim_id", "atom", "truth"), where)
            else:
                _exact_keys(item, ("label", "atom", "truth", "source_evidence_ids"), where)
            if item["label"] != expected_label or item["label"] in seen:
                raise BindingError(f"{where}: missing/duplicated/reordered P0 label")
            seen.add(item["label"])
            predicate = {"atom": item["atom"], "truth": item["truth"]}
            _predicate(predicate, where)
            if predicate != executable:
                raise BindingError(f"{where}: machine predicate does not match bound clause")
            if kind == "preconditions":
                claim = indexed_claims.get(item["claim_id"])
                if claim is None or claim["claim_type"] != "source_attributed":
                    raise BindingError(f"{where}: source-attributed premise claim required")
                if not any(item["claim_id"] in inf["premise_claim_ids"] for inf in matching):
                    raise BindingError(f"{where}: premise claim not used by an applying P0 inference")
                evidence_ids = claim["evidence_ids"]
            else:
                evidence_ids = item["source_evidence_ids"]
            if not isinstance(evidence_ids, list) or not evidence_ids or len(set(evidence_ids)) != len(evidence_ids):
                raise BindingError(f"{where}: nonempty unique evidence IDs required")
            if any(e not in indexed_evidence or indexed_evidence[e]["verification_status"] != "verified"
                   for e in evidence_ids):
                raise BindingError(f"{where}: source evidence missing or not P0-verified")

    correspondence(rule["preconditions"], binding["preconditions"],
                   spec["if_all"], "preconditions")
    correspondence(rule["exceptions"], binding["exceptions"],
                   spec.get("unless_any", []), "exceptions")
    conclusion = binding["conclusion"]
    _exact_keys(conclusion, ("claim_id", "atom", "truth"), "binding.conclusion")
    predicate = {"atom": conclusion["atom"], "truth": conclusion["truth"]}
    _predicate(predicate, "binding.conclusion")
    if predicate != spec.get("then"):
        raise BindingError("binding: conclusion predicate mismatch")
    if not any(inf["conclusion_claim_id"] == conclusion["claim_id"] for inf in matching):
        raise BindingError("binding: conclusion claim not produced by applying P0 inference")
    claim = indexed_claims.get(conclusion["claim_id"])
    if not claim or claim["claim_type"] != "inferred":
        raise BindingError("binding: inferred P0 conclusion claim required")
    return {
        "status": "STRUCTURALLY_BOUND",
        "rule_sha256": digest,
        "preconditions_bound": len(binding["preconditions"]),
        "exceptions_bound": len(binding["exceptions"]),
        "p0_conclusion_claim_id": conclusion["claim_id"],
        "semantic_equivalence_verified": False,
        "note": "Structural label/claim alignment and digest only; rule meaning is not independently certified.",
    }


def cited_sources(bundle, evidence_ids):
    """Reference metadata only. Excerpts and potentially copyrighted text omitted."""
    evidence = {x["id"]: x for x in bundle["evidence"]}
    sources = {x["id"]: x for x in bundle["sources"]}
    items = []
    for key in sorted(set(evidence_ids)):
        entry = evidence[key]
        source = sources[entry["source_id"]]
        items.append({
            "evidence_id": key,
            "source_id": source["id"],
            "work_title": source["work_title"],
            "edition": source["edition"],
            "source_locator": source["locator"],
            "evidence_locator": entry["locator"],
            "source_content_sha256": source["content_sha256"],
            "excerpt_sha256": entry["excerpt_sha256"],
            "verification_claim": entry["verification_status"],
            "attribution_scope": "P0_DECLARED_METADATA_NOT_EXTERNAL_SOURCE_AUTHENTICATION",
            "source_excerpt_reproduced": False,
            "redistribution_permission_inferred": False,
        })
    return items
