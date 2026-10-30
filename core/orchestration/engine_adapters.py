"""Wave B01 adapters over existing executable engines, not replacement engines.

Source objects and local paths are injected by the trusted application boundary;
requests cannot supply files, corpus bytes, or publication privileges. Findings are
metadata-only. Operational success never implies scholarly qualification.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from core.contracts import CONTRACT_VERSION, ContractError, EngineRegistry
from core.contracts.types import identifier
from engines.fiqh.contracts import prepare_research
from engines.fiqh.models import FiqhCase, JuristicOpinion
from engines.usul.executor import evaluate as usul_evaluate


def _response(req, status, findings=(), evidence=(), uncertainty=(), *, version):
    return {
        "contract_version": CONTRACT_VERSION, "request_id": req["request_id"],
        "engine": req["engine"], "engine_version": version, "status": status,
        "findings": list(findings)[:req["limits"]["max_results"]],
        "evidence_refs": list(dict.fromkeys(evidence))[:128],
        "uncertainties": list(uncertainty), "errors": [],
        "provenance": {"snapshot_ids": list(req["source_snapshot_ids"])},
        "trace_id": req["request_id"],
    }


def _input(req, names):
    if type(req["inputs"]) is not dict or (set(req["inputs"]) - {"_upstream"}) != set(names):
        raise ContractError("OPERATION_INPUT_SHAPE_INVALID")
    return req["inputs"]


def _reference(value):
    from engines.quran.q01.engine import verse_counts
    if type(value) is not str:
        raise ContractError("REFERENCE_INVALID")
    parts = value.split(":")
    if len(parts) != 2 or not all(part.isascii() and part.isdecimal() for part in parts):
        raise ContractError("REFERENCE_INVALID")
    s, a = map(int, parts)
    if s < 1 or s > 114 or a < 1 or a > verse_counts()[s-1]:
        raise ContractError("REFERENCE_INVALID")
    return f"{s}:{a}"


def build_engine_registry(*, snapshot_ids, quran_index=None,
                          tafsir_db=None, hadith_cache=None):
    """Trusted startup configuration. Source IDs are operator pins, not authenticity.

    QuranIndex is created with existing Q0.1 load_snapshot (SHA-checked bytes).
    Tafsir T0.3 and Hadith T0.2/HSearch use existing pinned local readers.
    No live network fetching, generation, or rights/scholarly evaluation.
    """
    if (type(snapshot_ids) is not tuple or not snapshot_ids
            or len(snapshot_ids) > 128 or len(set(snapshot_ids)) != len(snapshot_ids)
            or not all(identifier(s) for s in snapshot_ids)):
        raise ContractError("ADAPTER_SNAPSHOT_CONFIG_INVALID")
    for path in (tafsir_db, hadith_cache):
        if path is not None and not isinstance(path, Path):
            raise ContractError("ADAPTER_PATH_CONFIG_INVALID")
    registry = EngineRegistry()

    def gate(req):
        if tuple(req["source_snapshot_ids"]) != snapshot_ids:
            raise ContractError("SOURCE_SNAPSHOT_CONFIG_MISMATCH")

    def quran(req):
        gate(req)
        if quran_index is None:
            return _response(req, "UNAVAILABLE", uncertainty=["QURAN_SNAPSHOT_UNAVAILABLE"],
                             version="q01/0.1")
        data = _input(req, {"reference"})
        hit = quran_index.get(_reference(data["reference"]))
        if not hit["found"]:
            return _response(req, "NO_MATCH", version="q01/0.1")
        synthetic = quran_index.manifest["source_kind"] == "synthetic_fixture"
        ref = hit["reference"]
        identity = sha256(hit["text"].encode("utf-8")).hexdigest()
        evidence = [] if synthetic else [f"ev.quran.{ref.replace(':', '.')}.{identity[:24]}"]
        return _response(req, "OK", findings=[{
            "reference": ref, "source_id": hit["source_id"],
            "text_sha256": identity, "raw_snapshot_sha256": hit["raw_sha256"],
            "source_authenticated": False, "synthetic_fixture": synthetic,
            "text_included": False, "kind": "QURAN_VERSE_COORDINATE",
        }], evidence=evidence, version="q01/0.1")

    def _tafsir_lookup(ref):
        if tafsir_db is None:
            raise ContractError("TAFSIR_DB_NOT_CONFIGURED")
        from engines.tafsir.t01 import lookup_verse
        from engines.tafsir.t02_cli import extract_local_verse
        lookup = lookup_verse(tafsir_db, ref, include_private_text=True)
        return lookup, extract_local_verse(tafsir_db, lookup)

    def tafsir(req):
        gate(req)
        ref = _reference(_input(req, {"reference"})["reference"])
        if tafsir_db is None:
            return _response(req, "UNAVAILABLE", uncertainty=["TAFSIR_DB_UNAVAILABLE"],
                             version="tafsir-t03/0.1")
        from engines.tafsir.t03 import unified_research_query
        report = unified_research_query(tafsir_db, ref)
        tafsirs = report["tafsirs"]
        evidence = [t["evidence_id"] for t in tafsirs
                    if identifier(t.get("evidence_id"))]
        result = [{
            "reference": ref, "work_id": t["work_id"],
            "passage_count": t["passage_count"], "candidate_count": t["candidate_count"],
            "display_status": t["display_status"], "synthetic_fixture": (
                t.get("source_dataset") == "synthetic"),
            "scholarly_verified": False, "text_included": False,
        } for t in tafsirs]
        return _response(req, "OK" if result else "NO_MATCH", result, evidence,
                         version="tafsir-t03/0.1")

    def hadith(req):
        gate(req)
        ref = _reference(_input(req, {"reference"})["reference"])
        if tafsir_db is None:
            return _response(req, "UNAVAILABLE", uncertainty=["TAFSIR_DB_UNAVAILABLE"],
                             version="hsearch01/0.1")
        from engines.hadith.hsearch.mention import detect_all
        _, passages = _tafsir_lookup(ref)
        mentions = detect_all(passages)
        findings = [{
            "reference": ref, "mention_id": m["mention_id"],
            "mention_type": m["mention_type"], "passage_id": m["passage_id"],
            "candidate_only": True, "grade_assigned": False,
            "text_included": False,
        } for m in mentions]
        # Only a mention cue search; NO_MATCH does NOT mean no Hadith exists.
        return _response(req, "OK" if findings else "NO_MATCH", findings,
                         [m["mention_id"] for m in mentions if identifier(m["mention_id"])],
                         uncertainty=["HADITH_IDENTITY_AND_GRADE_NOT_VERIFIED"] if findings else
                                     ["NO_NARRATION_CUE_IN_SCOPED_TAFSIR"],
                         version="hsearch01/0.1")

    def usul(req):
        gate(req)
        model = _input(req, {"model"})["model"]
        if type(model) is not dict or model.get("methodology_id") != req["methodology_profile_id"]:
            raise ContractError("USUL_PROFILE_MISMATCH")
        assessment = usul_evaluate(model)
        return _response(req, "OK" if assessment["trace"] else "UNDETERMINED", [{
            "rule_id": t["rule_id"], "application_status": t["status"],
            "execution_scope": assessment["execution_scope"],
            "scholarly_verified": False,
        } for t in assessment["trace"]],
            uncertainty=["ONE_STEP_PROPOSITIONAL_SIMULATION_NOT_JURISTIC_REASONING"],
            version="usul-u01/0.1")

    def fiqh(req):
        gate(req)
        inputs = _input(req, {"question", "opinions"})
        upstream = inputs.get("_upstream", [])
        if type(upstream) is not list or any(type(x) is not dict or
           set(x) != {"engine", "status", "evidence_refs", "synthetic", "references"} for x in upstream):
            raise ContractError("FIQH_UPSTREAM_INVALID")
        if any(x["status"] not in ("OK", "NO_MATCH") for x in upstream):
            raise ContractError("FIQH_UPSTREAM_STATUS_INVALID")
        if any(type(x["references"]) is not list or
               any(type(ref) is not str for ref in x["references"]) or
               type(x["evidence_refs"]) is not list for x in upstream):
            raise ContractError("FIQH_UPSTREAM_REFERENCE_INVALID")
        opinions_raw = inputs["opinions"]
        if type(opinions_raw) is not list or len(opinions_raw) > 50:
            raise ContractError("FIQH_OPINIONS_INVALID")
        case = FiqhCase(req["case_id"], inputs["question"], req["methodology_profile_id"])
        opinions = []
        for row in opinions_raw:
            if type(row) is not dict or set(row) != {"opinion_id", "source_ref"}:
                raise ContractError("FIQH_OPINION_SHAPE_INVALID")
            opinions.append(JuristicOpinion(row["opinion_id"], row["source_ref"],
                                           case.methodology_profile_id))
        refs = tuple(dict.fromkeys(
            ev for entry in upstream for ev in entry["evidence_refs"]))
        references = {ref for entry in upstream for ref in entry["references"]}
        mismatched_references = len(references) > 1
        # No user-supplied evidence IDs: upstream refs come from checked engine receipts.
        scoped = tuple(op for op in opinions if op.source_ref in refs)
        finding = prepare_research(case, scoped, refs)
        synthetic = any(x["synthetic"] for x in upstream)
        uncertainties = list(finding.uncertainties) + (
            ["SYNTHETIC_UPSTREAM_PRESENT"] if synthetic else [])
        if len(scoped) != len(opinions):
            uncertainties.append("OPINION_SOURCE_NOT_IN_UPSTREAM_EVIDENCE")
        if not upstream:
            uncertainties.append("NO_ENGINE_DEPENDENCIES")
        if mismatched_references:
            uncertainties.append("CROSS_ENGINE_REFERENCE_MISMATCH")
        return _response(req, "PARTIAL" if finding.status == "PARTIAL" and not synthetic
                         and not mismatched_references
                         else "UNDETERMINED", [{
            "case_id": case.case_id, "opinion_refs": list(finding.opinion_refs),
            "linked_evidence_count": len(refs), "authority": "RESEARCH_ONLY",
            "juristic_conclusion": None, "source_claims_verified": False,
        }] if finding.status == "PARTIAL" and not synthetic else [],
            evidence=refs, uncertainty=uncertainties or ["JURISTIC_RESEARCH_INCOMPLETE"],
            version="fiqh-f01/0.1")

    registry.register("quran", {"lookup_verse"}, quran)
    registry.register("tafsir", {"research_verse"}, tafsir)
    registry.register("hadith", {"detect_tafsir_mentions"}, hadith)
    registry.register("usul", {"evaluate_proposition"}, usul)
    registry.register("fiqh", {"prepare_case"}, fiqh)
    return registry
