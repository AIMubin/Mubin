# Mubin — fast-lane development policy (engineering vs scientific evidence)

**Intent:** finish and integrate safe, limited software increments rapidly;
do not hold an unrelated engine hostage to private source investigation.
The baseline is Mubin `0.1.0-alpha`. This policy grants no authority to
publish fiqh rulings or represent candidate material as verified Islamics.

## Three independent gates, different owners

| Gate | Automatic/local checks | May proceed without human source adjudication? |
| --- | --- | --- |
| **Engineering** | Schema validation, anti-leak, pinned metadata, deterministic tests, CI, code review | **Yes** for research-only code and synthetic fixtures |
| **Source & rights** | Original byte hash, edition/locator metadata, attribution evidence, actual redistribution licence | Dev metadata may be labelled `UNVERIFIED`; **public text release must not proceed** without rights validation |
| **Scholarly** | Independent qualified human review of meaning, context, exceptions, disputes and textual variants | **No** for promoting an unassessed statement into a doctrinal rule, fatwa, `qiyas` or `tarjih` |

An **automated label is an authorization boundary, not a truth claim**:
`LEXICAL_ONLY`, `UNASSESSED`, `UNVERIFIED`, `RESTRICTED`,
`NOT_CLEARED` mean engineering can continue while conclusions do not
gain authority. A hash proves reproduction of an agreed byte sequence,
not textual authenticity, accuracy, source licensing or valid inference.

## Parallel work without shared blockers

- **Quran Q0.3:** regression-check immutable pinned original verse bytes,
  counts, chapter mapping and hashes whenever this engine's code changes.
  Do not retype or reinterpret verses just to test unrelated features.
  Fix any disagreement with a trusted independently recorded Quran
  reference before changing frozen pins. No automatic editing of the core.
- **Hadith H3.9.2:** build ranking, filtering and ingestion logic on
  *metadata-only* or genuinely licensed datasets with `UNVERIFIED` grade
  labels where applicable. Keep 158 human adjudications and frozen
  family/source-disjoint benchmarks unchanged. **Do not silently classify
  an ungraded hadith as sahih or raise scholarly gate status.**
- **Usul / PR #81:** integrate provenance-safe, offline data schemas and
  candidate tools now; run independent private local intake as a **parallel
  operator task**. A successful synthetic contract test is sufficient for
  an engineering PR review; original W1/W2 quotations and 16-chapter
  textual variance adjudication are separate, limited-data activities.
- **Tafsir prototype:** support per-explanation attribution, uncertainty,
  licensed source metadata and immediate `UNVERIFIED` development labels.
  Do not expose restricted editorial notes or interpretive texts publicly
  merely because a base work is old or available online.
- **Fiqh:** only typed research interfaces and explicit NOT_AUTHORIZED
  responses until real Usul/Hadith/Quran evidence and methodologies meet
  their individual gates. Do not invent normative rulings to fill a UI.

## Short feedback loop (local / CI / operator)

1. **First:** scoped tests for modified modules and relevant adversarial
   safety tests, e.g. for PR #81:
   ```bash
   python -m unittest -q engines.usul.tests.test_concept_definitions \
     engines.usul.tests.test_private_text_commitment \
     engines.usul.tests.test_waraqat_definition_private_intake
   ```
2. **Before review/merge:** `python -m unittest discover -s engines/usul/tests -v`
   and cross-OS GitHub CI at the **exact PR HEAD**; check source-integrity
   suites only when their inputs or shared contracts changed. Reuse existing
   green results for unchanged code, never assert CI ran on a new head
   when path filters skipped it.
3. **Independently:** local operator executes the private-source test
   gate on actual private files, preserves texts/keys outside Git, and
   submits only a separately privacy-audited metadata receipt.
4. **Review:** maintainer reads and validates HEAD, its invariants, CLI
   failure behavior, tests and diff **before** requesting Codex. Codex
   findings are triaged at the exact lines with regression tests. Lack
   of an optional bot response is not itself scholarly evidence or a
   release gate; never bypass mandatory GitHub branch protections.
5. **Release:** merge scoped engineering-only code once exact-code tests,
   review and required branch policies pass; leave scientific/source
   authenticity flags false. Do not wait for every scholarly case to
   close unless that PR actually claims scientific qualification.

## Reduce repeat manual work

- One pinned source receipt per immutable source snapshot. Consumers
  reference its SHA; **do not rerun W1/W2 just to change an unrelated
  metadata validator**.
- One shared `core/inference` typed contract; reuse the U0.1 P0 bridge.
  No second standalone Usul inference executor.
- Bulk candidate ingestion is allowed into private/dev stores with bounded
  sizes and machine tags; each candidate is `UNASSESSED`, no auto-promotion.
  Keep private texts, key material, proprietary notes and hidden paths
  out of GitHub, artifacts, CI logs and generated reports.
- Prefer reusable open-source *software*, then check work, digitization,
  edition, annotation and dataset **rights separately**. Historical
  underlying works and modern digital editions have different rights.
  An online text is not automatically licensed for redistribution.
- Use a bounded synthetic happy-path, negative-path and one traceable
  real-source operator pilot; expand tests in parallel. Do not block
  implementation of all engines on a 16-chapter human textual docket.

## Metrics to report on each engineering PR

`commit_sha`; changed modules; targeted test count/result;
cross-OS full tests/result; bot findings open/closed;
public leak controls; pinned evidence dependencies;
`engineering_ready`; `private_operator_state`;
`scholarly_state`; `rights_state`; `merge_state`.

Never turn `engineering_ready=true` into
`scholarly_verified=true`, `source_support_attested=true`,
`redistribution_approved=true`, `juristic_inference_allowed=true`
or `public_fatwa_authorized=true`. These states have separate
evidence and ownership.
