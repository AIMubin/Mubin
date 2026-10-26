"""E2E-01.3: server-rendered Arabic researcher view of an E2E-01.1/01.2 report.

This is a PURE HTML renderer for the existing operator workspace. It never
fetches source text, executes JavaScript, writes decisions or grants authority.
All variable content (including researcher-supplied tokens) is escaped.
"""
from __future__ import annotations

from html import escape

_ALLOWED_STATES = frozenset(("UNASSESSED", "PROPOSED_NOT_CERTIFIED"))


def _e(value) -> str:
    """HTML-escape every dynamic field; render no source text or notes."""
    return escape(str(value), quote=True)


def _label(value: bool | None) -> str:
    return "نعم" if value is True else ("لا" if value is False else "غير معروف")


def render_research_html(report: dict) -> bytes:
    """Render metadata and research uncertainty in one RTL operator page."""
    if (type(report) is not dict
            or report.get("research_mode") != "metadata_only"
            or report.get("limits", {}).get("text_included") is not False
            or report.get("limits", {}).get("publication_allowed") is not False
            or report.get("limits", {}).get("scholarly_verified") is not False
            or report.get("limits", {}).get("juristic_inference_allowed") is not False
            or report.get("limits", {}).get("public_fatwa_authorized") is not False):
        raise ValueError("E2E_RENDER_CONTRACT_REFUSED")
    link = report.get("research_linkage", {})
    if type(link) is not dict or link.get("status") not in _ALLOWED_STATES:
        raise ValueError("E2E_RENDER_LINKAGE_REFUSED")

    ref, question = _e(report["reference"]), _e(report["question"])
    rows = []
    for source in report["quran_retrieval"]["sources"]:
        rows.append(
            "<tr><td>" + _e(source["source_id"]) + "</td>"
            "<td>" + _e(source["adapter"]) + "</td>"
            "<td>" + _label(source["coordinate_present"]) + "</td>"
            "<td>" + _e(source["scholarly_decision_state"]) + "</td>"
            "<td>" + _e(source["rights_decision_state"]) + "</td></tr>")
    cases = []
    for name, outcome in report["usul_analysis"]["cases"].items():
        cases.append("<tr><td>" + _e(name) + "</td><td>"
                     + _e(outcome["status"]) + "</td></tr>")

    study = [
        '<section aria-labelledby="link-title"><h2 id="link-title">العلاقة البحثية</h2>',
        "<p><strong>حالة العلاقة:</strong> " + _e(link["status"]) + "</p>",
        "<p>تجميع المصادر لا يُثبت ارتباط الآية بالقاعدة الأصولية، "
        "ولا يثبت صحة الاستنباط.</p>",
    ]
    if link["status"] == "PROPOSED_NOT_CERTIFIED":
        proposal = link["proposal"]
        verse = proposal["verse"]
        ind = proposal["diverting_indicator"]
        scope = ind["scope"]
        study += [
            "<h3>ملاحظة الباحث (غير معتمدة)</h3>",
            "<p><strong>الكلمة المبلّغ عنها:</strong> " +
            _e(verse["imperative_word"]) + "</p>",
            "<p><strong>موقعها المبلّغ عنه:</strong> " +
            _e(verse["imperative_position"]) + "</p>",
            "<p><strong>حالة فحص القرينة:</strong> " +
            _e(ind["case"]) + "</p>",
            "<p><strong>المصادر المفحوصة حسب الباحث:</strong> " +
            _e(scope["sources_examined_count"]) + "</p>",
            "<p><strong>مصادر لم تُفحص حسب الباحث:</strong> " +
            _e(scope["sources_not_examined_count"]) + "</p>",
            "<p><strong>قرائن أبلغ عنها الباحث:</strong> " +
            _e(len(scope["indicators_found"])) + "</p>",
            "<p>لم يُتحقق من موضع الكلمة أو مطابقة بصمة النص آليًا. "
            "عدم رصد القرينة ضمن النطاق لا يعني انتفاءها.</p>",
        ]
    study.append("</section>")

    gaps = "".join("<li>" + _e(gap["type"]) + "</li>"
                   for gap in report["gaps"])
    undetermined = "".join("<li>" + _e(item) + "</li>"
                           for item in report["undetermined"])
    head = _e(report["quran_retrieval"]["evidence_head_sha256"][:16])
    html = (
        '<!doctype html><html dir="rtl" lang="ar"><head>'
        '<meta charset="utf-8"><title>مُبين — مسار البحث العلمي</title>'
        '</head><body dir="rtl" lang="ar">'
        '<nav aria-label="التنقل"><a href="/">حالات التأهيل</a> | '
        '<a href="/research?ref=2:43">بحث باب الأمر</a></nav>'
        '<main><h1>مُبين — مسار البحث العلمي</h1>'
        '<p><strong>السؤال:</strong> ' + question + '</p>'
        '<p><strong>الآية:</strong> ' + ref + '</p>'
        '<p>بحث داخلي في البيانات الوصفية فقط، دون عرض النصوص المقيّدة.</p>'
        '<p>رأس الأدلة الموثقة: ' + head + '…</p>'
        '<section aria-labelledby="sources-title"><h2 id="sources-title">'
        'مصادر القرآن والتفسير</h2>'
        '<table><thead><tr><th>المصدر</th><th>المحول</th>'
        '<th>الإحداثيات موجودة</th><th>المراجعة العلمية</th>'
        '<th>مراجعة الحقوق</th></tr></thead><tbody>' +
        "".join(rows) + '</tbody></table></section>'
        '<section aria-labelledby="usul-title"><h2 id="usul-title">'
        'أصول الفقه — نموذج الورقات البحثي</h2>'
        '<p>السيناريوهات التالية اصطناعية وليست نتائج فقهية معتمدة.</p>'
        '<table><thead><tr><th>سيناريو تجريبي</th><th>نتيجة المحرك</th>'
        '</tr></thead><tbody>' + "".join(cases) + '</tbody></table>'
        '</section>' + "".join(study) +
        '<section aria-labelledby="limits-title"><h2 id="limits-title">'
        'حدود البحث وما لم يُحسم</h2><ul>' + undetermined +
        '</ul><h3>الفجوات</h3><ul>' + gaps + '</ul>'
        '<p><strong>غير معتمد:</strong> صحة نسبة المصادر، التحقيق العلمي، '
        'حقوق النشر، الاستنباط الملزم والفتوى.</p>'
        '</section></main></body></html>'
    )
    return html.encode("utf-8")
