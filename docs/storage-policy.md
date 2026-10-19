# Mubin Corpus Storage — GitHub + Local Vault

Decision: **19 October 2026**. Defer permanent online hosting (R2/GCS/managed database) until public release. Keep formats and restoration provider-independent.

## Responsibilities

- **GitHub:** source code, workflows, scientific review records, schemas, checksums and non-sensitive provenance/rights metadata. Never commit raw text corpora, scans, restricted editions or secrets to git.
- **GitHub Actions:** reproducible builds, validation and temporary handoff artifacts (currently a 30-day configured retention). Artifacts are **not permanent backups**.
- **Local vault:** immutable snapshots of pinned original sources, derived SQLite, Quran witness (if available), manifests and reports.
- **Second local backup:** separate physical disk, preferably encrypted and disconnected when not in use.

## Snapshot structure

The utility at corpus/local_vault.py creates folders such as D:\MubinVault\snapshots\run-1234567890\ containing:
- originals/tafsircenter-quran.db — pinned upstream original, required for a FULL snapshot.
- linked/quran_tafsir.db — derived SQLite, validated against source reports and direct SQL audit.
- reference/tanzil-uthmani.txt — verbatim reference when available, checked against its manifest.
- reports/ — original import, audit, diagnostic reports.
- snapshot.json — file hashes, size, origin, run ID, missing-source flags and qualification status.

Content is copied without modification; snapshots never overwrite existing files. Source databases require verified SHA-256. Malformed historical reports are preserved with an explicit warning. A missing upstream original is treated as PARTIAL_NO_UPSTREAM_ORIGINAL. This utility does **not** certify sacred-text accuracy or publishing rights.

## Windows PowerShell usage

Install Python 3.11+ and GitHub CLI (https://cli.github.com/), then authenticate with gh auth login locally. Clone AIMubin/Mubin; execute from the repository root:

~~~powershell
# Get the numeric workflow run ID:
gh run list -R AIMubin/Mubin -w import-quran-tafsir.yml -L 5

# Substitute the actual successful run ID:
python -m corpus.local_vault pull --run-id 1234567890 --root D:\MubinVault --fetch-source

# Verify original, SQLite coverage, and per-file SHA-256:
python -m corpus.local_vault verify --run-id 1234567890 --root D:\MubinVault

# Duplicate to a separate, ideally BitLocker-encrypted external drive:
python -m corpus.local_vault mirror --run-id 1234567890 --root D:\MubinVault --mirror-root E:\MubinBackup

# Restore rehearsal (new, nonexistent destination):
python -m corpus.local_vault restore --run-id 1234567890 --root E:\MubinBackup --destination D:\MubinRestore\corpus-data
~~~

The --fetch-source option downloads the original Tafsir Center dataset separately; SHA-256 must be:
10e61f615ab5e6a3440e8ecc8ba1dc2273d12cd9048752760fe53a44d191cc27

If already present locally, use --source-db D:\Sources\quran.db instead. If unavailable and only an emergency partial snapshot is possible, explicitly pass --allow-missing-source; do not misrepresent it as complete.

For **extracted** GitHub artifacts downloaded manually:

~~~powershell
python -m corpus.local_vault capture --run-id 1234567890 --incoming D:\Downloads\MubinArtifacts --root D:\MubinVault --source-db D:\Sources\quran.db
~~~

Allow at least ~1 GB of temporary storage for current data, tools and copies; install and authenticate gh on the local machine. No secrets are stored in the repository. Keep vault folders outside the git checkout.

## Retention / resilience

Create a snapshot for each significant corpus baseline, and verify backup copies when created and at least quarterly. Periodically restore into a clean directory and test data queries. A different directory on the **same physical disk is not a separate fault domain**. Use Windows BitLocker or equivalent full-disk encryption. Unplug a backup disk when finished to reduce ransomware exposure.

GitHub cannot directly save files to an offline local workstation. The local machine must run pull and mirror, manually or through its own Task Scheduler. GitHub-hosted artifacts remain temporary.

## Release readiness gate (deferred)

Select online hosting only when publication is being prepared. Evaluate license/redistribution eligibility, capacity, query traffic, recovery targets, auditability, costs, regional needs, security and exportability. The Quran-text fidelity review and known 11 tafsir quality issues remain open regardless of backup success.
