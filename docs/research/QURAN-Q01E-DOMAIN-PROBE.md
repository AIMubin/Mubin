# Q0.1e-a — Official-domain HTTPS probe, **not** publisher authentication

**Scope:** an isolated read-only source transport diagnostic extracted from the historical mixed-scope PR #76, independently based on Mubin main `f567dca6cf0e73dfcf30a9706d79b65eabb60e93`. This PR neither creates the future Q0.1e direct reader nor changes Q0.1c/Q0.3. The system remains `0.1.0-alpha`.

## The actual evidence chain

The probe attempts **GET then POST** at a fixed HTTPS origin `https://tanzil.net/pub/download/index.php` with explicit hypothetical `quranType=uthmani`, `outType=txt-2`, `marks=true`, `sajdah=true`, `rub=true`, `tatweel=true`, and `agree=true`. Redirects are refused (including otherwise legitimate CDN destinations); responses are bounded at 4 MiB, checked for HTTP 200 and exact response URL. The returned candidate must be UTF-8/LF Quran-like rows before being passed to the existing offline **Q0.1d comparator**, which validates the complete verse numbering and contrasts it with a separately pinned, **unverified** Q0.1b mirror.

A successfully received and structurally comparable **domain response** can be described as `comparison_available_not_authenticated`. Even exact byte equality can only establish equivalence **to the pinned mirror**, not independent publisher signatures, accepted manuscript/reading authenticity, edition qualification or rights to redistribute. It is also possible to receive equal verse Unicode while file bytes differ (e.g., notices/preset export differences). The `retrieved_over_official_domain_https` field is set only by the CLI's fixed-host transport call, never by injected test fetchers. The CLI cannot attest publisher identity and all separate authority flags remain false.

No text, license footer, or source response is persisted by this script, committed to Git, printed, or uploaded as an artifact. Reports contain the candidate digest, status, numeric count, and up to 20 **coordinates only**, never verse text. The network caller may still be visible to the Tanzil host and any intermediate infrastructure; the probe is not an anonymity tool.

## Usage (operator or CI)

```bash
python -m qa.quran_official_probe \
  --manifest engines/quran/q01b/sources/tanzil-mirror-v1.1.json \
  --mirror /path/to/EXACT-pinned-third-party-mirror.txt
```

This is **advisory**. Exit status `0` means the diagnostic ran even when `outcome=unavailable_or_invalid`, not that HTTPS or source validation succeeded. File-open problems yield exit `2`. Failure to access the external host is not promoted into source acceptance and is not a project-wide CI failure.

In CI, a separately pinned third-party mirror is fetched to ephemeral runner storage and revalidated by Q0.1d. A distinct advisory step attempts the official-domain request; results must be **inspected**, not inferred from a green workflow badge. The official domain response may differ or become unavailable; the implementation does not silently change its preset or evidence hashes to compensate.

## Follow-up Q0.1e-b (separate PR)

A live localhost reader may later use a precisely pinned byte response and preserved copyright notice after comparing its parser/manifest boundaries with Q0.1c and Q0.1f. It must not copy source text into Git or enable network/public listening by default. The historical fixed digest `7f30c647331a61100ebf24a80507dc0fcdd9f2df97f1312b5b2dfcb982a7f326` is **a recorded old observation**, not independent evidence of current publisher authenticity.

**Fixed statuses:** `source_authenticated=false`, `official_candidate_attested=false`, `candidate_publisher_provenance_verified=false`, `rights_verified=false`, `redistribution_approved=false`, `scholarly_verified=false`, `juristic_inference_allowed=false`, `public_fatwa_authorized=false`.
