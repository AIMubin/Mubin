"""Fail-closed P0 structural checks, not scholarly authentication or rule execution."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "inference-foundation.schema.json"
COLLECTIONS = (
    "sources", "evidence", "methodologies", "claims", "rules",
    "inferences", "objections", "proofs", "historical_availability",
)
# P0 handles small research bundles, not corpus-scale untrusted graph ingestion.
MAX_ENTITIES = 5000
MAX_DEPENDENCY_DEPTH = 128


def validate_bundle(bundle: dict[str, Any]) -> list[str]:
    """Return structural problems; an empty list is NOT a religious verdict."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    errors = [
        "schema: " + ".".join(str(x) for x in error.absolute_path) + ": " + error.message
        for error in Draft202012Validator(schema).iter_errors(bundle)
    ]
    if errors:
        return sorted(set(errors))
    if sum(len(bundle[collection]) for collection in COLLECTIONS) > MAX_ENTITIES:
        return [f"bundle exceeds P0 structural entity cap of {MAX_ENTITIES}"]

    index: dict[str, dict[str, Any]] = {}
    membership: dict[str, str] = {}
    for collection in COLLECTIONS:
        index[collection] = {}
        for item in bundle[collection]:
            key = item["id"]
            if key in membership:
                errors.append("duplicate entity id: " + key)
            else:
                membership[key] = collection
            index[collection][key] = item

    def require(collection: str, key: str, context: str) -> dict[str, Any] | None:
        entity = index[collection].get(key)
        if entity is None:
            errors.append(f"{context}: unknown {collection} reference {key}")
        return entity

    def evidence_refs(ids: list[str], context: str, require_verified: bool = True) -> bool:
        if not ids:
            errors.append(f"{context}: no source evidence")
            return False
        okay = True
        for key in ids:
            e = require("evidence", key, context)
            if e is None:
                okay = False
            elif require_verified and e["verification_status"] != "verified":
                errors.append(f"{context}: evidence {key} is not verified")
                okay = False
        return okay

    for e in bundle["evidence"]:
        require("sources", e["source_id"], "evidence " + e["id"])
        actual = hashlib.sha256(e["excerpt"].encode("utf-8")).hexdigest()
        if actual != e["excerpt_sha256"]:
            errors.append(f"evidence {e['id']}: excerpt digest mismatch")
        if (e["verification_status"] == "verified") != (e["verification_method"] != "unverified"):
            errors.append(f"evidence {e['id']}: inconsistent verification method/status")

    for m in bundle["methodologies"]:
        evidence_refs(m["source_evidence_ids"], "methodology " + m["id"])

    for r in bundle["rules"]:
        require("methodologies", r["methodology_id"], "rule " + r["id"])
        evidence_refs(r["source_evidence_ids"], "rule " + r["id"])

    for inf in bundle["inferences"]:
        context = "inference " + inf["id"]
        require("methodologies", inf["methodology_id"], context)
        conclusion = require("claims", inf["conclusion_claim_id"], context)
        if conclusion is not None:
            if conclusion["claim_type"] != "inferred" or conclusion.get("inference_id") != inf["id"]:
                errors.append(f"{context}: conclusion not reciprocally bound")
            if inf["inference_kind"] == "qiyas" and conclusion["conclusion_kind"] != "qiyas_derived":
                errors.append(f"{context}: qiyas conclusion has wrong origin label")
            if inf["inference_kind"] != "qiyas" and conclusion["conclusion_kind"] == "qiyas_derived":
                errors.append(f"{context}: non-qiyas conclusion claims qiyas origin")
        # Prevent rule-kind laundering: a qiyas rule cannot be presented as deduction
        # to avoid the mandatory asl/far/hukm/illah trace. Auxiliary constraints
        # and exceptions can accompany a kind-matched rule, never replace it.
        kinds_seen = set()
        for key in inf["rule_ids"]:
            rule = require("rules", key, context)
            if rule is None:
                continue
            kind = rule["rule_type"]
            kinds_seen.add(kind)
            if rule["methodology_id"] != inf["methodology_id"]:
                errors.append(f"{context}: incompatible methodology in rule {key}")
            if kind not in (inf["inference_kind"], "constraint", "exception"):
                errors.append(f"{context}: rule kind {kind} incompatible with {inf['inference_kind']}")
        if inf["inference_kind"] not in kinds_seen:
            errors.append(f"{context}: missing matching {inf['inference_kind']} rule")
        for key in inf["premise_claim_ids"]:
            premise = require("claims", key, context)
            if premise is not None and conclusion is not None:
                if conclusion["modality"] == "actual" and premise["modality"] == "counterfactual":
                    errors.append(f"{context}: counterfactual premise cannot support actual claim")
            if premise is not None and premise["claim_type"] == "inferred":
                parent = index["inferences"].get(premise.get("inference_id"))
                if parent is not None and parent["methodology_id"] != inf["methodology_id"]:
                    errors.append(f"{context}: incompatible methodology in derived premise {key}")
        if inf["inference_kind"] == "qiyas":
            elements = inf.get("qiyas_elements", {})
            for role in ("asl", "far", "hukm_al_asl", "illah"):
                if elements.get(role) not in inf["premise_claim_ids"]:
                    errors.append(f"{context}: missing {role} among premises")
            if len(set(elements.values())) != 4:
                errors.append(f"{context}: qiyas roles must be distinct claims")
        for check in inf["exception_checks"]:
            if check["outcome"] == "cleared":
                evidence_refs(check["evidence_ids"], context + " exception " + check["exception"])

    # Evaluate every claim's rootedness AND longest dependency path. A boolean-only
    # memo lets long source-first chains bypass the cap; include the absolute depth
    # in the memo so the outcome is independent of collection ordering.
    memo: dict[str, tuple[bool, int]] = {}

    def rooted(claim_id: str, stack: frozenset[str] = frozenset()) -> bool:
        if claim_id in stack:
            errors.append(f"cycle: premise dependency includes {claim_id}")
            return False
        if len(stack) >= MAX_DEPENDENCY_DEPTH:
            errors.append(f"claim {claim_id}: dependency exceeds P0 depth cap")
            return False
        if claim_id in memo:
            valid, depth = memo[claim_id]
            if len(stack) + depth > MAX_DEPENDENCY_DEPTH:
                errors.append(f"claim {claim_id}: dependency exceeds P0 depth cap")
                return False
            return valid

        claim = require("claims", claim_id, "proof trace")
        if claim is None:
            return False
        depth = 1
        if claim["claim_type"] == "source_attributed":
            okay = claim["conclusion_kind"] == "source_derived"
            if not okay:
                errors.append(f"claim {claim_id}: source claim has non-source origin label")
            if "inference_id" in claim:
                errors.append(f"claim {claim_id}: source claim cannot own an inference")
                okay = False
            okay = evidence_refs(claim["evidence_ids"], "claim " + claim_id) and okay
        else:
            okay = claim["conclusion_kind"] != "source_derived"
            if not okay:
                errors.append(f"claim {claim_id}: inferred claim has source-only origin label")
            inf_id = claim.get("inference_id")
            inf = require("inferences", inf_id, "claim " + claim_id) if inf_id else None
            if not inf_id:
                errors.append(f"claim {claim_id}: inferred claim without inference")
            if inf is None:
                okay = False
            else:
                if inf["conclusion_claim_id"] != claim_id:
                    errors.append(f"claim {claim_id}: inference concludes a different claim")
                    okay = False
                premise_results = [
                    rooted(premise, stack | {claim_id})
                    for premise in inf["premise_claim_ids"]
                ]
                if not all(premise_results):
                    okay = False
                depth = 1 + max(
                    (memo.get(premise, (False, 0))[1] for premise in inf["premise_claim_ids"]),
                    default=0,
                )
                for rule_id in inf["rule_ids"]:
                    rule = index["rules"].get(rule_id)
                    if rule is None or not evidence_refs(
                        rule["source_evidence_ids"], "inference " + inf_id + " rule " + rule_id
                    ):
                        okay = False
                if claim["evidence_ids"] and not evidence_refs(
                    claim["evidence_ids"], "claim " + claim_id
                ):
                    okay = False
        if depth > MAX_DEPENDENCY_DEPTH:
            errors.append(f"claim {claim_id}: dependency exceeds P0 depth cap")
            okay = False
        memo[claim_id] = (okay, depth)
        return okay

    def trace_evidence(claim_id: str) -> set[str]:
        """Only claim and applied-rule evidence in the claim's own inference closure."""
        found: set[str] = set()
        visited_claims: set[str] = set()
        pending = [claim_id]
        while pending:
            current = pending.pop()
            if current in visited_claims:
                continue
            visited_claims.add(current)
            claim = index["claims"].get(current)
            if claim is None:
                continue
            found.update(claim["evidence_ids"])
            if claim["claim_type"] != "inferred":
                continue
            inf = index["inferences"].get(claim.get("inference_id"))
            if inf is None:
                continue
            for rule_id in inf["rule_ids"]:
                rule = index["rules"].get(rule_id)
                if rule is not None:
                    found.update(rule["source_evidence_ids"])
            pending.extend(inf["premise_claim_ids"])
        return found

    for claim in bundle["claims"]:
        rooted(claim["id"])
        if claim["modality"] == "counterfactual":
            context = "counterfactual claim " + claim["id"]
            ctx = claim["counterfactual_context"]
            history = require("historical_availability", ctx["historical_availability_id"], context)
            require("evidence", ctx["assumed_evidence_id"], context)
            if history is not None:
                if history["scholar_id"] != ctx["scholar_id"]:
                    errors.append(f"{context}: historical scholar identity mismatch")
                if history["evidence_id"] != ctx["assumed_evidence_id"]:
                    errors.append(f"{context}: assumed evidence not bound to historical case")
                if history["knowledge_state"] == "attested_reached":
                    errors.append(f"{context}: evidence already attested reached; no non-reachability counterfactual")
            if ctx["assumed_evidence_id"] not in trace_evidence(claim["id"]):
                errors.append(f"{context}: assumed evidence absent from inference trace")

    for o in bundle["objections"]:
        require("inferences", o["target_inference_id"], "objection " + o["id"])
        evidence_refs(o["evidence_ids"], "objection " + o["id"])
        if o["status"] == "answered":
            evidence_refs(o["answer"]["evidence_ids"], "objection answer " + o["id"])
        else:
            target = index["inferences"].get(o["target_inference_id"])
            if target is not None:
                conclusion = index["claims"].get(target["conclusion_claim_id"])
                if conclusion is not None and conclusion["assessment_status"] == "no_recorded_objection":
                    errors.append(
                        f"objection {o['id']}: open objection contradicts no_recorded_objection on {conclusion['id']}"
                    )

    def trace_inferences(claim_id: str) -> set[str]:
        # Iterative reachability: a global seen count measures width, NOT depth.
        # The rooted() pass independently limits maximum graph path depth.
        found: set[str] = set()
        visited_claims: set[str] = set()
        pending = [claim_id]
        while pending:
            current = pending.pop()
            if current in visited_claims:
                continue
            visited_claims.add(current)
            claim = index["claims"].get(current)
            if claim is None or claim["claim_type"] != "inferred":
                continue
            inference_id = claim.get("inference_id")
            inf = index["inferences"].get(inference_id)
            if inf is None:
                continue
            found.add(inference_id)
            pending.extend(inf["premise_claim_ids"])
        return found

    for p in bundle["proofs"]:
        context = "proof " + p["id"]
        require("methodologies", p["methodology_id"], context)
        if require("claims", p["conclusion_claim_id"], context) is None:
            continue
        expected = trace_inferences(p["conclusion_claim_id"])
        actual = set(p["inference_ids"])
        if expected != actual:
            errors.append(f"{context}: inference trace does not match conclusion dependencies")
        for key in p["inference_ids"]:
            inf = require("inferences", key, context)
            if inf is not None and inf["methodology_id"] != p["methodology_id"]:
                errors.append(f"{context}: mixed methodology in inference {key}")
        if p["verification_status"] == "structurally_checked":
            # Checking the final claim alone is insufficient: a contested/undetermined
            # premise can otherwise be laundered into a clean-looking descendant.
            closure = set()
            pending = [p["conclusion_claim_id"]]
            while pending:
                claim_id = pending.pop()
                if claim_id in closure:
                    continue
                closure.add(claim_id)
                claim = index["claims"].get(claim_id)
                if claim is not None and claim["claim_type"] == "inferred":
                    dep = index["inferences"].get(claim.get("inference_id"))
                    if dep is not None:
                        pending.extend(dep["premise_claim_ids"])
            for claim_id in closure:
                claim = index["claims"].get(claim_id)
                if claim is not None and claim["assessment_status"] != "no_recorded_objection":
                    errors.append(f"{context}: unresolved premise or conclusion {claim_id}")
            if not rooted(p["conclusion_claim_id"]) or not expected:
                errors.append(f"{context}: unsupported conclusion cannot be checked")
            for o in bundle["objections"]:
                if o["target_inference_id"] in actual and o["status"] != "answered":
                    errors.append(f"{context}: outstanding objection {o['id']}")
            for key in actual:
                inf = index["inferences"].get(key)
                if inf is None:
                    continue
                checks = inf["exception_checks"]
                declared = set()
                for rule_id in inf["rule_ids"]:
                    rule = index["rules"].get(rule_id)
                    if rule is not None:
                        declared.update(rule["exceptions"])
                outcomes = {check["exception"]: check["outcome"] for check in checks}
                if len(outcomes) != len(checks):
                    errors.append(f"{context}: duplicated exception check in {key}")
                if any(outcome != "cleared" for outcome in outcomes.values()):
                    errors.append(f"{context}: unresolved or triggered exception in {key}")
                if not declared.issubset({
                    name for name, outcome in outcomes.items() if outcome == "cleared"
                }):
                    errors.append(f"{context}: unchecked declared rule exceptions in {key}")

    for h in bundle["historical_availability"]:
        context = "history " + h["id"]
        require("evidence", h["evidence_id"], context)
        state, basis = h["knowledge_state"], h["basis_type"]
        if state != "unknown":
            evidence_refs([h["evidence_id"]], context + " historical target")
        if state == "unknown":
            if basis != "none" or h["basis_evidence_ids"]:
                errors.append(f"{context}: unknown cannot assert a verified reachability basis")
        else:
            evidence_refs(h["basis_evidence_ids"], context)
            if basis == "none":
                errors.append(f"{context}: attested knowledge needs an explicit basis")
            if state == "attested_not_reached" and basis not in (
                "explicit_historical_testimony", "documented_chronological_impossibility"
            ):
                errors.append(f"{context}: non-reachability cannot be inferred from silence")
            if state == "attested_reached" and basis != "explicit_historical_testimony":
                errors.append(f"{context}: reachability requires explicit historical testimony")

    return sorted(set(errors))
