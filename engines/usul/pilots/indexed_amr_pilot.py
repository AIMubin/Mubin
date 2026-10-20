"""Stage 03: code-pinned synthetic source-index inspection with al-Waraqat attribution.

Historical rule reference is real and excerpt-scoped; indexed data are
*synthetic*, the marker is literal, and outputs are not legal interpretations.
"""
from __future__ import annotations

import json

from engines.usul.p0_bridge import build_and_run
from engines.usul.pilots.amr_default import (
    SOURCE_URL, SOURCE_EXCERPT, _digest, example_bundle, example_spec,
)

CONCLUSION = "pilot:default-obligation-candidate"
RULE = "pilot:rule-amr-default"


def run() -> dict:
    bundle, specs = example_bundle(), example_spec(example_bundle())
    premise = [{"atom": "pilot:command-form", "truth": "true",
                "source_evidence_ids": ["pilot:ev-command"]}]
    scenarios = {
        "pinned_absent_in_synthetic_index": ("absent", premise),
        "pinned_positive_marker": ("present", premise),
        "index_search_not_performed": ("not_checked", premise),
        "synthetic_command_premise_missing": ("absent", []),
    }
    results = {}
    for name, (index, facts) in scenarios.items():
        output = build_and_run(
            bundle, specs, facts,
            require_semantic_binding=True,
            require_evidence_exceptions=True,
            pinned_scope_index=index,
            require_pinned_scope_index=True,
        )
        if (output["derivation_refused"] is not None
                or output["attribution"]["rules_rejected"]
                or output["attribution"]["facts_rejected"]):
            raise RuntimeError("Invalid pinned synthetic index pilot: " + name)
        results[name] = {
            "rule_status": output["usul_result"]["trace"][0]["status"],
            "conclusion_status": output["usul_result"]["conclusions"][CONCLUSION]["status"],
            "machine_index_proof": output["pinned_scope_index_proof"],
            "exception_finding": output["exception_assessment_trace"][0]["finding"],
            "rule_source_citations": output["rule_citations"][RULE],
            "real_world_absence_verified": output["real_world_absence_verified"],
        }
    return {
        "campaign": "U0.1-source-index-stage03",
        "rule_work": "الورقات في أصول الفقه",
        "rule_section": "باب الأمر",
        "author": "إمام الحرمين الجويني",
        "digital_witness_url": SOURCE_URL,
        "rule_excerpt_utf8_sha256": _digest(SOURCE_EXCERPT),
        "rule_excerpt_hash_scope": "SHORT_EXCERPT_ONLY_NO_PRINT_EDITION_VERIFICATION",
        "index_scope": "TWO_CODE_PINNED_SYNTHETIC_FIXTURE_ITEMS",
        "scanner": "EXACT_LITERAL_TOKEN_NO_ARABIC_SEMANTIC_ANALYSIS",
        "real_source_corpus_exhaustiveness_verified": False,
        "semantic_equivalence_verified": False,
        "scholarly_verified": False,
        "valid_juristic_ruling": False,
        "public_fatwa_authorized": False,
        "redistribution_approved": False,
        "scenarios": results,
    }


def main():
    print(json.dumps(run(), ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
