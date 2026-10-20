"""A source-attributed U0.1 *research* pilot of al-Juwayni's command-form rule.

Primary public digital witness: https://www.islamicbook.ws/asol/alwrqat.html
Book: Al-Waraqat, Imam al-Haramayn al-Juwayni; heading "الأمر".
Secondary cross-reading: islam.ms online al-Waraqat; NO printed-edition claim.

The only stored historical quotation is a short source excerpt, whose SHA256
pins the EXACT excerpt string, NOT the entire webpage or printed edition.
The scenario facts are wholly synthetic and NOT real fatwa inputs.
"""
from __future__ import annotations

import copy
import hashlib
import json

from engines.usul.p0_bridge import build_and_run
from engines.usul.semantic_binding import rule_fingerprint

SOURCE_URL = "https://www.islamicbook.ws/asol/alwrqat.html"
COMPARATOR_URL = "https://www.islam.ms/ar/كتاب-ورقات-أصول-فقه-إسلامي-إمام-حرمين-عبد-الملك-الجويني/"
# Single short quotation from primary public digital witness, under باب الأمر.
SOURCE_EXCERPT = ("وصيغته افعل وهي عند الإطلاق والتجرد عن القرينة تحمل عليه "
                  "إلا ما دل الدليل على أن المراد منه الندب أو الإباحة")
SYNTHETIC_VIGNETTE = "مثال اصطناعي مُنشأ لاختبار المحرك؛ لا يمثل واقعة شرعية."


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _evidence(identifier: str, source: str, locator: str, excerpt: str) -> dict:
    return {
        "id": identifier, "source_id": source, "locator": locator,
        "excerpt": excerpt, "excerpt_sha256": _digest(excerpt),
        # This 'verified' is a P0-declared excerpt SHA match, not external
        # website/edition authentication. Output keeps that boundary explicit.
        "verification_status": "verified",
        "verification_method": "exact_source_match",
    }


def example_bundle() -> dict:
    rule = {
        "id": "pilot:rule-amr-default", "methodology_id": "pilot:juwayni-waraqat",
        "rule_type": "deduction",
        "expression": "بحثي: صيغة أمر صريحة مع عدم قرينة صارفة => مرشح للوجوب",
        "preconditions": ["pilot:command-form"],
        "exceptions": ["pilot:diverting-indicator"],
        "source_evidence_ids": ["pilot:ev-waraqat"],
        "formalization_status": "machine_checkable",
    }
    return {
        "contract_version": "0.1.0",
        "sources": [
            {
                "id": "pilot:waraqat-digital", "kind": "usul",
                "work_title": "الورقات في أصول الفقه — إمام الحرمين الجويني",
                "edition": "Online digital text, print edition not established; excerpt-only witness",
                "locator": "باب الأمر",
                "content_sha256": _digest(SOURCE_EXCERPT),
            },
            {
                "id": "pilot:synthetic-fixture", "kind": "other",
                "work_title": "Mubin generated synthetic test vignette",
                "edition": "Technical fixture v0.1; no external religious source",
                "locator": "synthetic case inputs",
                "content_sha256": _digest(SYNTHETIC_VIGNETTE),
            },
        ],
        "evidence": [
            _evidence("pilot:ev-waraqat", "pilot:waraqat-digital",
                      "باب الأمر، paragraph on صيغة افعل", SOURCE_EXCERPT),
            _evidence("pilot:ev-command", "pilot:synthetic-fixture",
                      "synthetic case input: command form", SYNTHETIC_VIGNETTE),
            _evidence("pilot:ev-indicator", "pilot:synthetic-fixture",
                      "synthetic case input: diverting indication", SYNTHETIC_VIGNETTE),
        ],
        "methodologies": [{
            "id": "pilot:juwayni-waraqat",
            "label": "Source-attributed modeling of al-Juwayni's chapter on commands",
            "version": "0.1.0-research", "source_evidence_ids": ["pilot:ev-waraqat"],
        }],
        "claims": [
            {
                "id": "pilot:c-command", "statement": "Synthetic command-form premise",
                "claim_type": "source_attributed", "conclusion_kind": "source_derived",
                "evidence_ids": ["pilot:ev-command"],
                "modality": "actual", "assessment_status": "no_recorded_objection",
            },
            {
                "id": "pilot:c-default", "statement": "Research model default obligation candidate",
                "claim_type": "inferred", "conclusion_kind": "rule_derived",
                "evidence_ids": ["pilot:ev-waraqat"], "inference_id": "pilot:inf-default",
                "modality": "actual", "assessment_status": "undetermined",
            },
        ],
        "rules": [rule],
        "inferences": [{
            "id": "pilot:inf-default", "inference_kind": "deduction",
            "methodology_id": "pilot:juwayni-waraqat",
            "rule_ids": ["pilot:rule-amr-default"],
            "premise_claim_ids": ["pilot:c-command"],
            "conclusion_claim_id": "pilot:c-default",
            "exception_checks": [{
                "exception": "pilot:diverting-indicator", "outcome": "unknown",
                "evidence_ids": ["pilot:ev-indicator"],
            }],
        }],
        "objections": [],
        "proofs": [{
            "id": "pilot:proof-default", "conclusion_claim_id": "pilot:c-default",
            "inference_ids": ["pilot:inf-default"],
            "methodology_id": "pilot:juwayni-waraqat",
            "verification_scope": "structural_only",
            "verification_status": "undetermined",
        }],
        "historical_availability": [],
    }


def example_spec(bundle: dict) -> dict:
    rule = bundle["rules"][0]
    return {
        rule["id"]: {
            "if_all": [{"atom": "pilot:command-form", "truth": "true"}],
            "unless_any": [{"atom": "pilot:diverting-indicator", "truth": "true"}],
            "then": {"atom": "pilot:default-obligation-candidate", "truth": "true"},
            "binding": {
                "version": "0.1.0",
                "rule_sha256": rule_fingerprint(rule),
                "preconditions": [{
                    "label": "pilot:command-form", "claim_id": "pilot:c-command",
                    "atom": "pilot:command-form", "truth": "true",
                }],
                "exceptions": [{
                    "label": "pilot:diverting-indicator",
                    "atom": "pilot:diverting-indicator", "truth": "true",
                    "source_evidence_ids": ["pilot:ev-indicator"],
                }],
                "conclusion": {
                    "claim_id": "pilot:c-default", "atom": "pilot:default-obligation-candidate",
                    "truth": "true",
                },
            },
        }
    }


def _fact(atom: str, truth: str, evidence: str) -> dict:
    return {"atom": atom, "truth": truth, "source_evidence_ids": [evidence]}


def scenarios() -> dict:
    command = _fact("pilot:command-form", "true", "pilot:ev-command")
    no_indicator = _fact("pilot:diverting-indicator", "false", "pilot:ev-indicator")
    has_indicator = _fact("pilot:diverting-indicator", "true", "pilot:ev-indicator")
    return {
        "fully_declared_no_indicator": [command, no_indicator],
        "diverting_indicator_present": [command, has_indicator],
        "indicator_unknown": [command],
        "command_missing": [no_indicator],
    }


def run_pilot() -> dict:
    bundle = example_bundle()
    specs = example_spec(bundle)
    cases = {}
    for name, scenario in scenarios().items():
        out = build_and_run(bundle, specs, copy.deepcopy(scenario),
                            require_semantic_binding=True)
        if out["derivation_refused"] or out["attribution"]["rules_rejected"] or out["attribution"]["facts_rejected"]:
            raise RuntimeError("Pilot fixture rejected: " + name)
        cases[name] = {
            "status": out["usul_result"]["conclusions"]["pilot:default-obligation-candidate"]["status"],
            "rule_status": out["usul_result"]["trace"][0]["status"],
            "source_citations": out["rule_citations"]["pilot:rule-amr-default"],
            "binding_status": out["semantic_bindings"]["pilot:rule-amr-default"]["status"],
        }
    return {
        "pilot": "waraqat-bab-al-amr",
        "milestone": "U0.1_SOURCE_ATTRIBUTED_RESEARCH",
        "source_reference": {
            "author": "إمام الحرمين عبد الملك بن عبد الله الجويني",
            "work_title": "الورقات في أصول الفقه",
            "section": "باب الأمر",
            "public_digital_witness_url": SOURCE_URL,
            "comparator_url": COMPARATOR_URL,
            "edition": "UNVERIFIED_DIGITAL_WITNESS_NOT_PINNED_PRINT_EDITION",
            "source_sha256_scope": "EXCERPT_ONLY_UTF8_NOT_ENTIRE_BOOK_OR_WEBPAGE",
            "excerpt_utf8_sha256": _digest(SOURCE_EXCERPT),
            "witness_externally_revalidated_by_cli": False,
            "redistribution_rights_inferred": False,
        },
        "scenario_kind": "SYNTHETIC_TEST_INPUTS",
        "semantic_equivalence_verified": False,
        "scholarly_verified": False,
        "valid_juristic_ruling": False,
        "public_fatwa_authorized": False,
        "cases": cases,
    }


def main() -> int:
    # JSON Unicode escapes survive Windows consoles using legacy cp1252.
    print(json.dumps(run_pilot(), ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
