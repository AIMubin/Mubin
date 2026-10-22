"""U0.2.3 private-operator acceptance: deterministic real-source replay audit.

Only metadata/hashes leave the local operator. No private source strings,
HTML, quoted excerpts or paths appear in the public-ready output.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from engines.usul.concept_rule_catalog import CatalogError, canonical, need, sha
from engines.usul.pilots.waraqat_stage06 import (
    W1_RAW_SHA, W1_EXPORT_SHA, W1_MANIFEST_SHA, W1_SECTION_SHA, W2_RAW_SHA,
)
from engines.usul.pilots.waraqat_stage07 import W2_SECTION_SHA
from engines.usul.pilots.waraqat_u02_real_bridge import (
    REPO_DATA, replay_and_bind, VERSION as BRIDGE_VERSION,
)

VERSION = "waraqat-u02-private-acceptance/0.2.3"
EXPECTED_FILE_PINS = (
    W1_RAW_SHA, W1_EXPORT_SHA, W1_MANIFEST_SHA, W1_SECTION_SHA,
    W2_RAW_SHA, W2_SECTION_SHA,
)
HEX40 = re.compile(r"[0-9a-f]{40}\Z")


def _exact_occurrences(raw, literal):
    """Independent original-byte UTF-8 recount using bytes.find, not Stage07."""
    needle = literal.encode("utf-8")
    need(bool(needle), "EMPTY_LITERAL")
    start, positions = 0, []
    while True:
        position = raw.find(needle, start)
        if position < 0:
            return positions
        positions.append(position)
        start = position + len(needle)


def _read_public_queries(queries):
    need(type(queries) is list and len(queries) <= 32,
         "QUERY_CONTRACT_INVALID")
    index = {}
    for q in queries:
        need(type(q) is dict and
             type(q.get("id")) is str and
             type(q.get("literal")) is str and
             q["id"] not in index and
             0 < len(q["literal"]) <= 100,
             "QUERY_CONTRACT_INVALID")
        index[q["id"]] = q["literal"]
    return index


def _assert_private_files_pinned(paths):
    need(type(paths) in (list, tuple) and len(paths) == 6,
         "PRIVATE_PATH_COUNT_INVALID")
    for f, trusted in zip(paths, EXPECTED_FILE_PINS):
        need(sha(Path(f).read_bytes()) == trusted,
             "FROZEN_PRIVATE_INPUT_DIGEST_MISMATCH")
    return True


def _negative_source_replay(paths, metadata, target_index, expected_sha,
                            replay):
    """Attempt a hostile first-byte mutation on a disposable temp HTML.

    We require an exception, not a 'FAILED' string from the positive
    runner. Failure to reject a corrupted frozen source invalidates audit.
    """
    original = Path(paths[target_index]).read_bytes()
    need(len(original) >= 1, "EMPTY_PRIVATE_HTML")
    tampered = bytes([original[0] ^ 1]) + original[1:]
    need(sha(tampered) != expected_sha,
         "HOSTILE_SOURCE_MUTATION_FAILED")
    with TemporaryDirectory(prefix="mubin-u02-negative-") as tmp:
        changed = Path(tmp) / "tampered-original.html"
        changed.write_bytes(tampered)
        hostile_paths = list(paths)
        hostile_paths[target_index] = changed
        try:
            replay(hostile_paths, *metadata)
        except (ValueError, OSError, UnicodeError, KeyError, TypeError):
            return True
    raise CatalogError("HOSTILE_PRIVATE_HTML_REPLAY_NOT_REFUSED")


def attest_private_sources(paths, queries, pointers, catalog_manifest,
                           lexical_manifest, *, commit_sha, replay=replay_and_bind):
    """Pure-ish orchestrator requiring access to all six private bytes.

    Test injection 'replay' is for synthetic tests only. The public CLI
    always passes the actual strict Stage06→07→08→U0.2 runner.
    """
    need(type(commit_sha) is str and HEX40.fullmatch(commit_sha) is not None,
         "AUDITED_COMMIT_SHA_INVALID")
    _assert_private_files_pinned(paths)
    metadata = (queries, pointers, catalog_manifest, lexical_manifest)
    first, second = (replay(paths, *metadata) for _ in range(2))
    need(type(first) is dict and first.get("status") ==
         "U02_WARAQAT_PINNED_CATALOG_PASS" and first == second,
         "PRIVATE_REPLAY_NONDETERMINISTIC_OR_FAILED")
    public_queries = _read_public_queries(queries)
    lexical = first["lexical_bindings"]
    need(type(lexical) is list and len(lexical) == 3 and
         all(type(row) is dict and row.get("classification") ==
             "EXACT_LITERAL_ONLY" and row.get("source_id") ==
             "pilot:waraqat-primary" for row in lexical),
         "EXPECTED_W1_EXACT_LINKS_REQUIRED")
    counted = []
    source_bytes = Path(paths[3]).read_bytes()
    for row in lexical:
        query = row["query_id"]
        need(query in public_queries and
             row["section_sha256"] == W1_SECTION_SHA,
             "LEXICAL_LINK_SOURCE_MISMATCH")
        positions = _exact_occurrences(source_bytes, public_queries[query])
        need(len(positions) == row["unique_occurrence_count"] and
             len(positions) == len(row["occurrence_ids"]),
             "INDEPENDENT_W1_LITERAL_COUNT_MISMATCH")
        counted.append({"concept_id": row["concept_id"], "query_id": query,
                        "independent_exact_count": len(positions),
                        "matches_reported_graph": True})
    need(_negative_source_replay(paths, metadata, 0, W1_RAW_SHA, replay),
         "W1_MUTATION_NOT_REFUSED")
    need(_negative_source_replay(paths, metadata, 4, W2_RAW_SHA, replay),
         "W2_MUTATION_NOT_REFUSED")
    result = {
        "schema_version": "0.2.3",
        "engine": VERSION,
        "status": "U02_REAL_WARAQAT_PRIVATE_REPLAY_ACCEPTED",
        "operator_supplied_git_commit": commit_sha,
        "bridge_engine": BRIDGE_VERSION,
        "bridge_report_sha256": first["u02_real_replay_report_sha256"],
        "stage08_graph_sha256": first["stage08_graph_sha256"],
        "catalog_sha256": first["catalog_sha256"],
        "original_private_witness_pins": {
            "w1_html_sha256": W1_RAW_SHA,
            "w1_utf8_export_sha256": W1_EXPORT_SHA,
            "w1_manifest_sha256": W1_MANIFEST_SHA,
            "w1_bab_amr_sha256": W1_SECTION_SHA,
            "w2_html_sha256": W2_RAW_SHA,
            "w2_bab_amr_sha256": W2_SECTION_SHA,
        },
        "identical_two_source_replays": True,
        "full_private_inputs_matched_frozen_sha256": True,
        "stage08_reproduced_node_count": first["stage08_node_count"],
        "stage08_reproduced_edge_count": first["stage08_edge_count"],
        "candidate_concept_count": first["catalog_concept_count"],
        "candidate_rule_count": first["catalog_rule_candidates"],
        "independent_original_byte_literal_counts": sorted(
            counted, key=lambda x: x["concept_id"]),
        "w1_mutated_html_rejected": True,
        "w2_mutated_html_rejected": True,
        "source_text_included": False, "private_paths_included": False,
        "lexical_content_equivalence_certified": False,
        "source_edition_authenticated": False,
        "source_support_attested": False,
        "scholarly_verified": False, "redistribution_approved": False,
        "semantic_equivalence_verified": False,
        "rule_execution_performed": False,
        "juristic_inference_allowed": False, "public_fatwa_authorized": False,
    }
    return {**result, "acceptance_receipt_sha256": sha(canonical(result))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("primary-html", "primary-export", "primary-manifest",
                 "primary-section", "secondary-html", "secondary-section"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--queries", type=Path,
                        default=REPO_DATA / "waraqat-stage07-queries.json")
    parser.add_argument("--pointers", type=Path,
                        default=REPO_DATA / "waraqat-stage08-research-pointers.json")
    parser.add_argument("--catalog-manifest", type=Path,
                        default=REPO_DATA / "waraqat-u02-catalog-candidates.json")
    parser.add_argument("--lexical-manifest", type=Path,
                        default=REPO_DATA / "waraqat-u02-lexical-bindings.json")
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    paths = tuple(getattr(args, name.replace("-", "_")) for name in (
        "primary-html", "primary-export", "primary-manifest",
        "primary-section", "secondary-html", "secondary-section"))
    try:
        if not all(p.is_file() for p in paths):
            report, code = {
                "engine": VERSION, "status": "PENDING_PRIVATE_WITNESS_FILES",
                "source_text_included": False,
                "scholarly_verified": False,
            }, 3
        else:
            source = []
            for path in (args.queries, args.pointers,
                         args.catalog_manifest, args.lexical_manifest):
                if not path.is_file() or not 0 < path.stat().st_size <= 131072:
                    raise CatalogError("RESEARCH_METADATA_INPUT_MISSING")
                source.append(json.loads(path.read_text(encoding="utf-8")))
            report = attest_private_sources(paths, *source,
                                            commit_sha=args.commit_sha)
            code = 0
    except (CatalogError, OSError, ValueError, KeyError, TypeError,
            UnicodeError, RecursionError) as exc:
        # Failure reason is a stable reason code or exception type only;
        # never include untrusted exception messages or private text.
        report, code = {
            "engine": VERSION,
            "status": "U02_REAL_WARAQAT_PRIVATE_REPLAY_FAILED",
            "reason_code": (str(exc) if type(exc) is CatalogError
                            else type(exc).__name__),
            "source_text_included": False, "scholarly_verified": False,
        }, 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True,
                                    indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"],
                      "source_text_included": False}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
