"""Build a public, text-free Mubin preview from committed reviewed metadata.

This is an action-scoped PUBLIC_METADATA_PREVIEW, not a system release and
not proof of public hosting, Quran publication clearance or scholarly review.
Uses stdlib only. No original book text/section bytes can enter the output.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

PROJECT = Path(__file__).resolve().parents[1]
PROFILE = "mubin-public-metadata-preview/0.1.0"
STAGE07 = "corpus/reviews/u01-stage07-waraqat-arabic-retrieval.json"
STAGE08 = "corpus/reviews/u01-stage08-waraqat-context-graph.json"
QURAN = "corpus/reviews/q03-engineering-qualification.json"
OUT = "docs/preview-data.json"
SOURCE_URLS = {
    "W1": "https://www.islamicbook.ws/asol/alwrqat.html",
    "W2": "https://www.islam.ms/ar/كتاب-ورقات-أصول-فقه-إسلامي-إمام-حرمين-عبد-الملك-الجويني/",
}
QUERY_NAMES = {
    "pilot:amr-term": "الأمر",
    "pilot:qarinah-term": "القرينة",
    "pilot:wujub-term": "الوجوب",
    "pilot:nadb-term": "الندب",
    "pilot:ibaha-term": "الإباحة",
    "pilot:word-boundary-diagnostic": "و أما",
}
SHA = re.compile(r"^[0-9a-f]{64}$")


class PreviewError(ValueError):
    pass


def require(cond, reason):
    if not cond:
        raise PreviewError(reason)


def read(root, rel):
    path = root / rel
    require(path.is_file() and path.stat().st_size <= 100_000, "missing/oversized " + rel)
    return json.loads(path.read_text(encoding="utf-8"))


def public_manifest(root=PROJECT):
    root = Path(root)
    st7, st8, q = (read(root, p) for p in (STAGE07, STAGE08, QURAN))
    version = (root / "VERSION.yaml").read_text(encoding="utf-8")
    require(re.search(r"(?m)^  version: 0\.1\.0-alpha$", version) is not None,
            "system version requires explicitly reviewed preview policy")
    require(st7.get("campaign_decision") == "STAGE07_DUAL_WITNESS_ARABIC_RETRIEVAL_PASS"
            and st8.get("campaign_decision") == "STAGE08_DUAL_SOURCE_CONTEXT_GRAPH_PASS",
            "expected pinned operator research receipts absent")
    require(st8.get("stage07_strict_rerun", {}).get("status") ==
            st7["campaign_decision"], "Stage08 did not report strict Stage07 replay")
    require(st8.get("graph_counts", {}).get("nodes_total") == 53
            and st8["graph_counts"].get("edges_total") == 87,
            "graph numbers changed; re-review preview metadata before publishing")
    for name in ("graph_sha256", "private_report_sha256"):
        require(type(st8.get(name)) is str and SHA.fullmatch(st8[name]),
                "missing graph fingerprint " + name)
    for witness in ("W1", "W2"):
        a = st7["frozen_source_pins"][witness]
        b = st8["frozen_witness_pins"][witness]
        require(a == b, "Stage07/Stage08 witness pins diverge: " + witness)
        require(all(type(value) is str and SHA.fullmatch(value)
                    for value in a.values()), "invalid source fingerprint")
    require(st7.get("limits", {}).get("redistribution_approved") is False
            and st7["limits"].get("scholarly_verified") is False
            and st8.get("limits", {}).get("redistribution_approved") is False
            and st8["limits"].get("juristic_inference_allowed") is False,
            "preview cannot silently promote source or scholarly gates")
    require(q.get("decision", {}).get("engineering_qualified") is True
            and q.get("independent_gates_unchanged", {}).get("canonical_quran_verified") is False
            and q["independent_gates_unchanged"].get("redistribution_approved") is False,
            "Quran metadata scope or withheld-publication status changed")
    entries = st7.get("queries")
    require(type(entries) is list and len(entries) == len(QUERY_NAMES)
            and {row.get("query_id") for row in entries if type(row) is dict}
            == set(QUERY_NAMES), "Stage07 query set changed")
    counts = []
    for row in entries:
        label = QUERY_NAMES[row["query_id"]]
        for w in ("W1", "W2"):
            item = row[w]
            strict = item.get("strict")
            require(type(strict) is int and 0 <= strict <= 1000,
                    "unsafe literal match count")
        # Folded counts are profile-specific, not distinct occurrences.
        folded = row["W2"].get("candidates", {})
        require(type(folded) is dict and
                all(type(v) is int and 0 <= v <= 1000 for v in folded.values()),
                "invalid diagnostic candidate counts")
        counts.append({
            "label_ar": label,
            "w1_exact": row["W1"]["strict"],
            "w2_exact": row["W2"]["strict"],
            "w2_candidate_profiles": len(folded),
            "w2_candidate_counts_by_profile": {
                k: folded[k] for k in sorted(folded)
            },
        })
    require(sum(x["w1_exact"] + x["w2_exact"] for x in counts) == 12,
            "unexpected changed literal counts")
    graph = st8["graph_counts"]
    require(graph.get("unique_text_occurrences") == 22
            and graph.get("locating_edges_literal_exact_only") == 12
            and graph.get("locating_edges_orthographic_candidate_only") == 24,
            "graph alignment changed since review")
    return {
        "profile": PROFILE,
        "product_name": "مُبين — Mubin",
        "system_version": "0.1.0-alpha",
        "preview_status": "STATIC_ARTIFACT_READY_NOT_HOSTING_CONFIRMED",
        "audience": "public_read_only_metadata",
        "basis": {
            "stage07_review": STAGE07,
            "stage08_review": STAGE08,
            "quran_review": QURAN,
            "graph_sha256": st8["graph_sha256"],
        },
        "engines": [
            {"name": "Quran", "milestone": "Q0.3", "public_mode": "status_only",
             "note_ar": "العرض الحرفي للقرآن والتفسير محجوب حتى اعتماد النص والحقوق."},
            {"name": "Hadith", "milestone": "H3.9.2", "public_mode": "status_only",
             "note_ar": "الأحكام البشرية المجمدة لم تُستبدل بقرارات آلية."},
            {"name": "Usul", "milestone": "U0.1", "public_mode": "metadata_navigation_only",
             "note_ar": "بحث وصفي تجريبي؛ لا استنباط فقهي ولا اعتماد دلالي."},
            {"name": "Fiqh", "milestone": "F0.0", "public_mode": "not_available",
             "note_ar": "لم يُطلق محرك فقه أو خدمة فتوى."},
        ],
        "research_example": {
            "work_title": "الورقات في أصول الفقه",
            "author_attribution": "إمام الحرمين الجويني",
            "section": "باب الأمر",
            "witnesses": [
                {"id": key, "url": SOURCE_URLS[key],
                 "section_sha256": st7["frozen_source_pins"][key]["bab_amr_section"]}
                for key in ("W1", "W2")
            ],
            "query_counts": counts,
            "graph_nodes": graph["nodes_total"],
            "graph_edges": graph["edges_total"],
            "source_excerpts_included": False,
            "semantic_equivalence_certified": False,
        },
        "publication_gates": {
            "source_verbatim_publication": "WITHHELD",
            "canonical_quran_display": "WITHHELD",
            "scholarly_conclusion_publication": "WITHHELD",
            "hadith_frozen_gold_mutation": "PROHIBITED",
        },
        "rights_granted": False,
        "scholarly_verified": False,
        "public_fatwa_authorized": False,
        "source_text_included": False,
    }


def encode(data):
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=PROJECT)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--check", action="store_true",
                    help="Compare existing public artifact with reproducible build")
    args = ap.parse_args()
    try:
        result = public_manifest(args.root)
        payload = encode(result)
        target = args.out or args.root / OUT
        if args.check:
            require(target.is_file() and target.read_bytes() == payload,
                    "public artifact stale or does not match reviewed metadata")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        summary = {"status": "PUBLIC_METADATA_PREVIEW_ARTIFACT_PASS",
                   "mode": "check" if args.check else "build",
                   "system_version": result["system_version"],
                   "publication_rights_granted": False,
                   "public_hosting_verified": False}
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "FAIL", "reason_code": type(exc).__name__},
                         ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
