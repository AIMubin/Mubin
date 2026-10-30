"""B02-C.3 research chain consistency, scoped strictly to committed metadata.

No private sources, AI-review receipts or scholarly judgements are available in CI.
A pass proves only agreement of submitted records and precise checksum pointers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

HEX = re.compile(r"^[a-f0-9]{64}$")
RECEIPT = "b02c3-evidence-chain-6-145-v1.json"
ENGINE_IDS = ("n.quran", "n.tafsir", "n.hadith", "n.usul", "n.fiqh")
HOPS = (
    ("e.quran-tafsir", "n.quran", "n.tafsir", "TAFSIR_PASSAGE_BINDING", "ESTABLISHED_BYTE_PINNED"),
    ("e.tafsir-hadith", "n.tafsir", "n.hadith", "LEXICAL_WITNESS_CANDIDATE", "CANDIDATE_MATCH_LEXICAL"),
    ("e.hadith-usul", "n.hadith", "n.usul", "TEXTUAL_PARALLEL_UNASSESSED", "SEMANTIC_LINK_UNASSESSED_AT_THIS_HOP"),
    ("e.usul-fiqh", "n.usul", "n.fiqh", "STRUCTURAL_OPINION_BINDING", "STRUCTURALLY_BOUND_RESEARCH_ONLY"),
)


class ChainHandoffError(ValueError):
    pass


def require(value, code):
    if not value:
        raise ChainHandoffError(code)


def is_sha(value):
    return type(value) is str and HEX.fullmatch(value) is not None


def _load(path):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    require(type(data) is dict, "CHAIN_JSON_ROOT_INVALID")
    return data


def validate(root):
    folder = Path(root) / "research/b02b"
    chain = _load(folder / RECEIPT)
    evidence = _load(folder / "evidence-receipt.json")
    kernel_path = folder / "b02c2-kernel-receipt-6-145-v1.json"
    kernel = _load(kernel_path)
    require(chain.get("contract") == "mubin-b02c3-evidence-chain-v0.1",
            "CHAIN_CONTRACT_INVALID")
    require(chain.get("case_id") == evidence.get("case_id"),
            "CHAIN_CASE_MISMATCH")
    require(evidence.get("preserved_candidate", {}).get("selected") is False and
            evidence.get("strict_gate_v3", {}).get("verdict")
            == "REJECTED_ALL_CANDIDATES_UNDER_FULL_BAR",
            "CHAIN_STRICT_SELECTION_PROMOTED")
    nodes, edges = chain.get("nodes"), chain.get("edges")
    require(type(nodes) is list and len(nodes) == 5 and
            [n.get("node") for n in nodes if type(n) is dict] == list(ENGINE_IDS) and
            all(type(n.get("anchors")) is dict for n in nodes),
            "CHAIN_NODES_INVALID")
    require(type(edges) is list and len(edges) == 4,
            "CHAIN_HOPS_INVALID")
    for row, expected in zip(edges, HOPS):
        require(type(row) is dict and
                tuple(row.get(k) for k in ("edge","from","to","link_kind","status"))
                == expected, "CHAIN_HOP_IDENTITY_MISMATCH")
        require(type(row.get("basis")) is dict and
                type(row.get("reason")) is str and row["reason"].strip() and
                type(row.get("objections")) is list and
                all(type(x) is dict and type(x.get("open")) is bool
                    and type(x.get("type")) is str for x in row["objections"]),
                "CHAIN_HOP_BASIS_INVALID")
    summary, flags = chain.get("chain_summary"), chain.get("flags")
    require(type(summary) is dict and type(flags) is dict
            and summary.get("edges_total") == 4
            and all(summary.get(k) == 1 for k in (
                "edges_established_byte_pinned", "edges_candidate_lexical",
                "edges_structurally_bound", "edges_unassessed_no_certifier"))
            and summary.get("weakest_hop") == "e.hadith-usul"
            and summary.get("overall_status") == "PARTIALLY_BOUND_CHAIN_OPEN"
            and summary.get("scientifically_established_chain") is False
            and all(flags.get(k) is False for k in (
                "scholarly_verified", "juristic_inference_allowed",
                "completed_inference_claimed", "text_included")),
            "CHAIN_FALSE_SCIENTIFIC_CLAIM")
    require(all(any(x.get("open") is True for x in row["objections"])
                for row in edges), "CHAIN_OPEN_OBJECTION_REMOVED")
    require(is_sha(chain.get("evidence_payload_sha256")),
            "CHAIN_SELF_DIGEST_MISSING")
    raw = json.dumps(chain, ensure_ascii=False)
    require(not re.search(r"[\u0600-\u06ff]|(?:[A-Za-z]:\\|/home/|/Users/)", raw),
            "CHAIN_SENSITIVE_CONTENT_PRESENT")

    qref = nodes[0]["anchors"]
    qres = next(n["result"] for n in kernel["nodes"] if n["result"]["engine"] == "quran")
    require(qref.get("kernel_evidence_refs") == qres["evidence_refs"]
            and qref.get("verse_row_sha256") == qres["findings"][0].get("text_sha256"),
            "CHAIN_QURAN_REFERENCE_INVALID")
    taf = nodes[1]["anchors"]
    tres = next(n["result"] for n in kernel["nodes"] if n["result"]["engine"] == "tafsir")
    require(taf.get("kernel_evidence_refs") == tres["evidence_refs"]
            and taf.get("works") == len(tres["findings"]),
            "CHAIN_TAFSIR_REFERENCE_INVALID")
    usul = nodes[3]["anchors"]
    usul_res = next(n["result"] for n in kernel["nodes"] if
                    n["result"]["engine"] == "usul"
                    and n["result"]["engine_version"] == "usul-source-bridge/0.1")
    require(usul.get("ev_usul_handles") == usul_res["evidence_refs"]
            and usul.get("pinned_spans") == len(usul_res["findings"])
            and usul.get("p0_bundle_sha256") ==
            evidence["p0_projection_b02a"]["private_bundle_sha256"],
            "CHAIN_USUL_SOURCE_REFERENCE_INVALID")
    fiqh = nodes[4]["anchors"]
    fres = next(n["result"] for n in kernel["nodes"] if n["result"]["engine"] == "fiqh")
    require(fiqh.get("kernel_status") == fres["status"] == "PARTIAL"
            and fiqh.get("bound_opinions") == fres["findings"][0]["opinion_refs"]
            and fiqh.get("linked_evidence_count") == len(fres["evidence_refs"]) == 33
            and fiqh.get("juristic_conclusion") is None
            and set(usul_res["evidence_refs"]).issubset(set(fres["evidence_refs"]))
            and fres["findings"][0].get("source_claims_verified") is False
            and fres["findings"][0].get("opinion_source_attribution_verified") is False,
            "CHAIN_FIQH_ATTRIBUTION_NOT_BOUND")

    a, b, c, d = [x["basis"] for x in edges]
    stage = evidence.get("stages_executed", [])
    qstage = next(x for x in stage if x.get("stage") == "QURAN_TAFSIR")
    hstage = next(x for x in stage if x.get("stage") == "HADITH_HSEARCH01")
    require(a.get("receipt") == qstage.get("receipt")
            and a.get("payload_sha256") == qstage.get("payload_sha256")
            and a.get("kernel_refs") == tres["evidence_refs"],
            "CHAIN_QURAN_TAFSIR_RECEIPT_MISMATCH")
    require(b.get("receipt") == hstage.get("receipt")
            and b.get("payload_sha256") == hstage.get("payload_sha256")
            and b.get("classification") == "NARRATION_FRAGMENT_CANDIDATE"
            and edges[1].get("status") == "CANDIDATE_MATCH_LEXICAL"
            and any(x.get("type") == "narration_identity_not_established"
                    and x.get("open") is True for x in edges[1]["objections"]),
            "CHAIN_HADITH_FALSE_IDENTITY")
    require(c.get("receipt") == "sl-gate-v1.json" and
            is_sha(c.get("payload_sha256"))
            and c.get("closest_machine_status") == "MACHINE_SUPPORTED_RESEARCH_ONLY"
            and c.get("limitation") and
            any(x.get("type") == "no_implemented_certifier_for_hadith_usul_hop"
                    and x.get("open") is True for x in edges[2]["objections"]),
            "CHAIN_HADITH_USUL_UNASSESSED_NOT_PRESERVED")

    require(d.get("receipt") == kernel_path.name and
            d.get("ev_usul_handles") == usul_res["evidence_refs"]
            and d.get("diagnostic") == "b02c2-diagnostic-run-v1.json"
            and is_sha(d.get("payload_sha256")),
            "CHAIN_USUL_FIQH_DIGEST_REQUIRED")
    # Raw-file SHA256 is used here. A canonical-JSON digest would differ.
    require(d["payload_sha256"] ==
            hashlib.sha256(kernel_path.read_bytes()).hexdigest(),
            "CHAIN_USUL_FIQH_COMMITTED_PAYLOAD_MISMATCH")
    require(evidence.get("b02c3_evidence_chain", {}).get("chain_receipt_file")
            == RECEIPT and
            evidence["b02c3_evidence_chain"].get("scientifically_established_chain")
            is False and
            evidence["b02c3_evidence_chain"].get("weakest_hop") == "e.hadith-usul",
            "CHAIN_RECEIPT_CROSS_REFERENCE_MISMATCH")
    return {"edges": 4, "nodes": 5, "unassessed_hadith_usul": True,
            "scientifically_established": False,
            "scope": "PUBLISHED_METADATA_ONLY_NO_PRIVATE_SOURCE_AUTHENTICITY"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--if-present", action="store_true")
    args = parser.parse_args()
    if args.if_present and not (
            Path(args.root) / "research/b02b" / RECEIPT).is_file():
        print("B02-C.3 receipt absent; synthetic negative tests still run.")
        return 0
    try:
        result = validate(args.root)
    except (ChainHandoffError, OSError, TypeError, ValueError, KeyError,
            StopIteration, IndexError) as exc:
        print("B02C3 CHAIN FAIL: " +
              (str(exc) if isinstance(exc, ChainHandoffError) else "INVALID_INPUT"))
        return 1
    print("B02C3 CHAIN METADATA VALID " + json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
