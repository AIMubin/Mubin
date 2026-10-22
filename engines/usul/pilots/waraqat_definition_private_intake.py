"""Offline private operator intake for unassessed W1 concept-definition candidates.

Reads private research files from a bounded off-repository directory and
emits ONLY metadata-only HMAC commitments. Never copies private prose or
key bytes into GitHub, logs, reports or output JSON. Success establishes
structural provenance only, not scholarly attribution or source support.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from engines.usul.concept_definitions import (
    SCHEMA, build_definitions, canonical, sha, normalize_manifest,
)
from engines.usul.concept_rule_catalog import CatalogError, exact, need, valid_id
from engines.usul.private_text_commitment import make_private_commitment, MAX_BYTES

VERSION = "usul-private-definition-intake/0.1.0"
INPUT_SCHEMA = "u02-private-intake/0.1.0"
BASIS_PIN = "00f0d1c71f55dc226cd6b840decfcdada152a40746a5cdc39b1e4f019c6bf7df"
REPO_ROOT = Path(__file__).resolve().parents[3]
CONCEPT_OBSERVATION = (
    ("concept:amr-term", "pilot:amr-term", "observation:amr-term"),
    ("concept:qarinah-candidate", "pilot:qarinah-term", "observation:qarinah-term"),
    ("concept:wujub-candidate", "pilot:wujub-term", "observation:wujub-term"),
)
OBSERVATIONS = {c: oid for c, _qid, oid in CONCEPT_OBSERVATION}
SOURCE_ID = "source:waraqat-w1"
CLAIMED_AUTHOR = "author:unassessed"


def _private_path(root: Path, relative: str) -> Path:
    need(type(relative) is str and len(relative) <= 180 and
         relative and not Path(relative).is_absolute() and
         ".." not in Path(relative).parts and
         "\\" not in relative and ":" not in relative,
         "PRIVATE_RELATIVE_PATH_INVALID")
    path = (root / relative).resolve()
    need(path.is_relative_to(root) and path != root,
         "PRIVATE_PATH_OUTSIDE_ROOT")
    return path


def _key_from_environment(key_env: str) -> bytes:
    need(type(key_env) is str and key_env.isidentifier(),
         "PRIVATE_KEY_ENV_NAME_INVALID")
    value = os.environ.get(key_env, "")
    need(64 <= len(value) <= 256 and len(value) % 2 == 0,
         "PRIVATE_HMAC_KEY_UNAVAILABLE")
    try:
        key = bytes.fromhex(value)
    except ValueError:
        raise CatalogError("PRIVATE_HMAC_KEY_INVALID") from None
    need(len(key) >= 32, "PRIVATE_HMAC_KEY_TOO_SHORT")
    return key


def _text_commitment(path: Path, key: bytes) -> str:
    need(path.is_file() and 0 < path.stat().st_size <= MAX_BYTES,
         "PRIVATE_DEFINITION_FILE_INVALID")
    raw = path.read_bytes()
    need(0 < len(raw) <= MAX_BYTES, "PRIVATE_DEFINITION_BYTES_INVALID")
    try:
        raw.decode("utf-8")
    except UnicodeError:
        raise CatalogError("PRIVATE_TEXT_NOT_UTF8") from None
    return make_private_commitment(raw, key)


def prepare_private_manifest(receipt, intake, root: Path, key: bytes):
    """Strict initial W1 candidate manifest from local, private text files.

    The trusted receipt is always the independently frozen U0.2.3 one.
    Source/author fields are *claims* and scholarly status is UNASSESSED.
    """
    exact(intake, ("schema_version", "commitment_key_id",
                   "definition_files", "interpretation_files"),
          "PRIVATE_INTAKE_FIELDS_INVALID")
    key_id = intake["commitment_key_id"]
    defs, interpretations = intake["definition_files"], intake["interpretation_files"]
    need(intake["schema_version"] == INPUT_SCHEMA and valid_id(key_id)
         and type(defs) is list and 1 <= len(defs) <= 12
         and type(interpretations) is list and len(interpretations) <= 12,
         "PRIVATE_INTAKE_SCHEMA_OR_BOUNDS_INVALID")
    need(type(receipt) is dict and
         receipt.get("original_private_witness_pins", {}).get("w1_bab_amr_sha256"),
         "PRIVATE_INTAKE_RECEIPT_INVALID")
    root = root.resolve()
    need(root.is_dir() and not root.is_relative_to(REPO_ROOT)
         and not REPO_ROOT.is_relative_to(root),
         "PRIVATE_ROOT_MUST_BE_OUTSIDE_REPOSITORY")
    frozen = receipt["original_private_witness_pins"]["w1_bab_amr_sha256"]
    manifest = {
        "schema_version": SCHEMA,
        "basis_receipt_sha256": BASIS_PIN,
        "previous_manifest_sha256": None,
        "sources": [{
            "id": SOURCE_ID, "witness_id": "pilot:waraqat-primary",
            "work_id": "work:waraqat-candidate",
            "claimed_author_id": CLAIMED_AUTHOR,
            "edition_id": "edition:w1-digital-capture",
            "locator_id": "locator:bab-amr", "section_sha256": frozen,
            "rights_status": "NOT_CLEARED",
            "attribution_review_status": "UNASSESSED",
            "edition_review_status": "UNASSESSED", "version": "0.1.0",
        }],
        "source_observations": [
            {"id": oid, "concept_id": cid, "source_id": SOURCE_ID,
             "query_id": qid, "version": "0.1.0",
             "observation_status": "LEXICAL_ONLY", "source_text_included": False}
            for cid, qid, oid in CONCEPT_OBSERVATION
        ],
        "definition_candidates": [], "interpretation_candidates": [],
        "definition_comparisons": [],
    }
    used_files = set()
    for record in defs:
        exact(record, ("id", "concept_id", "version", "private_text_file"),
              "PRIVATE_DEFINITION_INTAKE_FIELDS_INVALID")
        cid = record["concept_id"]
        need(valid_id(record["id"]) and cid in OBSERVATIONS and
             type(record["version"]) is str,
             "PRIVATE_DEFINITION_INTAKE_REF_INVALID")
        path = _private_path(root, record["private_text_file"])
        need(path not in used_files, "PRIVATE_TEXT_FILE_REUSED")
        used_files.add(path)
        commitment = _text_commitment(path, key)
        manifest["definition_candidates"].append({
            "id": record["id"], "concept_id": cid,
            "source_observation_id": OBSERVATIONS[cid],
            "version": record["version"],
            "definition_commitment_sha256": commitment,
            "commitment_scheme": "HMAC_SHA256_PRIVATE",
            "commitment_key_id": key_id,
            "claimed_author_id": CLAIMED_AUTHOR,
            "review_status": "UNASSESSED", "source_text_included": False,
        })
    candidates = {r["id"]: r["concept_id"]
                  for r in manifest["definition_candidates"]}
    need(len(candidates) == len(defs), "PRIVATE_DEFINITION_IDS_DUPLICATED")
    for record in interpretations:
        exact(record, ("id", "concept_id", "version",
                       "definition_candidate_ids", "private_text_file"),
              "PRIVATE_INTERPRETATION_INTAKE_FIELDS_INVALID")
        cid, refs = record["concept_id"], record["definition_candidate_ids"]
        need(valid_id(record["id"]) and cid in OBSERVATIONS and
             type(record["version"]) is str and
             type(refs) is list and 1 <= len(refs) <= 8 and
             all(type(ref) is str and ref in candidates and
                 candidates[ref] == cid for ref in refs) and
             len(refs) == len(set(refs)),
             "PRIVATE_INTERPRETATION_CROSS_CONCEPT_INVALID")
        path = _private_path(root, record["private_text_file"])
        need(path not in used_files, "PRIVATE_TEXT_FILE_REUSED")
        used_files.add(path)
        commitment = _text_commitment(path, key)
        manifest["interpretation_candidates"].append({
            "id": record["id"], "concept_id": cid,
            "definition_candidate_ids": refs, "version": record["version"],
            "interpretation_commitment_sha256": commitment,
            "commitment_scheme": "HMAC_SHA256_PRIVATE",
            "commitment_key_id": key_id, "review_status": "UNASSESSED",
            "source_text_included": False,
        })
    report = build_definitions(receipt, BASIS_PIN, manifest)
    return normalize_manifest(manifest), report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private-root", type=Path, required=True)
    p.add_argument("--private-intake", required=True,
                   help="Relative JSON metadata filename under private root")
    p.add_argument("--output-manifest", required=True,
                   help="Relative JSON filename under private root")
    p.add_argument("--output-report", required=True,
                   help="Relative JSON filename under private root")
    p.add_argument("--basis-receipt", type=Path, default=(
        REPO_ROOT / "corpus/reviews/u02-waraqat-private-source-acceptance-PASS.json"))
    p.add_argument("--key-env", default="MUBIN_PRIVATE_HMAC_KEY_HEX")
    args = p.parse_args()
    try:
        root = args.private_root.resolve()
        need(root.is_dir() and not root.is_relative_to(REPO_ROOT)
             and not REPO_ROOT.is_relative_to(root),
             "PRIVATE_ROOT_MUST_BE_OUTSIDE_REPOSITORY")
        paths = [
            _private_path(root, name) for name in (
                args.private_intake, args.output_manifest, args.output_report)
        ]
        need(len(set(paths)) == 3 and
             all(path.parent == root for path in paths) and
             all(not path.exists() for path in paths[1:]),
             "PRIVATE_OUTPUT_COLLISION_OR_SUBDIRECTORY")
        key = _key_from_environment(args.key_env)
        source = paths[0].read_bytes()
        need(0 < len(source) <= 65536, "PRIVATE_INTAKE_INPUT_BOUNDS_INVALID")
        receipt_bytes = args.basis_receipt.read_bytes()
        need(0 < len(receipt_bytes) <= 131072,
             "BASIS_RECEIPT_SIZE_INVALID")
        intake = json.loads(source.decode("utf-8"))
        receipt = json.loads(receipt_bytes.decode("utf-8"))
        manifest, report = prepare_private_manifest(receipt, intake, root, key)
        out_report = {
            **report,
            "operator_intake_status": "PRIVATE_CANDIDATES_PREPARED_UNASSESSED",
            "private_source_files_uploaded": False,
            "private_text_attested_as_source_quotation": False,
            "private_key_exported": False,
        }
        for path, obj in zip(paths[1:], (manifest, out_report)):
            path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True,
                                       indent=2)+"\n", encoding="utf-8")
        code = 0
        display = "PRIVATE_CANDIDATES_PREPARED_UNASSESSED"
    except (CatalogError, OSError, ValueError, TypeError,
            UnicodeError, KeyError, RecursionError):
        code = 2
        display = "PRIVATE_DEFINITION_INTAKE_REJECTED"
    print(json.dumps({"status": display, "source_text_included": False,
                      "private_path_included": False}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
