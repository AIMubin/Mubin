# Mubin Quran — Chrome E2E smoke, independent extraction from #76

**Scope:** two actual headless Chrome sessions over an existing localhost-only Q0.1c web reader. This is a real browser test, not an HTTP-only API check, and requires installed Chrome and matching ChromeDriver. Based directly on merged main `27eda24edb4fc23e9e8d3a66be04cd100e9f15fb`; the private TafsirCenter SQLite sidecar and corpus ingestion are not included.

## Required E2E checks — fully synthetic, hard gates

`python -m qa.quran_browser_smoke` loads a **two-record invented Arabic source**. It tests RTL and Arabic page metadata, source disclosure, actual lookup and folded Arabic search without changing displayed Unicode, literal rendering of `<img src=x onerror=alert(1)>` without creating any DOM `img`, synthesized text not treated as Quran, no fabricated tafsir links or bibliographic titles, no AI-generated interpretation, synthetic source notice, Host rejection, mobile 390 px no-horizontal-overflow.

`python -m qa.quran_official_chrome_smoke --fixture` builds a **6,236-record artificial** source using the Quranic sura/ayah numerical topology but with *invented test-only Arabic text*. A local in-process test patch sets the expected SHA for this fixture **only during index construction and server startup**. It exercises the Q0.1e-b code path for direct bytes, then retrieves `2:1` via real Chrome and compares the displayed Unicode exactly with the artificial fixture's original string, verifies that the UI calls the already-integrated Q0.1f local metadata endpoint, shows six unreviewed bibliography rows, two fixed KSU outbound links (with `noopener noreferrer` and no referrer), and no tafsir iframe, AI interpretation, copyright notice masking, or mobile RTL overflow. **This synthetic route does not authenticate a real Tanzil source or make a synthetic passage actual scripture.** No Chrome screenshot, Quran text, or local corpus is uploaded or logged.

Both tests fail when Chrome or ChromeDriver is unavailable and both are mandatory for the `chrome-synthetic-gate` job. The suite does **not** silently skip a browser exercise or infer a successful click from a static DOM test.

## Separate optional live-domain browser observation

`python -m qa.quran_official_chrome_smoke --live` requests the Q0.1e-b historically pinned HTTPS Tanzil export and runs the same UI assertions. This job is **advisory / network-dependent** and `continue-on-error=true` applies only to the live-domain test step. Its actual result must be inspected in its log: the `"result":"PASS"` JSON is evidence of a successful browser run. A green overall workflow can be obtained when that advisory step fails; do **not** describe such a run as a successful live-domain Chrome test. Public external website navigation to KSU is **not** executed; link attributes and exact hrefs are inspected locally, without validating current KSU external fragment behavior.

ChromeDriver API uses localhost HTTP; the reader itself binds only `127.0.0.1` and rejects other Host/Origin values. No remote KSU iframe, LLM or religious ruling output is invoked. This is an engineering browser quality test, **not** an authenticated Mushaf/review of printed editions, rights approval or public fatwa authorization.

## Qualification and exclusions

No Q0.3 source modification, no tafsir text download/import, no change to frozen Hadith H3.9.2, no private corpus, no research-to-Scholarly promotion. `source_authenticated=false`, `scholarly_verified=false`, `rights_verified=false`, `redistribution_approved=false`, `juristic_inference_allowed=false`, `public_fatwa_authorized=false`. Whole-system version remains `0.1.0-alpha`.

Final exact-head PASS and independent code review must be recorded on the PR that actually adds the workflow. Older #76 documents are historical.
