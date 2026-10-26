"""E2E-01.4b.1: evidence-referenced AMR casebook; NOT a juristic evaluator.

The first 24 cases probe citation identity and whether to abstain without
verified Quran/Tafsir/qarinah witnesses. They do not establish independent
scientific gold labels or discover command morphology.

No private vault, Quran/Tafsir text, model API, or extra governance service.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any

from engines.quran.research.private_adapters import _reference

CONTRACT = "mubin-amr-casebook-v0.1"
CASEBOOK_PATH = Path(__file__).resolve().parents[2] / (
    "evaluation/benchmarks/e2e_amr_cases_v01.json")
KINDS = {
    "POSITIVE_CANDIDATE": "CANDIDATE_UNVERIFIED",
    "CONSTRUCTED_NEGATIVE": "REFUTED_REFERENCE_CONFLICT",
    "UNRESOLVED_CONTEXT": "UNDETERMINED",
}
SPLITS = ("development", "holdout")
LOCKED_GROUPS = {
    "development": ("2:43", "2:110", "4:59", "5:6"),
    "holdout": ("17:23", "24:56", "62:9", "2:282"),
}
FLAG_KEYS = (
    "scholarly_verified", "source_authenticated", "publication_allowed",
    "juristic_inference_allowed", "public_fatwa_authorized", "p1_admitted",
)


class CasebookError(ValueError):
    """Stable errors without embedding restricted content or local paths."""
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _require(ok: bool, code: str):
    if not ok:
        raise CasebookError(code)


def _outcome(case: dict) -> str:
    # Exactly the reference-integrity/absence boundary tested in v0.1.
    # A matched reference plus reported word does NOT entail usul support.
    if case["asserted_word_reference"] != case["reference"]:
        return "REFUTED_REFERENCE_CONFLICT"
    if case["observed_word"] is None:
        return "UNDETERMINED"
    return "CANDIDATE_UNVERIFIED"


def validate_casebook(data: Any) -> None:
    """Reject duplicate, leaked, unpinned, split-overlapping or promoted cases."""
    _require(type(data) is dict and data.get("contract") == CONTRACT
             and data.get("milestone") == "E2E-01.4b.1"
             and data.get("cases_total") == 24, "CASEBOOK_CONTRACT_INVALID")
    _require(type(data.get("cases")) is list
             and len(data["cases"]) == 24, "CASEBOOK_COUNT_INVALID")
    _require(data.get("categories") == {k: 8 for k in KINDS},
             "CASEBOOK_DISTRIBUTION_INVALID")
    plan = data.get("split_plan", {})
    _require(plan.get("source_family_disjoint") is False
             and type(plan.get("why_not_source_family_disjoint")) is str,
             "CASEBOOK_DISJOINT_CLAIM_INVALID")
    _require(data.get("source_authority", {}).get("scholarly_verified") is False
             and data["source_authority"].get("rights_status")
             == "legal_review_pending", "CASEBOOK_AUTHORITY_INVALID")

    counts = Counter()
    groups = defaultdict(set)
    case_ids: set[str] = set()
    word_by_group: dict[str, str] = {}
    for row in data["cases"]:
        _require(type(row) is dict, "CASEBOOK_ROW_INVALID")
        split, ref, kind = row.get("split"), row.get("reference"), row.get("category")
        _require(split in SPLITS and kind in KINDS and type(ref) is str,
                 "CASEBOOK_ROW_INVALID")
        try:
            _reference(ref)
        except ValueError as exc:
            raise CasebookError("CASEBOOK_REFERENCE_INVALID") from exc
        _require(ref in LOCKED_GROUPS[split]
                 and row.get("group_id") == "verse:" + ref,
                 "CASEBOOK_SPLIT_INVALID")
        _require(row.get("quran_witness_url")
                 == "https://quran.com/" + ref.replace(":", "/"),
                 "CASEBOOK_WITNESS_LOCATOR_INVALID")
        rule = row.get("usul_rule", {})
        _require(type(rule) is dict
                 and rule.get("rule_id") == "pilot:rule-amr-default"
                 and rule.get("url") == "https://www.islamicbook.ws/asol/alwrqat.html"
                 and rule.get("section") == "الأمر"
                 and rule.get("witness_grade")
                 == "DIGITAL_EXCERPT_ONLY_NOT_AUTHENTICATED_EDITION",
                 "CASEBOOK_RULE_INVALID")
        _require(row.get("source_family") == "quran.com_online_verse_reading"
                 and row.get("tafsir_witnesses") == []
                 and row.get("external_verse_digest") is None
                 and row.get("tafsir_connection_attested") is False,
                 "CASEBOOK_WITNESS_UNVERIFIED")
        _require(all(row.get(k) is False for k in FLAG_KEYS)
                 and row.get("scientific_gold_label") is None,
                 "CASEBOOK_AUTHORITY_INVALID")
        _require(row.get("indicator_scope") == "NOT_EXAMINED",
                 "CASEBOOK_INDICATOR_INVALID")
        rid = row.get("id")
        _require(type(rid) is str and rid not in case_ids,
                 "CASEBOOK_ID_DUPLICATED")
        case_ids.add(rid)
        index = list(LOCKED_GROUPS["development"] +
                     LOCKED_GROUPS["holdout"]).index(ref) + 1
        _require(rid == f"AMR-{index:02d}-" +
                 {"POSITIVE_CANDIDATE": "P",
                  "CONSTRUCTED_NEGATIVE": "N",
                  "UNRESOLVED_CONTEXT": "U"}[kind],
                 "CASEBOOK_ID_INVALID")
        word = row.get("observed_word")
        _require(word is None or (type(word) is str
                 and 1 <= len(word) <= 40 and word.isprintable()),
                 "CASEBOOK_WORD_INVALID")
        if kind == "UNRESOLVED_CONTEXT":
            _require(word is None and row.get("asserted_word_reference") == ref,
                     "CASEBOOK_UNRESOLVED_INVALID")
        else:
            _require(type(word) is str and bool(word)
                     and all("\u0600" <= ch <= "\u06ff" for ch in word),
                     "CASEBOOK_WORD_INVALID")
            if ref in word_by_group:
                _require(word_by_group[ref] == word,
                         "CASEBOOK_WORD_MISMATCH")
            else:
                word_by_group[ref] = word
        _require(row.get("expected_process_result") == KINDS[kind]
                 and _outcome(row) == KINDS[kind],
                 "CASEBOOK_EXPECTED_RESULT_INVALID")
        counts[kind] += 1
        groups[ref].add(kind)
    _require(counts == Counter({k: 8 for k in KINDS})
             and len(groups) == 8
             and all(kinds == set(KINDS) for kinds in groups.values()),
             "CASEBOOK_CASE_FAMILY_INVALID")


def load_casebook(path: Path = CASEBOOK_PATH) -> tuple[dict, str]:
    file = Path(path)
    raw = file.read_bytes()
    _require(len(raw) <= 64 * 1024, "CASEBOOK_TOO_LARGE")
    try:
        content = json.loads(raw.decode("utf-8", "strict"))
    except (ValueError, UnicodeError) as exc:
        raise CasebookError("CASEBOOK_JSON_INVALID") from exc
    validate_casebook(content)
    return content, hashlib.sha256(raw).hexdigest()


def evaluate_casebook(*, path: Path = CASEBOOK_PATH,
                      split: str = "development") -> dict:
    """Score ONLY scope/reference consistency, never scholarly accuracy.

    `holdout` is an explicitly requested evaluation slice, not hidden gold.
    This function does NOT run a model or assess interpretation correctness.
    """
    _require(split in SPLITS, "CASEBOOK_SPLIT_INVALID")
    data, digest = load_casebook(path)
    selected = [r for r in data["cases"] if r["split"] == split]
    results = [{
        "id": r["id"],
        "reference": r["reference"],
        "candidate_class": r["category"],
        "process_outcome": _outcome(r),
        "scientific_gold_label": None,
        "source_witness_byte_verified": False,
        "usul_semantic_link_certified": False,
        "qarinah_independently_examined": False,
    } for r in selected]
    return {
        "contract": "mubin-amr-casebook-scorecard-v0.1",
        "split": split,
        "casebook_sha256": digest,
        "count": len(results),
        "distribution": dict(sorted(Counter(
            row["candidate_class"] for row in results).items())),
        "results": results,
        "all_process_expectations_match": all(
            row["process_outcome"] == KINDS[row["candidate_class"]]
            for row in results),
        "scientific_accuracy_measured": False,
        "scholarly_verified": False,
        "source_authenticated": False,
        "publication_allowed": False,
        "juristic_inference_allowed": False,
        "public_fatwa_authorized": False,
        "p1_admitted": False,
    }


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=SPLITS, default="development")
    parser.add_argument("--cases", type=Path, default=CASEBOOK_PATH)
    args = parser.parse_args(argv)
    try:
        result = evaluate_casebook(path=args.cases, split=args.split)
        code = 0
    except (CasebookError, OSError, TypeError, KeyError) as exc:
        result, code = {
            "contract": "mubin-amr-casebook-scorecard-v0.1",
            "status": "REFUSED",
            "reason_code": (exc.code if isinstance(exc, CasebookError)
                            else "CASEBOOK_INPUT_REFUSED"),
            "scientific_accuracy_measured": False,
            "scholarly_verified": False, "publication_allowed": False,
            "juristic_inference_allowed": False,
            "public_fatwa_authorized": False,
        }, 1
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
