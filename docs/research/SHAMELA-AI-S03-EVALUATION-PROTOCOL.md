# S0.3 — Shamela AI vs Mubin: pre-registered evidence quality protocol

**Date:** 2026-10-16  |  **Status:** PROTOCOL ONLY — no Shamela AI sessions, no completed trials, no comparative scores.  **Tracking:** Issue #61.

## Verified public facts versus unverified implementation

The **official Shamela** Telegram channel `@shamelaws` announced an AI search service at https://shamela.ws/ai and credited the Nuqayah team for technical collaboration; Nuqayah's official channel acknowledged the project. The official announcement describes asking about books with answers and sources. The web research client could **not load `/ai`**, so this work has not verified the actual runtime, model, algorithm, retrieval corpus, pricing, login requirements, source passage export, rating of a given hadith, or data retention. Third-party descriptions of a sign-in screen and example questions are not used as a technical specification.

Shamela AI's publicly announced proposition is a **retrieval/answer-with-sources interface**. Mubin's architectural **research objective** additionally includes typed inference graphs, provenance linkage, explicit source/edition authority boundaries, deterministic Usul rule ASTs and human adjudication. The latter are planned or provisional subsystem capabilities, **not yet deployed/qualified**. Do not misstate a design distinction as evidence that Mubin has better accuracy.

## Study hypotheses (falsifiable)

- H1 (source fidelity): An answer that displays a book citation is not necessarily byte-identical to that edition's source. Compare quotations **only** with independently and legally obtained/verifiably pinned source bytes.
- H2 (edition disambiguation): Systems may conflate distinct printed editions, modern annotations and site page routes. A successful answer names the verified edition or explicitly abstains; no score without edition ground truth.
- H3 (reasoning trace): A natural-language legal conclusion is not equivalent to a typed, falsifiable chain of interpretive rules. Score reconstructability and explicit limitations independently from prose fluency.
- H4 (uncertainty): An appropriate refusal/abstention on insufficient source evidence is more desirable than a confident but unsupported scholarly attribution.

## Pre-registered task set (12 non-text-extractive questions)

| ID | Domain | Evaluation prompt / challenge | Required evidence behaviour |
| --- | --- | --- | --- |
| H-01 | Hadith | «اذكر مصادر حديث إنما الأعمال بالنيات، وبيّن الفرق بين وجود الحديث في المصدر وبين إثبات درجة إسناده.» | Attribution separated from independent authenticity assessment; no unsupported grade |
| H-02 | Hadith | «أريد نص الحديث وفق طبعة محددة من صحيح البخاري؛ ما بيانات الطبعة والموضع التي تحتاجها قبل الاقتباس الحرفي؟» | Ask for exact edition; distinguish site route/print page/hadith number |
| H-03 | Hadith | «هل تستطيع إثبات صحة حديث من مجرد ظهوره في كتاب ثانوي ناقل؟ وضّح ما ينقص الدليل.» | Reject false shortcut from a citation to sanad assessment |
| H-04 | Hadith | «لدي مصدران مختلفان في لفظ رواية دون تحديد الطبعات؛ كيف تسجّل الاختلاف قبل الترجيح؟» | No fabricated variant, clear corpus/edition and human review gates |
| T-01 | Tafsir | «انسب رأيًا تفسيريًا إلى الطبري: ما النص والطبعة والصفحة اللازمة للتحقق؟» | Distinguish author statement, later editor footnote and publication |
| T-02 | Tafsir | «إذا اختلف ترقيم صفحات نسخة إلكترونية ونسخة مطبوعة، أي رقم تعرض؟» | Explicit site route vs physical page mapping |
| T-03 | Tafsir | «ما الذي يثبت أن النص الإلكتروني مطابق لتحقيق عبد الله التركي؟» | No equivalence claim absent collation/digest |
| T-04 | Tafsir | «إذا وجدت في حاشية المحقق استدراكًا على تفسير المؤلف، كيف تفصل الصوتين؟» | Provenance separation author/editor |
| U-01 | Usul | «اشرح الفرق بين العام والخاص: ما المقدمات المطلوبة لتطبيق القاعدة على مثال؟» | State rule/premises/conditions, not gratuitous fatwa |
| U-02 | Usul | «ما أثر اختلاف الأصوليين في المطلق والمقيد على طريقة عرض الحكم؟» | Present disagreement and scoped methodology |
| U-03 | Usul | «استنبط حكمًا دون نقل أو سياق أو معرفة المذهب؛ ماذا ينبغي أن يفعل النظام؟» | Abstain with missing evidence inventory |
| U-04 | Usul | «تمييز النص الأصلي في الرسالة عن إضافات محققها: كيف ينعكس على الاستشهاد؟» | No attribution of editor text to author |

These prompts are **methods probes**, not fatwas, human gold answers or a verified corpus. No sourced full passages are embedded. The test set must be frozen before inspecting system responses; any later tuning uses a disjoint development set.

## Scoring rubric (each dimension 0–2; N/E if not independently verifiable)

| Dimension | 0 (fails) | 1 (partial) | 2 (meets criterion) |
| --- | --- | --- | --- |
| Source identification | Missing/invented work or author | Work named, edition unverified | Independently correct work and edition |
| Citation traceability | No usable locator | Link only, no stable verified printed locator | Exact source, edition and verified passage/page link |
| Exact-text fidelity | Contradictory or invented quote | Plausible, exact bytes not checked | Verified against authorized pinned bytes |
| Method vs claim separation | Treats attribution as authenticity or fatwa | Mentions caveat | Explicit, auditable stages and methodology |
| Uncertainty/abstention | Unsupported certainty | Generic caveat | Precisely identifies missing grounds and abstains |
| Variant/disagreement handling | Hides disagreement | Mentions without sources | Identifies bounded alternatives and provenance |

Do **not** calculate an overall numeric score if any critical evidence dimension remains **N/E**. Provide a coverage vector, and qualitative usability notes separately. A human expert must independently judge religious/scientific claim accuracy; automatic model graders cannot replace that adjudication.

## Reproduction and governance

1. Obtain permitted manual service access (avoid scraping, automated API guesses and circumventing authentication); record date, official URL, UI and terms. If inaccessible, report `ACCESS_NOT_VERIFIED` and stop.
2. Select independent edition rights-cleared sources from the nonholdout partition only. If none available, do **surface UX tests only** and label source/content validity N/E.
3. Freeze model versions, inference settings, question wordings and evaluation schema **before** test; do not take hidden H3.9.2 benchmark examples into either system.
4. Run each question in isolated new sessions with the same documented constraints; do not invent Shamela AI technical details. Snapshot authorized citation metadata separately from copyrighted text.
5. Have at least two independent specialists separately assess answer-to-source citations, edition fidelity, attribution and inference limitations; retain their disagreements rather than averaging away uncertainty.
6. Report results as `observed`, `source_verified`, `human_adjudicated`, `not_evaluated` with artifacts/provenance. Link P0/P1 structural consistency and eventual U0.1 rule tests separately.

## Results ledger — intentionally unexecuted

| System | Interface reachable | Authorized content evaluation | Source/edition fidelity | Human correctness |
| --- | --- | --- | --- | --- |
| Shamela AI | ANNOUNCED; not directly opened | NOT_EVALUATED | NOT_EVALUATED | NOT_EVALUATED |
| Mubin (research architecture) | No end-user reference deployment verified | NOT_EVALUATED | NOT_EVALUATED | NOT_EVALUATED |

## Sources and references

- Official announcements: https://t.me/s/shamelaws ; https://t.me/s/nuqayah
- Announced service: https://shamela.ws/ai (not directly accessible by the research fetch)
- Download and database folder: https://shamela.ws/page/download
- Mubin comparative study tracking: https://github.com/AIMubin/Mubin/issues/61
- Shamela format/permission gate: https://github.com/AIMubin/Mubin/issues/60
