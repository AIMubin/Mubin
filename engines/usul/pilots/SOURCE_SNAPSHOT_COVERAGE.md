# U0.1 Stage 04 — Source Snapshot & Coverage Contract

**Engineering capability implemented; Stage 04 real-source replay reported PASS by the local operator on 2026-10-20, with metadata-only evidence committed in [`u01-stage04-waraqat-source-link.json`](../../../corpus/reviews/u01-stage04-waraqat-source-link.json).**
This is a bounded, reproducible **source-fidelity** mechanism, not a juristic argument evaluator or a license to redistribute an online edition.

## Actual primary digital witness

- Work: *الورقات في أصول الفقه*, attributed to Imam al-Haramayn Abu al-Ma'ali al-Juwayni
- Witness: https://www.islamicbook.ws/asol/alwrqat.html
- Independently checkable heading: **الأمر**; next section: **النهي**
- Comparator: https://www.islam.ms/ar/كتاب-ورقات-أصول-فقه-إسلامي-إمام-حرمين-عبد-الملك-الجويني/
- Printed edition, copyright status for the hosting digital edition, authoritative historical wording, and source-capture hash are **not verified** by the repository.

The existing [short excerpt-only SHA](amr_default.py) is **not** a snapshot SHA of the webpage. The source website's text as displayed is not equivalent to private exact HTML bytes. **Historical note:** raw HTML bytes were not initially available in this assistant environment. The subsequent local Windows run reports exact raw capture and UTF-8 snapshot digests plus `SNAPSHOT_COVERAGE_PASS`; original bytes and private manifest remain outside GitHub. Public CI validates the extractor and coverage logic using synthetic fixtures, **not** an independent replay of the private original HTML.

## Provenance chain (three distinct artifacts)

1. **Raw capture, private:** save the actual HTML HTTP response *as bytes*, along with acquisition time, source URL, HTTP encoding and its independent full-file SHA-256. Keep it outside GitHub. Web page rendering, transcription and printed edition fidelity remain distinct questions.
2. **Extracted UTF-8 source text, private:** prepare a loss-audited text export with one heading per line, including exact `الأمر` and next `النهي` headings. Record extraction tool/version, transformation choices and a raw-capture SHA-256 as `transcription_provenance`. Neither stage-04 script silently strips HTML, normalizes diacritics or changes newline characters.
3. **Frozen metadata-only manifest:** create a **draft** using [source_snapshot_prepare.py](../source_snapshot_prepare.py); independently examine and pin its SHA-256 outside the source file (e.g., reviewed repository ledger/commit). Only then run [source_snapshot_coverage.py](../source_snapshot_coverage.py) with the separately established manifest digest.

### Operator replay example (local private files supplied to the Windows operator)

Start from `C:\AI\Mubin`. Create a local JSON metadata document with exactly these seven keys:

```json
{
  "source_id": "pilot:waraqat-text-export",
  "work_title": "الورقات في أصول الفقه",
  "author": "عبد الملك بن عبد الله الجويني",
  "edition": "Online digital witness; printed edition unverified",
  "source_url": "https://www.islamicbook.ws/asol/alwrqat.html",
  "locator": "باب الأمر حتى بداية باب النهي",
  "transcription_provenance": "Document the actual raw HTML SHA256, download timestamp, source encoding and deterministic export tool here"
}
```

**Replace the `transcription_provenance` placeholder with factual trace before qualification.**

```powershell
python -m engines.usul.source_snapshot_prepare `
  --source "D:\MubinSources\waraqat-private-utf8.txt" `
  --metadata "D:\MubinSources\waraqat-capture-metadata.json" `
  --section-id "pilot:waraqat-bab-amr" `
  --start-line "الأمر" --end-line "النهي" `
  --draft-manifest "D:\MubinSources\waraqat-draft-manifest.json"
```

The tool returns **`DRAFT_NOT_ATTESTED`**, the full export SHA and a proposed manifest SHA; this is not evidence of external provenance. After separately pinning the reviewed draft manifest's hash, run:

```powershell
python -m engines.usul.source_snapshot_coverage `
  --source "D:\MubinSources\waraqat-private-utf8.txt" `
  --manifest "D:\MubinSources\waraqat-draft-manifest.json" `
  --trusted-manifest-sha256 "<REVIEWED_MANIFEST_SHA256_FROM_INDEPENDENT_LEDGER>" `
  --report "D:\MubinSources\waraqat-source-coverage-report.json"
```

`SNAPSHOT_COVERAGE_PASS` checks exact source bytes, size, a separately pinned manifest, the unique source headings, section line count, section digest, every original source line's byte range, full byte partition and no overlaps. The metadata-only report omits source text. It must not be reinterpreted as a validated raw-HTML-to-export transformation.

Exit codes for the coverage CLI: **0** = pinned text export and declared section coverage match; **1** = invalid, altered or mismatched data; **3** = source text file not present, so `PENDING_SOURCE`. A draft tool's exit 0 only means a structurally valid draft was produced, **not** certification.

## Critical acceptance boundary

This does **not** establish that all interpretations or diverting legal indicators were captured. The extractor verifies that lines between two **specified** headings are complete relative to the pinned UTF-8 export; it does not infer that an author discussed all possible exceptions, or that an extracted text is the same as an authoritative printed edition.

Do not use `SNAPSHOT_COVERAGE_PASS` as a trigger to convert `ABSENT_IN_DECLARED_SCOPE` into **absence of qarā'in in the real text**. Stage-03 toy token scanning remains synthetic. A later, separately tested proof obligation must bind a source-derived segment index to this coverage report and define exact lexical queries; semantic jurisprudential analysis remains out of scope. `scholarly_verified=false`, `redistribution_approved=false`, `semantic_equivalence_verified=false`.

### CI acceptance

The [synthetic negative tests](../tests/test_source_snapshot_coverage.py) verify byte mutation, newline differences, headings missing/duplicated, overlapping sections, incorrect section count/hash, binary files, manifest self-consistency and no accidental source text output. [Draft-tool tests](../tests/test_source_snapshot_prepare.py) exercise preparation without elevating independent attestation.


## 2026-10-20 qualified run: metadata-only receipt

Committed [Stage 04 source link](../../../corpus/reviews/u01-stage04-waraqat-source-link.json) records:

| Bound artifact | Reported evidence |
| --- | --- |
| Full digital HTML capture | 18,923 bytes, SHA-256 `66ec33c1825acdf82b3720f89d89aac15aa6e993356c0d90b41e53fe9a2fa044` |
| `waraqat-extract/1.0.0` UTF-8 export | 16,410 bytes / 343 lines, SHA-256 `9ce9de30f1af3ef32b2bf55b0473c9459e0cf530e3b557535744b284c760f4df` |
| Separately archived manifest digest | `5bf586787dbb9f84d03fc21c62ee32619b66b474c66a6c890aeb813219f853cf` |
| Chapter `الأمر`, up to exclusive heading `النهي` | Lines 86–108 (22 lines), 1,232 bytes, SHA-256 `20879bade7a4a831a0020e1bae51806ca015d7803be42fdb44e580a9055581ab` |
| Local coverage decision | `SNAPSHOT_COVERAGE_PASS` (as attested by operator, not replayed from private bytes in CI) |
| Source-linked rule | `pilot:rule-amr-default`; only `LEXICAL_MATCH_ONLY` attested |

The operator additionally reports repeatable HTML extraction on those exact bytes and local `111/111` Usul tests. [GitHub Usul CI](https://github.com/AIMubin/Mubin/actions/runs/39468150321) and [corpus CI](https://github.com/AIMubin/Mubin/actions/runs/39468150407) both passed Ubuntu and Windows on commit `f748af46d769baadb9ae562e7728c5d1b305fdf3`.

**Precise terminology:** An independently recorded SHA-256 digest is a *frozen hash reference*, not a public-key digital signature. Any claim of cryptographic signing needs a verifiable signer identity, signature bytes and a verification process, none of which are in this metadata-only receipt. Distinguish the local operator's independently recomputed manifest digest from independent third-party provenance validation.

**Acceptance:** `REAL_SOURCE_SNAPSHOT_COVERAGE_PASS` applies to the explicitly captured digital text/declared section and deterministic extraction chain. `scholarly_verified=false`, `redistribution_approved=false`, `semantic_qarinah_detection_verified=false`, and printed-edition verification remain unaltered. The unverified comparator witness and other chapters are outside the acceptance scope.

**Stage 05 exit boundary:** a byte-addressed index regenerated from the private pinned UTF-8 source (not hand-authored records); segment coverage equality vs Stage 04; exact-match queries with query/normalization profiles; all-match locators and stable digests; explicit `LEXICAL_MATCH_ONLY` results with no empty-hit → negative legal inference. Optionally compare the second witness by separately pinned provenance. No need for blanket scholarly review to implement or test this engineering scope.
