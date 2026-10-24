# Quran Chrome E2E — extraction audit / evidence checklist

The original #76 included Chrome scaffolding together with a direct source reader, Tafsir/KSU UI, and private ingestion. This PR imports **only** current-compatible Chrome E2E scripts and the GitHub Actions workflow. It does not reuse the old PR's former pass results as qualification for this head.

## Required technical checks

- Mandatory actual Chrome/ChromeDriver located on Ubuntu runner, no skip if unavailable. The scripts navigate browser sessions to a private `127.0.0.1` HTTP server started from validated Q0.1b or test-only Q0.1e-b SourceIndex.
- Source types are separated: tiny `synthetic_fixture` with deliberate markup injection is **never** allowed Tafsir links; full `tanzil_domain_unattested_export` source-shape simulation uses **invented** full-size text and test-only digest override; optional real Tanzil HTTPS mode is unverified and network-dependent.
- Bounded loopback read, no public server, no screenshot or Quran verse text output. Chrome DOM `textContent` exact-match is checked without printing verse text or storing visual evidence.
- RTL and mobile viewport layout checks, source/rights warnings, preserved diacritics, no DOM XSS from literal HTML, six metadata-only unreviewed Tafsir titles and the exact two user-triggered KSU links with privacy attributes, disabled AI explanation and source notice.
- Real external network Chrome test is advisory only; the dedicated **mandatory offline Chrome gate** must actually pass. Read live advisory output line `result=PASS` separately; overall `success` of workflow is not proof.
- No Chrome click to actual KSU site; no inference of true bibliographic edition identity, publisher attestation or permission to copy Tafsir or Quran texts. Chrome version on GitHub-hosted runners is ephemeral.

**Current review status:** needs latest extracted-head Chrome CI, maintainer code review, Codex independent exact-head review and owner/governance merge gate. No result in this document predetermines CI success.
