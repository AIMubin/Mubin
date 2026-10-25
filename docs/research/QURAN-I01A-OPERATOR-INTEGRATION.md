# I0.1a — Operator-qualified metadata retrieval

**Engineering integration pilot, not a platform version.** Mubin stays 0.1.0-alpha. There is no independently authenticated Quran edition, reviewed private tafsir reuse license, enabled juristic inference or public-fatwa authority.

## Existing public-facing pieces

- Q0.1c — loopback-only Quran candidate reader, exact verse references, source notices.
- Q0.1e-b — fixed SHA-256 Tanzil-domain response held in memory, not publisher-signed or editorially approved.
- Q0.1f — six-title Tafsir bibliography with opt-in external navigation; zero private commentary text.
- R0.1c — operator-side private retrieval, metadata-first and HMAC-bound to R0.1a evidence.
- R0.1d — independent human-entered scholarly/rights decision log with signed head and continuity anchors.

## Integration scope

The new Python module engines/quran/research/operator_view.py is a **separate
operator-only CLI**, not a web endpoint or public Quran interface.

1. Validate canonical sura:ayah reference, and verify the signed R0.1d ledger.
   Missing, corrupt, uninitialized or history-rolled-back ledger => refuse.
2. Request only R0.1c private metadata from both read-only adapters; no text
   permit or include-text parameter is available.
3. Filter R0.1d decision history for the exact source/reference and the same
   R0.1a evidence-head SHA. Expired positive scholarly and internal-use states
   revert to UNREVIEWED / legal_review_pending. Source rejections, coordinate
   quarantine and NOT_CLEARED remain restrictive pending explicit future
   independent adjudication/revocation rules.
4. Re-verify R0.1d head/sequence and R0.1a evidence head before returning.
   Head movement => refuse the entire answer.
5. Return only allowlisted source identifiers, adapters, coordinate-presence
   and local decision states. No source text, footnotes, private paths, reviewer
   identities, publisher authentication, legal permission or public authority.

All publication, redistribution, P1, fiqh/fatwa, rights verification and global
scholarly verification flags remain false. Even an INTERNAL_USE_CLEARED or
SOURCE_TEXT_INTEGRITY_REVIEWED decision is local metadata and is not a legal
license or verified editorial certification.

**Important:** The Q0.1c/e-b/f browser remains isolated from private vault
files and operator key material. I0.1a adds operator-side composition only;
it does not yet install a mandatory gate in every public reader or downstream
inference interface. Any future consumer must explicitly implement and test
its separate deny-by-default qualification and licensing gate.

## Local operator usage (examples; never use hosted CI for real data)

Prerequisite: prepare the verified R0.1a evidence registry and explicitly
initialize R0.1d with the pre-existing CLI. The path values below are examples
only; choose storage locations respecting vault and signing-key separation.

    python -m engines.quran.research.qualification init \
      --ledger /private/qualification-ledger.jsonl \
      --anchor-dir /separate/qualification-anchors \
      --key-file /separate/qualification.key \
      --vault /private/operator-vault \
      --evidence-registry /separate/evidence-registry.jsonl \
      --evidence-anchor-dir /separate/evidence-anchors \
      --evidence-key /separate/evidence.key \
      --sidecar-db /private/tafsircenter-quran.db \
      --operator human-operator-id

Local research metadata retrieval:

    python -m engines.quran.research.operator_view lookup \
      --ref 2:1 \
      --vault /private/operator-vault \
      --corpus-db /private/operator-vault/mubin-private-corpus-v01.sqlite3 \
      --sidecar-db /private/tafsircenter-quran.db \
      --registry /separate/evidence-registry.jsonl \
      --anchor-dir /separate/evidence-anchors \
      --evidence-key /separate/evidence.key \
      --qualification-ledger /private/qualification-ledger.jsonl \
      --qualification-anchor-dir /separate/qualification-anchors \
      --qualification-key /separate/qualification.key

The operator CLI never accepts --include-text. No Quran/Tafsir bytes are copied
into the repository, automated CI, logs or browser. Private paths and HMAC
keys remain managed separately by the operator.

## Verification and limits

    python -m unittest core.tests.test_quran_operator_view_i01a \
      core.tests.test_quran_research_unified_r01c \
      core.tests.test_quran_qualification_ledger -v

Ubuntu + Windows GitHub CI uses entirely synthetic adapters and mocked
attestation. Live private-vault testing can be completed only by an authorized
human operator on the local secured machine, and synthetic success must not
be presented as real-world scholarly or legal qualification.

Future gates: real independently reviewed source qualification and rights;
separate legal authorization for publication; qualified source-to-claim link;
rollback-resistant external checkpoints; editorial revocation semantics.
