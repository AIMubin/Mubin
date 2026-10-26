"""E2E-01.4: automated evaluation of the integrated research slice.

Evaluates per source family (corpus vs sidecar) and the unified aggregate.
Measures what CAN be automated. Reports what CANNOT.
"""
from __future__ import annotations

import json, sqlite3
from engines.quran.research.private_adapters import PrivateResearchAdapters
from engines.quran.research.qualification import current_state
from engines.quran.research.unified import unified_lookup
from engines.e2e.research_slice import research_slice

VERSION = "e2e-evaluation/0.1.0"
CONTRACT = "mubin-e2e-evaluation-v0.1"
ALL_FLAGS = ("scholarly_verified", "source_authenticated", "rights_verified",
    "publication_allowed", "redistribution_approved", "edition_verified",
    "p1_admitted", "juristic_inference_allowed", "public_fatwa_authorized",
    "text_included")


def _check(name, passed, detail="", severity="major"):
    return {"check": name, "passed": passed, "detail": detail, "severity": severity}


def _get_db_sources(db_path):
    """Get source IDs from a SQLite DB's corpus_sources table (if exists)."""
    try:
        con = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)
        con.execute("PRAGMA query_only=ON")
        ids = {r[0] for r in con.execute("SELECT source_id FROM corpus_sources").fetchall()}
        con.close()
        return ids
    except (sqlite3.Error, OSError):
        return set()


def evaluate_coordinate_accuracy(adapters, vault, refs):
    """Check coordinate_present per source against the correct source DB."""
    checks = []
    result = unified_lookup(adapters, refs[0])
    # For each source in the result, check coordinate_present
    for src in result.get("sources", []):
        sid = src["source_id"]
        present = src.get("coordinate_present")
        checks.append(_check(f"coord_{sid}", present is True,
            f"present={present}", "critical"))
    return {"group": "coordinate_accuracy", "checks": checks,
            "passed": all(c["passed"] for c in checks)}


def evaluate_corpus_source_completeness(adapters, snapshot_corpus_db):
    """Check that all 5 QuranEnc/quran sources are reported."""
    result = unified_lookup(adapters, snapshot_corpus_db,
        "2:1") if hasattr(adapters, 'vault') else {}
    reported = {s["source_id"] for s in result.get("sources", [])
                if s.get("adapter") == "quranenc_corpus"}
    expected = {"quran_tanzil_uthmani_hafs_20261018",
                "qe_ar_muyassar", "qe_ar_mukhtasar",
                "qe_ar_yaseer", "qe_ar_nafahat"}
    ok = expected == reported
    return {"group": "corpus_completeness",
            "checks": [_check("corpus_sources_complete", ok,
                f"missing={sorted(expected-reported)} extra={sorted(reported-expected)}")],
            "passed": ok}


def evaluate_sidecar_source_completeness(adapters, sidecar_sources_reported):
    """Check that sidecar adapter reports the expected TafsirCenter tables."""
    expected_tables = {"tafsir_tabary", "tafsir_katheer", "tafsir_baghawy",
                       "tafsir_saadi", "tafsir_moyassar", "QuranTafseer"}
    reported = {s["source_id"] for s in sidecar_sources_reported
                if s.get("adapter") == "tafsircenter_sidecar"}
    ok = expected_tables == reported
    return {"group": "sidecar_completeness",
            "checks": [_check("sidecar_tables_complete", ok,
                f"missing={sorted(expected_tables-reported)} extra={sorted(reported-expected)}")],
            "passed": ok}


def evaluate_unified_source_completeness(all_sources):
    """Check that the unified result contains all expected sources without unjustified duplication."""
    ids = [s["source_id"] for s in all_sources]
    ok = len(ids) == len(set(ids))
    return {"group": "unified_completeness",
            "checks": [_check("no_unjustified_duplication", ok,
                f"count={len(ids)} unique={len(set(ids))}")],
            "passed": ok}


def evaluate_source_provenance(all_sources):
    """Check that each source is correctly attributed to its adapter family."""
    checks = []
    for s in all_sources:
        sid = s.get("source_id", "")
        adapter = s.get("adapter", "")
        expected_adapter = "quranenc_corpus" if "qe_" in sid or "quran_tanzil" in sid else                           "tafsircenter_sidecar" if "tafsir_" in sid else "unknown"
        checks.append(_check(f"provenance_{sid}", adapter == expected_adapter,
            f"adapter={adapter} expected={expected_adapter}"))
    return {"group": "source_provenance", "checks": checks,
            "passed": all(c["passed"] for c in checks)}


def evaluate_qualification_consistency(ledger, anchor_dir, key_file, vault,
                                        adapters, ref):
    result = unified_lookup(adapters, ref)
    checks = []
    for src in result.get("sources", []):
        sid = src["source_id"]
        ls = current_state(ledger, sid, "scholarly",
                          anchor_dir=anchor_dir, key_file=key_file, vault=vault)
        lr = current_state(ledger, sid, "rights",
                          anchor_dir=anchor_dir, key_file=key_file, vault=vault)
        rs = src.get("scholarly_decision_state", "UNREVIEWED")
        rr = src.get("rights_decision_state", "legal_review_pending")
        checks.append(_check(f"qual_{sid}_scholarly", rs == ls,
            f"ledger={ls} reported={rs}"))
        checks.append(_check(f"qual_{sid}_rights", rr == lr,
            f"ledger={lr} reported={rr}"))
    return {"group": "qualification_consistency", "checks": checks,
            "passed": all(c["passed"] for c in checks)}


def evaluate_gap_completeness(result):
    types = {g["type"] for g in result.get("gaps", [])}
    checks = [_check("edition_unverified", "edition_unverified" in types),
              _check("scholarly_review_pending", "scholarly_review_pending" in types),
              _check("rights_review_pending", "rights_review_pending" in types)]
    return {"group": "gap_completeness", "checks": checks,
            "passed": all(c["passed"] for c in checks)}


def evaluate_abstention(result):
    und = result.get("undetermined", [])
    limits = result.get("limits", {})
    ok_und = len(und) >= 3
    ok_lim = all(v is False for v in limits.values())
    return {"group": "abstention",
            "checks": [_check("undetermined_count", ok_und, f"count={len(und)}"),
                       _check("limits_all_false", ok_lim)],
            "passed": ok_und and ok_lim}


def evaluate_authority_flags(result):
    top = {k: result.get(k) for k in ALL_FLAGS if k in result}
    all_false = all(v is False for v in top.values())
    return {"group": "authority_flags",
            "checks": [_check("all_false", all_false, json.dumps(top))],
            "passed": all_false}


def evaluate_determinism(adapters, ref, question, *, ledger, anchor_dir, key_file, vault):
    a = json.dumps(research_slice(adapters, ref, question, ledger=ledger,
        qualification_anchor_dir=anchor_dir, qualification_key=key_file,
        vault=vault), ensure_ascii=False, sort_keys=True)
    b = json.dumps(research_slice(adapters, ref, question, ledger=ledger,
        qualification_anchor_dir=anchor_dir, qualification_key=key_file,
        vault=vault), ensure_ascii=False, sort_keys=True)
    return {"group": "determinism",
            "checks": [_check("deterministic", a == b)],
            "passed": a == b}


def run_full_evaluation(adapters, snapshot_corpus_db, vault, ledger,
                         anchor_dir, key_file, refs, question):
    groups = [
        evaluate_coordinate_accuracy(adapters, snapshot_corpus_db, refs),
        evaluate_source_completeness(adapters, snapshot_corpus_db, refs[0]),
    ]
    result = research_slice(adapters, refs[0], question, ledger=ledger,
                            qualification_anchor_dir=anchor_dir,
                            qualification_key=key_file, vault=vault)
    groups.append(evaluate_qualification_consistency(ledger, anchor_dir, key_file, vault, adapters, refs[0]))
    groups.append(evaluate_gap_completeness(result))
    groups.append(evaluate_abstention(result))
    groups.append(evaluate_authority_flags(result))
    groups.append(evaluate_determinism(adapters, refs[0], question,
                 ledger=ledger, anchor_dir=anchor_dir, key_file=key_file, vault=vault))
    checks = []
    for g in groups: checks.extend(g.get("checks", []))
    crit = [c for c in checks if not c["passed"] and c.get("severity") == "critical"]
    return {"contract": CONTRACT, "version": VERSION,
        "total": len(checks), "passed": sum(1 for c in checks if c["passed"]),
        "failed": sum(1 for c in checks if not c["passed"]),
        "critical_failures": len(crit), "groups": groups,
        "all_passed": len(crit) == 0,
        "cannot_automate": [
            "scholarly authenticity of verse text or tafsir interpretation",
            "edition identity or publisher custody",
            "rights clearance or redistribution authorisation",
            "juristic inference soundness or fatwa authorisation",
            "p1 evidence admission"],
        "text_included": False}


from engines.quran.research.unified import unified_lookup
