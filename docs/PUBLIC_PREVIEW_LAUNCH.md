# Mubin — Public metadata preview launch

**Scope:** a public, read-only, Arabic-first presentation of *already committed metadata*, source attribution and current capabilities. It is **not** publication of Quran/Hadith/Tafsir texts and **not** a fatwa or jurisprudential-reasoning service. Mubin system version stays **0.1.0-alpha**.

## Shipping files

- [Static browser UI](index.html), [styles](preview.css), [client logic](preview.js) and [metadata JSON](preview-data.json). No backend, accounts, model API keys, outside CDN or private database.
- [Reproducible generator](../release/public_preview.py) reads only Stage07, Stage08 and Q0.3 metadata receipts. The six small query labels filter *previously measured counts*, not live arbitrary full-text search.
- [Independent cross-OS preview CI](../.github/workflows/public-preview.yml) verifies byte-for-byte reproducibility and negative safety gates, without triggering frozen H3.9.2 or unrelated corpus qualification work.
- No original private HTML, source book text, Quran source/linked DB, tafsir editions or generated legal rulings are published.

## Local validation

From the project root, execute:

~~~bash
python -m release.public_preview --check
python -m unittest discover -s release/tests -v
python -m http.server 8765 --directory docs
~~~

Visit http://localhost:8765/ for a smoke test; file:// browsing is unsuitable because the page fetches metadata over HTTP.

When the **reviewed** underlying receipts change, regenerate with:

~~~bash
python -m release.public_preview
python -m release.public_preview --check
~~~

Review the exact resulting JSON diff for text or newly asserted permissions before committing. The metadata JSON is pinned to LF checkout by .gitattributes for Windows and Ubuntu.

## One-time GitHub Pages activation (authorized maintainer)

Open repository **Settings → Pages → Build and deployment → Deploy from a branch → main → /docs → Save**. GitHub can serve docs/index.html as the project page. Check the actual address shown in Settings, the deployment result, browser console, mobile layout, and visible limitations before asserting **publicly launched**. The repository and passing CI alone cannot prove Pages is currently enabled.

Alternatively publish only the docs/ directory on any static host; do not let cloud infrastructure procurement delay a metadata preview.

## Action-level release gates (not a global human-review queue)

| Capability | Status in this preview |
| --- | --- |
| Source-linked metadata, operator-recorded Stage07 search counts, Stage08 graph metrics | Included, read-only, explicitly research-grade |
| Quran verse or tafsir body text | **Withheld** pending specific canonical/edition integrity and rights |
| Reproducing modern Hadith/Tafsir edition material | **Withheld** pending specific redistribution rights |
| H3.9.2 frozen 158 human decisions | **Not modified**, not a blocker for metadata preview |
| Usul P0 deductive/juristic conclusions, qiyas, fatwa | **Not available** and not certified |
| Complete Quran/Hadith/Usul/Fiqh product | **Not shipped**; separate future gates |
| Mubin system version bump | **Not implied**; version remains 0.1.0-alpha |

Provenance and attribution are **not** licenses to redistribute publisher material. Metadata-only is a strictly bounded publishing action, not a claim that all classical or digitized materials are public domain.

**Engineering go:** generator --check and public-preview CI pass on Windows and Ubuntu, no source passages appear in the artifact, and a browser smoke test succeeds. **Launch go:** an authorized maintainer confirms hosting was enabled and the page is reachable. These are separate decisions.

Stage09 Typed Evidence Binding may develop independently: only unassessed candidate references from pinned Stage08 observations to P0 source/evidence IDs; *no automatic promotion* of P0 verification, rules or scholarly semantics. Stage09 completion is **not** a metadata preview release prerequisite.
