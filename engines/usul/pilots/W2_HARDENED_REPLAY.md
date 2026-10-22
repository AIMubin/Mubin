# U0.1 W1/W2 hardening — private replay

State: PENDING_PRIVATE_REPLAY. Public CI validates synthetic fixtures only.
Old local closure receipts apply to the previous implementation, not the
hardened new code.

## Changes

- W1 batch now validates the complete inventory, canonical digest, contiguous
  source byte/line spans, headings and source section hashes before processing.
- W2 extraction locates its balancing content div and rejects unsupported
  headings; the new metadata-only manifest records title fingerprints,
  derived-text export byte ranges, section file digests and a manifest digest.
- W2 comparison REQUIRES original pinned W2 HTML; it replays extraction,
  verifies source root digests and all section files against the manifest.
  Missing/unmatched sections cannot result in a complete exit-zero report.

## Re-run locally

Use the existing pinned private folder: D:\MubinSources\waraqat.
From the project root run the commands below, using distinct filenames so
historical artifacts remain intact. No private bytes belong in Git.

    $root = "D:\MubinSources\waraqat"
    python -m engines.usul.pilots.waraqat_full_book_batch --primary-html "$root\waraqat-original.html" --primary-export "$root\waraqat-private-utf8.txt" --queries "engines\usul\pilots\data\waraqat-stage07-queries.json" --inventory "$root\waraqat-full-w1-inventory.hardened.json" --report "$root\waraqat-full-w1-batch.hardened.json"
    if ($LASTEXITCODE -ne 0) { throw "W1 replay failed" }

    python -m engines.usul.pilots.waraqat_w2_full_extract --raw-html "$root\witness2-original.html" --w1-inventory "$root\waraqat-full-w1-inventory.hardened.json" --sections-dir "$root\w2-sections-hardened" --manifest "$root\w2-full-manifest.hardened.json"
    if ($LASTEXITCODE -ne 0) { throw "W2 extraction failed" }

    python -m engines.usul.pilots.waraqat_w2_pair_compare --inventory "$root\waraqat-full-w1-inventory.hardened.json" --w1-export "$root\waraqat-private-utf8.txt" --w2-manifest "$root\w2-full-manifest.hardened.json" --w2-raw-html "$root\witness2-original.html" --w2-sections-dir "$root\w2-sections-hardened" --out "$root\w2-pairs.hardened.json"
    if ($LASTEXITCODE -ne 0) { throw "W2 comparison failed" }

Repeat in a fresh output directory and compare SHA-256 hashes of JSON output.
Check that W1 remains 21/21 with the frozen historical Bab al-Amr span. Reconcile
the older W2 Bab al-Amr Stage06 output (1,702 bytes) with the newer
full-book-derived output (1,706 bytes), which could reflect formatting; the
difference must be explained, not presumed equivalent.

Record the new local run in a new metadata-only closure receipt after its
private replay. Until then scholarly/rights/semantic qualifications remain
false. The 16 textual differences belong to independent textual study; they
are not permission to normalize away nonidentical words.
