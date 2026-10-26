"""E2E-01.4: reproducible METADATA evaluation of the existing research slice.

Eight automated groups. Independently compare each reported coordinate with
the correct read-only SQLite source family, rather than using corpus_entries
as the oracle for the six TafsirCenter sidecar tables.

Not a scholarly, edition, rights, semantic-inference or fatwa assessment.
"""
from __future__ import annotations

import json
from contextlib import closing
from pathlib import Path
import sqlite3
from typing import Any

from engines.e2e.research_slice import research_slice, QUESTION
from engines.quran.research.operator_view import operator_lookup, _states
from engines.quran.research.private_adapters import (
    PrivateResearchAdapters, SIDE_TABLES, _reference,
)
from engines.quran.research import qualification as qual
from qa.corpus_ingest_v01 import load_manifest
from qa import private_evidence_v01 as evidence

CONTRACT = "mubin-e2e-evaluation-v0.1"
VERSION = "e2e-evaluation/0.1.1"
AUTHORITY_FLAGS = (
    "scholarly_verified", "source_authenticated", "rights_verified",
    "publication_allowed", "redistribution_approved", "edition_verified",
    "p1_admitted", "juristic_inference_allowed", "public_fatwa_authorized",
    "text_included",
)
_NON_AUTOMATABLE = (
    "scholarly authenticity of verse text or tafsir interpretation",
    "edition identity or publisher custody",
    "rights clearance or redistribution authorisation",
    "juristic inference soundness or fatwa authorisation",
    "p1 evidence admission",
    "semantic correctness of the proposed verse-to-Usul relationship",
)


class EvaluationError(ValueError):
    """Stable non-disclosing evaluation refusal."""
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _check(name: str, passed: bool, detail: str = "",
           severity: str = "major") -> dict:
    if type(passed) is not bool:
        raise EvaluationError("EVALUATION_BOOLEAN_INVALID")
    return {"check": name, "passed": passed, "detail": detail,
            "severity": severity}


def _group(name: str, checks: list[dict]) -> dict:
    # No empty groups and no vacuous success on skipped evaluation.
    return {"group": name, "checks": checks,
            "passed": bool(checks) and all(c["passed"] for c in checks)}


def _read_db(path: Path):
    """Same anchored, read-only immutable files as the existing adapters."""
    try:
        safe = evidence._guard_outside(Path(path), None)
        if not safe.is_file() or safe.is_symlink():
            raise EvaluationError("EVALUATION_DB_UNAVAILABLE")
        db = sqlite3.connect(safe.as_uri() + "?mode=ro&immutable=1",
                             uri=True, timeout=3)
        db.execute("PRAGMA query_only=ON")
        return db
    except (sqlite3.Error, OSError, evidence.EvidenceError) as exc:
        raise EvaluationError("EVALUATION_DB_UNAVAILABLE") from exc


def _oracle_snapshot(corpus_db: Path, sidecar_db: Path, refs: list[str]) -> tuple:
    """Fetch independently from both SQLite families; never read text."""
    expected_corpus = {item["id"] for item in load_manifest()["sources"]}
    expected_sidecar = set(SIDE_TABLES)
    existence: dict[tuple[str, str], bool] = {}
    try:
        with closing(_read_db(corpus_db)) as corpus, closing(_read_db(sidecar_db)) as sidecar:
            physical_corpus = {
                r[0] for r in corpus.execute("SELECT source_id FROM corpus_sources")}
            physical_sidecar = {
                r[0] for r in sidecar.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
            for ref in refs:
                sura, aya = _reference(ref)
                for sid in expected_corpus:
                    existence[(ref, sid)] = corpus.execute(
                        "SELECT 1 FROM corpus_entries "
                        "WHERE source_id=? AND sura=? AND aya=? LIMIT 1",
                        (sid, sura, aya)).fetchone() is not None
                for sid in expected_sidecar:
                    # SQL identifiers come ONLY from the hard-coded allowlist.
                    s_col, a_col = (("surahNo", "ayahNo") if sid == "QuranTafseer"
                                    else ("sura", "aya"))
                    existence[(ref, sid)] = sidecar.execute(
                        f'SELECT 1 FROM "{sid}" WHERE "{s_col}"=? '
                        f'AND "{a_col}"=? LIMIT 1', (sura, aya)
                    ).fetchone() is not None
    except (sqlite3.Error, OSError, ValueError) as exc:
        raise EvaluationError("EVALUATION_DB_QUERY_REFUSED") from exc
    return expected_corpus, expected_sidecar, physical_corpus, physical_sidecar, existence


def _complete_sources(sources: list[dict], corpus_ids: set, side_ids: set,
                      physical_corpus: set, physical_sidecar: set) -> dict:
    corpus_reported = [s["source_id"] for s in sources
                       if s["adapter"] == "quranenc_corpus"]
    sidecar_reported = [s["source_id"] for s in sources
                        if s["adapter"] == "tafsircenter_sidecar"]
    all_reported = [s["source_id"] for s in sources]
    checks = [
        _check("corpus_catalog_matches_manifest",
               physical_corpus == corpus_ids, "corpus source catalog", "critical"),
        _check("sidecar_tables_present",
               side_ids.issubset(physical_sidecar),
               "six allowlisted sidecar tables", "critical"),
        _check("corpus_sources_complete",
               set(corpus_reported) == corpus_ids
               and len(corpus_reported) == len(corpus_ids),
               f"expected={len(corpus_ids)} reported={len(corpus_reported)}",
               "critical"),
        _check("sidecar_sources_complete",
               set(sidecar_reported) == side_ids
               and len(sidecar_reported) == len(side_ids),
               f"expected={len(side_ids)} reported={len(sidecar_reported)}",
               "critical"),
        _check("unified_sources_unique_and_complete",
               set(all_reported) == corpus_ids | side_ids
               and len(all_reported) == len(corpus_ids) + len(side_ids),
               f"expected={len(corpus_ids)+len(side_ids)} reported={len(all_reported)}",
               "critical"),
    ]
    return _group("source_completeness", checks)


def _provenance(sources: list[dict], corpus_ids: set, side_ids: set) -> dict:
    checks = []
    for row in sources:
        sid = row["source_id"]
        expected = ("quranenc_corpus" if sid in corpus_ids else
                    "tafsircenter_sidecar" if sid in side_ids else "unknown")
        checks.append(_check(
            "provenance_" + sid, row.get("adapter") == expected
            and expected != "unknown",
            f"reported={row.get('adapter')} expected={expected}"))
    return _group("source_provenance", checks)


def _qualification(sources: list[dict], *, ledger: Path, anchor_dir: Path,
                   key_file: Path, vault: Path, evidence_head: str,
                   ref: str) -> dict:
    """Signed-ledger policy consistency, NOT independent scholarly adjudication."""
    checks = []
    # Signed ledger validation is mandatory; never use a default value
    # when verification fails, and never compare against raw unified rows.
    qual.verify_ledger(ledger, anchor_dir, key_file, vault=vault)
    for row in sources:
        sid = row["source_id"]
        decisions = qual.decisions_for(
            ledger, sid, anchor_dir=anchor_dir, key_file=key_file,
            vault=vault, reference=ref)
        scholarly, rights, count, stale = _states(decisions, evidence_head)
        checks.extend((
            _check("qualification_scholarly_" + sid,
                   row["scholarly_decision_state"] == scholarly),
            _check("qualification_rights_" + sid,
                   row["rights_decision_state"] == rights),
            _check("qualification_head_scope_" + sid,
                   row["matching_evidence_decisions"] == count
                   and row["historical_evidence_decisions_present"] == stale),
        ))
    return _group("qualification_consistency", checks)


def _gaps(result: dict) -> dict:
    sources = result["quran_retrieval"]["sources"]
    gaps = {(g["type"], g["source_id"]) for g in result["gaps"]}
    checks = [
        _check("edition_unverified",
               ("edition_unverified", "pilot:waraqat-bab-al-amr") in gaps),
        _check("semantic_link_unassessed",
               ("semantic_link_unassessed", "pilot:waraqat-bab-al-amr") in gaps),
        _check("hadith_retrieval_missing",
               ("hadith_retrieval_missing", "hadith") in gaps),
    ]
    for src in sources:
        sid = src["source_id"]
        if src["scholarly_decision_state"] == "UNREVIEWED":
            checks.append(_check(
                "scholarly_gap_" + sid, ("scholarly_review_pending", sid) in gaps))
        if src["rights_decision_state"] == "legal_review_pending":
            checks.append(_check(
                "rights_gap_" + sid, ("rights_review_pending", sid) in gaps))
    return _group("gap_completeness", checks)


def _abstention(result: dict) -> dict:
    und = result["undetermined"]
    link = result["research_linkage"]
    return _group("abstention", [
        _check("undetermined_nonempty",
               type(und) is list and len(und) >= 3
               and all(type(x) is str and bool(x.strip()) for x in und)),
        _check("link_not_certified",
               link["status"] in ("UNASSESSED", "PROPOSED_NOT_CERTIFIED")
               and link["verse_is_evidence_for_usul_rule"] is False),
        _check("synthetic_scenarios_not_promoted",
               link["synthetic_scenarios_are_real_case_evidence"] is False),
    ])


def _authority(result: dict) -> dict:
    limits = result["limits"]
    sources = result["quran_retrieval"]["sources"]
    entries = [("limits", limits)]
    entries += [(s["source_id"], s) for s in sources]
    checks = []
    for name, item in entries:
        fields = (AUTHORITY_FLAGS if name == "limits" else
                  ("text_included", "publication_allowed",
                   "juristic_inference_allowed", "public_fatwa_authorized"))
        for key in fields:
            # Missing required guard values are failures, not skipped checks.
            checks.append(_check(f"authority_{name}_{key}",
                                 item.get(key) is False, severity="critical"))
    checks.append(_check("rights_status_pending",
                         limits.get("rights_status") == "legal_review_pending",
                         severity="critical"))
    return _group("authority_flags", checks)


def _determinism(adapters, ref, question, args: dict, first: dict) -> dict:
    second = research_slice(adapters, ref, question, **args)
    canonical = lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False)
    return _group("determinism",
                  [_check("identical_report", canonical(first) == canonical(second))])


def run_full_evaluation(adapters: PrivateResearchAdapters,
                        snapshot_corpus_db: Path, vault: Path,
                        ledger: Path, anchor_dir: Path, key_file: Path,
                        refs: list[str], question: str) -> dict[str, Any]:
    """Run eight bounded checks; refusal on invalid/untrusted inputs.

    A green report certifies only metadata consistency on the checked refs.
    It does not approve scholarly, edition, rights or juristic conclusions.
    """
    if (type(refs) is not list or not refs or len(refs) > 32
            or any(type(r) is not str for r in refs)
            or len(refs) != len(set(refs))
            or question != QUESTION):
        raise EvaluationError("EVALUATION_SCOPE_INVALID")
    for ref in refs:
        try:
            _reference(ref)
        except ValueError as exc:
            raise EvaluationError("EVALUATION_REFERENCE_INVALID") from exc
    if Path(snapshot_corpus_db).resolve() != adapters.corpus_db.resolve():
        raise EvaluationError("EVALUATION_CORPUS_PATH_MISMATCH")
    before_head = adapters.evidence_head()
    args = dict(ledger=Path(ledger), qualification_anchor_dir=Path(anchor_dir),
                qualification_key=Path(key_file), vault=Path(vault))
    result = research_slice(adapters, refs[0], question, **args)
    corpus_ids, side_ids, physical_corpus, physical_sidecar, oracle = _oracle_snapshot(
        adapters.corpus_db, adapters.sidecar_db, refs)
    sources = result["quran_retrieval"]["sources"]
    coords = []
    for ref in refs:
        report = (result["quran_retrieval"] if ref == refs[0]
                  else operator_lookup(adapters, ref, **args))
        for src in report["sources"]:
            sid = src["source_id"]
            coords.append(_check(
                f"coordinate_{ref}_{sid}",
                src.get("coordinate_present") is oracle.get((ref, sid)),
                f"family={src.get('adapter')} expected={oracle.get((ref,sid))} "
                f"reported={src.get('coordinate_present')}",
                "critical"))
    groups = [
        _group("coordinate_accuracy", coords),
        _complete_sources(sources, corpus_ids, side_ids, physical_corpus, physical_sidecar),
        _qualification(sources, ledger=Path(ledger), anchor_dir=Path(anchor_dir),
                       key_file=Path(key_file), vault=Path(vault),
                       evidence_head=result["quran_retrieval"]["evidence_head_sha256"],
                       ref=refs[0]),
        _gaps(result),
        _abstention(result),
        _authority(result),
        _determinism(adapters, refs[0], question, args, result),
        _provenance(sources, corpus_ids, side_ids),
    ]
    if adapters.evidence_head() != before_head:
        raise EvaluationError("EVALUATION_EVIDENCE_HEAD_CHANGED")
    checks = [c for group in groups for c in group["checks"]]
    failed = [c for c in checks if not c["passed"]]
    return {
        "contract": CONTRACT, "version": VERSION, "references_examined": list(refs),
        "groups": groups, "total": len(checks),
        "passed": len(checks)-len(failed), "failed": len(failed),
        "critical_failures": sum(c["severity"] == "critical" for c in failed),
        "all_passed": bool(checks) and not failed
                      and all(g["passed"] for g in groups),
        "cannot_automate": list(_NON_AUTOMATABLE),
        "scholarly_verified": False, "source_authenticated": False,
        "rights_status": "legal_review_pending", "rights_verified": False,
        "publication_allowed": False, "p1_admitted": False,
        "juristic_inference_allowed": False,
        "public_fatwa_authorized": False, "text_included": False,
    }
