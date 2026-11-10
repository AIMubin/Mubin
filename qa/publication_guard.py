"""Public Git tracked-file and limited historical redaction safety gate.

This is NOT a legal or secret-scanning certification. Never print a private
text value, local secret or source path as part of diagnostic output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess

WITNESS_PATH = "research/b02b/b02c6-witness-prep-6-145-v1.json"
_PRIVATE_PARTS = frozenset({
    "corpus-data", "operator-vault", "private-vault", "vault-data",
    ".secrets", ".private", "private-sources",
})
_PRIVATE_EXTENSIONS = (
    ".sqlite", ".sqlite3", ".db", ".db-wal", ".db-shm", ".parquet",
    ".pem", ".p12", ".pfx", ".key", ".p8",
)


class PublicationGuardError(ValueError):
    """Machine-readable publication gate refusal, without source bytes."""


def _git(root, *args):
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PublicationGuardError("GIT_INSPECTION_UNAVAILABLE") from exc


def path_violation(path):
    """Inspect tracked path names, not content or legal permission."""
    if type(path) is not str or not path:
        return "TRACKED_PATH_INVALID"
    parts = PurePosixPath(path).parts
    lowered = [part.lower() for part in parts]
    if any(part in _PRIVATE_PARTS for part in lowered):
        return "PRIVATE_STORAGE_TRACKED"
    name = lowered[-1]
    if name == ".env" or (name.startswith(".env.") and
                          name not in (".env.example", ".env.sample")):
        return "ENVIRONMENT_CREDENTIALS_TRACKED"
    if name.startswith(("id_rsa", "id_ed25519")):
        return "PRIVATE_KEY_TRACKED"
    if name in ("credentials.json", "service-account.json",
                "accounts.json", "secrets.json", "token.json"):
        return "CREDENTIAL_CONTAINER_TRACKED"
    if name.endswith(_PRIVATE_EXTENSIONS):
        return "SOURCE_OR_KEY_BINARY_TRACKED"
    return None


def _path_id(path):
    # A stable reference for local remediation, never a displayed private path.
    return hashlib.sha256(path.encode("utf-8", "surrogateescape")).hexdigest()[:12]


def tracked_paths(root):
    raw = _git(root, "ls-files", "-z", "--cached")
    return [part.decode("utf-8", "surrogateescape")
            for part in raw.split(b"\0") if part]


def scan_tip(root):
    paths = tracked_paths(root)
    findings = []
    for path in paths:
        code = path_violation(path)
        if code:
            findings.append({"code": code, "path_id": _path_id(path)})
    # Reuse the strict, original B02-C.6 redacted receipt validator:
    # it verifies the original JSON self-digest and no raw Arabic excerpt.
    receipt = Path(root) / WITNESS_PATH
    checked = receipt.is_file()
    if checked:
        try:
            from qa.check_b02c6_witness_prep import validate
            validate(root)
        except (Exception, SystemExit):
            findings.append({"code": "WITNESS_PUBLICATION_GATE_INVALID",
                             "path_id": _path_id(WITNESS_PATH)})
    return {
        "status": "FAIL" if findings else "PASS",
        "tracked_count": len(paths),
        "violations": sorted(findings, key=lambda item: (item["code"], item["path_id"])),
        "witness_receipt_checked": checked,
        "rights_verified": False,
        "historical_eradication_verified": False,
    }


def _has_unredacted_witness_field(value):
    """Detect historical JSON key by name only; never return its value."""
    if type(value) is dict:
        if type(value.get("shared_span_folded")) is str and value["shared_span_folded"]:
            return True
        return any(_has_unredacted_witness_field(v) for v in value.values())
    if type(value) is list:
        return any(_has_unredacted_witness_field(v) for v in value)
    return False


def history_summary(root, max_commits=2000):
    """Best effort: only versions reachable from locally FETCHED Git refs.

    Original PR heads, deleted refs, forks and GitHub caches are not all covered
    by this API. Even zero findings is never evidence of historical erasure.
    """
    commits = _git(root, "rev-list", "--all", "--", WITNESS_PATH).splitlines()
    examined, detected = 0, 0
    for raw_sha in commits[:max_commits]:
        sha = raw_sha.decode("ascii", "strict")
        try:
            raw = _git(root, "show", sha + ":" + WITNESS_PATH)
            data = json.loads(raw.decode("utf-8-sig"))
        except (PublicationGuardError, UnicodeError, ValueError):
            continue
        examined += 1
        if _has_unredacted_witness_field(data):
            detected += 1
    return {
        "scope": "FETCHED_REACHABLE_REFS_ONLY",
        "history_complete_for_fetched_refs": len(commits) <= max_commits,
        "changed_commits_seen": len(commits),
        "witness_versions_examined": examined,
        "historical_unredacted_versions_found": detected,
        "historical_eradication_verified": False,
        "note": "External PR heads, deleted branches, forks and caches NOT covered",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--history", action="store_true")
    args = parser.parse_args(argv)
    try:
        root = Path(args.root).resolve()
        result = {"tip": scan_tip(root)}
        if args.history:
            result["history"] = history_summary(root)
        result["status"] = "PUBLICATION_TIP_FAIL" if (
            result["tip"]["status"] != "PASS") else "PUBLICATION_TIP_PASS"
    except PublicationGuardError:
        result = {"status": "PUBLICATION_AUDIT_UNAVAILABLE",
                  "details": "GIT_INSPECTION_UNAVAILABLE"}
    print(json.dumps(result, sort_keys=True, ensure_ascii=True))
    return 0 if result["status"] == "PUBLICATION_TIP_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
