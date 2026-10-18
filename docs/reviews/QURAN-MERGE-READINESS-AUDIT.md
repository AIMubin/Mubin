# مراجعة هندسية: جاهزية دمج سلسلة القرآن — استشارية فقط

**تاريخ المراجعة:** 2026-10-18. **النطاق:** طلبات الدمج [#73](https://github.com/AIMubin/Mubin/pull/73) ← [#74](https://github.com/AIMubin/Mubin/pull/74) ← [#75](https://github.com/AIMubin/Mubin/pull/75) ← [#76](https://github.com/AIMubin/Mubin/pull/76). **الفرع المعتمد:** `main` عند `567e55858a9911a23430ef81f1e41b7a5f26480e`، **غير محمي** عند القراءة. تنفيذ الفاحص الحالي قبل هذا المستند: `8bd0ff8f06a779b290a389a8ae557d20197dae36`.

## النتيجة والأولويات

لا يجوز اختزال الزمن بتحويل `main` إلى مسار تجاوز للفحوص. يسجل هذا الفاحص الاستشاري الجاهزية تلقائيًا على **رؤوس PR الحية**، ولكنه لا يمنح صلاحيات دمج، أو يكتب في GitHub، أو يعين مراجعًا، أو يصدق النص القرآني أو الحقوق. تشغيل التطوير بالتوازي يستمر عند وجود عوائق الحوكمة.

- **هندسيًا:** التحقق من تسلسل الآباء، وانتماء الفروع إلى المستودع، وعلاقة fast-forward لكل PR، وتطابق معرّف workflow/HEAD/event/status/conclusion على قوائم GitHub.
- **حوكمة:** حالة Draft، وحماية `main`، ووجود موافقة مراجعة شيفرة من مستخدم آخر ومقيدة بالـHEAD. لا يُسمَّى هذا اعتمادًا دينيًا أو مراجعة علمية مستقلة.
- **حدود الدليل:** حالات GitHub workflow ليست تحليلًا مستقلًا للسجلات الداخلية أو صحة النص. الفحص الآلي لا يفتح أو يغير مجموعة H3.9.2 المحجوبة.
- **المدخلات المزورة:** `assess_chain` يقبل نسخة بيانات غير موثوقة للاختبار؛ حتى وإن بدت مكتملة، تعيد دائمًا `merge_ready=false` و`eligible_for_auto_merge=false`، مع `conditionally_merge_ready` للاستشارة. لا تصدق تسمية `data_source` التي يقدمها المستدعي.
- **المصدر الحي:** CLI وحده ينفذ GET إلى نطاق GitHub API الثابت، مع حدود للحجم وJSON صارم والتحقق من عنوان الطلب، ثم يضع `data_source=github_rest_read_only`. لا يُسمح برد HTTP موجّه إلى نطاق مختلف.
- **التزام آلية GitHub:** Workflow له `contents:read` و`actions:read` و`pull-requests:read` فقط، ولا يستدعي `git push` أو merge endpoint أو LLM. لا يُعاد تعريف نجاح CI عند وجود فحص جارٍ؛ القرار الوقتي `CHECK_INCOMPLETE`.
- **عدم استنتاج سلطة:** دائمًا `quran_source_authenticated=false`، و`scholarly_approval_verified=false`، و`rights_verified=false`. لا تُدمج المسودة.

## RED → GREEN المثبت على GitHub

1. **اختبارات أولية قبل الوحدة** `7f7230a8e588f7fa17b2c37e603ee07dced81307`: [P0 #39152511600](https://github.com/AIMubin/Mubin/actions/runs/39152511600) فشل متوقع عند غياب `qa.quran_merge_readiness`.
2. **تنفيذ أولي** `0d73d770ac44f54ab80c009bb55daae17de0e798`: [P0 #39152692164](https://github.com/AIMubin/Mubin/actions/runs/39152692164) فشل 12 اختبارًا بسبب هروب خاطئ لمحدد regex الخاص ببصمات الالتزام؛ أصلح في `abc7adf6fb6c36aaf6323463e8023c47e53d0572`. [P0 #39152761038](https://github.com/AIMubin/Mubin/actions/runs/39152761038) **131/131** ناجح.
3. **اختبار نقض منفصل قبل الإصلاح** `d7cb7cb9ddb9c539a25fc13197c0046285b77ddd`: [P0 #39152837696](https://github.com/AIMubin/Mubin/actions/runs/39152837696) أحمر بسبب إمكان إرجاع `merge_ready=true` من مدخل اصطناعي حتى عند تزييف `data_source`. عولج في `26ea17b8d135bc025574351e37a8d6471fc743fa` بمنع إذن الدمج في التقارير الاصطناعية؛ **132 اختبارًا**.
4. **ربط CI بالقراءة الحية** `faff16608f976adc184a0046a9dd38f1b0b45f38`: [فحص الجاهزية #39152950665](https://github.com/AIMubin/Mubin/actions/runs/39152950665) رفض صيغة GitHub القياسية `compare/<base>...<head>` وخرج خطأ `unsafe_api_path` دون تصريح خاطئ. أصلح قبول الثلاث نقاط دون فتح مسار `../` في `8bd0ff8f06a779b290a389a8ae557d20197dae36`.
5. **القراءة الحية المصححة:** [#39153043893](https://github.com/AIMubin/Mubin/actions/runs/39153043893) **نجاح، 14/14 اختبارًا**. سجّلت قراءة GitHub: `MAIN_NOT_PROTECTED`، جميع PRs `DRAFT`، وعدم وجود موافقة مراجعة شيفرة على HEAD لأي منها. ظهرت أيضًا `PR76_CHECK_INCOMPLETE` لأن فحصًا متوازيًا لم ينته بعد لحظة القراءة؛ وبعد ذلك اكتملت الفحوص الأربعة للـHEAD `8bd0ff8f...` بنجاح: [P0 #39153043863](https://github.com/AIMubin/Mubin/actions/runs/39153043863)، [Q0.1 #39153043913](https://github.com/AIMubin/Mubin/actions/runs/39153043913)، [Q0.1d #39153043867](https://github.com/AIMubin/Mubin/actions/runs/39153043867)، [Chrome #39153043888](https://github.com/AIMubin/Mubin/actions/runs/39153043888). المراجعة الحية تتبع حالة **لحظية**، وليست تحديثًا تلقائيًا بعد انتهاء الفحص.

**تحقق بعد إضافة هذا الملف:** نتائج CI على آخر HEAD الذي يحتوي ملف التدقيق يجب مراجعتها مجددًا، دون الاكتفاء بـHEAD السابق.

## مخاطر وحدود معروفة وقرار الدمج

- لا تحاكي أداة PR-ready قواعد Github Rulesets / CODEOWNERS ولا تتحقق من حل جميع review threads؛ لذلك حتى `conditionally_merge_ready` لا تكفي لترخيص الدمج.
- لا تمتلك موثوقية مقاييس اكتشاف العيوب العلمية؛ ولا تُعادل نجاح اختبارات Chrome اعتمادًا للمصدر الرسمي Tanzil.
- تكوين branch protection يحتاج صلاحيات إدارية مستقلة؛ GitHub يعرض `main.protected=false` ولا توجد قواعد rulesets فعّالة مرئية، بينما قراءة تفاصيل فرع الحماية ردّت `403` لهذه الوصلة. لا ندعي أن حماية الفرع أُنشئت.
- لا يوجد reviewer موافق في GitHub على هذه السلسلة حتى الآن؛ المراجعة أعلاه **maintainer-only**. `codex_review=unavailable` بسبب نفاد الحصة التاريخي، دون ادعاء تشغيل وكيل مستقل جديد.
- لا تبرر أي نتيجة جمع مصادر غير مأذون بها أو تحويل مرآة `acfatah/tanzil` إلى مصحف رقمي موثوق.
- **قرار الدمج:** لا دمج الآن. نستمر بالمنتج والاختبار، ثم تفعيل حماية `main` والتحقق من نظام المراجعات وتنفيذ الدمج *بالترتيب* #73 → #74 → #75 → #76 عندما يصبح ذلك منضبطًا.

**لا تغيير للإصدار العام** `0.1.0-alpha`، ولا دمج لأي PR، ولا صلاحيات كتابة ضمن الفاحص. سجل العمل الخارجي `/Mubin/PROJECT_STATUS.md` في مكتبة ChatGPT، وليس GitHub.
