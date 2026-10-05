from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .core import SPLITS, Violation, canonical_json_bytes, load_json, load_jsonl, sha256_bytes
from .normalization import fingerprint_payload
from .source_registry import load_source_registry, source_map
from .holdout_seal import validate_public_seal_binding
from .queue_plan import build_curation_queue_plan

REQUIRED_FIELDS = {
    "benchmark_id",
    "case_id",
    "split",
    "source_ids",
    "anchor_source_id",
    "family_id",
    "content_fingerprint",
    "gold_status",
    "synthetic",
    "source_refs",
    "annotation",
    "payload",
}


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
        return value == value.lower()
    except ValueError:
        return False


def _validate_annotation(record: dict[str, Any], benchmark_id: str) -> list[Violation]:
    out: list[Violation] = []
    cid = record.get("case_id")
    ann = record.get("annotation")
    if not isinstance(ann, dict):
        return [Violation("annotation.invalid", "annotation must be an object", benchmark_id, cid)]
    reviewers = ann.get("reviewers", [])
    if not isinstance(reviewers, list) or any(not isinstance(x, str) or not x.strip() for x in reviewers):
        out.append(Violation("annotation.reviewers", "reviewers must be a list of non-empty reviewer IDs", benchmark_id, cid))
        reviewers = []
    if len(set(reviewers)) != len(reviewers):
        out.append(Violation("annotation.reviewers_not_independent", "reviewer IDs must be unique", benchmark_id, cid))

    status = record.get("gold_status")
    if status == "source_attributed":
        ap = record.get("answer_provenance")
        if not isinstance(ap, dict):
            out.append(Violation("qualification.answer_provenance", "source_attributed requires answer_provenance", benchmark_id, cid))
        else:
            if ap.get("answer_origin") != "human_authored_source":
                out.append(Violation("qualification.answer_origin", "answer_origin must be human_authored_source", benchmark_id, cid))
            if ap.get("extraction_method") not in {"ai", "human"}:
                out.append(Violation("qualification.extraction_method", "extraction_method must be ai or human", benchmark_id, cid))
            if ap.get("source_verified") is not True:
                out.append(Violation("qualification.answer_source_unverified", "source_attributed requires source_verified=true", benchmark_id, cid))
            if ap.get("mode") not in {"direct_extract", "attributed_composite"}:
                out.append(Violation("qualification.answer_mode", "source_attributed mode must be direct_extract or attributed_composite", benchmark_id, cid))
            if not isinstance(ap.get("human_reviewed"), bool):
                out.append(Violation("qualification.human_reviewed", "human_reviewed must be an explicit boolean", benchmark_id, cid))
            elif ap.get("human_reviewed") is True and len(reviewers) < 1:
                out.append(Violation("qualification.human_review_missing", "human_reviewed=true requires a reviewer ID", benchmark_id, cid))
    elif status == "reference_pilot":
        if ann.get("source_verified") is not True:
            out.append(Violation("qualification.reference_not_verified", "reference_pilot requires source_verified=true", benchmark_id, cid))
        if len(reviewers) < 1:
            out.append(Violation("qualification.reference_no_reviewer", "reference_pilot requires at least one named/pseudonymous reviewer", benchmark_id, cid))
    elif status == "expert_gold":
        if len(reviewers) < 2:
            out.append(Violation("qualification.expert_reviewers", "expert_gold requires at least two independent reviewers", benchmark_id, cid))
        if ann.get("adjudicated") is not True:
            out.append(Violation("qualification.expert_adjudication", "expert_gold requires adjudicated=true", benchmark_id, cid))
        adjudicator = ann.get("adjudicator")
        if not isinstance(adjudicator, str) or not adjudicator.strip():
            out.append(Violation("qualification.expert_adjudicator", "expert_gold requires an adjudicator ID", benchmark_id, cid))
        elif adjudicator in reviewers:
            out.append(Violation("qualification.adjudicator_not_independent", "adjudicator must be independent of reviewers", benchmark_id, cid))
    return out


def _validate_answer_support(record: dict[str, Any], benchmark_id: str) -> list[Violation]:
    out: list[Violation] = []
    if record.get("gold_status") != "source_attributed":
        return out
    cid = record.get("case_id")
    ap = record.get("answer_provenance")
    if not isinstance(ap, dict):
        return out
    refs = record.get("source_refs")
    if not isinstance(refs, list):
        return out
    refs_by_id = {r.get("source_id"): r for r in refs if isinstance(r, dict) and isinstance(r.get("source_id"), str)}
    supports = ap.get("supports")
    if not isinstance(supports, list) or not supports:
        return [Violation("qualification.answer_supports", "source_attributed requires non-empty supports", benchmark_id, cid)]
    for support in supports:
        if not isinstance(support, dict):
            out.append(Violation("qualification.answer_support", "each support must be an object", benchmark_id, cid))
            continue
        sid = support.get("source_id")
        text = support.get("support_text")
        ref = refs_by_id.get(sid)
        if ref is None:
            out.append(Violation("qualification.answer_support_source", "support source_id must reference source_refs", benchmark_id, cid))
            continue
        if not isinstance(text, str) or not text.strip() or text not in str(ref.get("excerpt", "")):
            out.append(Violation("qualification.answer_support_text", "support_text must occur verbatim in the pinned source excerpt", benchmark_id, cid))
            continue
        expected_support_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if support.get("support_text_sha256") != expected_support_sha:
            out.append(Violation("qualification.answer_support_hash", "support_text_sha256 mismatch", benchmark_id, cid))
        if support.get("source_excerpt_sha256") != ref.get("excerpt_sha256"):
            out.append(Violation("qualification.answer_support_excerpt_binding", "support is not bound to the cited source excerpt", benchmark_id, cid))
    mode = ap.get("mode")
    if mode == "direct_extract":
        verbatim_answer = ap.get("verbatim_answer")
        if not isinstance(verbatim_answer, str) or not verbatim_answer.strip() or not any(
            isinstance(s, dict) and isinstance(s.get("support_text"), str) and verbatim_answer in s["support_text"]
            for s in supports
        ):
            out.append(Violation("qualification.verbatim_answer", "direct_extract verbatim_answer must occur in support_text", benchmark_id, cid))
    elif mode == "attributed_composite":
        if len(supports) < 2:
            out.append(Violation("qualification.composite_support_count", "attributed_composite requires at least two supports", benchmark_id, cid))
        iv = ap.get("independent_verification")
        extractor = ap.get("extractor_family")
        verifier = iv.get("verifier_family") if isinstance(iv, dict) else None
        if not isinstance(iv, dict) or iv.get("verdict") != "supported":
            out.append(Violation("qualification.composite_verification", "attributed_composite requires independent supported verification", benchmark_id, cid))
        if not isinstance(extractor, str) or not extractor.strip() or not isinstance(verifier, str) or not verifier.strip() or extractor == verifier:
            out.append(Violation("qualification.composite_independence", "extractor_family and verifier_family must be distinct", benchmark_id, cid))
    payload = record.get("payload")
    if isinstance(payload, dict) and "gold" in payload:
        normalized_supports = [
            {
                "source_id": s.get("source_id"),
                "support_text": s.get("support_text"),
                "support_text_sha256": s.get("support_text_sha256"),
                "source_excerpt_sha256": s.get("source_excerpt_sha256"),
            }
            for s in supports if isinstance(s, dict)
        ]
        expected_binding = sha256_bytes(canonical_json_bytes({
            "gold": payload["gold"],
            "supports": normalized_supports,
            "mode": mode,
        }))
        if ap.get("gold_binding_sha256") != expected_binding:
            out.append(Violation("qualification.gold_binding", "gold_binding_sha256 mismatch", benchmark_id, cid))
    return out


def _validate_factory_verification(record: dict[str, Any], benchmark_id: str) -> list[Violation]:
    out: list[Violation] = []
    if record.get("gold_status") != "source_attributed":
        return out
    ap = record.get("answer_provenance")
    if not isinstance(ap, dict):
        return out
    if ap.get("extraction_method") != "ai" or ap.get("human_reviewed") is not False:
        return out
    cid = record.get("case_id")
    fv = record.get("factory_verification")
    if not isinstance(fv, dict):
        return [Violation(
            "qualification.factory_verification_missing",
            "unreviewed AI source_attributed gold requires independent factory verification",
            benchmark_id, cid,
        )]
    for field in ("curator_model_family", "curator_model_ref", "verifier_model_family", "verifier_model_ref"):
        if not isinstance(fv.get(field), str) or not fv[field].strip():
            out.append(Violation("qualification.factory_verification_identity", f"factory_verification.{field} is required", benchmark_id, cid))
    if (
        isinstance(fv.get("curator_model_family"), str)
        and fv.get("curator_model_family") == fv.get("verifier_model_family")
    ):
        out.append(Violation("qualification.factory_verification_independence", "curator and verifier model families must differ", benchmark_id, cid))
    for field in ("curator_response_sha256", "verifier_response_sha256", "task_fingerprint", "slot_binding_sha256"):
        if not _is_sha256(fv.get(field)):
            out.append(Violation("qualification.factory_verification_hash", f"factory_verification.{field} must be sha256", benchmark_id, cid))
    if fv.get("agreement") != "exact_gold_match":
        out.append(Violation("qualification.factory_verification_agreement", "factory verification must record exact_gold_match", benchmark_id, cid))
    if not isinstance(fv.get("factory_version"), int) or int(fv.get("factory_version", 0)) < 1:
        out.append(Violation("qualification.factory_version", "factory_version must be a positive integer", benchmark_id, cid))
    if not isinstance(fv.get("risk_tier"), int) or int(fv.get("risk_tier", 0)) not in {1, 2, 3}:
        out.append(Violation("qualification.factory_risk_tier", "risk_tier must be 1, 2, or 3", benchmark_id, cid))
    for role in ("curator", "verifier"):
        binding = fv.get(f"{role}_execution_binding")
        if not isinstance(binding, dict):
            out.append(Violation(
                "qualification.factory_execution_binding",
                f"factory_verification.{role}_execution_binding is required",
                benchmark_id, cid,
            ))
            continue
        for field in ("config_sha256", "raw_response_sha256", "adapter_command_sha256"):
            if not _is_sha256(binding.get(field)):
                out.append(Violation(
                    "qualification.factory_execution_hash",
                    f"{role} execution binding {field} must be sha256",
                    benchmark_id, cid,
                ))
        if binding.get("protocol_version") != 1:
            out.append(Violation(
                "qualification.factory_execution_protocol",
                f"{role} execution binding protocol_version must be 1",
                benchmark_id, cid,
            ))
        artifacts = binding.get("adapter_artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            out.append(Violation(
                "qualification.factory_adapter_artifacts",
                f"{role} execution binding requires adapter artifact hashes",
                benchmark_id, cid,
            ))
        else:
            for artifact in artifacts:
                if (
                    not isinstance(artifact, dict)
                    or not isinstance(artifact.get("path"), str)
                    or not artifact["path"].strip()
                    or not _is_sha256(artifact.get("sha256"))
                    or not isinstance(artifact.get("size_bytes"), int)
                    or artifact["size_bytes"] < 1
                ):
                    out.append(Violation(
                        "qualification.factory_adapter_artifact",
                        f"{role} execution adapter artifact binding is invalid",
                        benchmark_id, cid,
                    ))
    supports = fv.get("verifier_supports")
    if not isinstance(supports, list) or not supports:
        out.append(Violation("qualification.factory_verifier_supports", "independent verifier supports are required", benchmark_id, cid))
    else:
        source_ids = set(str(x) for x in record.get("source_ids", []) if isinstance(x, str))
        for support in supports:
            if not isinstance(support, dict):
                out.append(Violation("qualification.factory_verifier_support", "each verifier support must be an object", benchmark_id, cid))
                continue
            if support.get("source_id") not in source_ids:
                out.append(Violation("qualification.factory_verifier_source", "verifier support source must belong to record source_ids", benchmark_id, cid))
            if not isinstance(support.get("locator"), str) or not support["locator"].strip():
                out.append(Violation("qualification.factory_verifier_locator", "verifier support locator is required", benchmark_id, cid))
            for field in ("excerpt_sha256", "support_text_sha256"):
                if not _is_sha256(support.get(field)):
                    out.append(Violation("qualification.factory_verifier_hash", f"verifier support {field} must be sha256", benchmark_id, cid))
    return out


def _validate_factory_risk_policy(record: dict[str, Any], benchmark_id: str,
                                  benchmark_policy: dict[str, Any] | None) -> list[Violation]:
    if not isinstance(benchmark_policy, dict) or int(benchmark_policy.get("risk_tier", 0)) < 3:
        return []
    if record.get("gold_status") != "source_attributed":
        return []
    ap = record.get("answer_provenance")
    if not isinstance(ap, dict):
        return []
    if ap.get("extraction_method") == "ai" and ap.get("human_reviewed") is False:
        return [Violation(
            "qualification.risk_tier_human_gate",
            "risk-tier 3 AI-extracted source_attributed cases require human/authority review before qualification",
            benchmark_id, record.get("case_id"),
        )]
    return []


def _requires_factory_slot_binding(record: dict[str, Any]) -> bool:
    if record.get("gold_status") != "source_attributed":
        return False
    ap = record.get("answer_provenance")
    return bool(
        isinstance(ap, dict)
        and ap.get("extraction_method") == "ai"
        and ap.get("human_reviewed") is False
    )


def _validate_factory_reserve_policy(
    root: Path,
    record: dict[str, Any],
    benchmark_id: str,
) -> list[Violation]:
    """Freeze-24 reserve candidates are preregistered but not qualification-enabled."""
    slot_id = record.get("factory_slot_id")
    if not isinstance(slot_id, str) or not slot_id:
        return []
    try:
        from .factory import build_factory_plan
        slots = {
            str(slot["slot_id"]): slot
            for slot in build_factory_plan(root).get("slots", [])
        }
    except Exception as exc:
        return [Violation(
            "qualification.factory_plan_unavailable",
            f"cannot re-derive frozen factory plan: {exc}",
            benchmark_id,
            record.get("case_id"),
        )]
    slot = slots.get(slot_id)
    if slot is None or slot.get("candidate_slot_kind") != "reserve":
        return []
    return [Violation(
        "qualification.reserve_slot_not_eligible",
        (
            "freeze schema 24 preregisters reserve candidate slots but does not "
            "permit reserve-derived benchmark records before cumulative replacement "
            "eligibility is explicitly bound"
        ),
        benchmark_id,
        record.get("case_id"),
    )]


def _validate_factory_slot_binding(root: Path, record: dict[str, Any],
                                   benchmark_id: str) -> list[Violation]:
    if not _requires_factory_slot_binding(record):
        return []
    cid = record.get("case_id")
    out: list[Violation] = []
    try:
        from .factory import build_factory_plan
        plan = build_factory_plan(root)
    except Exception as exc:
        return [Violation(
            "qualification.factory_plan_unavailable",
            f"cannot re-derive frozen factory plan: {exc}",
            benchmark_id, cid,
        )]
    slots = {str(s["slot_id"]): s for s in plan.get("slots", [])}
    slot_id = record.get("factory_slot_id")
    task_id = record.get("factory_task_id")
    if not isinstance(slot_id, str) or not slot_id:
        return [Violation(
            "qualification.factory_slot_missing",
            "unreviewed AI source_attributed record requires factory_slot_id",
            benchmark_id, cid,
        )]
    if task_id != slot_id:
        out.append(Violation(
            "qualification.factory_task_slot_mismatch",
            "factory_task_id must equal factory_slot_id",
            benchmark_id, cid,
        ))
    slot = slots.get(slot_id)
    if slot is None:
        out.append(Violation(
            "qualification.factory_slot_unknown",
            "factory_slot_id is not present in the frozen candidate plan",
            benchmark_id, cid,
        ))
        return out

    expected_partition = "holdout" if record.get("split") == "holdout" else "non_holdout"
    checks = {
        "benchmark_id": benchmark_id,
        "partition": expected_partition,
        "anchor_source_id": record.get("anchor_source_id"),
    }
    for field, actual in checks.items():
        if slot.get(field) != actual:
            out.append(Violation(
                f"qualification.factory_slot_{field}",
                f"record {field} does not match frozen factory slot",
                benchmark_id, cid,
            ))
    if slot.get("auto_promotion") is not True:
        out.append(Violation(
            "qualification.factory_slot_not_auto_promotable",
            "unreviewed AI record cannot qualify from a slot that requires adjudication",
            benchmark_id, cid,
        ))

    fv = record.get("factory_verification")
    if not isinstance(fv, dict):
        return out
    expected_slot_hash = sha256_bytes(canonical_json_bytes(slot))
    if fv.get("slot_binding_sha256") != expected_slot_hash:
        out.append(Violation(
            "qualification.factory_slot_binding",
            "factory_verification.slot_binding_sha256 does not match frozen slot",
            benchmark_id, cid,
        ))
    if fv.get("risk_tier") != slot.get("risk_tier"):
        out.append(Violation(
            "qualification.factory_slot_risk_tier",
            "factory_verification risk_tier does not match frozen slot",
            benchmark_id, cid,
        ))
    policy_path = root / "config" / "factory-policy.json"
    if policy_path.exists():
        policy_version = load_json(policy_path).get("factory_version")
        if fv.get("factory_version") != policy_version:
            out.append(Violation(
                "qualification.factory_version_mismatch",
                "factory_verification factory_version does not match frozen factory policy",
                benchmark_id, cid,
            ))
    task_fp = record.get("factory_task_fingerprint")
    if not _is_sha256(task_fp) or task_fp != fv.get("task_fingerprint"):
        out.append(Violation(
            "qualification.factory_task_fingerprint_binding",
            "factory task fingerprint must be sha256 and match factory_verification.task_fingerprint",
            benchmark_id, cid,
        ))
    return out


def validate_record(record: dict[str, Any], benchmark_id: str, registry: dict[str, dict[str, Any]],
                    sealed_holdout_required: bool = False) -> list[Violation]:
    out: list[Violation] = []
    missing = sorted(REQUIRED_FIELDS - record.keys())
    if missing:
        out.append(Violation("record.missing_fields", f"missing fields: {', '.join(missing)}", benchmark_id, record.get("case_id")))
        return out
    cid = record.get("case_id")
    if record["benchmark_id"] != benchmark_id:
        out.append(Violation("record.benchmark_id", "benchmark_id does not match directory/spec", benchmark_id, cid))
    if record["split"] not in SPLITS:
        out.append(Violation("record.split", f"invalid split: {record['split']!r}", benchmark_id, cid))
    for key in ("case_id", "family_id"):
        if not isinstance(record[key], str) or not record[key].strip():
            out.append(Violation(f"record.{key}", f"{key} must be a non-empty string", benchmark_id, cid))

    source_ids = record.get("source_ids")
    if not isinstance(source_ids, list) or not source_ids or any(not isinstance(x, str) or not x.strip() for x in source_ids):
        out.append(Violation("provenance.source_ids", "source_ids must be a non-empty list of source IDs", benchmark_id, cid))
        source_ids = []
    elif len(set(source_ids)) != len(source_ids):
        out.append(Violation("provenance.duplicate_source_ids", "source_ids must be unique", benchmark_id, cid))

    anchor_source_id = record.get("anchor_source_id")
    if not isinstance(anchor_source_id, str) or anchor_source_id not in source_ids:
        out.append(Violation("provenance.anchor_source_id", "anchor_source_id must be a source_id used by the case", benchmark_id, cid))

    for source_id in source_ids:
        source = registry.get(source_id)
        if source is None:
            out.append(Violation("provenance.unregistered_source", f"source_id is not registered: {source_id}", benchmark_id, cid))
        elif source.get("qualification_eligible") is not True:
            out.append(Violation("provenance.source_not_eligible", f"source is not qualification-eligible: {source_id}", benchmark_id, cid))

    source_refs = record.get("source_refs")
    if not isinstance(source_refs, list) or not source_refs:
        out.append(Violation("provenance.source_refs", "source_refs must be a non-empty list", benchmark_id, cid))
    else:
        ref_ids: list[str] = []
        for ref in source_refs:
            if not isinstance(ref, dict):
                out.append(Violation("provenance.source_ref", "each source_ref must be an object", benchmark_id, cid))
                continue
            ref_id = ref.get("source_id")
            if isinstance(ref_id, str):
                ref_ids.append(ref_id)
            else:
                out.append(Violation("provenance.source_ref_id", "source_ref.source_id is required", benchmark_id, cid))
                continue
            source = registry.get(ref_id)
            locator = ref.get("locator")
            if not isinstance(locator, str) or not locator.strip():
                out.append(Violation("provenance.locator", f"locator is required for {ref_id}", benchmark_id, cid))
            excerpt = ref.get("excerpt")
            if not isinstance(excerpt, str) or not excerpt.strip():
                out.append(Violation("provenance.excerpt", f"source excerpt is required for {ref_id}", benchmark_id, cid))
            excerpt_sha = ref.get("excerpt_sha256")
            if not _is_sha256(excerpt_sha):
                out.append(Violation("provenance.excerpt_sha256", f"excerpt_sha256 must be lowercase sha256 for {ref_id}", benchmark_id, cid))
            elif isinstance(excerpt, str):
                import hashlib
                actual_excerpt_sha = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
                if excerpt_sha != actual_excerpt_sha:
                    out.append(Violation("provenance.excerpt_hash_mismatch", f"excerpt hash mismatch for {ref_id}", benchmark_id, cid))
            version_blob = ref.get("source_blob_sha")
            if source and source.get("source_blob_sha") and version_blob != source.get("source_blob_sha"):
                out.append(Violation("provenance.source_blob_sha", f"record source blob does not match pinned registry source: {ref_id}", benchmark_id, cid))

        if set(ref_ids) != set(source_ids):
            out.append(Violation("provenance.source_ref_set", "source_refs must cover exactly source_ids", benchmark_id, cid))
        if len(ref_ids) != len(set(ref_ids)):
            out.append(Violation("provenance.duplicate_source_refs", "source_refs must contain each source exactly once", benchmark_id, cid))

    if not isinstance(record["payload"], dict):
        out.append(Violation("record.payload", "payload must be an object", benchmark_id, cid))
    else:
        payload = record["payload"]
        split = record.get("split")
        if "input" not in payload:
            out.append(Violation("record.payload_input", "payload.input is required", benchmark_id, cid))
        if sealed_holdout_required and split == "holdout":
            if "gold" in payload:
                out.append(Violation("holdout.gold_exposed", "plaintext holdout gold is forbidden in public records", benchmark_id, cid))
            if payload.get("gold_sealed") is not True:
                out.append(Violation("holdout.gold_not_sealed", "holdout payload must declare gold_sealed=true", benchmark_id, cid))
        elif "gold" not in payload:
            out.append(Violation("record.payload_gold", "non-holdout payload must contain gold", benchmark_id, cid))
        try:
            expected_fp = fingerprint_payload(payload)
            if record.get("content_fingerprint") != expected_fp:
                out.append(Violation("record.fingerprint_mismatch", "content_fingerprint must be derived from normalized payload.input", benchmark_id, cid))
        except (TypeError, ValueError) as exc:
            out.append(Violation("record.fingerprint_input", str(exc), benchmark_id, cid))

    if not _is_sha256(record["content_fingerprint"]):
        out.append(Violation("record.content_fingerprint", "content_fingerprint must be lowercase sha256", benchmark_id, cid))
    out.extend(_validate_annotation(record, benchmark_id))
    out.extend(_validate_answer_support(record, benchmark_id))
    out.extend(_validate_factory_verification(record, benchmark_id))
    return out


def validate_benchmark(root: Path, bspec: dict[str, Any], campaign_spec: dict[str, Any], registry: dict[str, dict[str, Any]]) -> dict[str, Any]:
    benchmark_id = bspec["id"]
    path = root / "benchmarks" / benchmark_id / "records.jsonl"
    records = load_jsonl(path)
    violations: list[Violation] = []
    seen_case_ids: set[str] = set()
    fingerprints_by_split: dict[str, set[str]] = defaultdict(set)
    sources_by_split: dict[str, set[str]] = defaultdict(set)
    families_by_split: dict[str, set[str]] = defaultdict(set)
    counts: Counter[str] = Counter()

    sealed_holdout_required = campaign_spec.get("qualification", {}).get("require_sealed_holdout_gold") is True
    policy_path = root / "config" / "factory-policy.json"
    factory_policy = load_json(policy_path).get("benchmarks", {}).get(benchmark_id, {}) if policy_path.exists() else {}
    for r in records:
        violations.extend(validate_record(r, benchmark_id, registry, sealed_holdout_required))
        violations.extend(_validate_factory_risk_policy(r, benchmark_id, factory_policy))
        violations.extend(_validate_factory_reserve_policy(root, r, benchmark_id))
        violations.extend(_validate_factory_slot_binding(root, r, benchmark_id))
        cid = r.get("case_id")
        if isinstance(cid, str):
            if cid in seen_case_ids:
                violations.append(Violation("record.duplicate_case_id", "duplicate case_id", benchmark_id, cid))
            seen_case_ids.add(cid)
        split = r.get("split")
        if split in SPLITS:
            counts[split] += 1
            fp = r.get("content_fingerprint")
            if isinstance(fp, str):
                fingerprints_by_split[split].add(fp)
            srcs = r.get("source_ids")
            fam = r.get("family_id")
            if isinstance(srcs, list):
                for src in srcs:
                    if isinstance(src, str):
                        sources_by_split[split].add(src)
            if isinstance(fam, str):
                families_by_split[split].add(fam)
        if r.get("synthetic") is True or r.get("gold_status") == "synthetic":
            violations.append(Violation("qualification.synthetic", "synthetic records are not qualification-eligible", benchmark_id, cid))
        if r.get("gold_status") not in campaign_spec["qualification"]["allowed_gold_status"]:
            violations.append(Violation("qualification.gold_status", f"gold_status {r.get('gold_status')!r} is not qualification-eligible", benchmark_id, cid))

    target = {
        "development": bspec["target_development"],
        "validation": bspec["target_validation"],
        "holdout": bspec["target_holdout"],
    }
    for split, expected in target.items():
        actual = counts[split]
        if actual != expected:
            violations.append(Violation("cardinality.not_exact", f"{split}: {actual} != {expected}", benchmark_id))
    total = sum(counts.values())
    if total != bspec["target_total"]:
        violations.append(Violation("cardinality.total_not_exact", f"total: {total} != {bspec['target_total']}", benchmark_id))

    all_sources = set().union(*[sources_by_split[s] for s in SPLITS])
    all_families = set().union(*[families_by_split[s] for s in SPLITS])
    if len(all_sources) < bspec["min_unique_sources"]:
        violations.append(Violation("coverage.sources", f"unique sources: {len(all_sources)} < {bspec['min_unique_sources']}", benchmark_id))
    if len(sources_by_split["holdout"]) < bspec["min_holdout_sources"]:
        violations.append(Violation("coverage.holdout_sources", f"holdout sources: {len(sources_by_split['holdout'])} < {bspec['min_holdout_sources']}", benchmark_id))
    if len(all_families) < bspec["min_unique_families"]:
        violations.append(Violation("coverage.families", f"unique families: {len(all_families)} < {bspec['min_unique_families']}", benchmark_id))
    if len(families_by_split["holdout"]) < bspec["min_holdout_families"]:
        violations.append(Violation("coverage.holdout_families", f"holdout families: {len(families_by_split['holdout'])} < {bspec['min_holdout_families']}", benchmark_id))

    non_holdout_sources = sources_by_split["development"] | sources_by_split["validation"]
    source_overlap = sorted(non_holdout_sources & sources_by_split["holdout"])
    if source_overlap:
        violations.append(Violation("leakage.source_overlap", f"holdout source overlap: {source_overlap[:10]}", benchmark_id))
    non_holdout_families = families_by_split["development"] | families_by_split["validation"]
    family_overlap = sorted(non_holdout_families & families_by_split["holdout"])
    if family_overlap:
        violations.append(Violation("leakage.family_overlap", f"holdout family overlap: {family_overlap[:10]}", benchmark_id))
    non_holdout_fp = fingerprints_by_split["development"] | fingerprints_by_split["validation"]
    fp_overlap = sorted(non_holdout_fp & fingerprints_by_split["holdout"])
    if fp_overlap:
        violations.append(Violation("leakage.fingerprint_overlap", f"holdout fingerprint overlap: {fp_overlap[:10]}", benchmark_id))

    if sealed_holdout_required:
        holdout_rows = [r for r in records if r.get("split") == "holdout"]
        for message in validate_public_seal_binding(root, campaign_spec["campaign_id"], benchmark_id, holdout_rows):
            violations.append(Violation("holdout.seal_binding", message, benchmark_id))

    return {
        "benchmark_id": benchmark_id,
        "records_path": str(path.relative_to(root)),
        "counts": {s: counts[s] for s in SPLITS},
        "total": total,
        "coverage": {
            "unique_sources": len(all_sources),
            "holdout_sources": len(sources_by_split["holdout"]),
            "unique_families": len(all_families),
            "holdout_families": len(families_by_split["holdout"]),
        },
        "source_disjoint": not source_overlap,
        "family_disjoint": not family_overlap,
        "fingerprint_disjoint": not fp_overlap,
        "qualification_eligible": not violations,
        "violations": [v.to_dict() for v in violations],
    }


def validate_campaign(root: Path, spec: dict[str, Any]) -> dict[str, Any]:
    registry_obj = load_source_registry(root)
    registry = source_map(registry_obj)
    results = [validate_benchmark(root, b, spec, registry) for b in spec["benchmarks"]]
    campaign_violations: list[dict[str, Any]] = []

    plan_path = root / "config" / "curation-plan.json"
    if spec.get("qualification", {}).get("require_frozen_curation_plan") is True and not plan_path.exists():
        campaign_violations.append(Violation("curation_plan.missing", "frozen curation plan is required").to_dict())
    if plan_path.exists():
        plan = load_json(plan_path)
        partition = plan.get("global_source_partition", {})
        hold = set(partition.get("holdout", []))
        non = set(partition.get("non_holdout", []))
        eligible = {sid for sid, src in registry.items() if src.get("qualification_eligible") is True}
        overlap = sorted(hold & non)
        missing = sorted(eligible - hold - non)
        unknown = sorted((hold | non) - eligible)
        if overlap:
            campaign_violations.append(Violation("curation_plan.source_partition_overlap", f"sources in both partitions: {overlap[:10]}").to_dict())
        if missing:
            campaign_violations.append(Violation("curation_plan.unpartitioned_sources", f"eligible sources missing from global partition: {missing[:10]}").to_dict())
        if unknown:
            campaign_violations.append(Violation("curation_plan.unknown_or_ineligible_sources", f"partition includes unknown/ineligible sources: {unknown[:10]}").to_dict())
        bplans = plan.get("benchmarks", {})
        for b in spec["benchmarks"]:
            bp = bplans.get(b["id"])
            if not isinstance(bp, dict):
                campaign_violations.append(Violation("curation_plan.missing_benchmark", "benchmark missing from curation plan", b["id"]).to_dict())
                continue
            bh = set(bp.get("holdout_source_pool", []))
            bn = set(bp.get("non_holdout_source_pool", []))
            if bh - hold:
                campaign_violations.append(Violation("curation_plan.holdout_pool_escape", f"benchmark holdout sources outside global holdout: {sorted(bh-hold)[:10]}", b["id"]).to_dict())
            if bn - non:
                campaign_violations.append(Violation("curation_plan.non_holdout_pool_escape", f"benchmark non-holdout sources outside global non-holdout: {sorted(bn-non)[:10]}", b["id"]).to_dict())
            if bh & bn:
                campaign_violations.append(Violation("curation_plan.benchmark_pool_overlap", f"benchmark source pools overlap: {sorted(bh&bn)[:10]}", b["id"]).to_dict())
            if bp.get("target_holdout") != b["target_holdout"] or bp.get("target_non_holdout") != b["target_development"] + b["target_validation"]:
                campaign_violations.append(Violation("curation_plan.target_mismatch", "curation-plan target counts do not match benchmark spec", b["id"]).to_dict())

    # Enforce the preregistered partition against the actual records, not merely the plan file.
    if plan_path.exists():
        plan = load_json(plan_path)
        for b in spec["benchmarks"]:
            bp = plan.get("benchmarks", {}).get(b["id"], {})
            hold_pool = set(bp.get("holdout_source_pool", []))
            non_pool = set(bp.get("non_holdout_source_pool", []))
            for r in load_jsonl(root / "benchmarks" / b["id"] / "records.jsonl"):
                srcs = set(str(x) for x in r.get("source_ids", []) if isinstance(x, str))
                allowed = hold_pool if r.get("split") == "holdout" else non_pool
                if srcs and not srcs.issubset(allowed):
                    campaign_violations.append(Violation(
                        "curation_plan.record_partition_mismatch",
                        f"record sources {sorted(srcs)} escape preregistered pool for split {r.get('split')}",
                        b["id"], r.get("case_id"),
                    ).to_dict())

    quotas_path = root / "config" / "curation-quotas.json"
    if spec.get("qualification", {}).get("require_frozen_curation_quotas") is True:
        if not quotas_path.exists():
            campaign_violations.append(Violation("curation_quotas.missing", "frozen curation quotas are required").to_dict())
        else:
            try:
                actual_quotas = load_json(quotas_path)
                expected_quotas = build_curation_queue_plan(root, spec)
                if canonical_json_bytes(actual_quotas) != canonical_json_bytes(expected_quotas):
                    campaign_violations.append(Violation("curation_quotas.mismatch", "curation quotas do not match the frozen spec/source partition").to_dict())
                else:
                    by_benchmark = {x["benchmark_id"]: x for x in actual_quotas.get("benchmarks", [])}
                    for b in spec["benchmarks"]:
                        q = by_benchmark.get(b["id"], {})
                        expected_hold = {x["anchor_source_id"]: int(x["target_cases"]) for x in q.get("holdout", {}).get("anchor_quotas", [])}
                        expected_non = {x["anchor_source_id"]: int(x["target_cases"]) for x in q.get("non_holdout", {}).get("anchor_quotas", [])}
                        actual_hold: Counter[str] = Counter()
                        actual_non: Counter[str] = Counter()
                        for r in load_jsonl(root / "benchmarks" / b["id"] / "records.jsonl"):
                            anchor = r.get("anchor_source_id")
                            if not isinstance(anchor, str):
                                campaign_violations.append(Violation("curation_quotas.anchor_missing", "record lacks anchor_source_id", b["id"], r.get("case_id")).to_dict())
                                continue
                            (actual_hold if r.get("split") == "holdout" else actual_non)[anchor] += 1
                        if dict(actual_hold) != expected_hold:
                            campaign_violations.append(Violation("curation_quotas.holdout_counts", f"actual holdout anchor counts {dict(actual_hold)} != frozen quotas {expected_hold}", b["id"]).to_dict())
                        if dict(actual_non) != expected_non:
                            campaign_violations.append(Violation("curation_quotas.non_holdout_counts", f"actual non-holdout anchor counts {dict(actual_non)} != frozen quotas {expected_non}", b["id"]).to_dict())
            except Exception as exc:
                campaign_violations.append(Violation("curation_quotas.invalid", f"unable to validate curation quotas: {exc}").to_dict())

    global_sources: dict[str, set[str]] = defaultdict(set)
    global_families: dict[str, set[str]] = defaultdict(set)
    global_fingerprints: dict[str, set[str]] = defaultdict(set)
    for b in spec["benchmarks"]:
        for r in load_jsonl(root / "benchmarks" / b["id"] / "records.jsonl"):
            split = r.get("split")
            if split not in SPLITS:
                continue
            bucket = "holdout" if split == "holdout" else "non_holdout"
            srcs = r.get("source_ids", [])
            if isinstance(srcs, list):
                for src in srcs:
                    if isinstance(src, str):
                        global_sources[bucket].add(src)
            fam = r.get("family_id")
            if isinstance(fam, str):
                global_families[bucket].add(fam)
            fp = r.get("content_fingerprint")
            if isinstance(fp, str):
                global_fingerprints[bucket].add(fp)

    source_overlap = sorted(global_sources["holdout"] & global_sources["non_holdout"])
    family_overlap = sorted(global_families["holdout"] & global_families["non_holdout"])
    fingerprint_overlap = sorted(global_fingerprints["holdout"] & global_fingerprints["non_holdout"])
    global_violations: list[dict[str, Any]] = []
    if source_overlap:
        global_violations.append(Violation("leakage.global_source_overlap", f"campaign-wide holdout source overlap: {source_overlap[:10]}").to_dict())
    if family_overlap:
        global_violations.append(Violation("leakage.global_family_overlap", f"campaign-wide holdout family overlap: {family_overlap[:10]}").to_dict())
    if fingerprint_overlap:
        global_violations.append(Violation("leakage.global_fingerprint_overlap", f"campaign-wide holdout fingerprint overlap: {fingerprint_overlap[:10]}").to_dict())
    campaign_violations.extend(global_violations)
    all_pass = all(r["qualification_eligible"] for r in results) and not campaign_violations
    return {
        "campaign_id": spec["campaign_id"],
        "source_registry_entries": len(registry),
        "benchmarks": results,
        "global_disjointness": {
            "source_disjoint": not source_overlap,
            "family_disjoint": not family_overlap,
            "fingerprint_disjoint": not fingerprint_overlap,
            "source_overlap": source_overlap,
            "family_overlap": family_overlap,
            "fingerprint_overlap": fingerprint_overlap,
        },
        "global_violations": global_violations,
        "campaign_violations": campaign_violations,
        "all_benchmarks_qualified": all_pass,
        "violation_count": sum(len(r["violations"]) for r in results) + len(campaign_violations),
    }
