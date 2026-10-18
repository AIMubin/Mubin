# U0.5 — maintainer-first primary and adversarial audit

**Date:** 2026-10-18. **Exact reviewed implementation HEAD:**
`780927585189310963d82dbb413729b889fbf642`.
**Stacked base:** U0.4 PR #69 `41e4e560d487b74c3ae26f4739eb0d46e8adfd2f`.
U0.5 PR #70 remains draft, stacked on unmerged #69 → #68 → #67 → #66.
The global Mubin release remains `0.1.0-alpha`.

## Source and historical implementation boundary

The local historical U0.5 research documents (workflow,
falsification matrix, and local test-evidence notes) were read from
the project Library. Their historical ZIP file was not imported
byte-for-byte. The implementation in this PR is **new** and
independently tested on the repository's current stacked GitHub
code. No historical local 154/154 test report is substituted for
this PR's GitHub runner results.

The parent data are **local metadata**: U0.2 Shamela chapter docket,
U0.3 researcher questions and U0.4 site-display short excerpts.
Their deterministic hashes are neither a verified print-edition
source digest nor publisher custody nor scholarly authentication.

## Exact implementation scope

Eight paths changed before this audit:
- `core/usul/review_queue.py` — strict bounded queue validator,
  typed status reporting and clearly synthetic vote summarizer.
- `core/usul/review_cli.py` — offline four-file JSON validator.
- `core/tests/test_usul_u05.py` — positive and negative regression
  tests for source identities, evidence gates, fraud scenarios and CLI.
- `schemas/usul-u05-review-queue.schema.json` — strict Draft
  2020-12 JSON Schema.
- `research/usul/u05-risala-review-queue.json` — four
  unsubmitted requests and 24 pending evidence tasks.
- `docs/research/USUL-U05-INDEPENDENT-REVIEW-WORKFLOW.md` and
  `docs/research/USUL-U05-FALSIFICATION-MATRIX.md` — bounded
  procedures and hypothetical counterexample requirements.
- `.github/workflows/mubin-usul-synthetic.yml` — changed
  paths and explicit U0.5 CLI execution in PR/main contexts.

U0.1's fixed rulebook/case bytes, U0.2–U0.4 parent registries,
Hadith H3.9.2 frozen source/family-disjoint holdouts, system
version and main branch were **not modified by this PR**.

## Primary code/security and trust-boundary assessment

1. **Parent-first binding:** `validate_review_queue` invokes
   `validate_observations` which validates U0.3 and U0.2
   ancestors. It compares the submitted queue hashes to their
   respective independently computed *local metadata* canonical
   fingerprints. It then binds each `u05_r00N` review to exact
   `u04_t00N`, `u03_h00N`, `u02_c00N`, question wording,
   site route, site-displayed page number and editorial status.
   Validating these links is not independent source authenticity.
2. **Unsubmitted-only design:** exactly four reviews, six
   canonically ordered axes per review, each `pending` with
   zero evidence references; each has exactly two
   `unassigned` reviewer slots; `reviewer_submissions=[]`.
   `review_status=not_adjudicated`, `admission_status=no_admission`,
   `automatic_promotion=false`, `rights_status=not_assessed_for_use`.
   The schema rejects additional raw source-book content,
   individual reviewer identities, fabricated approvals/signatures,
   optional ASTs, or imported P1 receipts.
3. **Editorial and hypothetical-risk integrity:** The four
   researcher-authored risk statements and falsification probes
   are pinned against accidental/hostile rewrites for this
   *fixed four-slot v1 pilot*. The critical Ijma risk remains
   explicit: an editor-added chapter title and an
   interlocutor's question cannot be treated as the author's
   authenticated conclusion. These strings are **research
   prompts, not verified historical or juristic claims**.
4. **Negative testing:** card/observation/source ID swaps,
   page-route substitutions, partial/duplicate/reordered
   evidence tasks, missing and forged reviewer claims,
   author/editor mislabeling in U0.4, conflicting parent digests,
   non-plain dict subclasses that forge equality, aliases,
   cycles, invalid Unicode, large untrusted input and
   unexpected nested fields are rejected fail-closed.
5. **Safe CLI scope:** uses U0.1's existing bounded offline
   `_read` (256KiB per file; Linux regular-file/no-symlink
   checking; duplicate JSON members, NaN/Infinity, invalid
   UTF-8/surrogates rejected). CLI exit code 0 means **metadata
   validation only**, 1 means semantically invalid metadata,
   2 means unreadable/unsafe file or malformed JSON. It returns
   aggregate statuses and hashes, never excerpts, contact
   details, private reviews or proposed actual decisions.
6. **Synthetic review-position classifier:** `accept/accept`
   is labeled `unverified_concurrence`, a mismatch requires
   escalation, and every input returns
   `independent_human_review_verified=false`,
   `verified_human_review_count=0`, and
   `eligible_for_engine=false`. No two tokens/strings could
   establish independent real humans or authorize a rule.
7. **Correct diagnostics:** `parent_bindings_match` separately
   verifies metadata parents and is not conflated with
   invalid local review-task content. `queue_sha256` is an
   order-normalized local JSON digest (stable when review
   records reorder), not a digital signature, publisher
   hash, append-only audit log or legal permission.
8. **Permanent no-admission outputs:** counts of real human
   reviews and admitted rules remain zero; `rights_verified`,
   `edition_authenticated`, `source_bytes_pinned`,
   `independent_human_review_verified` and
   `eligible_for_engine` remain false even when all metadata
   is structurally valid.

## Verified RED → GREEN GitHub evidence

- **Red-first tests only:** commit
  `19f4236f9f476739219763406dc02c5557ae0425`,
  [P0 run 39101842536](https://github.com/AIMubin/Mubin/actions/runs/39101842536)
  failed as designed with `ModuleNotFoundError:
  No module named 'core.usul.review_queue'`
  (**129 methods, one import error**). No tests silently
  modified to make the later implementation green.
- **Initial implementation:** commit
  `44ec9d51f6d393ece22c8bc593c1e4ee0a727380`,
  [Usul run 39102069079](https://github.com/AIMubin/Mubin/actions/runs/39102069079)
  and [P0 run 39102069071](https://github.com/AIMubin/Mubin/actions/runs/39102069071)
  both succeeded (**150/150 tests** plus offline CLI).
- **Adversarial flaw found by primary review:** originally,
  changing the four research-risk descriptions or
  counterexample prompts to claims denying the need for review
  still passed. RED-only commit
  `26ab7aec43e675592db296f228f3cd61c097fad1`
  added eight targeted mutations. [Usul run 39102180257](https://github.com/AIMubin/Mubin/actions/runs/39102180257)
  failed **151 methods, 7 expected failing subcases**;
  the remaining critical Ijma warning was already pinned.
- **Repair:** commit
  `780927585189310963d82dbb413729b889fbf642`
  binds all four risk/probe pairs to the explicit v1 research
  contract. [Usul run 39102240615](https://github.com/AIMubin/Mubin/actions/runs/39102240615)
  and [P0 run 39102240616](https://github.com/AIMubin/Mubin/actions/runs/39102240616)
  completed successfully, **151/151 passing**. CLI outputs
  `queued_claim_count=4`,
  `open_evidence_task_count=24`,
  `admitted_rule_count=0`,
  `verified_human_review_count=0`,
  `eligible_for_engine=false`,
  and queue metadata digest
  `5545c84d835be8c81770041c729aecff8e36a2da96a9852aae218da1d3034730`.

**After this audit-document commit, check latest-HEAD CI again.**
Earlier runs cannot be silently treated as proof of a changed HEAD.

## Quota fallback and remaining scientific blockers

An earlier U0.2 PR #67 review attempt returned an exhausted Codex
code-review quota. **No independent secondary Codex review for
this U0.5 HEAD has been obtained.** Record
`codex_review=unavailable`, with a further maintainer-only
adversarial review above; this is not third-party approval.

- No exact independently collated edition, verified book bytes,
  source licensing conclusion, signed publisher attestation, or
  protected-document custody exists in U0.5.
- No independently identified, credentialed specialist human
  has performed a substantive review. A fake token or AI
  answer is never counted as such. Future real reviewer intake
  must be private, independently authenticated and governed.
- Counterexamples, methodological comparisons and risk
  descriptions are hypothetical research prompts, not accepted
  school doctrine. No Qur'an/Hadith authenticity, Ijma or Fiqh
  proposition has been established. Source rights and
  permissible quotation are not inferred from excerpt length.
- A user with code/fixture write access can change contracts
  and their hashes: GitHub CI does not constitute a trusted
  external signature. OS-specific safe open checks should not
  be assumed identically enforced on all non-Linux platforms.

**Decision:** structurally acceptable unsubmitted review-task pilot
after latest-HEAD CI confirmation. **No merging until dependency
chain and review gates are handled; no human/signature/rights
authentication and no operational rule admission.** The system
version is unchanged.
