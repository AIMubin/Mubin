"""E2E-01.4b.2: bounded AI-only evidence comparison, *not* fatwa adjudication.

Consumes an OPERATOR-LOCAL three-witness packet and independently-produced
AI evaluator/critic JSON. Never downloads sources, invokes an LLM, publishes
protected source text, or treats two model votes as scientific ground truth.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from engines.e2e.scientific_benchmark import load_casebook, CasebookError

CONTRACT = "mubin-e2e-scientific-trial-v0.1"
ROLES = frozenset(("verse", "tafsir", "usul"))
DECISIONS = frozenset(("SUPPORTED", "REFUTED", "UNDETERMINED"))


class TrialError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _require(ok, code):
    if not ok:
        raise TrialError(code)


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _local_json(path: Path) -> dict:
    """Bounded operator files; no file content in an exception or report."""
    try:
        path = Path(path)
        if path.is_symlink() or not path.is_file():
            raise TrialError("TRIAL_FILE_INVALID")
        with path.open("rb") as handle:
            raw = handle.read(65537)
        _require(0 < len(raw) <= 65536, "TRIAL_FILE_TOO_LARGE")
        value = json.loads(raw.decode("utf-8", "strict"))
        _require(type(value) is dict, "TRIAL_JSON_INVALID")
        return value
    except (OSError, ValueError, UnicodeError) as exc:
        if isinstance(exc, TrialError):
            raise
        raise TrialError("TRIAL_FILE_INVALID") from exc


def _witness_packet(case: dict, packet: dict) -> tuple[str, tuple[str, ...], dict]:
    _require(type(packet) is dict
             and packet.get("case_id") == case["id"]
             and packet.get("reference") == case["reference"],
             "TRIAL_CASE_MISMATCH")
    records = packet.get("witnesses")
    _require(type(records) is list and len(records) <= 3,
             "TRIAL_WITNESSES_INVALID")
    by_role = {}
    by_id = set()
    witness_metadata = {}
    for record in records:
        _require(type(record) is dict
                 and set(record) == {"id", "role", "url", "family",
                                     "text", "sha256"},
                 "TRIAL_WITNESS_SHAPE_INVALID")
        rid, role = record["id"], record["role"]
        text = record["text"]
        url, fam = record["url"], record["family"]
        _require(type(rid) is str and 1 <= len(rid) <= 80
                 and rid not in by_id and type(role) is str
                 and role in ROLES and role not in by_role,
                 "TRIAL_WITNESS_ID_INVALID")
        _require(type(text) is str and 0 < len(text) <= 12000
                 and not any(ord(ch) < 32 and ch not in "\n\t" for ch in text),
                 "TRIAL_WITNESS_TEXT_INVALID")
        _require(type(url) is str and len(url) <= 350
                 and type(fam) is str and 1 <= len(fam) <= 100,
                 "TRIAL_WITNESS_ORIGIN_INVALID")
        u = urlsplit(url)
        _require(u.scheme == "https" and bool(u.hostname)
                 and not u.username and not u.password and not u.fragment,
                 "TRIAL_WITNESS_ORIGIN_INVALID")
        digest = _sha(text.encode("utf-8"))
        _require(type(record["sha256"]) is str
                 and record["sha256"] == digest,
                 "TRIAL_WITNESS_HASH_MISMATCH")
        by_id.add(rid)
        by_role[role] = record
        witness_metadata[role] = {
            "id": rid, "family": fam, "url": url,
            "local_utf8_sha256": digest,
            "hash_matches_submitted_bytes": True,
            "external_custody_authenticated": False,
        }

    # Enforce a narrow role/citation mapping; a plausible unrelated
    # document must not silently impersonate the requested Quran verse.
    if "verse" in by_role:
        v = by_role["verse"]
        _require(v["url"] == case["quran_witness_url"],
                 "TRIAL_VERSE_LOCATOR_MISMATCH")
    if "usul" in by_role:
        u = by_role["usul"]
        _require(u["url"] == case["usul_rule"]["url"],
                 "TRIAL_USUL_LOCATOR_MISMATCH")

    exact = ("verse" in by_role
             and type(case["observed_word"]) is str
             and case["observed_word"] in by_role["verse"]["text"])
    families = [by_role[r]["family"] for r in by_role]
    # Different domains/families are operator assertions, not proof of
    # independence, though duplicate declared families are diagnosable.
    completeness = set(by_role) == ROLES
    return _sha(_canonical(packet)), tuple(sorted(by_id)), {
        "roles_present": sorted(by_role),
        "three_witness_roles_present": completeness,
        "exact_candidate_substring_in_verse_bytes": bool(exact),
        "family_labels_distinct": len(set(families)) == len(families),
        "origin_verified_against_upstream": False,
        "witnesses": witness_metadata,
    }


def _agent(report: dict, expected_role: str, digest: str,
           witness_ids: tuple[str, ...]) -> dict:
    _require(type(report) is dict
             and report.get("role") == expected_role
             and report.get("packet_sha256") == digest
             and report.get("decision") in DECISIONS,
             "TRIAL_AGENT_CONTRACT_INVALID")
    for field in ("model_id", "provider", "run_id"):
        v = report.get(field)
        _require(type(v) is str and 1 <= len(v) <= 100
                 and v.isprintable(), "TRIAL_AGENT_ID_INVALID")
    ids = report.get("evidence_ids")
    _require(type(ids) is list and len(ids) <= 3
             and all(type(x) is str and x in witness_ids for x in ids)
             and len(ids) == len(set(ids)), "TRIAL_AGENT_CITATION_INVALID")
    # No free-form excerpts/responses in shared scorecard; local full
    # report can be separately inspected, never published by this tool.
    return {k:report[k] for k in (
        "role", "model_id", "provider", "run_id", "decision",
        "evidence_ids")}


def run_trial(casebook: dict, case_id: str, packet: dict,
              evaluator: dict, critic: dict) -> dict:
    """Return evidence availability and independently-labelled AI agreement.

    It cannot call a finding SUPPORTED as *scientifically correct* without
    an independently adjudicated reference; that is unavailable in b.2.
    """
    cases = [c for c in casebook["cases"] if c["id"] == case_id]
    _require(len(cases) == 1 and cases[0]["category"] == "POSITIVE_CANDIDATE",
             "TRIAL_CASE_OUT_OF_SCOPE")
    case = cases[0]
    digest, ids, state = _witness_packet(case, packet)
    a = _agent(evaluator, "evaluator", digest, ids)
    b = _agent(critic, "critic", digest, ids)
    _require(a["model_id"] != b["model_id"]
             and a["run_id"] != b["run_id"]
             and a["provider"] != b["provider"],
             "TRIAL_AGENT_INDEPENDENCE_UNESTABLISHED")
    evidence_sufficient = (
        state["three_witness_roles_present"]
        and state["exact_candidate_substring_in_verse_bytes"]
        and state["family_labels_distinct"])
    if not evidence_sufficient:
        state_name = "UNDETERMINED"
    elif a["decision"] == b["decision"] == "UNDETERMINED":
        state_name = "UNDETERMINED"
    elif a["decision"] == b["decision"]:
        state_name = "AI_AGREEMENT_UNCERTIFIED"
    else:
        state_name = "AI_DISAGREEMENT"
    return {
        "contract": CONTRACT, "case_id": case_id,
        "evidence_packet_sha256": digest,
        "evidence": state,
        "evaluator": a, "critic": b,
        "research_state": state_name,
        "independently_assessed_scientific_accuracy": False,
        "independent_external_source_custody_proven": False,
        "independent_model_execution_proven": False,
        "scholarly_verified": False, "source_authenticated": False,
        "rights_status": "legal_review_pending",
        "publication_allowed": False,
        "juristic_inference_allowed": False,
        "public_fatwa_authorized": False, "p1_admitted": False,
        "source_text_included": False,
    }


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--evaluator", required=True, type=Path)
    parser.add_argument("--critic", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        casebook, _ = load_casebook()
        report = run_trial(casebook, args.case, _local_json(args.packet),
                           _local_json(args.evaluator),
                           _local_json(args.critic))
        exit_code = 0
    except (CasebookError, TrialError, KeyError, TypeError) as exc:
        report, exit_code = {
            "contract": CONTRACT, "status": "REFUSED",
            "reason_code": (exc.code if isinstance(exc, TrialError)
                            else "TRIAL_INPUT_REFUSED"),
            "scholarly_verified": False,
            "publication_allowed": False,
            "public_fatwa_authorized": False,
            "source_text_included": False,
        }, 1
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
