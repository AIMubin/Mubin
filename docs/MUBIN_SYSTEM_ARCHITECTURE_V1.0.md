# Mubin System Architecture v1.0 — Five-Engine Integration Design

**المشروع:** مُبين (Mubin)  
**نوع الوثيقة:** معمارية النظام وعقود التكامل وخطة التنفيذ AI-native  
**إصدار الوثيقة:** Architecture v1.0 — Design Baseline  
**إصدار النظام المرجعي:** `0.1.0-alpha` (لا يعني هذا المستند ترقية إصدار النظام)  
**المصدر المرجعي:** [AIMubin/Mubin](https://github.com/AIMubin/Mubin) — `main` عند `953ffd703e7df285cd062a316753c9e665e33169`، 2026-10-29  
**حالة التنفيذ:** تصميم مستهدف؛ لا تعني صياغته أن المكونات الجديدة موجودة أو مجرّبة.

---

## 1. القرار التنفيذي والرؤية

**مُبين منظومة معرفية واستدلالية إسلامية واحدة، لا مجموعة أدوات مستقلة.** يتكون جوهرها المعرفي من خمسة محركات واجبة الوجود: **Quran, Tafsir, Hadith, Usul, Fiqh**. وتعمل جميعها من خلال **Mubin Integration Kernel** وبالاعتماد على **Evidence & Knowledge Core** مشترك، بينما تُقاس سلامة التنفيذ والأدلة بواسطة **Engineering & Evaluation Plane**.

**معيار اكتمال النظام:** ليس اكتمال محرك منفرد أو وصول محرك الحديث إلى رقم داخلي مرتفع، بل القدرة على تشغيل حالة معرفية حقيقية محدودة يساهم فيها كل واحد من المحركات الخمسة بدور مميز، مع مخرجات مترابطة، وإسناد قابل للتتبع، وفحص استدلالي، وإمكانية إعادة التشغيل، وإظهار الخلاف أو الامتناع عند نقص الأدلة.

**قرارات معمارية مُلزمة للتطوير:**

1. **AI-native by default:** وكلاء AI ينفذون التحليل، والبرمجة، والاختبارات، والنقد، والتصحيح، والتوثيق تلقائياً؛ لا توجد موافقات بشرية دورية مفروضة على التقدم الهندسي الداخلي.
2. **Parallel-first:** تُطوَّر المحركات الخمسة بالتوازي مقابل عقود مشتركة صغيرة مثبتة الإصدار، باستخدام mocks/fixtures عندما لا يتوافر تنفيذ محرك آخر بعد.
3. **Thin integration, not a giant orchestrator:** نواة التنسيق تتحكم في دورة الطلب، لا في المعرفة المتخصصة، ولا تصبح قفلاً عاماً أو طابور تنفيذ وحيداً.
4. **Reuse before rewrite:** إعادة استخدام `core/inference/validator.py`، وعقود P0، ووحدات Tafsir/Usul/Hadith/E2E الحالية؛ لا تُكرر محركات الاستدلال أو أنظمة الدليل.
5. **Local-first modular monolith:** وحدات Python مستقلة منطقياً داخل عملية/تطبيق واحد، مع مهام متزامنة بحسب الحاجة، ومخزن محلي قابل للاستبدال؛ لا Microservices أو Kubernetes أو message broker كمتطلبات أولية.
6. **Evidence before assertion:** تمييز النص المصدري عن المرشح الآلي، والاستنتاج عن النقل، والتحقق البنيوي عن صحة الدلالة. لا يُختلق إثبات مصدر أو مراجعة عالم أو نتيجة benchmark.
7. **Development is not publication:** لا فحص تراخيص نشر ولا اعتماد علمي بشري كشرط لاستخراج البيانات أو اختبارها أو تطوير المحركات داخلياً. تُنقل قرارات الترخيص وإعادة التوزيع والاعتماد الرسمي إلى بوابة نشر منفصلة، دون افتراض أن الاستخدام الداخلي يبيح الاستعمال المخالف للقانون.
8. **Finish integrated slices:** كل دفعة عمل تنتهي بقدرة تشغيلية أو عقد قابل للاختبار، وليس بمزيد من الوثائق أو حملة benchmark غير مرتبطة بالتكامل.

## 2. الواقع الحالي وحدود الادعاء

| المكوّن | الحالة المثبتة في المستودع | فجوة المعمارية المستهدفة |
|---|---|---|
| Quran | `Q0.3` مؤهل هندسياً لنطاق الاستيراد/القراءة المثبت، وليس لكل الاستخدامات | واجهة موحدة وقاعدة نص مرجعية مثبتة وإرجاع الأدلة عبر العقد المشترك |
| Tafsir | `T0.3` بحث محلي وإحالات ومقاطع وقرائن مرشحة | تمثيل أقوال تفسيرية وعلاقات دلالية قابلة للفحص |
| Hadith | `H3.9.2` تأهيل بحثي وH-Search للمرشحات | API موحد للروايات والطرق والأحكام المنسوبة وقيم عدم اليقين |
| Usul | `U0.1` محاكاة محدودة؛ جسور P0 وروابط مرشحة أوسع نطاقاً | قواعد رسمية قابلة للتنفيذ، شروط/موانع، تتبع تطبيق القاعدة |
| Fiqh | `F0.0` مخطط فقط؛ README بلا محرك عامل | نموذج المسألة والأقوال، والتجميع والتقييم والتوقف المسبب |
| Integration | P0 validator وE2E slices مقيدة؛ تكامل بحثي جزئي | Kernel موحد، عقود طلب/استجابة، تخطيط وتنفيذ واستئناف |

**لا يجوز وصف تكامل مرجع آية مع تجربة قاعدة أصولية اصطناعية بأنه تحقق دلالي مكتمل.** ولا يعني نجاح اختبار JSON Schema أن حكماً فقهياً صحيح. تبقى بيانات المصدر المحلي والنتائج الحقيقية متميزة عن fixtures الاصطناعية.

## 3. البنية المنطقية

```text
                       MUBIN USER / RESEARCH API / CLI / UI
                                      |
                    +------------------------------------+
                    |     MUBIN INTEGRATION KERNEL       |
                    | Planner | DAG Runner | Case State |
                    | Budget  | Trace      | Aggregator |
                    +------------------------------------+
                      |       |       |       |       |
             +--------+-------+-------+-------+-------+--------+
             |        |       |       |       |                |
          QURAN    TAFSIR   HADITH   USUL    FIQH      AI ASSISTANTS
             |        |       |       |       |       (propose/critique)
             +--------+-------+-------+-------+-------+--------+
                                      |
                   EVIDENCE & KNOWLEDGE CORE (shared)
                 Source Pins | Evidence | Graph | Methodology
                 Claim/Rule  | Opinion  | Case  | Revision IDs
                                      |
                       ENGINEERING & EVALUATION
                    Contracts | Tests | Replay | Audit
                                      |
                    OFFICIAL PUBLICATION BOUNDARY
                  Rights / Formal Approval / Distribution
```

هذا **مخطط اعتمادات منطقية** لا سلسلة اتصالات متسلسلة. يمكن لأي محرك إنتاج نتيجة مباشرة، ويمكن لخطة البحث تشغيل محركين أو أكثر بالتوازي. ويستدعي Fiqh محركات الأدلة والأصول عبر عقود Kernel، لا عبر استيراد تفاصيلها الداخلية.

### 3.1 المسؤوليات المعزولة

- **Quran Engine:** النص المثبت، الإحداثيات (سورة/آية)، المقاطع، سياق الآيات، اختلاف المرجع/الرواية عند دعمه صراحة. لا يفسر ولا يصدر حكماً.
- **Tafsir Engine:** أقوال المفسرين، إسنادها لمواضعها، اختلاف الأقوال، قرائن السياق؛ يميز *النص المنقول* عن *فهم AI المقترح*.
- **Hadith Engine:** الأحاديث، المتون، طرق الإسناد، الرواة، الشواهد، العلل المرشحة، الدرجات المنسوبة إلى مصادرها؛ لا يحوّل درجة مرشحة إلى حكم حديثي معتمد.
- **Usul Engine:** القواعد والمناهج وشروط التطبيق والقرائن والموانع، والتطبيق الرسمي المحدود والاعتراضات. صياغة قاعدة نصية لا تعني أنها قابلة للتنفيذ آلياً.
- **Fiqh Engine:** تصوير المسألة، الأقوال والمذاهب والسوابق، طلب الأدلة، بناء الفرضيات والاستنتاجات، التعارض والترجيح بحسب منهج محدد، أو `UNDETERMINED`. لا يختزل إلى واجهة تلخيص LLM.
- **Integration Kernel:** تخطيط وتنفيذ وتخزين سياق الطلبات وتوزيعها؛ لا يقرر صحة حديث أو حكم أو تفسير.
- **Evidence Core:** توحيد الهوية والروابط والتتبع والمناهج؛ لا يعمل بوصفه «قاعدة حقائق» تستبدل المصادر.

## 4. نموذج المعرفة المشترك Canonical Knowledge Model

يُعتمد نموذج علاقات موحد، مع بقاء مخازن المصادر الخاصة بكل محرك مستقلة. الكيانات الأساسية:

| الكيان | الحقول/العلاقات الحاسمة |
|---|---|
| `SourceWitness` | `source_id`, `work_id`, `edition_or_witness`, `snapshot_sha256`, `locator_scheme`, `version` |
| `EvidenceSpan` | `evidence_id`, `source_id`, `locator`, `exact_text_hash`, `verification_scope` |
| `QuranVerse` | `verse_id`, `witness_id`, `surah`, `ayah`, `text_hash` |
| `TafsirStatement` | `statement_id`, `verse_refs`, `author/work`, `evidence_refs`, `interpretation_status` |
| `HadithReport` / `HadithRoute` | `report_id`, `matn_refs`, `route_ids`, `narrator_refs`, `attributed_assessments` |
| `UsulRule` / `RuleApplication` | `rule_id`, `methodology_id`, `preconditions`, `exceptions`, `formalization_status`, `trace` |
| `FiqhCase` / `JuristicOpinion` | `case_id`, `issue_facts`, `opinion_refs`, `school/profile`, `evidence_refs` |
| `Claim` / `Inference` / `Objection` | `origin`, `premises`, `rule_refs`, `defeaters`, `modality`, `assessment_status` |
| `CaseExecution` | `request_id`, `plan`, `node_results`, `event_log`, `snapshot_refs`, `outcome` |

**القاعدة:** كل علاقة دلالية بين محركين تحمل نوعها (`CITES`, `EXPLAINS`, `MENTIONS`, `SUPPORTS`, `CONTRADICTS`, `APPLIES_RULE`, `DERIVES`, `PROPOSED_MATCH`) ومصدرها وطريقة إنشائها وحالتها. `PROPOSED_MATCH` ليس `SUPPORTS`، والتطابق اللفظي ليس دليلاً على صحة النسبة أو الدلالة.

يُستخدم مخزن علائقي محلي للكيانات والفهارس/الحواف مع بحث نصي مناسب؛ **لا تُفرض قاعدة graph مستقلة** قبل ظهور قياس يبررها. يمكن استخدام SQLite WAL لنسخة محلية أولية مع قفل كتابة قصير ومعاملات محدودة، وتوسعة التخزين لاحقاً عبر adapter. تُحفظ ملفات corpus كبيرة بصورة مستقلة ومثبتة البصمة، ولا تُنسخ في كل Case.

### 4.1 أربع حقائق لا يجوز خلطها

1. **Byte fidelity:** تطابق النص المخزن مع لقطة معلومة.
2. **Attribution:** نسبة المقطع إلى مصدر ومؤلف وموضع محدد، وقد تبقى مرشحة.
3. **Semantic validity:** صحة فهم النص وتطبيق القاعدة في نطاق السؤال.
4. **Formal publication status:** أهلية إتاحة النص أو الحكم للجمهور بوصفه مادة منشورة أو معتمدة؛ لا تدخل مسار التطوير الداخلي.

تبقى الحالة التقنية للاستدلال `SOURCE_ATTESTED / CANDIDATE / FORMALLY_CHECKED / CONTESTED / UNDETERMINED` بحسب الأدلة الفعلية؛ وهي ليست شهادة اعتماد شرعي. تُفصل بيانات نشر الحقوق/الاعتماد في manifest مستقل يُبنى عند الإطلاق ولا يُطلب من كل Developer Agent.

## 5. عقد المحرك الموحد — Engine Contract v1

تنشأ واجهة صغيرة في `core/contracts/` وتُثبت بإصدار `engine-contract/1.0`، مع الاستفادة من `schemas/inference-foundation.schema.json` دون استبداله. لا يُلزم المحرك بإرجاع نص خام إذا كانت العملية تُرجع مراجع فقط.

```json
{
  "contract_version": "engine-contract/1.0",
  "request_id": "req-001",
  "case_id": "case-001",
  "engine": "hadith",
  "operation": "find_relevant_reports",
  "inputs": {"evidence_refs": ["evidence-001"], "query": "..."},
  "methodology_profile_id": "profile-research-v1",
  "source_snapshot_ids": ["snapshot-001"],
  "limits": {"timeout_ms": 8000, "max_results": 50},
  "idempotency_key": "case-001:hadith:find:1"
}
```

```json
{
  "contract_version": "engine-contract/1.0",
  "request_id": "req-001",
  "engine": "hadith",
  "engine_version": "H-internal",
  "status": "PARTIAL",
  "findings": [{"kind": "CANDIDATE_MATCH", "ref": "finding-001"}],
  "evidence_refs": ["evidence-007"],
  "uncertainties": ["GRADE_NOT_ESTABLISHED"],
  "errors": [],
  "provenance": {"snapshot_ids": ["snapshot-001"]},
  "trace_id": "trace-001"
}
```

**حالات موحدة:** `OK`, `PARTIAL`, `UNDETERMINED`, `NO_MATCH`, `UNAVAILABLE`, `REJECTED`, `ERROR`. يجب عدم تفسير `UNAVAILABLE` أو timeout على أنه `NO_MATCH`، وعدم تمرير `PARTIAL` بوصفه إجابة مكتملة. تكون الأخطاء رموزاً آمنة لا تسرب نصوص المصادر المقيدة أو مفاتيح النظام.

**قواعد التعاقد:** تحقق آلي من المدخلات/المخرجات؛ compatibility tests لكل محرك؛ semantic versioning للعقد؛ capabilities discovery (`supported_operations`, `input_schema`, `output_schema`, `limits`)، وفحص snapshot/methodology IDs؛ لا import مباشر من ملفات Engine داخل Engine آخر. يجوز للـ adapters استدعاء APIs داخلية موجودة مؤقتاً حتى اكتمال الترحيل.

## 6. محرك التنسيق بلا اختناقات تشغيلية

### 6.1 التنفيذ

1. `Classify`: تحديد غرض السؤال: `LOOKUP`, `COMPARE`, `RESEARCH`, `FIQH_CASE`.
2. `Plan`: رسم DAG للمهام مع الاعتمادات وحالات التوقف؛ لا يُستدعى كل محرك لكل سؤال.
3. `Fan-out`: تنفيذ المهام المستقلة بالتوازي (async I/O، وعمال محدودون للمهام الثقيلة).
4. `Verify`: التحقق من عقود الاستجابة والأدلة والحالات الدلالية، لا إعادة تحليل كل corpus.
5. `Integrate`: بناء Evidence Graph وطلب المهام المكملة عند ظهور فجوات.
6. `Critique`: فاحص حتمي ثم ناقد AI مستقل عند الحاجة للاستدلال المركب.
7. `Return`: عرض النقل، والاستنتاج، والاعتراض، وحدود الاستنتاج بصورة منفصلة.
8. `Persist`: تدوين أحداث Case واستئناف حالات الفشل دون إعادة كل المهام الناجحة.

### 6.2 منع الاختناق

- **لا قفل عالمي للتنفيذ:** حالة كل Case معزولة؛ التنسيق لا يسلسِل جميع الطلبات.
- **لا سلسلة استدعاءات ثابتة:** يعتمد الـ DAG على السؤال؛ تشغيل Quran/Tafsir/Hadith بالتوازي متى أمكن.
- **لا LLM لكل عملية:** القراءة والتحقق والربط القائم على الهوية وإعادة حساب hashes والبحث المهيكل عمليات حتمية؛ يستدعى النموذج في المهام الدلالية فقط.
- **Bounded parallelism:** حدود منفصلة للـ CPU/GPU/IO والتزام بعدالة المهام؛ منع انهيار الذاكرة أو احتكار نموذج محلي للعتاد.
- **Budgets & fallbacks:** المهلة والحد الأقصى للنتائج والحجم والكلفة؛ إرجاع `PARTIAL` الموصوف بدلاً من حجز الاستعلام كله.
- **Caching:** memoization بحسب `operation + normalized inputs + snapshot + methodology + engine version`، مع إبطال مضبوط عند تبديل اللقطة؛ لا تخزين خلطات من مصادر مختلفة على أنها متجانسة.
- **Incremental work:** نتائج nodes المثبتة محفوظة؛ لا يعاد البحث عن المصادر أو معالجة 1,280 حالة benchmark لمجرد تعديل واجهة.
- **Fault isolation:** تعطل محرك اختياري لا يهدم بقية البحث؛ إن كان ضرورياً لاستنتاج معين تُحجب *تلك النتيجة* مع بيان السبب.
- **Observability:** زمن كل Node، الانتظار، cache hits، استخدام GPU، معدلات الخطأ، عدد الأدلة والإجابات غير المحسومة، وأسباب التوقف.

### 6.3 حواجز التخطيط الذكي دون عنق زجاجة

قد يقترح AI Planner خطة بحث ديناميكية، لكن لا تُنفّذ الخطة مباشرة. يفحصها validator سريع من حيث أسماء العمليات المسجلة، وصحة أنواع المدخلات، وعدم وجود دورات في DAG، وميزانيات الموارد، وتطابق مصادر الأدلة وملف المنهج. إذا لم يستجب المخطط أو أنتج خطة غير صالحة، يُستخدم **deterministic fallback plan** للمسار المناسب. لا حاجة إلى نموذج لغوي آخر للموافقة على كل خطوة.

نصوص corpus المسترجعة **بيانات غير موثوقة تنفيذياً**: لا تتلقى صلاحية لتغيير تعليمات الوكيل أو استدعاء أدوات النظام أو تعديل ملفات المستودع. تنفذ أدوات التطوير في نطاق وصول محدود، مع حدود استخدام للذاكرة وGPU ومساحات الملفات وأثر مدقق لكل تغيير.

### 6.4 مسارات التشغيل

| المسار | الرسم المبدئي | شرط النجاح |
|---|---|---|
| `LOOKUP` | محرك واحد غالباً | مصدر/إحداثيات قابلة للاسترجاع |
| `COMPARE` | محركان أو أكثر بالتوازي | مقارنة منسوبة لمصادرها |
| `RESEARCH` | أدلة متعددة → روابط → فرضية → اعتراض | تقرير بحثي قابل للتتبع، ولو `UNDETERMINED` |
| `FIQH_CASE` | Fiqh يحدد المسألة → أدلة Quran/Hadith/Tafsir → Usul → Fiqh | نتيجة محدودة موثقة أو توقف مسبب؛ لا ادعاء فتوى رسمية |

## 7. الحد الأدنى الوظيفي للمحركات الخمسة — MVE

**MVE = Minimum Viable Engine**: وحدة تقدم قيمة معرفية حقيقية في نطاق ضيق، وتلتزم عقد المحرك، لا stub يُرجع `OK` دائماً.

| المحرك | أول قدرة حقيقية إلزامية | حالات رفض/نقص مطلوبة |
|---|---|---|
| Quran | قراءة الآية من مرجع مثبت، وإرجاع locator + hash + سياق محدود | نسخة مشتبه بها، آية غير موجودة، mismatch |
| Tafsir | استخراج قول/مقطع تفسيري من مصدر مثبت وربطه بآية مع attribution | مقطع غير محدد، نسبة غير ثابتة، تعارض نسخ |
| Hadith | استرجاع تقرير/متن وطرقه أو الشواهد المعروفة في عينة محددة وإرجاع تقييماته المنسوبة | مرشح لفظي فقط، درجة غير معروفة، مصدر غير متاح |
| Usul | تشغيل قاعدة أصولية **مصاغة رسمياً** على معطيات مقيدة مع trace لشروطها وموانعها | قاعدة غير قابلة للتنفيذ، قرينة مجهولة، خلط منهجين |
| Fiqh | إنشاء مسألة منظّمة مع قول فقهي موثق واحد على الأقل، وتوجيه طلب أدلة وقاعدة، وإرجاع نتيجة بحثية مقيدة | اختلاف غير محسوم، دليل ناقص، استنتاج يتجاوز حدود القاعدة |

**قاعدة Quran:** المرجع المؤلف من 6,236 موضع آية يُثبّت دون تعديل صامت، وتُفحص مطابقة النصوص آلياً إلى نسخة مرجعية محددة؛ ولا تُرفع نسخة مشتقة تحتوي عيوباً مكتشفة إلى نص canonical لمجرد نجاح الاختبارات البنيوية. **قاعدة Hadith/Tafsir:** إدخال جماعي آلي مع وسم فوري `UNVERIFIED`/`CANDIDATE`؛ لا صفوف مراجعة بشرية في مسار تطوير المحرك.

**ملحوظة Hadith H3.9.2:** تبقى حملة Schema-31 القديمة (158 قراراً بشرياً معلقاً، وبوابات تقييم تاريخية) مستقلة وغير معدلة. يجوز تطوير تكامل Hadith وتشغيل تجارب machine-only جديدة بعينة منفصلة وواضحة؛ لا يُزوّر gold ولا تُفتح بوابات التأهيل المجمدة آلياً.

## 8. AI-native Development Operating Model

### 8.1 وحدة العمل: Integration Slice لا مرحلة بحثية مفتوحة

كل Slice صغيرة تحتوي على: `objective`, `contract_version`, `owned_paths`, `inputs`, `outputs`, `tests`, `negative_cases`, `performance_budget`, `evidence_receipt`, `done_definition`. لا تحتاج موافقة بشرية لكل ملف أو كل commit. يعمل AI بصورة تكرارية حتى يحقق شروط الاختبار أو يسجل مانعاً هندسياً حقيقياً.

### 8.2 التوازي المسموح

| AI Workstream | ملكية الملفات الرئيسية | الاعتماد الوحيد في البداية |
|---|---|---|
| Contract & Kernel Agent | `core/contracts/`, `core/orchestration/` | واجهة v1 مثبتة |
| Quran Agent | `engines/quran/` | واجهة v1 + fixtures |
| Tafsir Agent | `engines/tafsir/` | واجهة v1 + fixtures |
| Hadith Agent | `engines/hadith/` | واجهة v1 + fixtures |
| Usul Agent | `engines/usul/` | واجهة v1 + fixtures |
| Fiqh Agent | `engines/fiqh/` | واجهة v1 + mocks للأربعة |
| Integration/Evaluation Agent | `engines/e2e/`, `evaluation/`, اختبارات العقود | واجهة v1 + mocks |

الأعمال المتوازية لا تعدل عقداً مشتركاً في الوقت نفسه؛ أي تغيير جوهري للعقد ينتج `v1.x` متوافقاً أو اقتراح `v2` وتختبر adapters قبل التحويل. لا يُنتظر اكتمال Hadith أو Quran لإنشاء محرك Fiqh واختباره ضد fixture معلن.

### 8.3 سلسلة التطوير الآلية

```text
Slice specification
    → AI implementation
    → AI-generated positive & adversarial tests
    → targeted local checks
    → primary AI maintainer-grade review of exact HEAD
    → fixes + regression tests
    → optional independent AI/Codex adversarial pass
    → risk-scoped CI + contract tests
    → automatic merge only when mandatory engineering checks pass
    → nightly/integration matrix + performance baseline
```

**الأولوية للمراجعة الأساسية قبل Codex** وفق ملاحظة PR-review: قراءة diff والكود والمسارات والفشل والمخططات والاختبارات وسلوك CLI وCI في HEAD؛ لا يُستخدم Codex بديلاً عن الفهم الأولي. عند نفاد حصته، يستمر المسار بمراجعة AI أساسية واختبارات هجومية إضافية موثقة. لا تُختلق مراجعة ثانية. يجب إصلاح أخطاء التأثير المعروف قبل الدمج، خاصة فقدان نتائج البحث أو تخطي guard.

**قواعد السرعة:**

- اختبار unit/contract للمسارات المتغيرة أولاً؛ CI أوسع بحسب impact graph، ومصفوفة دورية عامة. لا تكرار للـ CI دون تغير أو مبرر.
- AI يقترح الاستثناءات والاختبارات المضادة تلقائياً؛ لا ينتظر خبيراً بشرياً ليكتب بيانات اختبار هندسية.
- واجهة وهمية موجهة بالعقد مقبولة لإطلاق تطوير محرك مستقل، لكن لا تحتسب إنجاز MVE أو E2E حقيقياً.
- مراجعة تلقائية للفروقات والحالات المرجعية والـ reproducibility؛ لا موافقات لجان هندسية على تغييرات البحث العادية.
- التغييرات الجوهرية ذات أثر فقد بيانات/أمان/تعديل نص مرجعي لا تُدمج مع اختبار أحمر أو فشل تحقق؛ الأتمتة لا تبرر إخفاء المخاطر.
- تُفعّل حماية `main` وrequired checks؛ السرعة تُحقق بتصغير التغييرات والتوازي، لا تجاوز الاختبارات.
- لا إعادة بناء لمكوّن سليم بسبب اختلاف ترتيب الملفات أو رغبة وكيل AI في تصميم جديد.

### 8.4 آلية تنسيق وكلاء التطوير بلا انتظار متبادل

يعمل كل وكيل في worktree/branch مستقل وبملكية ملفات معلنة. تُجمد النسخة الرئيسية من العقد خلال الدفعة، ويولد Contract Agent حزمة schemas وfixtures واختبارات توافق موحدة؛ يستهلكها بقية الوكلاء مباشرة بدلاً من تبادل الأسئلة. تُدمج نتائج المحركات بواسطة Integration Agent وفق ترتيب اعتمادات الاختبارات، وليس ترتيب انتهاء الوكلاء.

عند تعارض تعديلين، يحل AI Integration Agent التعارض على أساس العقد والاختبارات، ثم يعيد الاختبارات المتأثرة؛ ولا تُلغى تغييرات ناجحة لفرض تنسيق شكلي. ويستطيع AI Research Agent إنتاج مراجع وبحث دلالي وبيانات اختبار داخلية، لكن نتائج الوكلاء تظل مرفقة بـ provenance وليست Gold علمياً.

### 8.5 مقاييس الإنتاجية، لا النشاط

`time_to_green_slice`, `integration_slices_closed`, `contract_pass_rate`, `real_engine_coverage`, `E2E_replay_pass_rate`, `regression_escape_count`, `p95_case_latency`, `manual_intervention_count`, `open_shared_dependencies`.

**هدف التطوير:** `manual_intervention_count = 0` في المسار الهندسي الروتيني مع أسباب آلية قابلة للتشخيص؛ لا نعطي وزناً مستقلاً لعدد commits أو milestones أو وثائق منفصلة.

## 9. الفصل الصارم بين التطوير الداخلي والنشر الرسمي

### Development / Research Lane — مستقل وسريع

يسمح بالبرمجة والاختبار على corpus محلي مناسب، والاستخراج الآلي، واختبارات النماذج، ووسم المرشحات، وبناء الفرضيات، وتخزين مخرجات بحثية داخلية. **لا يُدرج تدقيق حقوق إعادة النشر أو انتظار اعتماد علمي رسمي في شروط بداية العمل أو قبول الـ PR أو اجتياز MVE أو اختبار E2E الداخلي.** لا يعتمد schema التطوير على حقول `redistribution_approved` أو `scholarly_signed_off`، ولا يُمنع محرك كامل لغيابها.

تظل سلامة المصدر **تقنية**: locator، hashes، نسب ومصدر، والتحقق من عدم اختلاق الأدلة. ويظل عدم تسريب بيانات التطوير إلى نشر عام أو CI logs شرط حماية تشغيلية وليس مراجعة قانونية مسبقة. تُستخدم المواد في النطاق المسموح به قانوناً؛ لا تفترض هذه السياسة أن توافر النص على الإنترنت يعني حرية نسخه ونشره.

### Official Publication / Release Lane — منفصل عند نشر محتوى أو ادعاء رسمي

عند قرار نشر نصوص/قاعدة بيانات أو تقديم أحكام معتمدة: تجرى فحوص الحقوق اللازمة للمادة المنشورة، والتحقق من الإسناد والاعتماد العلمي عند الادعاءات التي تتطلبه، وفحوص التوزيع والأمان. تعطل هذه البوابة **القطعة المنشورة المخالفة فقط**، ولا توقف تطوير المحركات أو تجاربها الداخلية. لا يجوز تسمية مخرجات AI غير المراجعة «حكماً شرعياً معتمداً» في أي قناة؛ ويمكن تقديمها داخلياً بوصفها فرضية أو نتيجة بحثية غير معتمدة.

**الاستثناء الوحيد للتسلسل:** اختبارات صحة البيانات والأمان وعدم التسريب مستمرة أثناء التطوير لأن الخطأ فيها يفسد النتائج أو يعرّض البيئة للخطر؛ وهي ليست لجان اعتماد أو تدقيق نشر.

## 10. استراتيجية الاختبار والتقييم المستمر

أربع طبقات مستقلة وقابلة للتوازي:

1. **Contract tests:** schemas, operation capabilities, version negotiation, idempotency, source/methodology pinning, `PARTIAL`/`UNAVAILABLE`/`NO_MATCH` semantics.
2. **Engine tests:** fixtures اصطناعية + عينات محلية حقيقية مثبتة؛ حالات إيجابية وسلبية، وتغيّر اللقطة، ومعالجة التكرار.
3. **Cross-engine semantics:** حواف Quran↔Tafsir، Tafsir↔Hadith، Evidence↔Usul، Usul↔Fiqh؛ كشف رابطٍ بلا شاهد، واختلاف مناهج، ومقدمة دائرية، وقاعدة لم تستوف شروطها.
4. **End-to-end evaluation:** حالة حقيقية تتطلب المحركات الخمسة، مرجعها مثبت، وإعادة تشغيلها على لقطة ثابتة؛ اختبارات اعتراض وإزالة مصدر وتعطل محرك وbudget exhaustion.

لا نخلط بين النجاح الهندسي، ودقة الاسترجاع، وصحة توصيف النص، وصحة تطبيق القاعدة، والموافقة على قول فقهي؛ لكل مقياس تجربته. تُنشأ benchmark machine-only جديدة للاستجابة الهندسية السريعة مع عزل source/family holdouts حيث يلزم؛ **لا تُستبدل** بها مجموعة Hadith H3.9.2 المجمدة أو شهادتها البشرية.

### موازنة الأداء

المقاييس أولاً ثم الأهداف: تُسجل p50/p95 لكل operation، وcache hit rate، وزمن الـ planning، وزمن انتظار GPU، ومعدل الاستئناف. تحدد ميزانيات أولية من قياسات فعلية على العتاد المحلي؛ لا نضع أرقام latency اعتباطية بوصفها ضماناً. شرط القبول الهندسي: إثبات أن زيادة حالة مستقلة لا تفرض انتظار قفل عالمي، وأن استعلام lookup لا يشغل محركات لا يحتاجها.

## 11. تجربة القبول الشاملة Five-Engine Acceptance Case

**نطاق تجريبي مقترح:** مسألة فقهية ضيقة تتصل بدلالة صيغة الأمر، يكون لها شاهد قرآني، ونص تفسيري، ورواية متعلقة بالاستدلال، وقاعدة أصولية مصاغة، وقول فقهي منسوب. **تختار الحالة النهائية فقط بعد التحقق من وجود كل هذه الروابط في المصادر المحلية**؛ لا تُفرض روابط وهمية على آية 2:43 لأن تكامل E2E القديم لم يثبت دلالتها.

**شروط القبول الإلزامية:**

- تشغيل **خمسة adapters حقيقية** لا mocks في المسار النهائي.
- كل محرك ينتج مساهمة خاصة به موثقة بمصدر/trace؛ الحديث لا يكتفي بتطابق نصي ويسميه تصحيحاً، والأصول لا يكتفي بوصف قاعدة نصياً ويسميه تنفيذها.
- Fiqh ينشئ `FiqhCase`، ويستدعي الأدلة، ويعيد `ResearchFinding` أو `UNDETERMINED` بأسباب مفصلة.
- لا ترابط دلالياً بلا evidence edge مسندة أو موسومة صراحة `CANDIDATE`.
- إثبات تشغيل متوازي لما لا يعتمد بعضه على بعض، واستئناف حالة عند تعطل محرك.
- صحة كاملة لعقود المصدر والمناهج، وتقرير نقد/اعتراض، وsnapshot replay determinism للعمليات الحتمية؛ تُثبت نتائج LLM بالبصمة والبذرة والإصدار حيث أمكن ولا يُشترط تطابق نصي مطلق عبر عتاد مختلف.
- تقرير E2E يحفظ `commit_sha`, `engine_versions`, `contract_version`, `snapshot_ids`, `model_ids`, test outputs, failures, timings, and final status.
- لا يتطلب القبول الداخلي clearance نشر أو توقيع عالم. ولا يُسمى هذا القبول إطلاقاً عاماً.

**معيار الفشل الصريح:** نجاح واجهة المستخدم مع غياب Fiqh أو Hadith الحقيقي، أو استخدام mock في النتيجة النهائية، أو إخفاء اعتراض أو غياب مصدر، أو استبدال `UNAVAILABLE` بـ `NO_MATCH`.

## 12. التنفيذ على دفعات منجزة لا على بوابات بحثية ضخمة

### Wave A — Thin Contract & Runtime Skeleton

إنشاء `core/contracts/`, `core/orchestration/`, `core/evidence/` كطبقات رقيقة؛ اختبار request/response، ودورة case، وmock adapters، وDAG متوازٍ، وtrace. **لا إعادة كتابة للمحركات**. يتغير العقد نادراً، وتستطيع الفرق الستة التالية العمل بالتوازي.

### Wave B — Five Engine Adapters, in parallel

تطوير adapters من وحدات Quran/Tafsir/Hadith/Usul الموجودة؛ **بدء Fiqh Engine فوراً** بعقد `FiqhCase`, `JuristicOpinion`, `ResearchFinding`. تنفيذ أول MVE لكل محرك. لا تنتظر Fiqh انتهاء حملة Hadith H3.9.2 أو أهلية عرض النص للجمهور.

### Wave C — Evidence Graph & Orchestrated Research

وصل روابط الأدلة والقرائن والاعتراضات، وتحويل الأدوات E2E الحالية إلى مستهلك لواجهة Kernel، وإضافة AI planner/critic قابلين للتعطيل مع fallback حتمي، وتنفيذ حالة أربع محركات تسبق إضافة Fiqh النهائي إذا كانت أسرع لإظهار العيوب.

### Wave D — Real Five-Engine Case + Adversarial Closure

تشغيل حالة المصادر المحلية الحقيقية، وإثبات عدم إخفاء المدخلات الفاسدة والتعارض وغياب الأدلة، وتسجيل replay وperformance baseline، ثم إصدار **Engineering Integration Report**. لا يُرفع إصدار مُبين تلقائياً إلى `0.2.0-alpha` إلا بعد توثيق قدرات الإصدار المقصودة؛ أي إصدار علني يمر ببوابة النشر المستقلة.

## 13. الهيكل المستهدف والترحيل

```text
Mubin/
  core/
    contracts/         # NEW: shared typed engine API
    orchestration/     # NEW: planner, DAG, case state
    evidence/          # NEW: identity, links, provenance adapters
    methodology/       # NEW: profile registry / versioning
    inference/         # EXISTING P0 validator, retained
  engines/
    quran/             # EXISTING + v1 adapter
    tafsir/            # EXISTING + v1 adapter
    hadith/            # EXISTING + v1 adapter
    usul/             # EXISTING + v1 adapter
    fiqh/             # EXISTING placeholder → working engine
    e2e/              # EXISTING → integrated replay consumer
  schemas/             # EXISTING + engine-contract schemas
  evaluation/          # EXISTING + integrated scenarios
  docs/                # this architecture and ADRs
  release/             # NEW: official-publication-only checks
```

لا تنقل الشجرة القديمة إلى هذه البنية دفعة واحدة؛ استخدم anti-corruption adapters وأضف ملفات جديدة دون إعادة تسمية غير ضرورية. تُضاف Tafsir إلى manifest الإصدارات عندما يوحد `VERSION.yaml` الحالة الفعلية، مع بقاء أرقام المحركات مستقلة عن SemVer النظام.

## 14. معايير الخروج وموانع الإغلاق

| معيار | المطلوب للإغلاق الهندسي |
|---|---|
| `A1` | خمس واجهات contract-versioned تعمل وتنجح باختبارات التوافق |
| `A2` | لكل محرك MVE حقيقي محدود بنطاق مصدري مثبت |
| `A3` | Case orchestrator يعمل دون قفل عام، ويعيد partial/undetermined بصدق |
| `A4` | Evidence Graph يربط مصدر/نقل/قاعدة/رأي/استنتاج/اعتراض |
| `A5` | مسار حقيقي واحد يشمل Quran + Tafsir + Hadith + Usul + Fiqh |
| `A6` | عدم الاعتماد على mocks في قبول المسار النهائي، وثبات replay للبنية الحتمية |
| `A7` | اختبارات سلبية لفقد المصادر والتعارض والقرائن والطرق والمهلات |
| `A8` | CI على SHA الدمج المطلوب، ومراجعة AI أساسية، وإغلاق عيوب severity عالية مثبتة |
| `A9` | قياسات زمن وتوازي وذاكرة وخطة تحسين تستند إلى بيانات |
| `A10` | لا اعتماد علمي بشري ولا فحص نشر يوقفان إغلاق هندسة التطوير الداخلي |

**موانع الإغلاق الهندسي المحددة:** تلف بيانات دون كشف، دليل مختلق، نتائج مفقودة بصمت، تلوث snapshot، انقلاب `UNAVAILABLE` إلى `NO_MATCH`، اختلاط منهج صامت، تنفيذ تعبير قاعدة حر بوصفه كوداً، أو تشغيل mock مع ادعاء تنفيذ واقعي. أما نقص نتائج علمية خارج نطاق MVE المعلن فيُسجل كنطاق لاحق لا كمانع تطوير شامل.

## 15. سجل القرارات المعمارية (ADR Baseline)

| ADR | القرار |
|---|---|
| `ADR-001` | خمس محركات معرفية ونواة تكامل مشتركة؛ لا محرك AI سادس يحل محلها |
| `ADR-002` | Modular Monolith محلي أولاً؛ فصل منطقي، لا تعقيد خدمات مبكر |
| `ADR-003` | Interface-first وcontract tests، وتطوير المحركات بالتوازي باستخدام mocks |
| `ADR-004` | Evidence Graph typed + provenance + source snapshots قابلة لإعادة التشغيل |
| `ADR-005` | AI للتوليد والاقتراح والنقد؛ الحتمية للمرجع والتحقق وتنفيذ القواعد الرسمية |
| `ADR-006` | CI/AI engineering reviews بديل الموافقات البشرية الروتينية في التطوير |
| `ADR-007` | حقوق إعادة النشر والاعتماد الرسمي في Release Lane منفصلة، لا Dev Gate |
| `ADR-008` | الحفاظ على H3.9.2 qualification protocol دون تعطيل تطوير Hadith/النظام |
| `ADR-009` | نجاح Mubin يقاس بحالة Five-Engine E2E مثبتة، لا بعدد مراحل المحركات |
| `ADR-010` | ترحيل تدريجي وreuse existing code؛ لا big-bang rewrite |

## 16. أول دفعة تنفيذ قابلة للإسناد إلى AI

**اسم الحزمة:** `MUBIN-SYS-A01 — Contract-First Integration Kernel`.

**مخرجاتها:**

1. `schemas/engine-request-v1.schema.json` و`schemas/engine-result-v1.schema.json`.
2. `core/contracts/types.py`, `registry.py` و`compatibility.py`، مع قدرات كل محرك.
3. `core/orchestration/plan.py`, `runner.py`, `case_store.py` لإدارة DAG وtimeouts وpartial failures.
4. خمسة mock adapters مستقلة لا تُحتسب MVE، مع regression tests لعقد `UNAVAILABLE != NO_MATCH` وعدم اختلاط المصادر والمناهج.
5. `engines/fiqh/contracts.py` و`engines/fiqh/models.py` لبدء العمل الحقيقي لمحرك الفقه بالتوازي.
6. `evaluation/integration/test_contract_v1.py` و`test_parallel_cases.py` و`test_failure_isolation.py`.
7. تحديث خفيف لوثائق الربط دون تعديل جوهري للمحركات أو بيانات Hadith H3.9.2 المجمدة.

**Definition of Done للحزمة:** اختبارات الإيجاب والنفي ناجحة على HEAD، تنفيذ استعلامين مستقلين بلا قفل عام، timeout محرك واحد لا يفسد نتائج الآخرين، وreceipt يظهر إصدارات العقد والتتبع وزمن كل عقدة. لا حاجة إلى مصدر شرعي خاص أو تدقيق حقوق نشر أو توقيع بشري لتنفيذ هذه الحزمة.

---

## 17. المراجع ودرجة اليقين

**مستندات المستودع التي بُني عليها توصيف الواقع:** `README.md`, `VERSION.yaml`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, `docs/INFERENCE_CONTRACTS.md`, `docs/DEVELOPMENT_FAST_LANES.md`, `docs/RISK_BASED_ASSURANCE.md`, `engines/e2e/research_slice.py`, `engines/e2e/semantic_linkage.py`, `engines/usul/p0_bridge.py`, `engines/fiqh/README.md`، وشجرة المسارات عند SHA المحدد أعلاه. كما استُخدمت تعليمات المشروع المحلية: `قواعد-تسريع-التطوير.txt` و`PR-review.txt`.

**التفريق:** كل مسار موسوم `NEW`، وكل عقد `engine-contract/1.0`، وكل MVE/Wave/ADR في هذا المستند **اقتراح تنفيذي ملزم بعد تبنيه، وليس إنجازاً مثبتاً في GitHub حالياً**. أي تطوير لاحق يجب أن يحدث حالة تنفيذ المستند وفق نتائج الكود والاختبارات، لا وفق ادعاءات الوكيل المنفذ.

**خلاصة قرار v1.0:** **نبني مُبين كاملاً منذ أول Slice: خمسة محركات مستقلة معرفياً، مترابطة بعقود رشيقة، تعمل بالتوازي تحت تنسيق منخفض الكلفة؛ الذكاء الاصطناعي هو المنفذ الأساسي للتطوير والاختبار والنقد، والإثبات التقني آلي، أما بوابة النشر والاعتماد الرسمي فمستقلة ولا تتحكم في سرعة تطوير النظام الداخلي.**