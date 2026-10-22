"use strict";
// Rendering is textContent-only. The only source URLs accepted by the builder
// are explicitly pinned public HTTPS bibliography links, not source text.
const $ = (id) => document.getElementById(id);
const node = (tag, className, value) => {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (value !== undefined) e.textContent = String(value);
  return e;
};
let searchEntries = [];
function row(label, value, className = "count") {
  const item = node("div", className);
  item.append(node("span", "", label), node("strong", "", value));
  return item;
}
function drawResults(filter) {
  const root = $("query-results");
  root.replaceChildren();
  const matches = searchEntries.filter((q) => q.label_ar.includes(filter.trim()));
  if (!matches.length) {
    root.append(node("p", "hint", "لا توجد استعلامات محفوظة بهذا الاسم. لا تعني هذه النتيجة غياب اللفظ في المصدر."));
    return;
  }
  for (const item of matches) {
    const card = node("article", "result");
    card.append(node("h3", "", item.label_ar));
    card.append(row("الشاهد الأول · حرفي", item.w1_exact));
    card.append(row("الشاهد الثاني · حرفي", item.w2_exact));
    const candidate = node("p", "candidate");
    candidate.textContent = "مرشحات W2 عبر ملفات التطبيع (قد تشير إلى الموضع نفسه): ";
    const counts = Object.values(item.w2_candidate_counts_by_profile);
    candidate.append(node("strong", "", counts.length ? counts.join(" / ") : "لا شيء"));
    card.append(candidate);
    root.append(card);
  }
}
function render(data) {
  if (data.profile !== "mubin-public-metadata-preview/0.1.0" ||
      data.source_text_included !== false ||
      data.rights_granted !== false ||
      data.scholarly_verified !== false ||
      data.public_fatwa_authorized !== false ||
      data.publication_gates.canonical_quran_display !== "WITHHELD" ||
      data.publication_gates.source_verbatim_publication !== "WITHHELD") {
    throw new Error("Public-preview safety contract refused the data");
  }
  $("statusline").textContent =
    "الإصدار " + data.system_version + " · معاينة وصفية للقراءة فقط · ليست خدمة فتوى";
  $("metric-nodes").textContent = String(data.research_example.graph_nodes);
  $("metric-edges").textContent = String(data.research_example.graph_edges);
  const modes = {
    status_only: "حالة المحرك فقط",
    metadata_navigation_only: "بيانات وصفية فقط",
    not_available: "غير متاح"
  };
  for (const engine of data.engines) {
    const card = node("article", "engine");
    card.append(node("div", "tag", engine.milestone));
    card.append(node("h3", "", engine.name));
    card.append(node("p", "", engine.note_ar));
    card.append(node("span", "mode", modes[engine.public_mode] || "غير متاح"));
    $("engine-grid").append(card);
  }
  searchEntries = data.research_example.query_counts;
  drawResults("");
  const allowed = new Set([
    "https://www.islamicbook.ws/asol/alwrqat.html",
    "https://www.islam.ms/ar/كتاب-ورقات-أصول-فقه-إسلامي-إمام-حرمين-عبد-الملك-الجويني/"
  ]);
  for (const source of data.research_example.witnesses) {
    if (!allowed.has(source.url)) throw new Error("Unapproved source link");
    const a = node("a", "", "الشاهد " + source.id + " — المصدر الرقمي ↗");
    a.href = source.url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    $("source-links").append(a);
  }
}
$("query-filter").addEventListener("input", (event) => drawResults(event.target.value));
fetch("./preview-data.json", { cache: "no-store" })
  .then((resp) => { if (!resp.ok) throw new Error("metadata unavailable"); return resp.json(); })
  .then(render)
  .catch(() => {
    $("statusline").textContent = "تعذر التحقق من البيانات الوصفية؛ عُطّل العرض الديناميكي حمايةً للمصدر.";
    $("query-results").replaceChildren(node("p", "hint", "تعذر عرض المثال البحثي الآن."));
  });
