# Q0.1c/d — real Chrome browser regression smoke: primary engineering audit

**Date:** 2026-10-18. **PR:** [#76](https://github.com/AIMubin/Mubin/pull/76), stacked on draft #75. **Status:** maintainer-only technical test; no independent scholarly attestation, no source authentication, no rights decision.

## Why this was needed

The previous 108/118 Python tests exercised the HTTP API and structural invariants but did not prove that actual Chrome would run the JavaScript forms, preserve RTL/mobile rendering, or prevent XSS. This test is an **actual Chrome 155 WebDriver session**, not a static HTML assertion and not a simulated browser. Its only input corpus is two explicitly invented Arabic examples; **these are not Quranic ayahs**.

## Real tested behavior

- A real Chrome browser loads the locally hosted HTTP page through `127.0.0.1`.
- HTML `lang=ar` and `dir=rtl`; mobile viewport width 390 pixels remains right-to-left and has no horizontal document overflow.
- Startup reports synthetic source and says text authentication is unverified.
- Form submission retrieves `1:1` with byte-equivalent Unicode text; the deliberate literal `<img src=x onerror=alert(1)>` in the synthetic source remains a **literal text string**, not an HTML image or executing JavaScript.
- Mark-insensitive Arabic search finds the same text, preserving original diacritics in the displayed result.
- The rendered item identifies invented text as not Quran, and the source-notice panel shows the synthetic warning.
- A forged HTTP `Host` header is rejected (403).
- No external Quran corpus was downloaded by this test. No remote browser, public HTTP service, LLM, automatic merge or human review was involved.

## Trace: failing bootstrap → corrected browser invocation

1. **Added tests / workflow at HEAD `8c5f74ebea9be17cb5880bac602e0daef569e189`:** [Chrome run 39146191867](https://github.com/AIMubin/Mubin/actions/runs/39146191867) **failed** because `python qa/quran_browser_smoke.py` lacked the repository root on `sys.path` (`No module named 'engines'`). This was a test-harness launch problem, not evidence of a defective Quran parser.
2. **Fixed the runner invocation** to `python -m qa.quran_browser_smoke` at `fc9abadb3801f8f3e2d7727b1fc71a3670db6244`. [Chrome run 39146263291](https://github.com/AIMubin/Mubin/actions/runs/39146263291) **passed**, with log reporting `browser=actual_headless_chrome`, `rtl=true`, `mobile_rtl=true`, `exact_text_preserved=true`, `html_injection_blocked=true`, `source=synthetic_only`, `source_authenticated=false`, and `rights_verified=false`. Chrome 155.0.8059.39 and corresponding ChromeDriver version were recorded in runner logs. Same HEAD: [P0 run 39146263292](https://github.com/AIMubin/Mubin/actions/runs/39146263292), [Q0.1d run 39146263331](https://github.com/AIMubin/Mubin/actions/runs/39146263331), and [Q0.1 run 39146263327](https://github.com/AIMubin/Mubin/actions/runs/39146263327) **all successful**.
3. **Final audit-document HEAD:** CI results MUST be checked again on the exact commit introducing this document; old test-run success does not automatically certify a newer commit.

## Boundaries, threats and remaining known gaps

- The browser test confirms only the **synthetic local fixture** and tested navigation paths; it is not an approval of the unverified 6,236-verse GitHub mirror, and does not compare an authentic Tanzil publisher export.
- It does not assert visual perfection, accessibility compliance, multiple browsers, a real human usability study or comprehensive XSS prevention beyond the example tested. The driver/browser package versions are those installed on the GitHub-hosted runner; they can change over time.
- A URL containing user-controllable data is never interpolated into `innerHTML`. Production or internet-facing deployment would require a separate security/release review; loopback remains the only supported listening address.
- All PRs in the Quran chain #73–#76 remain **draft and unmerged**. The main branch is still not protected per GitHub status; do not bypass repository governance to reduce PR count.
- `codex_review=unavailable` (quota exhaustion reported in project), no actual secondary independent code reviewer has approved this exact commit.
- Test fixture is deliberately disjoint from Hadith H3.9.2 frozen holdouts. No edition authentication, rights verification or `eligible_for_religious_ruling` is inferred from UI tests.

**Next bottleneck-focused action:** consolidate the four stacked Quran PRs **in dependency order** after repo protection, up-to-date exact-HEAD checks, primary audits and review/thread resolution. Prepare the *official Tanzil download configuration and a real second independently retrieved file* separately so this does not delay local UI engineering. Do not add another exploratory PR merely to rename the same work.
