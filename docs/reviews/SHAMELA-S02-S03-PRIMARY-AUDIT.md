# S0.2/S0.3 — primary maintainer evidence and trust-boundary audit

**Date:** 2026-10-16  |  **Type:** documentation-only feasibility / pre-registration, no code, data ingestion, license grant or AI answer evaluated.

## Reviewed inputs (actual evidence)

1. Inspected current Mubin GitHub main `567e55858a9911a23430ef81f1e41b7a5f26480e` and open S0.1 PR #59 `1fdb3de1ee59637e387bd9fb4ab054b1ef3c0f0b`: PR #59 has 72/72 latest-HEAD CI, two initial Codex findings resolved, *no verified second Codex review*, and is **not merged**. These S0.2/S0.3 docs are independently based on main; neither merges nor mutates #59.
2. Official Shamela download page https://shamela.ws/page/download provides platform packages and portable `database` folder, plus a complete database download option. It includes a contact mechanism but **does not specify a supported DB schema, corpus rights, stable content API or reuse-license permission**.
3. The official Shamela channel https://t.me/s/shamelaws announces its Shamela AI web offering https://shamela.ws/ai and thanks Nuqayah. This supersedes the earlier `coming soon` claim. The web research fetch to `/ai` was unsuccessful; announcement verified, **live features/performance NOT verified**. The official Nuqayah channel https://t.me/s/nuqayah echoes the launch.
4. Shamela's official Android app listing https://play.google.com/store/apps/details?id=com.arabdt.shamla displays support email `mail@shamela.ws`. This is an **unsent inquiry candidate**, not evidence of an answered permission request.
5. Shamela's official channel warns of **uncoordinated paid** third-party AI services claiming to use Shamela books. This is not a blanket legal prohibition on noncommercial research nor a blanket reuse license. Rights must be reviewed separately by stated purpose and edition.
6. Open-source third-party projects containing purported Shamela API wrappers, and paid products referencing Shamela books, **do not constitute official provider API documentation or permission**. They were intentionally excluded as proof of an authorized integration.

## Review of outgoing inquiry document

- It explicitly labels the message `DRAFT, NOT SENT`, requires human approval before sending, names the candidate official address with verification warning, and asks separately about metadata display, automated API, authorized offline sample, source data schema, edition rights and downstream AI training.
- It makes no assertions that permissions or contact replies exist, provides no unauthorized corpus bytes, and does not request anyone to bypass access controls. It warns that user-local database files may contain private preferences/annotations/session data beyond books, preventing indiscriminate upload.
- An explicit rights/intake table keeps all unverified rights **on hold**, including embeddings/RAG, quotes, redistribution and training, and distinguishes site content from modern editor/printed-edition contributions.

## Review of comparative study

- The official product announcement is differentiated from directly observed functionality and third-party account descriptions. No Shamela AI login, output, citations or benchmarks were captured, and no Mubin user-facing release is represented as built.
- The twelve prompts test **methods and citation behaviour** but include no transcribed proprietary book contents, gold religious rulings, copyrighted material or H3.9.2 sealed holdouts.
- All critical numeric dimensions remain N/E unless independently verified; no aggregate winner or accuracy claim. Independent subject-matter review remains required. A working bibliography citation does not automatically establish exact text, reliable hadith grading or a valid fiqh inference.
- The protocol asks for version/terms/access logging and a frozen prompt set, followed by held-out source partitions separate from H3.9.2. It disallows automation unless official terms permit and recorded authorizations exist.

## Negative assurance tests / counterclaims examined

| Tempting inference | Review verdict |
| --- | --- |
| Published download = database schema officially documented | REJECT; format unknown |
| Free browser reading = permission to train Mubin | REJECT; rights unverified |
| Shamela AI announced = verified system latency/accuracy | REJECT; no service trials |
| Citation link from AI = byte-exact signed source | REJECT; needs independent pinned source |
| Scholarly historical text is old = modern edition unrestricted | REJECT; rights/edition may be separate |
| Copy entire local database to GitHub to inspect | REJECT; user annotations/private state could be included |
| A small pilot may use H3.9.2 holdout sources | REJECT; source-disjoint heldout integrity is preserved |

## Merge/readiness recommendation

These docs can be reviewed as **policy/research scaffolding** independent of S0.1 code. No green CI claim should be made for this docs-only branch unless the exact HEAD actually runs a check. No S0.2 acquisition authorization or S0.3 technical evaluation result can be inferred from merging documentation. A second reviewer may inspect the claims, source links and no-go boundaries **after** this primary audit; this does not substitute for rights-holder approval.

Main system remains `0.1.0-alpha`; frozen H3.9.2 benchmarks, source registry, H4 gates and unresolved human adjudications were not touched.
