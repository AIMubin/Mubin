"""Offline-first Mubin corpus snapshots backed by verified GitHub Actions artifacts.

GitHub stores code/provenance; a local vault stores data bytes. This tool does not
publish texts or claim religious authenticity. Python 3.11+, standard library.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import urllib.request
import subprocess

from corpus.import_tafsircenter import PIN
from corpus.audit_linked import audit

REPO = "AIMubin/Mubin"
SOURCE_URL = "https://huggingface.co/datasets/tafsircenter/tafsir-mcp-data/resolve/main/quran.db"
REQUIRED = {
    "quran_tafsir.db": "linked/quran_tafsir.db",
    "import-manifest.json": "reports/import-manifest.json",
    "audit-report.json": "reports/audit-report.json",
}
OPTIONAL = {
    "tafsir-quality.json": "reports/tafsir-quality.json",
    "derived-quran-quality.json": "reports/derived-quran-quality.json",
    "quran-comparison-summary.json": "reports/quran-comparison-summary.json",
    "quran-triage.json": "reports/quran-triage.json",
    "tanzil-manifest.json": "reports/tanzil-manifest.json",
    "tanzil-uthmani.txt": "reference/tanzil-uthmani.txt",
}


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def locate(incoming, name, required=False):
    matches = [p for p in incoming.rglob(name) if p.is_file() and not p.is_symlink()]
    if len(matches) > 1 and len({digest(p) for p in matches}) > 1:
        raise ValueError(f"Conflicting copies of {name} in artifacts")
    if required and not matches:
        raise FileNotFoundError(f"Missing required artifact file: {name}")
    return matches[0] if matches else None


def verify_database(path, import_manifest, audit_report):
    sha = digest(path)
    if sha != import_manifest.get("output_sha256") or sha != audit_report.get("sha256"):
        raise ValueError("Derived SQLite checksum mismatch against import/audit reports")
    if import_manifest.get("source_sha256") != PIN:
        raise ValueError("Unexpected upstream source release hash")
    verified = audit(path)
    if not verified["structural_audit_passed"]:
        raise ValueError(f"SQLite structural audit failed: {verified['issues']}")
    if import_manifest.get("verses") != 6236 or not audit_report.get("structural_audit_passed"):
        raise ValueError("Upstream import report did not pass basic coverage")
    for name in ("tabary", "katheer", "baghawy", "saadi", "moyassar"):
        entry = import_manifest.get("tafsirs", {}).get(name, {})
        if entry.get("nonempty") != 6236 or verified["tafsir_counts"].get(name) != 6236:
            raise ValueError(f"Tafsir coverage mismatch: {name}")
    return sha


def fetch_original(destination):
    """Download pinned upstream original. Never trust an unverified response."""
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "Mubin-local-vault/0.1"})
        with urllib.request.urlopen(req, timeout=120) as source, destination.open("xb") as target:
            size = 0
            while data := source.read(1024 * 1024):
                size += len(data)
                if size > 500_000_000:
                    raise ValueError("Upstream file exceeds safety size limit")
                target.write(data)
        if digest(destination) != PIN:
            raise ValueError("Upstream original does not match PIN")
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return destination


def capture(incoming, root, run_id, source_db=None, allow_missing_source=False):
    incoming, root = Path(incoming).resolve(), Path(root).resolve()
    if not incoming.is_dir() or not re.fullmatch(r"[0-9]{1,20}", str(run_id)):
        raise ValueError("Incoming folder or numeric GitHub run ID invalid")
    snapshots = root / "snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    destination = snapshots / f"run-{run_id}"
    if destination.exists():
        raise FileExistsError(f"Immutable snapshot already exists: {destination}")
    if incoming == root or incoming.is_relative_to(root) or root.is_relative_to(incoming):
        raise ValueError("Incoming folder and vault root must not contain each other")
    required = {name: locate(incoming, name, True) for name in REQUIRED}
    optional = {name: locate(incoming, name) for name in OPTIONAL}
    imported = read_json(required["import-manifest.json"])
    checked = read_json(required["audit-report.json"])
    verify_database(required["quran_tafsir.db"], imported, checked)
    if source_db is None and not allow_missing_source:
        raise ValueError("Full backup requires pinned original source DB. Supply --source-db or --fetch-source; use --allow-missing-source for partial recovery only")
    if source_db is not None:
        source_db = Path(source_db).resolve()
        if digest(source_db) != PIN:
            raise ValueError("Original source database fails pinned SHA-256")
    tmp = Path(tempfile.mkdtemp(prefix=".incomplete-", dir=snapshots))
    try:
        copied = {}
        all_files = [(n, p, REQUIRED[n]) for n, p in required.items()]
        all_files += [(n, p, OPTIONAL[n]) for n, p in optional.items() if p is not None]
        if source_db is not None:
            all_files.append(("upstream-quran.db", source_db, "originals/tafsircenter-quran.db"))
        malformed_reports = []
        for name, original, relative in all_files:
            dest = tmp / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, dest)
            copied[relative] = {"sha256": digest(dest), "size_bytes": dest.stat().st_size}
            if relative.endswith(".json"):
                try:
                    read_json(dest)
                except (ValueError, UnicodeError):
                    malformed_reports.append(relative)
        reference = tmp / "reference/tanzil-uthmani.txt"
        ref_manifest = tmp / "reports/tanzil-manifest.json"
        if reference.exists():
            if not ref_manifest.exists() or digest(reference) != read_json(ref_manifest).get("sha256"):
                raise ValueError("Reference witness hash and source manifest disagree")
        record = {
            "schema_version": "0.1.0", "project": "Mubin", "run_id": str(run_id),
            "source_workflow": "AIMubin/Mubin/.github/workflows/import-quran-tafsir.yml",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "files": copied,
            "has_pinned_original": source_db is not None,
            "has_reference_witness": reference.exists(),
            "malformed_source_reports_preserved": malformed_reports,
            "backup_status": "FULL_ORIGINAL_PRESERVED" if source_db else "PARTIAL_NO_UPSTREAM_ORIGINAL",
            "canonical_quran_verified": False,
            "scholarly_verified": False,
            "redistribution_approved": False,
        }
        (tmp / "snapshot.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.rename(tmp, destination)
        return destination
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def verify_snapshot(snapshot):
    snapshot = Path(snapshot).resolve()
    record = read_json(snapshot / "snapshot.json")
    if record.get("schema_version") != "0.1.0":
        raise ValueError("Unknown snapshot format")
    files = record.get("files", {})
    for relative, description in files.items():
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Unsafe file path in snapshot")
        file = snapshot / path
        if not file.is_file() or file.is_symlink():
            raise ValueError(f"Missing or unsafe file: {relative}")
        if file.stat().st_size != description["size_bytes"] or digest(file) != description["sha256"]:
            raise ValueError(f"Corrupt snapshot file: {relative}")
    if record["has_pinned_original"]:
        if digest(snapshot / "originals/tafsircenter-quran.db") != PIN:
            raise ValueError("Pinned upstream original mismatch")
    verify_database(snapshot / "linked/quran_tafsir.db", read_json(snapshot / "reports/import-manifest.json"),
                    read_json(snapshot / "reports/audit-report.json"))
    return record


def mirror(root, run_id, mirror_root):
    src = Path(root).resolve() / "snapshots" / f"run-{run_id}"
    dst_root = Path(mirror_root).resolve()
    first = Path(root).resolve()
    if dst_root == first or dst_root.is_relative_to(first) or first.is_relative_to(dst_root):
        raise ValueError("Mirror path must be separate from vault root")
    verify_snapshot(src)
    dst = dst_root / "snapshots" / f"run-{run_id}"
    if dst.exists():
        raise FileExistsError(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)
    verify_snapshot(dst)
    return dst


def restore(root, run_id, destination):
    src = Path(root).resolve() / "snapshots" / f"run-{run_id}"
    record = verify_snapshot(src)
    destination = Path(destination).resolve()
    if destination.exists():
        raise FileExistsError("Restore target must not exist: " + str(destination))
    mapping = {
        "linked/quran_tafsir.db": "linked/quran_tafsir.db",
        "originals/tafsircenter-quran.db": "source/tafsircenter-quran.db",
        "reference/tanzil-uthmani.txt": "reference/tanzil-uthmani.txt",
    }
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".mubin-restore-", dir=parent))
    try:
        for relative in record["files"]:
            target = mapping.get(relative, relative)
            dest = staging / target
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src / relative, dest)
        os.rename(staging, destination)
        return destination
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def github_pull(run_id, root, source_db, fetch_source, allow_missing_source):
    if shutil.which("gh") is None:
        raise EnvironmentError("GitHub CLI 'gh' is required; authenticate using 'gh auth login' locally")
    with tempfile.TemporaryDirectory(prefix="mubin-gh-") as t:
        incoming = Path(t) / "artifacts"
        incoming.mkdir()
        subprocess.run(["gh", "run", "download", str(run_id), "--repo", REPO,
                        "--dir", str(incoming)], check=True)
        if fetch_source:
            source_db = fetch_original(Path(t) / "tafsircenter-quran.db")
        return capture(incoming, root, run_id, source_db, allow_missing_source)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest="command", required=True)
    cap = commands.add_parser("capture", help="Archive already downloaded and extracted GitHub artifacts")
    pull = commands.add_parser("pull", help="Download a completed GitHub Actions run then archive it")
    for parser in (cap, pull):
        parser.add_argument("--root", type=Path, required=True)
        parser.add_argument("--run-id", required=True)
        parser.add_argument("--source-db", type=Path)
        parser.add_argument("--allow-missing-source", action="store_true")
    cap.add_argument("--incoming", type=Path, required=True)
    pull.add_argument("--fetch-source", action="store_true", help="Download pinned original from Tafsir Center dataset")
    check = commands.add_parser("verify")
    check.add_argument("--root", type=Path, required=True)
    check.add_argument("--run-id", required=True)
    clone = commands.add_parser("mirror")
    clone.add_argument("--root", type=Path, required=True)
    clone.add_argument("--run-id", required=True)
    clone.add_argument("--mirror-root", type=Path, required=True)
    recover = commands.add_parser("restore")
    recover.add_argument("--root", type=Path, required=True)
    recover.add_argument("--run-id", required=True)
    recover.add_argument("--destination", type=Path, required=True)
    a = p.parse_args()
    if a.command == "capture":
        output = capture(a.incoming, a.root, a.run_id, a.source_db, a.allow_missing_source)
    elif a.command == "pull":
        if a.fetch_source and a.source_db:
            p.error("Choose --fetch-source or --source-db, not both")
        output = github_pull(a.run_id, a.root, a.source_db, a.fetch_source, a.allow_missing_source)
    elif a.command == "verify":
        output = verify_snapshot(a.root / "snapshots" / f"run-{a.run_id}")
    elif a.command == "mirror":
        output = mirror(a.root, a.run_id, a.mirror_root)
    else:
        output = restore(a.root, a.run_id, a.destination)
    print(json.dumps(output if isinstance(output, dict) else {"path": str(output)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
