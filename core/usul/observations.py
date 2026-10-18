"""U0.4: bounded site-display observations, no text authority or rule admission.

Eight tiny source-display fragments are locally pinned to this research
commit, NOT to verified print-book bytes or a publisher's authenticated text.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .claims import assess_cards, validate_cards
from .docket import _plain_json_tree, assess_docket
from .engine import _preflight

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas/usul-u04-text-observations.schema.json"
_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
Draft202012Validator.check_schema(_SCHEMA)
_VALIDATOR = Draft202012Validator(_SCHEMA)

# Fixed independent local-commit identifications of EXACT recorded snippets.
# No source-library/PDF/trust/edition SHA is asserted by these hex digests.
_PINS = {"u04_t001_e01":["author_discussion","252c544c32fe33d7f7ce2cec31dfa3cae6c5b6410cd47c895dfba4056a4fecb1"],"u04_t001_e02":["editor_footnote","4df863eadaba711c382b5afe57f005068f3b8af652893c56dc36726641b3b876"],"u04_t002_e01":["author_discussion","5a4545d3c3f322356aabd58d255f7d65ddbefa2cb67543a2a0fde593cd76c053"],"u04_t002_e02":["editor_footnote","31b547e5dd5eade8cd930ff37c97998af3d9be598f08ba1108ed4384e6eb1102"],"u04_t003_e01":["unverified_heading","98969d965c2c0881284e773707dbe20374c350fb917cc9ca28cf8f3e569836cc"],"u04_t003_e02":["editor_footnote","5dbb25b83d1a312be9edcbbe25c4d491ccc2dc33f6bc81ec36168df1d7b0ba15"],"u04_t004_e01":["interlocutor_question","4c6d4b1d310a0c569d6f08f53f52f39c6d236cc90b3370b7901e298f971f6114"],"u04_t004_e02":["editor_footnote","a59c49c79d62b9cb353302417864ca94afd0769a08079fa202cface849419f6e"]}
_EXPECTED_ROUTES = (146, 149, 157, 556)
_CRITICAL_IJMA_ID = "u04_t004"

def _unknown_fields(data: dict[str, Any]) -> list[str]:
    if any(type(k) is not str or k not in _SCHEMA["properties"] for k in data):
        return ["unknown:root_field"]
    rows = data.get("observations")
    if type(rows) is list:
        if len(rows) > 4:
            return ["invalid:observation_count_exceeded"]
        props = _SCHEMA["properties"]["observations"]["items"]["properties"]
        eprops = props["source_excerpts"]["items"]["properties"]
        for i,row in enumerate(rows):
            if type(row) is dict:
                if any(type(k) is not str or k not in props for k in row):
                    return [f"unknown:observation_field:{i}"]
                excerpts = row.get("source_excerpts")
                if type(excerpts) is list:
                    if len(excerpts) > 2:
                        return [f"invalid:excerpt_count_exceeded:{i}"]
                    for j,item in enumerate(excerpts):
                        if type(item) is dict and any(
                            type(k) is not str or k not in eprops for k in item
                        ):
                            return [f"unknown:excerpt_field:{i}:{j}"]
    return []

def validate_observations(data: Any, cards: Any, docket: Any) -> list[str]:
    """Validate strict local research ledger, not source text or scholarship."""
    if type(data) is not dict:
        return ["invalid:ledger_must_be_plain_object"]
    issues = _unknown_fields(data)
    if issues:
        return issues
    if not _plain_json_tree(data):
        return ["invalid:untrusted_json_container"]
    issues = _preflight(data)
    if issues:
        return ["invalid:budget:" + i for i in issues]
    errors: list[str] = []
    try:
        for e in _VALIDATOR.iter_errors(data):
            errors.append("schema:" + "/".join(map(str,e.absolute_path))[:150]
                          + ":" + str(e.validator))
            if len(errors) >= 24:
                break
    except (TypeError, ValueError, UnicodeError, RecursionError, OverflowError):
        return ["invalid:schema_validation_error"]
    if errors:
        return sorted(set(errors))
    # Validate all parent invariants before looking up their declared digests.
    parent_errors = validate_cards(cards, docket)
    if parent_errors:
        return ["invalid:question_parent"] + parent_errors[:4]
    card_report = assess_cards(cards, docket)
    docket_report = assess_docket(docket)
    if (data["question_cards_sha256"] != card_report["card_set_sha256"]
            or data["source_docket_sha256"] != docket_report["docket_sha256"]):
        return ["invalid:parent_digest_mismatch"]
    parent = {c["card_id"]:c for c in cards["cards"]}
    source = {c["candidate_id"]:c for c in docket["candidates"]}
    ids = set()
    for row in data["observations"]:
        oid = row["observation_id"]
        if oid in ids:
            return ["invalid:duplicate_observation_id"]
        ids.add(oid)
        if oid not in ("u04_t001","u04_t002","u04_t003","u04_t004"):
            return ["invalid:unknown_observation_id"]
        slot = int(oid[-3:])
        cid = f"u03_h{slot:03}"
        sid = f"u02_c{slot:03}"
        if row["card_id"] != cid or row["candidate_id"] != sid:
            return ["invalid:observation_parent_id_mismatch"]
        candidate = source[sid]
        linked = parent[cid]
        loc = candidate["locator"]
        if (row["source_route_id"] != _EXPECTED_ROUTES[slot-1]
                or row["source_route_id"] != loc["route_id"]
                or row["printed_page_on_site"] != loc["printed_page_on_site"]
                or row["site_page_url"] != loc["url"]
                or row["heading_provenance"] != candidate["heading_provenance"]
                or row["source_route_id"] != linked["source_route_id"]):
            return ["invalid:observation_locator_or_editorial_mismatch"]
        words = 0
        for j,excerpt in enumerate(row["source_excerpts"],1):
            eid = f"{oid}_e{j:02}"
            if excerpt["excerpt_id"] != eid:
                return ["invalid:excerpt_slot_mismatch"]
            expected_role, expected_sha = _PINS[eid]
            actual = hashlib.sha256(excerpt["text_ar"].encode("utf-8","strict")).hexdigest()
            if (excerpt["voice_role"] != expected_role
                    or excerpt["local_excerpt_sha256"] != expected_sha
                    or actual != expected_sha):
                return ["invalid:excerpt_role_or_local_pin_mismatch"]
            words += len(excerpt["text_ar"].split())
        if words > 25:
            return ["invalid:route_quote_word_limit_exceeded"]
    if len(ids) != 4:
        return ["invalid:incomplete_observations"]
    return []

def _parent_fingerprints_match(data: Any, cards: Any, docket: Any) -> bool:
    """Does this ledger name the two supplied valid metadata parents?

    This is deliberately independent of unrelated U0.4 excerpt errors.
    Matching user-supplied metadata does NOT attest publisher source custody.
    """
    if type(data) is not dict or not _plain_json_tree(data) or _preflight(data):
        return False
    left = data.get("source_docket_sha256")
    right = data.get("question_cards_sha256")
    if type(left) is not str or type(right) is not str:
        return False
    if validate_cards(cards, docket):
        return False
    return (left == assess_docket(docket)["docket_sha256"]
            and right == assess_cards(cards, docket)["card_set_sha256"])


def assess_observations(data: Any, cards: Any, docket: Any) -> dict[str, Any]:
    errors = validate_observations(data,cards,docket)
    report = {
        "scope":"unverified_site_display_observations_only",
        "valid_metadata":not errors,
        "parent_bindings_match":_parent_fingerprints_match(data,cards,docket),
        "observation_count":0,
        "excerpt_count":0,
        "observation_set_sha256":None,
        "approved_rule_count":0,
        "eligible_for_engine":False,
        "human_review_performed":False,
        "edition_authenticated":False,
        "source_bytes_pinned":False,
        "legal_rights_verified":False,
        "author_attribution_verified":False,
        "errors":errors,
    }
    if not errors:
        normalized = dict(data)
        normalized["observations"]=sorted(data["observations"],key=lambda r:r["observation_id"])
        raw=json.dumps(normalized,sort_keys=True,ensure_ascii=False,
                       allow_nan=False,separators=(",",":")).encode("utf-8","strict")
        report["observation_set_sha256"]=hashlib.sha256(raw).hexdigest()
        report["observation_count"]=len(data["observations"])
        report["excerpt_count"]=sum(len(r["source_excerpts"]) for r in data["observations"])
    return report
