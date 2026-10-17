# Mubin heritage-first source-use routing — Stage A

**Status:** proposed research governance, not legal advice or content clearance. **System release:** remains `0.1.0-alpha`. Tracks [Issue #63](https://github.com/AIMubin/Mubin/issues/63).

## Working policy

Mubin is an open, non-profit scholarly research project. Classical Islamic knowledge should remain accessible for legitimate research. **The absence of a publisher's new written reply is not a project-wide stop condition** when a particular source and action already have an applicable documented legal basis. This policy does **not** treat every ancient book, modern edited edition or downloadable database as automatically open source.

1. Distinguish each **original classical text** from separately edited texts, investigator notes, translations, publisher databases and personal annotations.
2. For every source layer and intended use, an operator records the claimed basis: original-text public domain, specifically applicable statutory exception, explicit scope-bound license, or **unverified**.
3. A source's legal position depends on its jurisdiction, provenance, publication and rights facts. A human source/rights reviewer must check them; this module only inspects supplied declarations.
4. Public bibliographic metadata and links may be indexed within a **bounded facts-only scope**, without copying a protected database as a whole.
5. Source-specific complaints are logged and the affected source is held while reviewed; unrelated research and synthetic tests continue. A credible report is not ignored because of the project's non-profit purpose.
6. Original text in the public domain does not automatically clear a particular modern electronic transcription, edition, editor's additions or whole publisher database.
7. A proportionate research/AI exception is not a license for bulk republication, unrestricted redistribution, or commercial reuse. Rules for text copying, public display and inference output must be independently checked.
8. Preserve the H3.9.2 held-out source/family partition, independent human adjudication and explicit nonpromotion gates. No rule or hadith record is qualified by passing this routing helper.

## Programmatic interface

`core.source_policy.assess_source_use(SourceUseRecord, purpose)` yields one of `proceed`, `restricted`, `source_hold`, `invalid`, always with `assurance="operator_declarations_only"`.

**Critical semantics:** `proceed` means *only* that fields in a source-use request follow these policy gates. It is **not** a license, an authoritative legal opinion, a verified custody receipt, an actual AI-use audit event, or authorization to ingest any raw book into Mubin. Downstream source acquisition and content processing remain **closed** until separate source- and purpose-specific verification.

This Stage A PR intentionally excludes `core/source_policy/intake.py`, private `usage_log.py`, all Usul U0.1–U0.6 code/fixtures and production text acquisition. Those modules require separate reviewable code PRs.

## Receiving and resolving rights or attribution complaints

Use the public `RIGHTS_NOTICE.md` and GitHub issue template. Ask for precise source URL/ID, edition and issue; never publish private identity documents, license contracts or confidential content in a public issue. Review scope, hold and correct only the affected material when warranted, retain an audit of disposition outside confidential repositories, and continue unrelated work. A complaint procedure does not retroactively legalize unauthorized use.

## Basis for legal review

The project's local policy research cites the Saudi 2026 copyright law and implementing regulation concerning proportionate non-profit research, lawfully obtained AI development copies, quotation, databases, authors' moral rights and applicable constraints. **Whether any specific provision applies to a particular text is deliberately outside this Python module.** The developer must consult an appropriate qualified reviewer for real use, including rules in other relevant jurisdictions.

## Reproduction

```bash
python -m unittest discover -s core/tests -p 'test_heritage_rights_routing.py' -v
python -m unittest discover -s core/tests -v
```

A successful suite proves these *synthetic routing conditions*, not the accuracy of source declarations. See the versioned primary audit in `docs/reviews/HERITAGE-FIRST-STAGE-A-PRIMARY-AUDIT.md`.
