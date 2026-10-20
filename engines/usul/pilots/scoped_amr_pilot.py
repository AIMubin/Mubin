"""An al-Waraqat attributed demonstration of scoped exception inspections.

This pilot exercises source citations + bounded synthetic evidence checks.
It is not an attestation of real-world absence of qarain or a fiqh ruling.
"""
from __future__ import annotations

import json

from engines.usul.p0_bridge import build_and_run
from engines.usul.pilots.amr_default import (
    SOURCE_URL, SOURCE_EXCERPT, _digest, example_bundle, example_spec,
)


RULE = "pilot:rule-amr-default"
ATOM = "pilot:diverting-indicator"
CONCLUSION = "pilot:default-obligation-candidate"
SEARCH_SCOPE = {
    "id": "pilot:declared-case-inspection",
    "kind": "synthetic_fixture",
    "declared_items": ["pilot:case-part1", "pilot:case-part2"],
}


def _inspection(finding, inspected):
    return [{
        "rule_id": RULE,
        "exception_atom": ATOM,
        "finding": finding,
        "evidence_ids": (
            ["pilot:ev-indicator"] if finding != "NOT_CHECKED" else []
        ),
        "scope": {**SEARCH_SCOPE, "checked_items": inspected},
    }]


def run() -> dict:
    b = example_bundle()
    specs = example_spec(b)
    command = [{"atom": "pilot:command-form", "truth": "true",
                "source_evidence_ids": ["pilot:ev-command"]}]
    cases = {
        "declared_scope_inspected_no_indicator": (
            command,
            _inspection("ABSENT_IN_DECLARED_SCOPE", list(SEARCH_SCOPE["declared_items"])),
        ),
        "indicator_observed": (
            command, _inspection("PRESENT", ["pilot:case-part1"]),
        ),
        "inspection_not_performed": (
            command, _inspection("NOT_CHECKED", []),
        ),
        "premise_missing_despite_scope_check": (
            [], _inspection("ABSENT_IN_DECLARED_SCOPE",
                            list(SEARCH_SCOPE["declared_items"])),
        ),
    }
    results = {}
    for key, (facts, checks) in cases.items():
        outcome = build_and_run(
            b, specs, facts,
            require_semantic_binding=True,
            exception_assessments=checks,
            require_evidence_exceptions=True,
        )
        if (outcome["derivation_refused"]
                or outcome["attribution"]["rules_rejected"]
                or outcome["attribution"]["facts_rejected"]):
            raise RuntimeError("Invalid scoped exception pilot fixture: " + key)
        results[key] = {
            "rule_status": outcome["usul_result"]["trace"][0]["status"],
            "conclusion_status": outcome["usul_result"]["conclusions"][CONCLUSION]["status"],
            "assessment": outcome["exception_assessment_trace"][0],
            "cited_evidence": outcome["rule_citations"][RULE],
            "real_world_absence_verified": outcome["real_world_absence_verified"],
        }
    return {
        "name": "al-waraqat-amr-scoped-exception-evidence",
        "milestone": "U0.1_RESEARCH_EXPERIMENT",
        "work": "الورقات في أصول الفقه",
        "section": "باب الأمر",
        "author": "إمام الحرمين الجويني",
        "digital_witness_url": SOURCE_URL,
        "excerpt_sha256": _digest(SOURCE_EXCERPT),
        "sha256_scope": "EXACT_UTF8_EXCERPT_NOT_FULL_TEXT",
        "scope_type": "DECLARED_SYNTHETIC_CASES_ONLY",
        "search_not_performed_is_not_negative": True,
        "scope_completeness_does_not_prove_universal_absence": True,
        "semantic_equivalence_verified": False,
        "external_source_authentication_verified": False,
        "scholarly_verified": False,
        "valid_juristic_ruling": False,
        "public_fatwa_authorized": False,
        "cases": results,
    }


def main():
    # ASCII-safe escaped JSON survives legacy Windows console encodings.
    print(json.dumps(run(), ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
