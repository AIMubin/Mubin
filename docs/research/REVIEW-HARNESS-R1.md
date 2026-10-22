# Mubin Automated Review Harness R1 — bounded offline intake

Status: **implementation candidate only (not AI execution or independent acceptance)**. The project `PROJECT_STATUS.md` remains in ChatGPT's Mubin personal Library; this source file is a repository contract, not a duplicate state ledger.

## What ships

- JSON Schema 2020-12 for a **self-reported, untrusted** review packet bound to repository/base/head, changed-file declarations, impact tags, claimed CI checks and up to three reviewer-channel results.
- A deterministic tier classifier `T0`–`T3`. High-impact tags, governance/holdout/release paths override applicant-provided lower risk tags. Unknown paths are treated conservatively as `T2`.
- `python -m core.review_harness PACKET.json --mode plan --json` creates reviewer tasks for **code_security**, **source_attribution**, and **methodology_falsifier**. It **does not call a model** or acquire external data.
- `python -m core.review_harness PACKET.json --json` checks bounded structural consistency and reconciles **reported** check results and reviewer envelopes. It never verifies those reports with GitHub's CI API and never executes submitted code.
- Local regression tests and a public *development* taxonomy for four historically documented U0.2–U0.5 classes of defects. The taxonomy is **not** sealed, not independent reviewer recall, and never accesses H3.9.2 holdouts.

## Threat model and trust semantics

1. Packet data and model labels are potentially adversarial. Equal model labels, distinct channel names or a supposed 3/3 consensus do not prove separate invocation, expertise, independence or reliable tests.
2. The `changed_paths` input is a **self-declaration**, not a fetched Git diff. `inferred_tier` is a conservative floor for those declared paths and tags only; actual file scope must be verified separately on exact GitHub HEAD.
3. Claimed CI URLs are syntactically constrained to the project repository; they are **not** fetched or independently verified in this R1 tool. The report must therefore keep `ci_head_verified=false`.
4. `PASS_SCOPED_UNVERIFIED` describes **internal packet completeness only**, not trust or a pass for merge. `FAIL_REPORTED` is not a reproduced defect. A run of the harness itself is not evidence that three AI agents executed.
5. The sole outputs with authorization meaning are negative: `eligible_for_auto_merge=false`, `eligible_for_release=false`, `eligible_for_engine=false`, `scholarly_authority_verified=false`, `rights_verified=false`, `h392_gold_eligible=false` and `human_review_performed=false` in every case, including complete packets.
6. No file in this PR changes H3.9.2 frozen assets, Schema-31's 158 pending human adjudications or the system version `0.1.0-alpha`.
7. Packet JSON is not a safe prompt: do not pass arbitrary embedded text to future reviewers without isolated context and prompt-injection mitigations. Never submit private reviewer identities, third-party corpus bytes or holdout examples via this public packet format.

## CLI interface

```bash
python -m pip install -r core/requirements-test.txt
python -m unittest discover -s core/tests -p 'test_review_harness_v01.py' -v
python -m core.review_harness research/review_harness/review-packet.example.json --mode plan --json
python -m core.review_harness research/review_harness/review-packet.example.json --json
```

Exit 0 means only **structurally valid untrusted metadata**. Exit 1 means metadata rejected. Exit 2 means unreadable, unsafe or malformed input (file capped at 128KiB; no symlink or special file on Linux; duplicate keys, NaN/Infinity and non-UTF-8 rejected).

## What R2 must add to make automatic review real

- Fetch immutable PR diff and latest checks directly via an authorized GitHub connector or permission-scoped API, rather than trusting submitted paths/URLs. Pin the exact base/head and protected branch rules.
- Execute three actual isolated reviewer invocations; record verified invocation receipts, model/config identifiers and distinct contexts. No use of claimed model labels as proof of independence.
- Produce falsifying tests on isolated branches, replay them against pre-fix and post-fix commits, and check assertions with an independent deterministic evaluator.
- Benchmark reviewer defect detection on a truly held-out **non-H3.9.2** set, with honest precision/recall. The four public cases are only examples, not a measured review score.
- Allow T0/T1 development gating on a protected integration branch **only after** enforcement and security verification. T2 research can progress with `machine_tested` and abstentions; T3 gold/rights/authoritative rulings require their own non-machine gate.

### R1 acceptance criteria

Passing the test suite establishes: parsable bounded packets, conservative declared-risk floor, structural check reconciliation, no review-origin spoofing in schema, no eligibility promotion, failure/report separation, CLI safety. **It does not establish an LLM reviewer, CI verification, defect-detection ability or scholarly approval.**
