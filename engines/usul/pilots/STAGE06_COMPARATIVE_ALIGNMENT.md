# U0.1 Stage 06 — Comparative Witness Alignment

**State:** Engineering implementation with synthetic CI tests; private real-witness comparison has NOT yet been independently replayed through this new module. This is not an edition verification, semantic equivalence proof, or fiqh ruling.

## Primary-source provenance

Witness 1: *الورقات في أصول الفقه*, Imam al-Haramayn al-Juwayni, [islamicbook.ws](https://www.islamicbook.ws/asol/alwrqat.html). Pinned Stage04 raw HTML SHA-256: 66ec33c1825acdf82b3720f89d89aac15aa6e993356c0d90b41e53fe9a2fa044. Exact W1 Bab al-Amr snapshot: 22 lines, bytes 3735:4967, SHA-256 20879bade7a4a831a0020e1bae51806ca015d7803be42fdb44e580a9055581ab.

Witness 2: [islam.ms](https://www.islam.ms/ar/كتاب-ورقات-أصول-فقه-إسلامي-إمام-حرمين-عبد-الملك-الجويني/). The separate operator report pins its original HTML SHA-256 to 3c4de1baa99bad782b5fba066523ca9f12798525907edede93bd1046ef36f0fa. The W2 HTML-to-section converter and **independently pinned extracted-section hash are not yet present in the public repository**.

Source receipts: [Stage04 W1 source](../../../corpus/reviews/u01-stage04-waraqat-source-link.json), [Stage05 W1 search](../../../corpus/reviews/u01-stage05-waraqat-lexical-replay.json) and [W2 pilot comparison](../../../corpus/reviews/u01-stage05-witness2-comparison.json).

## What has been built

[Witness alignment engine](../witness_alignment.py) verifies two independently pinned UTF-8 **section files**, indexes every strict character edit with byte spans, source line numbers and changed-span hashes, and outputs NO source text. It reports four distinct comparison profiles: exact bytes, Arabic combining marks and square bracket delimiters ignored (never bracket contents), collapsed whitespace, and removed whitespace. The latter is a **word-boundary candidate**, not certified lexical identity. None of these profiles assert meaning preservation. Arabic marks can change meaning; negation, hamza/alef and words inside editorial brackets remain material differences.

[Stage06 al-Waraqat runner](waraqat_stage06.py) verifies BOTH frozen original HTML SHA-256 digests, reproduces W1 UTF-8 extraction from its original HTML, checks W1 section bytes against the frozen Stage04 receipt, and requires the W2 section to match an independently supplied SHA-256. However, the runner currently **does not prove that the W2 section was extracted from the W2 HTML**. It returns STAGE06_TEXT_ALIGNMENT_PROVENANCE_PARTIAL, not a full comparison pass.

[Comparator tests](../tests/test_witness_alignment.py) and [pinned source tests](../tests/test_waraqat_stage06.py) exercise original-byte anchors, reproducibility, residual textual changes, negation and diacritics, tamper detection, and missing private files.

## Local operator execution

From C:\AI\Mubin, preserve the Stage04 W1 full source and manifest and both private source captures.

Prepare W1's section file **bytewise**, without changing line endings or normalization:

    $d = "D:\MubinSources\waraqat"
    $raw = [System.IO.File]::ReadAllBytes("$d\waraqat-private-utf8.txt")
    if ($raw.Length -ne 16410) { throw "Wrong Stage04 W1 snapshot length" }
    $slice = New-Object byte[] 1232
    [System.Array]::Copy($raw, 3735, $slice, 0, 1232)
    [System.IO.File]::WriteAllBytes("$d\waraqat-bab-amr-private.txt", $slice)
    if ((Get-FileHash "$d\waraqat-bab-amr-private.txt" -Algorithm SHA256).Hash.ToLowerInvariant() -ne "20879bade7a4a831a0020e1bae51806ca015d7803be42fdb44e580a9055581ab") { throw "W1 section altered" }

For W2, extract Bab al-Amr from the separately captured W2 HTML **using a recorded and versioned transformation** and archive the exact W2 section bytes, extraction rules, section locator and digest independently. The W1 extractor does not support the reportedly different W2 HTML structure. An independently recorded W2 text digest alone is not proof of extraction fidelity.

Run:

    python -m engines.usul.pilots.waraqat_stage06 --primary-html "D:\MubinSources\waraqat\waraqat-original.html" --primary-export "D:\MubinSources\waraqat\waraqat-private-utf8.txt" --primary-manifest "D:\MubinSources\waraqat\waraqat-draft-manifest.json" --primary-section "D:\MubinSources\waraqat\waraqat-bab-amr-private.txt" --secondary-html "D:\MubinSources\waraqat\witness2-original.html" --secondary-section "D:\MubinSources\waraqat\witness2-bab-amr-private.txt" --secondary-section-sha256 "<PINNED_W2_SECTION_DIGEST>" --report "D:\MubinSources\waraqat\stage06-alignment-report.json"

On success, status STAGE06_TEXT_ALIGNMENT_PROVENANCE_PARTIAL (exit 0); if private files are missing, PENDING_PRIVATE_WITNESS_FILES (exit 3); invalid, altered or unpinned input returns FAIL (exit 1).

## Interpretation and next acceptance gate

The [Stage05 W2 comparison record](../../../corpus/reviews/u01-stage05-witness2-comparison.json) reports 127 vs 126 whitespace tokens, a difference like و أما versus وأما, vocalization and editorial brackets. The record also states identical_after_normalization=false while describing lexical_word_differences=0. The latter is a **conditional operator assessment**, not a reproduced identical normalized token sequence and not a scholarly finding.

To close Stage06 on full dual-witness provenance, implement the W2 HTML-to-section extractor, independently freeze its raw and exported byte identity, add source-relative section byte coverage, and replay extraction+alignment over BOTH private captures. No third-party signature, critical edition or rights permission is inferred from SHA-256 alone.

Do not change Mubin system 0.1.0-alpha, Q0.3, or H3.9.2. Keep scholarly_verified=false, redistribution_approved=false, semantic_qarinah_verified=false, lexical_content_equivalence_certified=false, and full_witness_comparison_qualified=false until separately justified.
