"""Purpose-scoped, risk-proportionate assurance for Mubin actions.

This policy decides whether declared evidence would be sufficient for an action.
It does NOT authenticate the caller's claims, grant copyright licenses, perform
religious certification, or override historical H3.9.2 Schema-31 gates.
"""
from __future__ import annotations

ACTIONS = frozenset({
    "engineering_change",
    "document_source_anomaly",
    "internal_text_diagnostics",
    "publish_verbatim_source",
    "publish_editorial_reconstruction",
    "publish_scholarly_conclusion",
    "promote_h392_gold",
    "system_release",
})

BOOLEAN_EVIDENCE = frozenset({
    "machine_checks_passed", "provenance_verified", "source_untouched",
    "access_restricted", "quran_witness_verified", "editorial_approved",
    "qualified_scholarly_review", "h392_protocol_passed",
    "independent_human_protocol_verified", "integration_evaluation_passed",
    "known_safety_blockers_absent", "includes_scholarly_conclusions",
})

RIGHTS = frozenset({"unknown", "restricted", "internal_only", "redistribution_permitted"})
KINDS = frozenset({"quran", "tafsir", "hadith", "usul", "fiqh", "metadata"})
HUMAN_GATED = frozenset({
    "publish_editorial_reconstruction", "publish_scholarly_conclusion",
    "promote_h392_gold",
})


def evaluate_action(request: dict) -> dict:
    """Return a *policy eligibility* decision, not verified scholarly approval.

    Inputs are assertions from the requesting subsystem. Provenance/rights
    attestations must be checked by independent evidence plumbing upstream.
    Unexpected fields and unknown actions fail closed.
    """
    if not isinstance(request, dict):
        raise ValueError("Review request must be a mapping")
    action = request.get("action")
    if not isinstance(action, str) or action not in ACTIONS:
        raise ValueError("Unknown or missing review action")
    allowed_keys = {"action", "rights", "source_kind"} | BOOLEAN_EVIDENCE
    unknown = set(request) - allowed_keys
    if unknown:
        raise ValueError("Unrecognized assurance fields: " + ", ".join(sorted(unknown)))
    if "rights" in request and (not isinstance(request["rights"], str) or request["rights"] not in RIGHTS):
        raise ValueError("Unknown rights state")
    if "source_kind" in request and (not isinstance(request["source_kind"], str) or request["source_kind"] not in KINDS):
        raise ValueError("Unknown source kind")
    for key in BOOLEAN_EVIDENCE & set(request):
        if type(request[key]) is not bool:
            raise ValueError(f"{key} must be a literal boolean")

    reasons = []
    def require(key, code=None):
        if request.get(key) is not True:
            reasons.append(code or ("REQUIRES_" + key.upper()))

    def provenance():
        require("provenance_verified")

    def rights():
        if request.get("rights", "unknown") != "redistribution_permitted":
            reasons.append("REDISTRIBUTION_RIGHTS_NOT_VERIFIED")

    def technical():
        require("machine_checks_passed")
        require("known_safety_blockers_absent")

    source_kind = request.get("source_kind")
    if action == "engineering_change":
        technical()
    elif action == "document_source_anomaly":
        technical()
        provenance()
        require("source_untouched")
    elif action == "internal_text_diagnostics":
        provenance()
        require("access_restricted")
    elif action == "publish_verbatim_source":
        technical()
        provenance()
        require("source_untouched")
        rights()
        if source_kind is None or source_kind == "metadata":
            reasons.append("TEXT_SOURCE_KIND_REQUIRED")
        if source_kind == "quran":
            require("quran_witness_verified")
    elif action == "publish_editorial_reconstruction":
        technical()
        provenance()
        rights()
        require("editorial_approved")
        if source_kind in (None, "metadata", "quran"):
            reasons.append("SOURCE_KIND_NOT_ELIGIBLE_FOR_EDITORIAL_RECONSTRUCTION")
    elif action == "publish_scholarly_conclusion":
        technical()
        provenance()
        require("qualified_scholarly_review")
    elif action == "promote_h392_gold":
        technical()
        require("h392_protocol_passed")
        require("independent_human_protocol_verified")
    elif action == "system_release":
        technical()
        require("integration_evaluation_passed")
        if request.get("includes_scholarly_conclusions") is True:
            require("qualified_scholarly_review")
        # Any source corpus served publicly also needs its own rights checks
        # under publish_verbatim_source, independently of this umbrella gate.

    return {
        "action": action,
        "decision": "ELIGIBLE" if not reasons else "BLOCKED",
        "blockers": reasons,
        "qualified_human_review_is_action_gate": action in HUMAN_GATED or (
            action == "system_release" and request.get("includes_scholarly_conclusions") is True
        ),
        "assurance_scope": "DECLARED_EVIDENCE_POLICY_ONLY",
        "scholarly_verified": False,
        "rights_granted_by_this_check": False,
        "note": "Eligibility does not verify inputs, publish content, attest a printed edition or waive licenses.",
    }


def main():
    """Policy triage CLI: exit 0 eligible; 1 blocked; 2 invalid input."""
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path, help="UTF-8 JSON policy request")
    arguments = parser.parse_args()
    try:
        size = arguments.request.stat().st_size
        if size > 65536:
            raise ValueError("Request exceeds 64 KiB policy input limit")
        request = json.loads(arguments.request.read_text(encoding="utf-8"))
        decision = evaluate_action(request)
    except (OSError, ValueError) as exc:
        print(json.dumps({"decision": "INVALID", "errors": [str(exc)]},
                         ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if decision["decision"] == "ELIGIBLE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
