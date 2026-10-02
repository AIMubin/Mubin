from __future__ import annotations

import argparse
import json
from pathlib import Path

from .audit import emit_pre_m4_audit
from .core import load_json, write_json
from .curation import curate_reviewed_file
from .evaluate import evaluate_holdout
from .freeze import create_freeze_anchor, freeze_campaign, verify_freeze
from .lifecycle import export_tuning_pack, lock_model, mark_tuning_started
from .holdout_seal import generate_holdout_key
from .manifests import emit_campaign_manifests
from .split import build_splits
from .source_cache import acquire_sources, verify_source_cache
from .queue_plan import build_curation_queue_plan
from .validate import validate_campaign


def _default_spec(root: Path) -> Path:
    return root / "config" / "benchmark-spec.json"


def _resolve(root: Path, p: Path | None) -> Path | None:
    if p is None:
        return None
    return p if p.is_absolute() else root / p


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="mubin-m392", description="H3.9.2 Benchmark Expansion Campaign")
    p.add_argument("--root", type=Path, default=Path("."))
    sub = p.add_subparsers(dest="cmd", required=True)

    gk = sub.add_parser("generate-holdout-key")
    gk.add_argument("--out", type=Path, required=True)

    s = sub.add_parser("build-splits")
    s.add_argument("--spec", type=Path)
    s.add_argument("--staging-dir", type=Path, default=Path("staging"))
    s.add_argument("--holdout-key-file", type=Path)

    qp = sub.add_parser("curation-queue-plan")
    qp.add_argument("--spec", type=Path)
    qp.add_argument("--out", type=Path, default=Path("config/curation-quotas.json"))

    acq = sub.add_parser("acquire-sources")
    acq.add_argument("--cache-dir", type=Path, default=Path("source-cache"))
    acq.add_argument("--include-ineligible", action="store_true")

    vcs = sub.add_parser("verify-source-cache")
    vcs.add_argument("--cache-dir", type=Path, default=Path("source-cache"))
    vcs.add_argument("--include-ineligible", action="store_true")

    cr = sub.add_parser("curate-reviewed")
    cr.add_argument("--benchmark-id", required=True)
    cr.add_argument("--input", type=Path, required=True)
    cr.add_argument("--out", type=Path)
    cr.add_argument("--source-cache-dir", type=Path, default=Path("source-cache"))

    prep = sub.add_parser("prepare-manifests")
    prep.add_argument("--spec", type=Path)
    prep.add_argument("--artifacts-dir", type=Path, default=Path("artifacts"))

    v = sub.add_parser("validate")
    v.add_argument("--spec", type=Path)
    v.add_argument("--out", type=Path, default=Path("artifacts/validation-report.json"))

    f = sub.add_parser("freeze")
    f.add_argument("--spec", type=Path)
    f.add_argument("--out", type=Path, default=Path("artifacts/FREEZE_MANIFEST.json"))

    af = sub.add_parser("anchor-freeze")
    af.add_argument("--manifest", type=Path, default=Path("artifacts/FREEZE_MANIFEST.json"))
    af.add_argument("--anchor-file", type=Path, default=Path("private/FREEZE_ANCHOR.json"))
    af.add_argument("--source-commit", required=True)

    vf = sub.add_parser("verify-freeze")
    vf.add_argument("--manifest", type=Path, default=Path("artifacts/FREEZE_MANIFEST.json"))
    vf.add_argument("--anchor-file", type=Path, default=Path("private/FREEZE_ANCHOR.json"))

    tp = sub.add_parser("export-tuning-pack")
    tp.add_argument("--spec", type=Path)
    tp.add_argument("--out-dir", type=Path, default=Path("artifacts/tuning-pack"))
    tp.add_argument("--freeze-manifest", type=Path, default=Path("artifacts/FREEZE_MANIFEST.json"))
    tp.add_argument("--freeze-anchor-file", type=Path, default=Path("private/FREEZE_ANCHOR.json"))

    mt = sub.add_parser("mark-tuning-started")
    mt.add_argument("--freeze-manifest", type=Path, default=Path("artifacts/FREEZE_MANIFEST.json"))
    mt.add_argument("--model-ref", required=True)
    mt.add_argument("--model-config", type=Path)
    mt.add_argument("--freeze-anchor-file", type=Path, default=Path("private/FREEZE_ANCHOR.json"))

    lm = sub.add_parser("lock-model")
    lm.add_argument("--freeze-manifest", type=Path, default=Path("artifacts/FREEZE_MANIFEST.json"))
    lm.add_argument("--model-ref", required=True)
    lm.add_argument("--system-commit", required=True)
    lm.add_argument("--model-artifact", type=Path, required=True)
    lm.add_argument("--model-config", type=Path, required=True)
    lm.add_argument("--generation-config", type=Path, required=True)
    lm.add_argument("--freeze-anchor-file", type=Path, default=Path("private/FREEZE_ANCHOR.json"))

    ev = sub.add_parser("evaluate-holdout")
    ev.add_argument("--spec", type=Path)
    ev.add_argument("--freeze-manifest", type=Path, default=Path("artifacts/FREEZE_MANIFEST.json"))
    ev.add_argument("--predictions-dir", type=Path, required=True)
    ev.add_argument("--holdout-key-file", type=Path)
    ev.add_argument("--out", type=Path, default=Path("artifacts/HOLDOUT_EVALUATION.json"))
    ev.add_argument("--freeze-anchor-file", type=Path, default=Path("private/FREEZE_ANCHOR.json"))

    a = sub.add_parser("pre-h4-audit")
    a.add_argument("--spec", type=Path)
    a.add_argument("--freeze-manifest", type=Path, default=Path("artifacts/FREEZE_MANIFEST.json"))
    a.add_argument("--evaluation-report", type=Path, default=Path("artifacts/HOLDOUT_EVALUATION.json"))
    a.add_argument("--architecture-audit", type=Path)
    a.add_argument("--holdout-key-file", type=Path)
    a.add_argument("--freeze-anchor-file", type=Path, default=Path("private/FREEZE_ANCHOR.json"))
    a.add_argument("--json-out", type=Path, default=Path("artifacts/PRE_H4_AUDIT.json"))
    a.add_argument("--ini-out", type=Path, default=Path("artifacts/pre-h4-audit.ini"))

    args = p.parse_args(argv)
    root = args.root.resolve()
    if args.cmd == "generate-holdout-key":
        out = _resolve(root, args.out)
        assert out is not None
        result = generate_holdout_key(out)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    spec_path = (args.spec if getattr(args, "spec", None) else _default_spec(root))
    if not spec_path.is_absolute():
        spec_path = root / spec_path

    if args.cmd == "curation-queue-plan":
        out = _resolve(root, args.out)
        assert out is not None
        report = build_curation_queue_plan(root, load_json(spec_path), out)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "build-splits":
        staging = _resolve(root, args.staging_dir)
        holdout_key_file = _resolve(root, args.holdout_key_file)
        report = build_splits(root, load_json(spec_path), staging, holdout_key_file)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["all_feasible"] else 5

    if args.cmd == "acquire-sources":
        cache_dir = _resolve(root, args.cache_dir)
        assert cache_dir is not None
        report = acquire_sources(root, cache_dir, args.include_ineligible)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["all_verified"] else 7

    if args.cmd == "verify-source-cache":
        cache_dir = _resolve(root, args.cache_dir)
        assert cache_dir is not None
        report = verify_source_cache(root, cache_dir, args.include_ineligible)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["all_verified"] else 7

    if args.cmd == "curate-reviewed":
        inp = _resolve(root, args.input)
        cache_dir = _resolve(root, args.source_cache_dir)
        out = _resolve(root, args.out) if args.out else root / "staging" / args.benchmark_id / "reviewed.jsonl"
        assert inp and cache_dir and out
        report = curate_reviewed_file(root, args.benchmark_id, inp, out, cache_dir)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "prepare-manifests":
        spec = load_json(spec_path)
        outdir = _resolve(root, args.artifacts_dir)
        assert outdir is not None
        paths = emit_campaign_manifests(root, spec, outdir)
        print(json.dumps({k: str(v) for k, v in paths.items()}, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "validate":
        report = validate_campaign(root, load_json(spec_path))
        out = _resolve(root, args.out)
        assert out is not None
        write_json(out, report)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["all_benchmarks_qualified"] else 2

    if args.cmd == "freeze":
        out = _resolve(root, args.out)
        assert out is not None
        manifest = freeze_campaign(root, spec_path, out)
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "anchor-freeze":
        manifest = _resolve(root, args.manifest)
        anchor_file = _resolve(root, args.anchor_file)
        assert manifest is not None and anchor_file is not None
        result = create_freeze_anchor(manifest, anchor_file, args.source_commit)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "verify-freeze":
        manifest = _resolve(root, args.manifest)
        anchor_file = _resolve(root, args.anchor_file)
        assert manifest is not None and anchor_file is not None
        result = verify_freeze(root, manifest, anchor_file)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["verified"] else 3

    if args.cmd == "export-tuning-pack":
        outdir = _resolve(root, args.out_dir)
        freeze_manifest = _resolve(root, args.freeze_manifest)
        freeze_anchor = _resolve(root, args.freeze_anchor_file)
        assert outdir is not None and freeze_manifest is not None and freeze_anchor is not None
        report = export_tuning_pack(root, load_json(spec_path), outdir, freeze_manifest, freeze_anchor)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "mark-tuning-started":
        freeze_manifest = _resolve(root, args.freeze_manifest)
        model_config = _resolve(root, args.model_config)
        freeze_anchor = _resolve(root, args.freeze_anchor_file)
        assert freeze_manifest is not None and freeze_anchor is not None
        marker = mark_tuning_started(root, freeze_manifest, args.model_ref, model_config, freeze_anchor)
        print(json.dumps(marker, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "lock-model":
        freeze_manifest = _resolve(root, args.freeze_manifest)
        model_config = _resolve(root, args.model_config)
        generation_config = _resolve(root, args.generation_config)
        model_artifact = _resolve(root, args.model_artifact)
        freeze_anchor = _resolve(root, args.freeze_anchor_file)
        assert freeze_manifest is not None and model_config is not None and generation_config is not None and model_artifact is not None and freeze_anchor is not None
        marker = lock_model(
            root, freeze_manifest, args.model_ref, model_config,
            system_commit=args.system_commit,
            model_artifact_path=model_artifact,
            generation_config_path=generation_config,
            freeze_anchor_path=freeze_anchor,
        )
        print(json.dumps(marker, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "evaluate-holdout":
        freeze_manifest = _resolve(root, args.freeze_manifest)
        predictions_dir = _resolve(root, args.predictions_dir)
        holdout_key_file = _resolve(root, args.holdout_key_file)
        out = _resolve(root, args.out)
        freeze_anchor = _resolve(root, args.freeze_anchor_file)
        assert freeze_manifest and predictions_dir and out and freeze_anchor
        report = evaluate_holdout(
            root, spec_path, freeze_manifest, predictions_dir, out,
            holdout_key_path=holdout_key_file, freeze_anchor_path=freeze_anchor
        )
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["all_benchmarks_passed"] else 6

    if args.cmd == "pre-h4-audit":
        freeze_manifest = _resolve(root, args.freeze_manifest)
        evaluation_report = _resolve(root, args.evaluation_report)
        architecture_audit = _resolve(root, args.architecture_audit)
        holdout_key_file = _resolve(root, args.holdout_key_file)
        freeze_anchor = _resolve(root, args.freeze_anchor_file)
        json_out = _resolve(root, args.json_out)
        ini_out = _resolve(root, args.ini_out)
        assert json_out and ini_out
        audit = emit_pre_m4_audit(
            root, spec_path, freeze_manifest, architecture_audit, evaluation_report,
            holdout_key_file, freeze_anchor, json_out, ini_out
        )
        print(json.dumps(audit, indent=2, ensure_ascii=False))
        return 0 if audit["h4_qualification_allowed"] else 4

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
