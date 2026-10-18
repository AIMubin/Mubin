# Q0.1c — Maintainer-first primary/adversarial engineering audit

Date: 2026-10-18. **Reviewed repaired HEAD:** c59987f5f06fb7d904b6503419be685b3cb9a292.
Draft PR [#75](https://github.com/AIMubin/Mubin/pull/75) is stacked on unmerged Q0.1b #74 and Q0.1 #73. Base main and Mubin version 0.1.0-alpha unchanged.

## Exact scope and trust boundaries

The submitted code adds a loopback-only HTTP reader, Arabic RTL page, source attribution and original copyright notice display, bounded exact verse lookup/search, CLI, offline workflow, tests, and docs. The source text is **never downloaded by this service, added to Git, or modified in a new corpus file**. This demo reads an already locally available Q0.1b-validated raw source.

- Server binds to 127.0.0.1 only and does not accept arbitrary bind hosts, POST/PUT/PATCH/DELETE, file downloads or arbitrary file paths. It validates Host, Origin and cross-site request headers and has no CORS policy for external websites.
- Route and query allowlists, URL byte-size caps, percent/UTF-8 error checking, no duplicate query keys, noncanonical reference rejection, and diacritic-only folded-query rejection are tested.
- CSP (default-src none, scripts/styles/connect from self), no-store, no-referrer, nosniff, DENY framing and DOM textContent rendering avoid predictable XSS, injection and caching risks. The exact source string is returned unmodified even when a transient search comparison strips marks.
- Source content cannot be trusted simply because a constructed SourceIndex object claims a matching SHA-256. The reader re-derives the entire index once at startup from the original bytes and the manifest through Q0.1b.load_raw and compares the actual rows and manifest, rejecting subclasses. This is an explicit correction of a maintainer-discovered trust flaw.
- Synthetic fixture results are visibly marked **not Quran**. Full mirror mode displays the original Tanzil copyright footer from the input file plus Tanzil source link, not a fabricated publisher certification. Public terms: https://tanzil.net/docs/Text_License.
- The mirror acfatah/tanzil pinned commit 052b515f3a24dfacbe4cafc3b89f0681a447f462 and raw SHA-256 f64fe7657dbe2e185e9995e14f7a67ee6cf1a30773f39184883d7a763d70fb19 is still a **third-party mirror, not an independently authenticated Tanzil official export**. Differences in official download variants may change bytes. Source authenticity, rights adjudication, scholarly Quran judgment and public-service production hardening are not implied.

## Reproduced RED → GREEN GitHub CI

1. **RED test-only** d4b0ee9c2986729637bbe95e4770102fc62bdf0d: [P0 run 39134366814](https://github.com/AIMubin/Mubin/actions/runs/39134366814) failed due to missing engines.quran.q01c module, 90 discovered tests/one import error.
2. **Initial implementation** 30aae47a7158a7ffca48c8e86c9698c07cd33c2b: [Q0.1c run 39134793884](https://github.com/AIMubin/Mubin/actions/runs/39134793884), [P0 run 39134793873](https://github.com/AIMubin/Mubin/actions/runs/39134793873), [Q0.1 run 39134793808](https://github.com/AIMubin/Mubin/actions/runs/39134793808) succeeded, 106/106 tests.
3. **Adversarial test-only RED** aa7bb395c34f6ed807f135fbd926712dd8932ce0: [Q0.1c run 39134899559](https://github.com/AIMubin/Mubin/actions/runs/39134899559) failed, 108 tests and exactly two new failures: forged SourceIndex with unpinned verse text and subclassed index accepted.
4. **Repaired implementation** c59987f5f06fb7d904b6503419be685b3cb9a292: [Q0.1c run 39134984125](https://github.com/AIMubin/Mubin/actions/runs/39134984125), [P0 run 39134984136](https://github.com/AIMubin/Mubin/actions/runs/39134984136), [Q0.1 run 39134984246](https://github.com/AIMubin/Mubin/actions/runs/39134984246) passed, **108/108 tests** on that exact implementation SHA.

After this audit-document commit, recheck **latest-HEAD** CI. The prior green runs cannot stand in for new-HEAD evidence.

## Residual limits / release decision

This is a private localhost demonstration. No separate browser automation/independent penetration test has yet occurred; security controls tested in Python on Linux are not a universal guarantee. No outside scholarly or legal rights reviewer authenticated the source. No AI reviewer agents were executed for PR75; Codex secondary review was **not performed on this HEAD** (prior project-wide quota exhaustion); all review is maintainer-only, not independent approval.

All downstream flags remain source_authenticated=false, rights_verified=false, eligible_for_religious_ruling=false. No authority to merge automatically or publish a religious ruling, and no touching frozen Hadith H3.9.2 test assets. **Keep PR draft, open, unmerged** until dependency order and governance requirements have been handled. Source approval for public use is a separate track and must not stall local engineering or parallel P1/Hadith/Usul development.
