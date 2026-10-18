"""U0.5 non-executable, unsubmitted scholarly review task registry.

This records tasks, NOT observed human decisions, source authenticity,
legal permission, juristic consensus, or executable Usul/Fiqh rules.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .docket import _plain_json_tree, assess_docket
from .claims import assess_cards
from .observations import assess_observations, validate_observations
from .engine import _preflight

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas/usul-u05-review-queue.schema.json"
_SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
Draft202012Validator.check_schema(_SCHEMA)
_VALIDATOR = Draft202012Validator(_SCHEMA)
AXES = ["independent_edition_collation","author_editor_attribution","legal_use_basis_review","methodology_and_disagreement_review","conditions_exceptions_counterexamples","two_independent_scholarly_reviews"]
_IJMA_WARNING = "عنوان «باب الإجماع» أضافه المحقق، وسؤال المحاور ليس قولًا نهائيًا للشافعي."

# Four-slot v1 is a frozen review-task proposal, not a general source corpus.
# Explicit code review is required to change these researcher hypotheses.
# Pinning these strings proves local fixture identity, NOT scholarly truth.
_PILOT_REVIEW_TEXT = {"u05_r001":["الحاشية تشير إلى زيادة اسم القائل في شواهد أخرى، فلا تُنسب كل صياغة إلى المؤلف دون مقابلة.","افترض وجود قرينة في السياق تخصص بعض الأفراد؛ هل يبقى الاستدلال بالعموم المطلق صالحًا؟"],"u05_r002":["اختلاف ألفاظ عنوان الباب «الخاص» و«الخصوص» يقتضي فصل عنوان المحقق عن متن الاستدلال.","افترض اختلافًا معتبرًا بين ألفاظ العنوان والمتن؛ هل يصح بناء نسبة أصل أصولي من العنوان وحده؟"],"u05_r003":["اختلاف لفظ «دلت» و«فدلت» وعنوان الباب لا يثبتان خبرًا معينًا ولا دلالة تخصيص.","افترض عدم ثبوت الخبر أو عدم اتحاد محل الحكم؛ هل يصح جعله مخصصًا للعموم؟"],"u05_r004":["عنوان «باب الإجماع» أضافه المحقق، وسؤال المحاور ليس قولًا نهائيًا للشافعي.","افترض أن المحاور يعترض وأن المؤلف لا يوافق على المقدمة؛ هل يصح جعل السؤال حجية إجماع؟"]}

def _unexpected_fields(document: dict[str, Any]) -> list[str]:
    if any(type(k) is not str or k not in _SCHEMA["properties"] for k in document):
        return ["unknown:root_field"]
    rows = document.get("reviews")
    if type(rows) is list:
        if len(rows) > 4:
            return ["invalid:review_count_exceeded"]
        rprops = _SCHEMA["properties"]["reviews"]["items"]["properties"]
        tprops = rprops["evidence_tasks"]["items"]["properties"]
        for i,row in enumerate(rows):
            if type(row) is dict:
                if any(type(k) is not str or k not in rprops for k in row):
                    return [f"unknown:review_field:{i}"]
                tasks = row.get("evidence_tasks")
                if type(tasks) is list:
                    if len(tasks) > 6:
                        return [f"invalid:task_count_exceeded:{i}"]
                    for j,t in enumerate(tasks):
                        if type(t) is dict and any(
                            type(k) is not str or k not in tprops for k in t
                        ):
                            return [f"unknown:task_field:{i}:{j}"]
    return []

def _parent_matches(queue: Any, observations: Any, cards: Any, docket: Any) -> bool:
    """Structural parent fingerprint consistency, NOT attested source custody.

    Other U0.5 review-task errors should not falsely label the parent as
    different. The supplied parents can be replaced by a caller together
    with matching new hashes; no independent authenticity claim is made.
    """
    if type(queue) is not dict or not _plain_json_tree(queue) or _preflight(queue):
        return False
    keys = ("source_docket_sha256","question_cards_sha256","observation_set_sha256")
    if any(type(queue.get(k)) is not str for k in keys):
        return False
    if validate_observations(observations,cards,docket):
        return False
    return (queue["source_docket_sha256"] == assess_docket(docket)["docket_sha256"]
            and queue["question_cards_sha256"] == assess_cards(cards,docket)["card_set_sha256"]
            and queue["observation_set_sha256"] ==
                assess_observations(observations,cards,docket)["observation_set_sha256"])

def validate_review_queue(queue: Any, observations: Any, cards: Any, docket: Any) -> list[str]:
    """Validate bounded unsubmitted metadata, fail closed for fake approvals."""
    if type(queue) is not dict:
        return ["invalid:queue_must_be_plain_object"]
    errors = _unexpected_fields(queue)
    if errors:
        return errors
    if not _plain_json_tree(queue):
        return ["invalid:untrusted_json_container"]
    issues = _preflight(queue)
    if issues:
        return ["invalid:budget:" + i for i in issues]
    errors = []
    try:
        for issue in _VALIDATOR.iter_errors(queue):
            path = "/".join(str(x) for x in issue.absolute_path)[:160]
            errors.append("schema:" + path + ":" + str(issue.validator))
            if len(errors) >= 24:
                break
    except (TypeError, ValueError, UnicodeError, RecursionError, OverflowError):
        return ["invalid:schema_validation_error"]
    if errors:
        return sorted(set(errors))
    parent_errors = validate_observations(observations,cards,docket)
    if parent_errors:
        return ["invalid:observation_parent"] + parent_errors[:5]
    if not _parent_matches(queue,observations,cards,docket):
        return ["invalid:parent_digest_mismatch"]
    parent_obs = {r["observation_id"]: r for r in observations["observations"]}
    parent_cards = {r["card_id"]: r for r in cards["cards"]}
    ids: set[str] = set()
    for row in queue["reviews"]:
        rid = row["review_id"]
        if rid in ids:
            return ["invalid:duplicate_review_id"]
        ids.add(rid)
        if rid not in ("u05_r001","u05_r002","u05_r003","u05_r004"):
            return ["invalid:unexpected_review_id"]
        slot = int(rid[-3:])
        oid = f"u04_t{slot:03}"
        cid = f"u03_h{slot:03}"
        did = f"u02_c{slot:03}"
        if (row["observation_id"] != oid or row["card_id"] != cid
                or row["candidate_id"] != did):
            return ["invalid:review_parent_id_mismatch"]
        obs = parent_obs[oid]
        card = parent_cards[cid]
        if (row["research_question_ar"] != card["question_ar"]
                or row["source_route_id"] != obs["source_route_id"]
                or row["printed_page_on_site"] != obs["printed_page_on_site"]
                or row["heading_provenance"] != obs["heading_provenance"]):
            return ["invalid:review_parent_content_mismatch"]
        if [task["axis_id"] for task in row["evidence_tasks"]] != AXES:
            return ["invalid:noncanonical_evidence_axis_order"]
        pinned_risk, pinned_probe = _PILOT_REVIEW_TEXT[rid]
        if (row["editorial_risk_ar"] != pinned_risk
                or row["falsification_probe_ar"] != pinned_probe):
            return ["invalid:pilot_research_risk_or_falsification_downgrade"]
    if ids != {"u05_r001","u05_r002","u05_r003","u05_r004"}:
        return ["invalid:incomplete_review_queue"]
    return []

def assess_review_queue(queue: Any, observations: Any, cards: Any, docket: Any) -> dict[str, Any]:
    errors = validate_review_queue(queue,observations,cards,docket)
    report = {
        "scope":"unsubmitted_scholarly_review_queue_only",
        "valid_metadata":not errors,
        "parent_bindings_match":_parent_matches(queue,observations,cards,docket),
        "queued_claim_count":0,
        "open_evidence_task_count":0,
        "review_queue":[],
        "queue_sha256":None,
        "admitted_rule_count":0,
        "verified_human_review_count":0,
        "claimed_reviewer_count":0,
        "eligible_for_engine":False,
        "independent_human_review_verified":False,
        "edition_authenticated":False,
        "rights_verified":False,
        "source_bytes_pinned":False,
        "errors":errors,
    }
    if not errors:
        canon = dict(queue)
        canon["reviews"] = sorted(queue["reviews"],key=lambda row:row["review_id"])
        raw = json.dumps(canon,sort_keys=True,ensure_ascii=False,
                         separators=(",",":"),allow_nan=False).encode("utf-8","strict")
        report["queue_sha256"]=hashlib.sha256(raw).hexdigest()
        report["queued_claim_count"]=len(queue["reviews"])
        report["open_evidence_task_count"]=sum(len(x["evidence_tasks"]) for x in queue["reviews"])
        report["review_queue"]=[x["review_id"] for x in canon["reviews"]]
    return report

def summarize_unverified_review_positions(first: Any, second: Any) -> dict[str, Any]:
    """Illustrative, UNAUTHENTICATED positions; no human review asserted.

    This is not an interface for storing identities or releasing conclusions.
    """
    supported = {"accept","reject","revise","abstain"}
    if type(first) is not str or type(second) is not str or (
        first not in supported or second not in supported
    ):
        raise ValueError("invalid unverified position")
    if "abstain" in (first,second):
        status="unverified_abstention"
    elif "revise" in (first,second):
        status="requires_revision"
    elif first != second:
        status="escalate_disagreement"
    elif first == second == "accept":
        status="unverified_concurrence"
    else:
        status="unverified_nonapproval"
    return {"status":status,"eligible_for_engine":False,
            "verified_human_review_count":0,
            "independent_human_review_verified":False}
