"""Verify SHA-256 evidence packages without modifying private package bytes.

Supports ZIP members written with Windows backslash or POSIX slash separators.
The manifest (sha256-manifest.json) is excluded from its own file listing.
Fail closed on incorrect digests/sizes, duplicate normalized paths and unsafe
members. The validator does not extract or publish any evidence images.
"""
import argparse
import hashlib
import json
from pathlib import PurePosixPath
import zipfile


class EvidencePackageError(ValueError):
    pass


def normalize_member(name):
    candidate = name.replace("\\", "/")
    parts = candidate.split("/")
    if (not candidate or candidate.startswith("/") or any(
        part in ("", ".", "..") for part in parts
    ) or ":" in parts[0]):
        raise EvidencePackageError(f"Unsafe ZIP member path: {name!r}")
    return str(PurePosixPath(candidate))


def verify_package(path, manifest_name="sha256-manifest.json"):
    errors = []
    members = {}
    with zipfile.ZipFile(path) as archive:
        for item in archive.infolist():
            if item.is_dir():
                continue
            logical = normalize_member(item.filename)
            if logical in members:
                raise EvidencePackageError(f"Duplicate normalized member: {logical}")
            members[logical] = item
        if manifest_name not in members:
            raise EvidencePackageError("Missing package manifest")
        manifest = json.loads(archive.read(members[manifest_name]).decode("utf-8"))
        listed = {}
        for entry in manifest["files"]:
            name = normalize_member(entry["path"])
            if name == manifest_name:
                raise EvidencePackageError("Manifest cannot list its own digest")
            if name in listed:
                raise EvidencePackageError(f"Duplicate manifest entry: {name}")
            listed[name] = entry
        expected = set(members) - {manifest_name}
        missing = sorted(set(listed) - expected)
        unlisted = sorted(expected - set(listed))
        errors.extend(f"MISSING:{name}" for name in missing)
        errors.extend(f"UNLISTED:{name}" for name in unlisted)
        checked = 0
        for name in sorted(expected & set(listed)):
            data = archive.read(members[name])
            actual_hash = hashlib.sha256(data).hexdigest()
            actual_size = len(data)
            entry = listed[name]
            checked += 1
            if actual_hash.lower() != str(entry["sha256"]).lower():
                errors.append(f"HASH_MISMATCH:{name}")
            if actual_size != entry["bytes"]:
                errors.append(f"SIZE_MISMATCH:{name}:expected={entry['bytes']}:actual={actual_size}")
        return {
            "status": "PASS" if not errors else "FAIL",
            "package_sha256": _file_sha256(path),
            "zip_file_count": len(members),
            "manifest_listed_files": len(listed),
            "verified_member_count": checked,
            "errors": errors,
            "note": "PASS covers only ZIP content and manifest checksums, not the provenance of unbundled source PDFs or scholarly content.",
        }


def _file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for data in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(data)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package")
    parser.add_argument("--report")
    args = parser.parse_args()
    result = verify_package(args.package)
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        from pathlib import Path
        dst = Path(args.report)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(serialized, encoding="utf-8")
    print(serialized)
    raise SystemExit(0 if result["status"] == "PASS" else 2)


if __name__ == "__main__":
    main()
