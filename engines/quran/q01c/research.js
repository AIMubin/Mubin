"use strict";
// T0.3 research UI. Metadata-only: the API never returns protected text.
const $ = (id) => document.getElementById(id);
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}
function field(k, v) {
  const row = el("div", "meta");
  row.appendChild(el("span", null, k + ": "));
  row.appendChild(el("code", null, String(v)));
  return row;
}
function boolSpan(label, value) {
  const s = el("span", value ? "status-true" : "status-false",
    label + ": " + (value ? "نعم" : "لا"));
  return s;
}
async function search() {
  const ref = $("ref").value.trim();
  $("error").hidden = true;
  $("result").hidden = true;
  $("tafsirs").textContent = "";
  $("relations").textContent = "";
  if (!/^[1-9][0-9]{0,2}:[1-9][0-9]{0,2}$/.test(ref)) {
    $("error").textContent = "مرجع غير صالح — الصيغة سورة:آية مثل 2:43";
    $("error").hidden = false;
    return;
  }
  let data;
  try {
    const res = await fetch("/api/research?ref=" + encodeURIComponent(ref),
                            {credentials: "omit"});
    data = await res.json();
    if (!res.ok) {
      $("error").textContent = "رفض الاستعلام: " + (data.error || res.status);
      $("error").hidden = false;
      return;
    }
  } catch (e) {
    $("error").textContent = "فشل الاتصال";
    $("error").hidden = false;
    return;
  }
  $("ref-title").textContent = "الآية " + ref +
    " — " + data.tafsir_count + " مصادر تفسيرية";
  $("quran-state").textContent =
    "نص القرآن: " + data.quran_text.state +
    " — لا يُعرض نص مشتق بوصفه مصحفاً معتمداً";
  const counts = data.counts || {};
  for (const t of data.tafsirs) {
    const box = el("section", "work");
    box.appendChild(el("h3", null,
      (t.work_title_ar || t.work_id) + " — " + (t.author_ar || "مؤلف غير محدد")));
    const c = el("div", "counts");
    c.appendChild(el("span", null, "مقاطع: " + t.passage_count));
    c.appendChild(el("span", null, "مرشحات: " + t.candidate_count));
    c.appendChild(el("span", null, "مؤشرات نسبة مسمّاة: " + t.attribution_cues_named));
    c.appendChild(el("span", null, "مؤشرات اختيار المؤلف: " + t.author_preference_cues));
    c.appendChild(el("span", null, "متحدث غير محدد: " + t.unidentified_speaker_candidates));
    box.appendChild(c);
    box.appendChild(boolSpan("الطبعة موثقة", t.edition_authenticated));
    box.appendChild(boolSpan("المصدر موثق", t.source_authenticated));
    box.appendChild(boolSpan("الحقوق موثقة", t.rights_verified));
    box.appendChild(boolSpan("التحقق العلمي", t.scholarly_verified));
    box.appendChild(field("حالة العرض", t.display_status));
    box.appendChild(field("بصمة السجل", t.imported_record_sha256));
    box.appendChild(field("معرف الشاهد", t.evidence_id));
    // Passage → candidate → source drilldown is entirely metadata-only.
    // Raw source offsets are Unicode codepoint indices, not byte indices.
    const passageList = el("details");
    passageList.appendChild(el("summary", null,
      "استعراض المقاطع والمرشحات (" + t.passage_count + " مقطع)"));
    for (const p of (t.passages_redacted || [])) {
      const pbox = el("section", "passage");
      pbox.appendChild(field("معرف المقطع", p.passage_id));
      pbox.appendChild(field("معرف المصدر الأصلي", p.source_record_id));
      pbox.appendChild(field("إزاحات المقطع في النص الخام (محارف)",
        p.raw_source_span.join("..")));
      pbox.appendChild(field("بصمة المقطع", p.evidence_sha256));
      pbox.appendChild(field("حالة المقطع", p.verification_status));
      const matching = (t.candidates_redacted || [])
        .filter(cd => cd.passage_id === p.passage_id);
      const clist = el("details");
      clist.appendChild(el("summary", null,
        "المرشحات المرتبطة (" + matching.length + ")"));
      for (const cd of matching) {
        const item = el("div", "candidate");
        item.appendChild(field("معرف المرشح", cd.candidate_id));
        item.appendChild(field("النوع", cd.interpretation_type));
        item.appendChild(field("المتحدث", cd.speaker_name === null
          ? "غير محدد" : cd.speaker_name));
        item.appendChild(field("حالة الهوية", cd.speaker_identity_status));
        item.appendChild(field("نوع النسبة", cd.attribution_type));
        item.appendChild(field("ترشيح المؤلف", cd.author_endorsement));
        item.appendChild(field("ثقة النسبة", cd.attribution_confidence));
        item.appendChild(field("حالة التحقق", cd.verification_status));
        item.appendChild(field("إزاحات المرشح في النص الخام (محارف)",
          cd.raw_source_span.join("..")));
        item.appendChild(field("إزاحات المرشح داخل المقطع (محارف)",
          cd.statement_start + ".." + cd.statement_end));
        item.appendChild(field("بصمة شاهد المرشح", cd.evidence_sha256));
        clist.appendChild(item);
      }
      if (!matching.length) clist.appendChild(el("p", "empty", "لا مرشحات"));
      pbox.appendChild(clist);
      passageList.appendChild(pbox);
    }
    if (!(t.passages_redacted || []).length) {
      passageList.appendChild(el("p", "empty", "لا مقاطع متاحة"));
    }
    box.appendChild(passageList);
    $("tafsirs").appendChild(box);
  }
  if (data.hadith) {
    const h = data.hadith;
    const hb = el("section", "work");
    hb.appendChild(el("h3", null, "الروايات والأحاديث المرتبطة بالتفسير"));
    if (h.status !== "OK") {
      hb.appendChild(el("p", "empty", "تعذر التشغيل: " + (h.code || h.status)));
    } else {
      const hc = el("div", "counts");
      hc.appendChild(el("span", null, "نوافذ إشارات روائية غير متحقق منها: " + h.mentions_total));
      hc.appendChild(el("span", null, "مقاطع مصادر مفهرسة (ليست أحاديث مستقلة): " + h.witnesses_total));
      hc.appendChild(el("span", null, "روابط: " + h.links_total));
      for (const [st, n] of Object.entries(h.links_by_status || {})) {
        hc.appendChild(el("span", null, st + ": " + n));
      }
      hb.appendChild(hc);
      hb.appendChild(field("المصادر المستخدمة", (h.sources_used || []).join(", ") || "—"));
      hb.appendChild(field("حالة القراءة", h.sources_unavailable && h.sources_unavailable.length ? "بعض المصادر غير متاحة محلياً (SOURCE_UNAVAILABLE)" : "جميع المصادر المصرح بها متاحة وموثقة"));
      const jd = el("details");
      jd.appendChild(el("summary", null, "مؤشرات نقدية لغوية غير محققة (" + ((h.commentary || {}).records_total || 0) + ")"));
      hb.appendChild(jd);
      const ml = el("details");
      ml.appendChild(el("summary", null, "نوافذ الذكر المرشحة (" + h.mentions_total + ") — بيانات وصفية فقط"));
      for (const mn of (h.mentions || []).slice(0, 50)) {
        const mi = el("div", "work");
        mi.appendChild(field("معرف الذكر", mn.mention_id));
        mi.appendChild(field("النوع", mn.mention_type));
        mi.appendChild(field("حالة النسبة", mn.attribution_status));
        mi.appendChild(field("حالة التحقق", mn.verification_status));
        mi.appendChild(field("بصمة الموضع", mn.evidence_sha256));
        ml.appendChild(mi);
      }
      hb.appendChild(ml);
    }
    $("relations").appendChild(hb);
  }
  const rel = el("section", "work");
  rel.appendChild(el("h3", null, "العلاقات المرشحة"));
  rel.appendChild(boolSpan("موثقة علمياً", false));
  const rs = data.relations || [];
  if (!rs.length) rel.appendChild(el("p", "empty", "لا علاقات"));
  for (const r of rs) {
    const type = r.relation_type === "UNDETERMINED"
      ? "غير محسومة (ليست اتفاقاً ولا خلافاً)" : r.relation_type;
    const row = el("p", "relation");
    row.appendChild(el("span", null, type + " — "));
    row.appendChild(el("code", null, r.relation_id));
    row.appendChild(field("من المرشح", r.from_candidate_id));
    row.appendChild(field("إلى المرشح", r.to_candidate_id));
    row.appendChild(field("حالة التحقق", r.verification_status));
    rel.appendChild(row);
  }
  $("relations").appendChild(rel);
  $("result").hidden = false;
}
$("go").addEventListener("click", search);
$("ref").addEventListener("keydown", (e) => { if (e.key === "Enter") search(); });
