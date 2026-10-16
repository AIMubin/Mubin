# S0.2 — Shamela permission and supported-format inquiry (DRAFT, NOT SENT)

**Prepared:** 2026-10-16  |  **Project:** Mubin (`0.1.0-alpha`)  |  **Status:** authorization NOT GRANTED, no contents acquired.

## Verified contact and availability

- Official app listing, publisher `Shamela.ws`, displays a support email `mail@shamela.ws`: https://play.google.com/store/apps/details?id=com.arabdt.shamla . The official download page also exposes a contact form, but its web-obfuscated email link was not accessible via the research tool: https://shamela.ws/page/download . **Verify the addressee before sending.**
- Official documentation describes cross-platform Windows/macOS/Linux application packages, a portable `database` folder and a downloadable complete database package: https://shamela.ws/page/download . It does **not** reveal the current storage engine, canonical export/API schema, version signatures, per-edition permissions or rights to reuse.
- Official channel describes the `app` (application code) and `database` (books, preferences and user data) separation: https://t.me/s/shamelaws . Do not assume that the user-local `database` folder contains only published book contents: it may include personal notes and sessions. **Do not upload complete user database folders to this project or issue trackers.**
- The official channel also reports release of Shamela AI, https://shamela.ws/ai, with technical collaboration from Nuqayah. An external research fetch failed; actual interface/model/provenance terms remain untested. The channel previously cautioned that third-party paid services claiming to use the library were not coordinated with it. Neither announcement is a blanket licensing decision.

## Outgoing Arabic message — requires human approval

**To:** `mail@shamela.ws` (candidate official support address; verify before delivery)

**Subject:** استفسار بحثي عن فهرسة بيانات المكتبة الشاملة وتكامل مرجعي غير تجاري

> السلام عليكم ورحمة الله وبركاته،
>
> نعمل على مشروع بحثي مفتوح المصدر باسم «مُبين»، هدفه توثيق المصادر العلمية وإظهار طبعاتها ومواضع الاستشهاد بها، مع الفصل بين نقل النص، وتقييم الحديث، وقواعد الاستدلال الأصولي، دون إصدار فتوى آلية. ونرغب في دراسة تكامل منضبط مع المكتبة الشاملة، بعد الحصول على الموافقات اللازمة.
>
> نرجو التكرم بإيضاح المسائل الآتية:
>
> 1. هل تسمحون بإعادة استخدام بيانات الفهرسة العامة (معرّف الكتاب، المؤلف، الطبعة، المحقق، الناشر، الروابط) مع عزوها إلى المكتبة الشاملة؟ وهل تتوافر واجهة برمجية موثقة أو طريقة رسمية للحصول على هذه البيانات؟
> 2. هل يُسمح لنا بفحص عينة صغيرة من ملفات البيانات الرسمية محليًا لأغراض بحثية، بهدف التحقق من صيغة الملفات ومعرّفات الكتب والصفحات والفقرات والحواشي، من دون نشر النصوص أو إعادة توزيع الملفات؟ وما المرجع الفني المعتمد لصيغة البيانات وإصداراتها؟
> 3. نرجو بيان حقوق الاستخدام بحسب الطبعة وبحسب الغرض: الاحتفاظ المحلي، الفهرسة الآلية، اشتقاق التمثيلات الدلالية، إظهار مقتطفات مع عزوها، إتاحة بيانات مشتقة، وتدريب النماذج. وهل يلزم إذن مستقل من محققي الطبعات أو ناشريها؟
> 4. هل روابط صفحات الكتب ومقاطعها ثابتة؟ وما العلاقة بين معرّف صفحة الموقع وترقيم الجزء والصفحة في الطبعة المطبوعة؟
> 5. هل يمكن ترتيب تعاون بحثي يتيح تجربة محدودة تحت إشرافكم، وما شروط نسب المحتوى والمساهمات والتمييز بين الخدمات المجانية والمدفوعة؟
>
> الأمثلة الأولية للفحص الوصفي فقط: صحيح البخاري (معرّف 1681)، جامع البيان للطبري (7798)، والرسالة للشافعي (8180). لم نستورد المتون إلى مشروعنا، ولن نبدأ الاستخراج أو إعادة الاستخدام دون وضوح الشروط والموافقات.
>
> جزاكم الله خيرًا على جهودكم في خدمة العلم، ونرحب بأي توجيه رسمي أو اتفاق تعاون مناسب.
>
> والسلام عليكم ورحمة الله وبركاته.

**Status:** This message is a *draft*. There is **no evidence that it was sent, received or approved**. Do not commit claimed approval or privileged email responses to git; store only a safe decision summary with verifiable reference and responsible reviewer.

## Minimal evidence register before S0.2 text-level work

| Decision dimension | Current status | Acceptable evidence / next action |
| --- | --- | --- |
| Catalog display of public bibliographic metadata | unverified permission | Written website/operator guidance, including attribution |
| Automated metadata API or export | undocumented | Provider-authored endpoint/schema/version and allowed rate limits |
| Offline database file format, stable record IDs | undocumented | Official format documentation or explicitly authorized inspection |
| Reusing individual printed-edition text | unverified, per edition | Separate publisher/rights-holder basis where applicable |
| Local copy/index/embeddings/RAG | unverified, each a distinct purpose | Explicit allowed use and access boundaries |
| Excerpt display and public redistribution | unverified | Scope-limited permission and attribution rules |
| Model pretraining/fine-tuning or commercial use | unverified | Explicit independently reviewed authorization |
| AI service evaluation | announcement verified, functional claims untested | Authorized manual access and separately cleared evaluation samples |

## Hold / stop rules

- Never translate availability of a database download into rights to scrape, mirror, host, embed or train on content.
- Never treat a page link, a catalog digest or a Git blob pin as authenticated publisher custody.
- Never ingest the legacy frozen H3.9.2 holdout sources for a new calibration or development benchmark.
- Inspect only authorized, non-personal sample artifacts; report filenames, format signatures and mappings without uploading full source text or local personal settings. Distinguish source identification from permission to use it.
- Keep S0.1 metadata inventory PR #59 independent of this S0.2 rights gate Issue #60.

## Sources

- https://shamela.ws/page/download
- https://t.me/s/shamelaws
- https://play.google.com/store/apps/details?id=com.arabdt.shamla
- https://github.com/AIMubin/Mubin/issues/60
