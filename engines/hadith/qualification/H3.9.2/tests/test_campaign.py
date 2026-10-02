from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from benchmark_campaign.audit import build_pre_m4_audit
from benchmark_campaign.core import dump_jsonl, load_json, write_json
from benchmark_campaign.curation import curate_reviewed_file
from benchmark_campaign.evaluate import evaluate_holdout
from benchmark_campaign.freeze import create_freeze_anchor, freeze_campaign, verify_freeze
from benchmark_campaign.manifests import emit_campaign_manifests
from benchmark_campaign.holdout_seal import generate_holdout_key, sealed_gold_path
from benchmark_campaign.lifecycle import export_tuning_pack, lock_model
from benchmark_campaign.normalization import fingerprint_payload
from benchmark_campaign.source_cache import cache_filename, git_blob_sha, verify_cached_source
from benchmark_campaign.queue_plan import build_curation_queue_plan
from benchmark_campaign.split import build_splits
from benchmark_campaign.validate import validate_campaign


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.project = Path(__file__).resolve().parents[1]
        (self.root / "config").mkdir()
        (self.root / "sources").mkdir()
        (self.root / "schemas").mkdir()
        (self.root / "benchmark_campaign").mkdir()
        for rel in [
            "schemas/benchmark-record.schema.json",
            "schemas/source-registry.schema.json",
            "benchmark_campaign/__init__.py",
            "benchmark_campaign/__main__.py",
            "benchmark_campaign/cli.py",
            "benchmark_campaign/validate.py",
            "benchmark_campaign/split.py",
            "benchmark_campaign/evaluate.py",
            "benchmark_campaign/audit.py",
            "benchmark_campaign/freeze.py",
            "benchmark_campaign/lifecycle.py",
            "benchmark_campaign/core.py",
            "benchmark_campaign/normalization.py",
            "benchmark_campaign/source_registry.py",
            "benchmark_campaign/holdout_seal.py",
            "benchmark_campaign/queue_plan.py",
            "benchmark_campaign/curation.py",
            "benchmark_campaign/manifests.py",
            "benchmark_campaign/source_cache.py",
        ]:
            dst = self.root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.project / rel, dst)
        shutil.copy2(self.project / "requirements.txt", self.root / "requirements.txt")

        self.spec = {
            "campaign_id": "H3.9.2-test",
            "qualification": {
                "synthetic_eligible": False,
                "allowed_gold_status": ["reference_pilot", "expert_gold"],
                "require_source_disjoint_holdout": True,
                "require_family_disjoint_holdout": True,
                "require_cross_split_fingerprint_disjointness": True,
                "require_frozen_holdout": True,
            },
            "benchmarks": [{
                "id": "b1", "target_total": 4,
                "target_development": 2, "target_validation": 1, "target_holdout": 1,
                "min_unique_sources": 3, "min_holdout_sources": 1,
                "min_unique_families": 3, "min_holdout_families": 1,
                "evaluation": {
                    "task_type": "classification",
                    "labels": ["yes", "no"],
                    "thresholds": {"accuracy": {"min": 1.0}, "macro_f1": {"min": 0.5}},
                },
            }],
        }
        self.spec_path = self.root / "config" / "benchmark-spec.json"
        write_json(self.spec_path, self.spec)
        (self.root / "benchmarks" / "b1").mkdir(parents=True)
        sources = []
        for sid in ["s-dev", "s-val", "s-ho", "s-extra"]:
            sources.append({
                "source_id": sid,
                "work_id": sid,
                "qualification_eligible": True,
                "provider": "test",
                "source_repo": "test/repo",
                "source_path": f"{sid}.txt",
                "source_blob_sha": (sid.encode().hex() + "0" * 40)[:40],
                "version_id": "v1",
                "repo_ref": "a" * 40,
            })
        write_json(self.root / "sources" / "source-registry.json", {"schema_version": 2, "sources": sources})

    def tearDown(self):
        self.tmp.cleanup()

    def rec(self, cid, split, sources, fam, label="yes", synthetic=False, gold="reference_pilot"):
        if isinstance(sources, str):
            sources = [sources]
        payload = {"input": {"text": cid}, "gold": {"label": label}}
        registry = {s["source_id"]: s for s in load_json(self.root / "sources" / "source-registry.json")["sources"]}
        refs = []
        for sid in sources:
            excerpt = f"excerpt:{cid}:{sid}"
            refs.append({
                "source_id": sid,
                "locator": f"loc:{cid}:{sid}",
                "source_blob_sha": registry[sid]["source_blob_sha"],
                "excerpt": excerpt,
                "excerpt_sha256": hashlib.sha256(excerpt.encode()).hexdigest(),
            })
        return {
            "benchmark_id": "b1", "case_id": cid, "split": split,
            "source_ids": list(sources), "anchor_source_id": sources[0], "family_id": fam,
            "content_fingerprint": fingerprint_payload(payload), "gold_status": gold,
            "synthetic": synthetic, "source_refs": refs,
            "annotation": {"reviewers": ["r1"], "source_verified": True, "adjudicated": False, "adjudicator": None},
            "payload": payload,
        }

    def write_good(self):
        rows = [
            self.rec("d1", "development", "s-dev", "f-dev"),
            self.rec("d2", "development", "s-dev", "f-dev"),
            self.rec("v1", "validation", "s-val", "f-val"),
            self.rec("h1", "holdout", "s-ho", "f-ho"),
        ]
        dump_jsonl(self.root / "benchmarks" / "b1" / "records.jsonl", rows)

    def _freeze(self):
        p = self.root / "artifacts" / "FREEZE_MANIFEST.json"
        freeze_campaign(self.root, self.spec_path, p)
        (self.root / ".gitignore").write_text("private/\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "init"], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["git", "-C", str(self.root), "config", "user.email", "tests@aimubin.invalid"], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.name", "Mubin Tests"], check=True)
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-m", "freeze fixture"], check=True, stdout=subprocess.DEVNULL)
        source_commit = subprocess.check_output(
            ["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True
        ).strip()
        create_freeze_anchor(p, self.root / "private" / "FREEZE_ANCHOR.json", source_commit)
        return p

    def _perfect_predictions(self, path: Path, label="yes"):
        path.mkdir(parents=True, exist_ok=True)
        dump_jsonl(path / "b1.jsonl", [{"case_id": "h1", "prediction": {"label": label}}])

    def _lock_model(self, manifest_path: Path):
        model_cfg = self.root / "model-config.json"
        generation_cfg = self.root / "generation-config.json"
        model_artifact = self.root / "model.bin"
        write_json(model_cfg, {"model": "test"})
        write_json(generation_cfg, {"temperature": 0})
        model_artifact.write_bytes(b"immutable-test-model")
        system_commit = subprocess.check_output(
            ["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True
        ).strip()
        return lock_model(
            self.root, manifest_path, "test-model@locked", model_cfg,
            system_commit=system_commit,
            model_artifact_path=model_artifact,
            generation_config_path=generation_cfg,
        )

    def _architecture_audit(self):
        evidence = self.root / "architecture-evidence.json"
        write_json(evidence, {"check": "passed"})
        arch = self.root / "architecture.json"
        write_json(arch, {
            "schema_version": 1,
            "audit_kind": "architecture_qualification",
            "audit_id": "test-architecture-audit",
            "candidate_commit": subprocess.check_output(
                ["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True
            ).strip(),
            "frozen": True,
            "architecture_gate_passed": True,
            "evidence": [{"path": str(evidence.relative_to(self.root)), "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest()}],
        })
        return arch

    def _enable_sealed_holdout(self):
        self.spec["qualification"]["require_sealed_holdout_gold"] = True
        write_json(self.spec_path, self.spec)
        key_path = self.root / "private" / "holdout.key"
        generate_holdout_key(key_path)
        return key_path

    def _build_sealed_good(self):
        key_path = self._enable_sealed_holdout()
        staging = self.root / "staging" / "b1"
        staging.mkdir(parents=True)
        rows = [
            self.rec("d1", "development", "s-dev", "f-dev"),
            self.rec("d2", "development", "s-extra", "f-extra"),
            self.rec("v1", "validation", "s-val", "f-val"),
            self.rec("h1", "holdout", "s-ho", "f-ho"),
        ]
        for r in rows:
            r.pop("split", None)
        dump_jsonl(staging / "reviewed.jsonl", rows)
        write_json(self.root / "config" / "curation-plan.json", {
            "global_source_partition": {"holdout": ["s-ho"], "non_holdout": ["s-dev", "s-val", "s-extra"]},
            "benchmarks": {"b1": {
                "holdout_source_pool": ["s-ho"],
                "non_holdout_source_pool": ["s-dev", "s-val", "s-extra"],
                "target_holdout": 1, "target_non_holdout": 3,
            }},
        })
        report = build_splits(self.root, self.spec, self.root / "staging", key_path)
        self.assertTrue(report["all_feasible"])
        return key_path

    def test_good_campaign_qualifies_and_freezes(self):
        self.write_good()
        report = validate_campaign(self.root, self.spec)
        self.assertTrue(report["all_benchmarks_qualified"])
        manifest_path = self._freeze()
        self.assertTrue(verify_freeze(self.root, manifest_path)["verified"])

    def test_any_source_in_multisource_holdout_causes_overlap(self):
        self.write_good()
        p = self.root / "benchmarks" / "b1" / "records.jsonl"
        rows = [json.loads(x) for x in p.read_text().splitlines()]
        rows[-1] = self.rec("h1", "holdout", ["s-ho", "s-dev"], "f-ho")
        dump_jsonl(p, rows)
        report = validate_campaign(self.root, self.spec)
        codes = {v["code"] for v in report["benchmarks"][0]["violations"]}
        self.assertIn("leakage.source_overlap", codes)

    def test_family_overlap_fails(self):
        self.write_good()
        p = self.root / "benchmarks" / "b1" / "records.jsonl"
        rows = [json.loads(x) for x in p.read_text().splitlines()]
        rows[-1]["family_id"] = "f-dev"
        dump_jsonl(p, rows)
        codes = {v["code"] for v in validate_campaign(self.root, self.spec)["benchmarks"][0]["violations"]}
        self.assertIn("leakage.family_overlap", codes)

    def test_fingerprint_overlap_fails(self):
        self.write_good()
        p = self.root / "benchmarks" / "b1" / "records.jsonl"
        rows = [json.loads(x) for x in p.read_text().splitlines()]
        rows[-1]["payload"]["input"] = rows[0]["payload"]["input"]
        rows[-1]["content_fingerprint"] = rows[0]["content_fingerprint"]
        dump_jsonl(p, rows)
        codes = {v["code"] for v in validate_campaign(self.root, self.spec)["benchmarks"][0]["violations"]}
        self.assertIn("leakage.fingerprint_overlap", codes)

    def test_excerpt_hash_is_recomputed(self):
        self.write_good()
        p = self.root / "benchmarks" / "b1" / "records.jsonl"
        rows = [json.loads(x) for x in p.read_text().splitlines()]
        rows[0]["source_refs"][0]["excerpt"] += " tampered"
        dump_jsonl(p, rows)
        codes = {v["code"] for v in validate_campaign(self.root, self.spec)["benchmarks"][0]["violations"]}
        self.assertIn("provenance.excerpt_hash_mismatch", codes)

    def test_source_refs_must_cover_all_source_ids(self):
        self.write_good()
        p = self.root / "benchmarks" / "b1" / "records.jsonl"
        rows = [json.loads(x) for x in p.read_text().splitlines()]
        rows[-1]["source_ids"].append("s-extra")
        dump_jsonl(p, rows)
        codes = {v["code"] for v in validate_campaign(self.root, self.spec)["benchmarks"][0]["violations"]}
        self.assertIn("provenance.source_ref_set", codes)

    def test_synthetic_cannot_qualify(self):
        self.write_good()
        p = self.root / "benchmarks" / "b1" / "records.jsonl"
        rows = [json.loads(x) for x in p.read_text().splitlines()]
        rows[0]["synthetic"] = True
        rows[0]["gold_status"] = "synthetic"
        dump_jsonl(p, rows)
        self.assertFalse(validate_campaign(self.root, self.spec)["all_benchmarks_qualified"])

    def test_tamper_after_freeze_fails_verification(self):
        self.write_good()
        manifest_path = self._freeze()
        with (self.root / "benchmarks" / "b1" / "records.jsonl").open("a") as f:
            f.write("\n")
        self.assertFalse(verify_freeze(self.root, manifest_path)["verified"])

    def test_manifest_tamper_after_freeze_fails_even_if_frozen_files_are_unchanged(self):
        self.write_good()
        manifest_path = self._freeze()
        manifest = load_json(manifest_path)
        manifest["freeze_id"] = "f" * 64
        write_json(manifest_path, manifest)
        result = verify_freeze(self.root, manifest_path)
        self.assertFalse(result["verified"])
        reasons = {x["reason"] for x in result["mismatches"]}
        self.assertTrue("freeze_id_mismatch" in reasons or "anchor_manifest_hash_mismatch" in reasons)

    def test_freeze_verification_requires_detached_anchor(self):
        self.write_good()
        manifest_path = self._freeze()
        (self.root / "private" / "FREEZE_ANCHOR.json").unlink()
        result = verify_freeze(self.root, manifest_path)
        self.assertFalse(result["verified"])
        self.assertIn("detached_anchor_missing", {x["reason"] for x in result["mismatches"]})

    def test_manifests_are_emitted_with_source_sets(self):
        self.write_good()
        paths = emit_campaign_manifests(self.root, self.spec, self.root / "artifacts")
        holdout = load_json(paths["holdout"])
        self.assertEqual(holdout["benchmarks"][0]["records"][0]["source_ids"], ["s-ho"])

    def test_freeze_refuses_if_tuning_marker_exists(self):
        self.write_good()
        write_json(self.root / "artifacts" / "TUNING_STARTED.json", {"started": True})
        with self.assertRaises(ValueError):
            self._freeze()

    def test_freeze_cannot_be_overwritten(self):
        self.write_good()
        manifest_path = self._freeze()
        with self.assertRaises(FileExistsError):
            freeze_campaign(self.root, self.spec_path, manifest_path)

    def test_audit_requires_real_evaluator_access_marker(self):
        self.write_good()
        manifest_path = self._freeze()
        arch = self.root / "architecture.json"
        write_json(arch, {"architecture_gate_passed": True})
        forged = self.root / "artifacts" / "HOLDOUT_EVALUATION.json"
        write_json(forged, {"freeze_id": load_json(manifest_path)["freeze_id"], "all_benchmarks_passed": True, "prediction_hashes": {}})
        audit = build_pre_m4_audit(self.root, self.spec_path, manifest_path, arch, forged)
        self.assertFalse(audit["benchmark_gate_passed"])

    def test_m4_gate_requires_passing_frozen_holdout_evaluation(self):
        key_path = self._build_sealed_good()
        manifest_path = self._freeze()
        self._lock_model(manifest_path)
        preds = self.root / "predictions"
        self._perfect_predictions(preds)
        evaluation = self.root / "artifacts" / "HOLDOUT_EVALUATION.json"
        report = evaluate_holdout(self.root, self.spec_path, manifest_path, preds, evaluation, holdout_key_path=key_path)
        self.assertTrue(report["all_benchmarks_passed"])
        arch = self._architecture_audit()
        audit = build_pre_m4_audit(self.root, self.spec_path, manifest_path, arch, evaluation, key_path)
        self.assertTrue(audit["benchmark_gate_passed"])
        self.assertTrue(audit["architecture_gate_passed"])
        self.assertTrue(audit["h4_development_allowed"])
        self.assertTrue(audit["h4_qualification_allowed"])
        self.assertFalse(audit["h4_release_allowed"])

    def test_holdout_is_one_shot_except_identical_replay(self):
        key_path = self._build_sealed_good()
        manifest_path = self._freeze()
        self._lock_model(manifest_path)
        preds = self.root / "predictions"
        self._perfect_predictions(preds)
        evaluation = self.root / "artifacts" / "HOLDOUT_EVALUATION.json"
        evaluate_holdout(self.root, self.spec_path, manifest_path, preds, evaluation, holdout_key_path=key_path)
        evaluate_holdout(self.root, self.spec_path, manifest_path, preds, evaluation, holdout_key_path=key_path)
        self._perfect_predictions(preds, label="no")
        with self.assertRaises(RuntimeError):
            evaluate_holdout(self.root, self.spec_path, manifest_path, preds, evaluation, holdout_key_path=key_path)

    def test_split_components_include_every_source_id(self):
        staging = self.root / "staging" / "b1"
        staging.mkdir(parents=True)
        rows = [
            self.rec("a", "development", ["s-dev", "s-extra"], "fa"),
            self.rec("b", "development", "s-extra", "fb"),
            self.rec("c", "development", "s-val", "fc"),
            self.rec("d", "development", "s-ho", "fd"),
        ]
        for r in rows:
            r.pop("split", None)
        dump_jsonl(staging / "reviewed.jsonl", rows)
        report = build_splits(self.root, self.spec, self.root / "staging")
        self.assertTrue(report["all_feasible"])
        self.assertEqual(report["benchmarks"][0]["component_count"], 3)

    def test_curation_seals_hashes_and_requires_verbatim_excerpt(self):
        cache = self.root / "source-cache"
        cache.mkdir()
        text = "prefix EXACT EXCERPT suffix"
        cache_path = cache / cache_filename("s-dev")
        cache_path.write_text(text, encoding="utf-8")
        registry_path = self.root / "sources" / "source-registry.json"
        registry = load_json(registry_path)
        for src in registry["sources"]:
            if src["source_id"] == "s-dev":
                src["source_blob_sha"] = git_blob_sha(cache_path.read_bytes())
        write_json(registry_path, registry)
        inp = self.root / "candidate.jsonl"
        row = {
            "case_id": "c1", "family_id": "f1", "gold_status": "reference_pilot", "synthetic": False,
            "source_refs": [{"source_id": "s-dev", "locator": "loc:1", "excerpt": "EXACT EXCERPT"}],
            "annotation": {"reviewers": ["r1"], "source_verified": True, "adjudicated": False, "adjudicator": None},
            "payload": {"input": {"x": 1}, "gold": {"label": "yes"}},
        }
        dump_jsonl(inp, [row])
        out = self.root / "staging" / "b1" / "reviewed.jsonl"
        curate_reviewed_file(self.root, "b1", inp, out, cache)
        sealed = json.loads(out.read_text())
        self.assertEqual(sealed["source_ids"], ["s-dev"])
        self.assertEqual(sealed["content_fingerprint"], fingerprint_payload(row["payload"]))
        self.assertEqual(sealed["source_refs"][0]["excerpt_sha256"], hashlib.sha256(b"EXACT EXCERPT").hexdigest())
        row["source_refs"][0]["excerpt"] = "NOT IN SOURCE"
        dump_jsonl(inp, [row])
        with self.assertRaises(ValueError):
            curate_reviewed_file(self.root, "b1", inp, out, cache)

    def test_git_blob_verification(self):
        p = self.root / "source-cache-test"
        data = b"abc\n"
        p.write_bytes(data)
        source = {"source_id": "s", "source_blob_sha": git_blob_sha(data)}
        self.assertTrue(verify_cached_source(p, source)["verified"])

    def test_campaign_global_source_disjointness(self):
        self.write_good()
        b2 = {
            "id": "b2", "target_total": 1,
            "target_development": 0, "target_validation": 0, "target_holdout": 1,
            "min_unique_sources": 1, "min_holdout_sources": 1,
            "min_unique_families": 1, "min_holdout_families": 1,
            "evaluation": {"task_type": "classification", "labels": ["yes", "no"], "thresholds": {"accuracy": {"min": 1.0}}},
        }
        spec = json.loads(json.dumps(self.spec))
        spec["benchmarks"].append(b2)
        (self.root / "benchmarks" / "b2").mkdir()
        r = self.rec("h2", "holdout", "s-dev", "f-b2")
        r["benchmark_id"] = "b2"
        dump_jsonl(self.root / "benchmarks" / "b2" / "records.jsonl", [r])
        report = validate_campaign(self.root, spec)
        codes = {v["code"] for v in report["global_violations"]}
        self.assertIn("leakage.global_source_overlap", codes)

    def test_frozen_curation_plan_rejects_cross_partition_component(self):
        staging = self.root / "staging" / "b1"
        staging.mkdir(parents=True)
        rows = [
            self.rec("a", "development", ["s-ho", "s-dev"], "fa"),
            self.rec("b", "development", "s-dev", "fb"),
            self.rec("c", "development", "s-val", "fc"),
            self.rec("d", "development", "s-extra", "fd"),
        ]
        for r in rows:
            r.pop("split", None)
        dump_jsonl(staging / "reviewed.jsonl", rows)
        write_json(self.root / "config" / "curation-plan.json", {
            "global_source_partition": {"holdout": ["s-ho"], "non_holdout": ["s-dev", "s-val", "s-extra"]},
            "benchmarks": {"b1": {
                "holdout_source_pool": ["s-ho"],
                "non_holdout_source_pool": ["s-dev", "s-val", "s-extra"],
                "target_holdout": 1, "target_non_holdout": 3,
            }},
        })
        report = build_splits(self.root, self.spec, self.root / "staging")
        self.assertFalse(report["all_feasible"])
        self.assertIn("bridges frozen source partitions", report["benchmarks"][0]["reason"])

    def test_sealed_holdout_removes_plaintext_gold_and_qualifies(self):
        key_path = self._build_sealed_good()
        rows = [json.loads(x) for x in (self.root / "benchmarks" / "b1" / "records.jsonl").read_text().splitlines()]
        holdout = [r for r in rows if r["split"] == "holdout"]
        self.assertEqual(len(holdout), 1)
        self.assertNotIn("gold", holdout[0]["payload"])
        self.assertTrue(holdout[0]["payload"]["gold_sealed"])
        self.assertTrue(sealed_gold_path(self.root, "b1").exists())
        self.assertNotIn('"label": "yes"', sealed_gold_path(self.root, "b1").read_text())
        staging_text = (self.root / "staging" / "b1" / "reviewed.jsonl").read_text()
        staging_h = [json.loads(x) for x in staging_text.splitlines() if json.loads(x)["case_id"] == "h1"][0]
        self.assertNotIn("gold", staging_h["payload"])
        rerun = build_splits(self.root, self.spec, self.root / "staging", key_path)
        self.assertTrue(rerun["all_feasible"])
        report = validate_campaign(self.root, self.spec)
        self.assertTrue(report["all_benchmarks_qualified"], report)
        self.assertTrue(key_path.exists())

    def test_sealed_holdout_evaluation_requires_key_and_unlocks_only_after_model_lock(self):
        key_path = self._build_sealed_good()
        manifest_path = self._freeze()
        self._lock_model(manifest_path)
        preds = self.root / "predictions"
        self._perfect_predictions(preds)
        evaluation = self.root / "artifacts" / "HOLDOUT_EVALUATION.json"
        with self.assertRaises(ValueError):
            evaluate_holdout(self.root, self.spec_path, manifest_path, preds, evaluation)
        report = evaluate_holdout(self.root, self.spec_path, manifest_path, preds, evaluation, holdout_key_path=key_path)
        self.assertTrue(report["all_benchmarks_passed"])
        self.assertEqual(report["sealed_holdout"]["key_id"], load_json(self.root / "artifacts" / "HOLDOUT_ACCESSED.json")["holdout_key_id"])

    def test_wrong_holdout_key_cannot_decrypt(self):
        key_path = self._build_sealed_good()
        manifest_path = self._freeze()
        self._lock_model(manifest_path)
        preds = self.root / "predictions"
        self._perfect_predictions(preds)
        wrong = self.root / "private" / "wrong.key"
        generate_holdout_key(wrong)
        with self.assertRaises(ValueError):
            evaluate_holdout(self.root, self.spec_path, manifest_path, preds, self.root / "artifacts" / "eval.json", holdout_key_path=wrong)
        self.assertTrue(key_path.exists())

    def test_sealed_holdout_ciphertext_tamper_breaks_freeze(self):
        self._build_sealed_good()
        manifest_path = self._freeze()
        p = sealed_gold_path(self.root, "b1")
        p.write_text(p.read_text() + "\n", encoding="utf-8")
        self.assertFalse(verify_freeze(self.root, manifest_path)["verified"])

    def test_tuning_pack_never_contains_holdout_case_or_sealed_gold(self):
        self._build_sealed_good()
        manifest_path = self._freeze()
        out = self.root / "tuning"
        export_tuning_pack(self.root, self.spec, out, manifest_path)
        text = (out / "b1.jsonl").read_text()
        self.assertNotIn('"case_id": "h1"', text)
        self.assertNotIn("gold_sealed", text)
        self.assertFalse(any("sealed-holdout" in str(p) for p in out.rglob("*")))

    def test_plaintext_holdout_gold_is_rejected_when_sealing_required(self):
        self._enable_sealed_holdout()
        self.write_good()
        report = validate_campaign(self.root, self.spec)
        codes = {v["code"] for v in report["benchmarks"][0]["violations"]}
        self.assertIn("holdout.gold_exposed", codes)
        self.assertIn("holdout.seal_binding", codes)

    def test_curation_queue_quotas_are_exact_and_partition_bounded(self):
        write_json(self.root / "config" / "curation-plan.json", {
            "campaign_id": "H3.9.2-test",
            "global_source_partition": {"holdout": ["s-ho"], "non_holdout": ["s-dev", "s-val", "s-extra"]},
            "benchmarks": {"b1": {
                "holdout_source_pool": ["s-ho"],
                "non_holdout_source_pool": ["s-dev", "s-val", "s-extra"],
                "target_holdout": 1, "target_non_holdout": 3,
            }},
        })
        q = build_curation_queue_plan(self.root, self.spec)
        b = q["benchmarks"][0]
        self.assertEqual(sum(x["target_cases"] for x in b["holdout"]["anchor_quotas"]), 1)
        self.assertEqual(sum(x["target_cases"] for x in b["non_holdout"]["anchor_quotas"]), 3)
        self.assertEqual({x["anchor_source_id"] for x in b["holdout"]["anchor_quotas"]}, {"s-ho"})

    def test_actual_records_must_match_frozen_anchor_quotas(self):
        self.write_good()
        self.spec["qualification"]["require_frozen_curation_quotas"] = True
        write_json(self.spec_path, self.spec)
        write_json(self.root / "config" / "curation-plan.json", {
            "campaign_id": "H3.9.2-test",
            "global_source_partition": {"holdout": ["s-ho"], "non_holdout": ["s-dev", "s-val", "s-extra"]},
            "benchmarks": {"b1": {
                "holdout_source_pool": ["s-ho"],
                "non_holdout_source_pool": ["s-dev", "s-val", "s-extra"],
                "target_holdout": 1, "target_non_holdout": 3,
            }},
        })
        quotas = build_curation_queue_plan(self.root, self.spec)
        write_json(self.root / "config" / "curation-quotas.json", quotas)
        report = validate_campaign(self.root, self.spec)
        codes = {v["code"] for v in report["campaign_violations"]}
        self.assertIn("curation_quotas.non_holdout_counts", codes)
        self.assertFalse(report["all_benchmarks_qualified"])

    def test_model_lock_rejects_nonexistent_system_commit(self):
        self.write_good()
        manifest_path = self._freeze()
        model_cfg = self.root / "model-config.json"
        generation_cfg = self.root / "generation-config.json"
        model_artifact = self.root / "model.bin"
        write_json(model_cfg, {"model": "test"})
        write_json(generation_cfg, {"temperature": 0})
        model_artifact.write_bytes(b"model")
        with self.assertRaisesRegex(ValueError, "system_commit"):
            lock_model(
                self.root, manifest_path, "test-model", model_cfg,
                system_commit="0" * 40,
                model_artifact_path=model_artifact,
                generation_config_path=generation_cfg,
            )

    def test_frozen_curation_quota_mismatch_fails_campaign_validation(self):
        self.write_good()
        self.spec["qualification"]["require_frozen_curation_quotas"] = True
        write_json(self.spec_path, self.spec)
        write_json(self.root / "config" / "curation-plan.json", {
            "campaign_id": "H3.9.2-test",
            "global_source_partition": {"holdout": ["s-ho"], "non_holdout": ["s-dev", "s-val", "s-extra"]},
            "benchmarks": {"b1": {
                "holdout_source_pool": ["s-ho"],
                "non_holdout_source_pool": ["s-dev", "s-val", "s-extra"],
                "target_holdout": 1, "target_non_holdout": 3,
            }},
        })
        q = build_curation_queue_plan(self.root, self.spec)
        q["benchmarks"][0]["holdout"]["anchor_quotas"][0]["target_cases"] = 2
        write_json(self.root / "config" / "curation-quotas.json", q)
        report = validate_campaign(self.root, self.spec)
        codes = {v["code"] for v in report["campaign_violations"]}
        self.assertIn("curation_quotas.mismatch", codes)


if __name__ == "__main__":
    unittest.main()
