# B02-B Handoff — MUBIN-SYS-B02-B

**Batch:** MUBIN-SYS-B02 · **Lane:** B02-B (Local Execution Lead)
**Preserved candidate (selection REJECTED under strict gate v3):** `B02B-CASE-6-145` — verse 6:145 + al-Waraqat «الحظر والإباحة»
**Baseline:** re-based on `main` @ `a68bc20` (A01/B01/B02-A/semantic-link merged); initial work began @ `953ffd7`
**Date:** 2026-10-30
**Outcome classification (architect review):** documented research campaign closed with a negative selection result — NOT a successful scientific integration case. Gate execution succeeded; gate passage did not.

> **تحديث STRICT GATE V3 (بعد دمج A01/B01/B02-A — baseline `5306410`):**
> حسب توجيه المعمار، حُكم على المرشحين الثلاثة بشروط مشددة. النتيجة:
> **رفض اختيار أي حالة تحت العتبة الكاملة** — شرط «ثبوت الارتباط الدلالي
> من المصادر» لا آلية اعتماد منفذة له خارج تجربة الأمر المقفلة، وأفضل
> دليل متاح مرسسات مصطلحات معجمية مثبتة (6:145: الأصل+أباحته؛ 49:6: الخبر
> في 4 تفاسير؛ 16:43: العلم — الضعيف) وليست إثباتاً دلالياً معتمداً.
> شرطا المطابقة النصية واكتمال المصادر الأربعة PASS في إيصالات v2
> (`run_hsearch` الفعلي على 54,599 كتلة، `source_unavailable=[]`).
> إطارات 6:145/49:6 محفوظة كمرشحين بحثيين غير معتمدين، وFiqh F0.1 شُغّل
> بحق: `PARTIAL / USUL_APPLICATION_NOT_EXECUTED`. لم تُخفض العتبة.
> الإيصالات: `selection-verdict-v3.json`، `gate-semantic-bridge-v1.json`،
> `stage-fiqh-f01-run-v1.json` (مساحة خاصة).
>
> **إضافة B02-C التشخيصية (P3):** شُغّلت نواة A01 الكاملة (`run_case`)
> على المصادر المحلية المثبتة لحالة 6:145: quran **OK** (لقطة partial
> external_unverified مشتقة من القاعدة المثبتة)؛ tafsir **OK** (5 أعمال)؛
> hadith **OK** (23 نافذة إشارة — كاشف فقط، البحث الكامل إيصال H-Search-01
> منفصل)؛ usul **OK** (تتبع 3 قواعد، القولان محجوبان بالاعتراضات)؛ fiqh
> **UNDETERMINED** (`OPINION_SOURCE_NOT_IN_UPSTREAM_EVIDENCE` — لا عقدة
> في النواة تبتلع مقاطع الأصول المثبتة: فجوة نواة حقيقية مسجلة). الحالات
> الأربع منفصلة والفجوات محمولة، بلا ادعاء استدلال مكتمل وبلا ادعاء
> تكامل حالة مختارة (الاختيار ما زال مرفوضاً تحت البوابة الصارمة).
> الإيصالات: `b02c-kernel-receipt-6-145-v1.json` +
> `b02c-diagnostic-run-v1.json`.
>
> **إضافة B02-C.2 (main @ `217de11` — Source-Bound Diagnostic Replay):**
> أُعيد التشغيل مع `usul.bind_source_spans`: **4 مقاطع ورقات مثبتة
> بالبايت** (بصمة الملف الكامل + بصمة المقطع + إزاحات خام) → 4 مقابض
> `ev.usul.*` داخل نتائج النواة، وfiqh انتقل من UNDETERMINED إلى
> **PARTIAL** بكلتا القولين مربوطين بالمقابض (33 مرجع دليل) مع بقاء
> `opinion_source_attribution_verified=false` و
> `source_claims_verified=false` و`juristic_conclusion=null`
> و`SOURCE_SPAN_MATCH_NOT_OPINION_ATTRIBUTION`. حكم بوابة الاختيار
> لم يتغير، وحالة MACHINE_SUPPORTED لم تتحول لاعتماد علمي، وإيصالات v1
> لم تُمس. الإيصالات: `b02c2-kernel-receipt-6-145-v1.json` +
> `b02c2-diagnostic-run-v1.json`.
>
> **إضافة B02-C.3 (main @ `74e3cd9` — Cross-Engine Evidence Chain، الجانب المحلي):** مادة السلسلة عبر المحركات مجمّدة من الإيصالات المجمدة حصراً (بلا تشغيلات جديدة): 5 عقد و4 حواف — quran→tafsir `ESTABLISHED_BYTE_PINNED`؛ tafsir→hadith `CANDIDATE_MATCH_LEXICAL` (باعتراضَي عدم ثبوت الهوية واستبعاد رابط artifact)؛ hadith→usul `SEMANTIC_LINK_UNASSESSED_AT_THIS_HOP` (**رفض fail-closed: لا مُقيّم منفذ لهذه الحلقة**)؛ usul→fiqh `STRUCTURALLY_BOUND_RESEARCH_ONLY` (باعتراضَي عدم إسناد وعدم تنفيذ تطبيق). السلسلة ككل: `PARTIALLY_BOUND_CHAIN_OPEN`، `scientifically_established_chain=false`. الإيصال: `b02c3-evidence-chain-6-145-v1.json` (metadata-only، صفر حرف عربي).
>
>
> **إضافة B02-C.5 (main @ `3b02aa469` — Plan-Bound Execution Provenance):** أُعيد تنفيذ الخطة المصدرية نفسها عبر `run_case_plan_bound` بمفتاح تدقيق خاص (48 بايت، خزنة المشغل، لم يغادر البيئة): `PLAN_AND_RESULT_BOUND_OPERATOR_LOCAL_ONLY`، 6 عقد و5 حواف DAG معلنة من الخطة، التزاما HMAC-SHA256 للمدخلات الخاصة والمخرجات (plan/receipt hmac محفوظان في الإيصال العام)، `verify_plan_bound_replay=True`، واختباران سلبيان رفضا تدليك الحالة ومفتاحاً خاطئاً. الخطة الكاملة وإيصال التشغيل في الخزنة الخاصة؛ المنشور التدقيق المنقح فقط: `b02c5-plan-bound-audit-6-145-v1.json` (بلا مدخلات عُقد ولا نصوص). `scientific_chain_established=false` وحكم الاختيار كما هو.
>
> **إضافة B02-C.6 (main @ `c18b439` — Hadith Witness Identity Qualification، الجانب المحلي، الخطوتان 1-2):** كتلة الشاهد L144309 (290 حرفاً) مستخرجة ومُرمَّزة آلياً: أثر إسناد (أخبرنا ×1)، لا نص قرآني مقتبس داخلها، لا مؤشرات نقدية في نطاقها؛ والمتن المرشح مصنف NARRATION_FRAGMENT_CANDIDATE. **إزاحات المقتطفات المنشورة محارف Unicode وليست بايتات UTF-8، وتستلزم تحويلاً مثبتاً قبل عقد الهوية.** **البحث عبر المصادر الأربعة:** الشاهد مُشاهَد في مصدر واحد فقط (البيهقي — مصدر الاكتشاف) وTirmidhi/ NasbRaya/Tuhfa كلها NO_MATCH_IN_THIS_SOURCE مع علم أن العدم في نطاق البحث لا يدل على العدم مطلقاً. **الضابط السلبي** (كتلة L142475): أبلغ الفحص المحلي أن المقطع المشترك من نص الآية 6:145 بعد التطبيع (احتواء معجمي؛ النص نفسه محجوب عن GitHub) — الفصل بين النص المقتبس والمرشحات يعمل. **قرار الهوية: لم يُصدر — عقد mubin-hadith-witness-identity/1.0 متاح على main @ 3ace886، والتشغيل المحلي عليه لم ينجز بعد**؛ القراءة المؤقتة: شاهد أحادي المصدر، التعدد المصدرية غائب، الهوية UNDETERMINED.
> **إضافة عقد الربط الدلالي (P2 — main @ `a68bc20`، PR #130):** شُغّل
> `evaluate_research_link` على مصادر مثبتة بأربع حالات: **6:145 وساطة
> تفسيرية → `MACHINE_SUPPORTED_RESEARCH_ONLY`** (مرسسة تفسيرية بايتية على
> المقتطف المتني غير القرآني؛ 2 مؤيد + 1 ناقد-نطاق؛ ذاتية-التشغيل
> `model_independence_established=false`؛ ليس إجازة scholarly)، **49:6 →
> `CONTESTED`** (تحفظ صادق: الآية في التثبت من نبأ معين لا في تصنيف
> الأخبار)، **ضابط 2:8 الزائف → `CONTESTED`** (رفض)، **متغير معجمي →
> `LEXICAL_ONLY`**. أربعة/أربعة مطابقة للتوقع. الإيصال: `sl-gate-v1.json`
> + إيصالات المراجعات في `sl-runs/` (خاصة).
>
> **إضافة جسر B02-A:** بُنيت حزمة P0 حقيقية دنيا للجانب الأصولي المحفوظ
> (2 مصادر، 4 أدلة بنصوصها الحرفية — خاصة، منهجية 1، قولان كقاعدتي
> deduction مسودتين، استنتاج واحد خلاصته UNDETERMINED، اعتراضان مفتوحان
> متقابلان، إثبان UNDETERMINED) → `validate_bundle` ناجح (0 مشاكل) →
> `project_p0_bundle` أنتج عرضاً منقحاً بلا نصوص (16 عقدة/35 حافة) →
> `verify_redacted_projection=True` و`verify_private_projection=True`
> واختباران سلبيان رفضا تلاعب الحافة والنص المزور. العرض المنقح هنا:
> `p0-projection-b02b-6-145-v1.json` (ملزم بـ`private_bundle_sha256`
> في إيصال التشغيل الخاص). حزمة P0 الكاملة تبقى في الخزنة الخاصة.

## النتيجة

الجدول التالي يؤرخ **التشغيل المحلي الأول** للمرشح غير المختار؛ وليس حكماً باجتياز بوابة الاختيار. في تشغيل B02-C الأحدث استُخدم F0.1 وأعاد `UNDETERMINED` كما توضحه الإضافة أعلاه.

حملة بحثية واحدة محدودة النطاق أُغلقت مراحلها الأربع الأولية المنفذة (من خمس)
على المصادر المحلية المثبتة، بلا أي نص مصدر في هذه الحزمة — أسماء وسجلات
وبصمات فقط:

| المرحلة | المحرك/العقد | النتيجة | الإيصال (خاص + payload sha) |
| --- | --- | --- | --- |
| Quran+Tafsir | T0.1/T0.2 pinned lookup+passages | 5/5 تفاسير، 128 مقطعًا | `stage-quran-tafsir-6-145-v1.json` |
| Hadith | H-Search-01 replay v1 | 23 نافذة، 54,599 كتلة، 2 روابط: 1 `CANDIDATE_MATCH` جوهري + 1 artifact نص قرآني | `hsearch-6-145-gate-v2.json` |
| Usul | U0.1 one-step executor | قاعدتا القولين `BLOCKED_BY_OBJECTION` (اعتراضات مفتوحة متقابلة من النص نفسه)، خلاصة `UNDETERMINED`، بلا ترجيح | `stage-usul-6-145-v1.json` |
| Fiqh | F0.0 | فجوة معلنة صراحة، بلا أي مخرج حكم | `stage-fiqh-6-145-v1.json` |

بوابة الاختيار نُفذت على خمس آيات مرشحة بجميع إيصالاتها المجمدة
(`hsearch-*-gate-v2.json`) مع تصنيف آلي قابل للتكرار
(`gate-classification-v1.json`): 5:87 و9:122 و16:43 رُفضت (صفر مرشحات جوهرية
— كلها artifacts نص قرآني أو لا شيء)، و49:6 وصيفة بمرشح جوهري واحد
(إيصالاتها محفوظة كحالة ثانية لاختبار Evidence Graph متعدد الحالات).

**حدود صريحة:** `CANDIDATE_MATCH` تطابق معجمي محدد الإطار فقط؛ ليس هوية
حديث ولا درجة ولا دلالة شرعية. تتبع U0.1 محاكاة افتراضية أحادية الخطوة
(`propositional_demo`) وليس تنفيذًا أصوليًا معتمدًا.

## الفجوات الفعلية المعلنة

1. **Fiqh F0.0 (تاريخياً في التشغيل الأول)**: لم يكن محركاً منفذاً. لاحقاً شُغّل F0.1 البحثي وكانت النتيجة `PARTIAL` في التشغيل المستقل و`UNDETERMINED` في النواة؛ لا حكم فقهي ولا إثبات نسبة قول.
2. **رابط UT-01.2/3 المعجمي** لهذا المقطع يتطلب سلسلة Stage05–08 لـ`w2-h2-017`
   (لم تُشغّل بعد) — فجوة موثقة لا نتيجة مفتركة.
3. **`engines.e2e.research_slice` القديم فقط يقفل السؤال** على حالة الأمر/2:43
   (`E2E_QUESTION_OUT_OF_SCOPE`) — تمديد النواة لحالات آيات اعتباطية مطلوب
   في B02-A/B02-C. هذه نقطة الاندماج الأولى الملموسة بين مسارينا.
4. **ماسح المرشحات v1** ينتج إيجابيات زائفة لافتتاحيات عامة — قيد موثق،
   والبوابة اعتمدت التأكيد المزدوج + التصنيف الآلي بدلًا منه.

## المطلوب من مسار B02-A (يُوصل عبر الـPR)

- عقد Evidence Graph يبلع إيصالات المواقع الأربعة أعلاه عبر payload digests.
- قرار هندسي: هل تُعمَّم `research_slice` (سؤال/آية بارامترات) أم تُبنى طبقة
  تجميع جديدة فوق T0.3/H-Search/UT؟ نوصي بالتعميم المقيد.

## التكرار (من جذر المستودع)

```bash
python -m unittest core.tests.test_hadith_hsearch01 core.tests.test_tafsir_t01 core.tests.test_usul_ut011 core.tests.test_inference_foundation -v
```

الإيصالات الخاصة وغير القابلة للعزم تعيد إنتاجها بما يطابق توثيق
`engines/hadith/hsearch/README.md` (مسار الكاش = مجلد ملفات `.source` مباشرة).
الأدوات المحلية المستخدمة: `b02b_case_scan_v1.py`، `stage_*.py`،
`build_package.py` في مساحة الإيصالات الخاصة.

## سلامة البيانات

- لا نصوص مصادر ولا مسارات خاصة في هذه الحزمة.
- لم تُمس H3.9.2 المجمدة ولا holdouts ولا قرار الـ158.
- `VERSION.yaml` لم يُغير؛ النظام يبقى `0.1.0-alpha`.
