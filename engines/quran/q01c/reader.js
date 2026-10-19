"use strict";
const $=id=>document.getElementById(id);
const hits=$("hits");
const feedback=$("feedback");
let sourceType="unknown";
function clearHits(){while(hits.firstChild)hits.removeChild(hits.firstChild);}
function showMessage(message){feedback.textContent=message;}
async function api(path){
  const response=await fetch(path,{method:"GET",credentials:"omit",cache:"no-store"});
  const data=await response.json();
  if(!response.ok)throw new Error(data.error||"Request rejected");
  return data;
}
// External citations are navigation only: NO KSU scraping, embedding, or tafsir API.
const AYAT_BASE="https://quran.ksu.edu.sa/index.php";
const REAL_SOURCES=new Set(["unverified_github_mirror","tanzil_domain_unattested_export"]);
function addText(parent,tag,message,className){
  const el=document.createElement(tag);
  if(className)el.className=className;
  el.textContent=message;
  parent.appendChild(el);
  return el;
}
function addExternal(parent,label,url){
  const a=document.createElement("a");
  a.href=url;
  a.textContent=label;
  a.target="_blank";
  a.rel="noopener noreferrer";
  a.referrerPolicy="no-referrer";
  parent.appendChild(a);
}
function renderTafsir(item,card){
  const tafsir=document.createElement("section");
  tafsir.className="tafsir-links";
  tafsir.setAttribute("aria-label","مصادر التفسير الخارجية");
  addText(tafsir,"h3","التفسير — إحالات خارجية");
  const m=typeof item.reference==="string"?
    /^([1-9][0-9]{0,2}):([1-9][0-9]{0,2})$/.exec(item.reference):null;
  if(!REAL_SOURCES.has(sourceType)||!m||Number(m[1])>114||Number(m[2])>286){
    addText(tafsir,"p",sourceType==="synthetic_fixture"?
      "مراجع التفسير غير متاحة للبيانات الاصطناعية؛ النص المعروض ليس آية.":
      "روابط التفسير معطّلة: مصدر النص أو مرجع الآية غير مؤهل للإحالة.",
      "tafsir-warning");
  }else{
    const verseHash="#aya="+m[1]+"_"+m[2]+"&m=hafs";
    addText(tafsir,"p","الإحالة إلى مشروع «آيات» بجامعة الملك سعود؛ التفسير يبقى في الموقع الخارجي ولا يُنقل إلى مُبين. قد تتغير إعدادات الموقع.","tafsir-note");
    const links=document.createElement("div");
    links.className="tafsir-outbound";
    addExternal(links,"عرض الآية مع خيار التفسير الميسر على «آيات»",
      AYAT_BASE+verseHash+"&qaree=husary&trans=ar_mu");
    addExternal(links,"فتح الآية واختيار تفسير آخر في «آيات»",
      AYAT_BASE+verseHash);
    tafsir.appendChild(links);
    addText(tafsir,"p","يوفر الموقع اختيار تفاسير مثل السعدي والبغوي وابن كثير والقرطبي والطبري. أسماء الكتب هنا مرجع للتصفح، وليست نصوصًا مستوردة أو موافقات حقوق.","tafsir-note");
    addText(tafsir,"small","مصدر منصة آيات: جامعة الملك سعود؛ تسند المنصة أصول التفاسير إلى mosshaf.com، والنص القرآني إلى Tanzil.");
  }
  card.appendChild(tafsir);
  const ai=document.createElement("section");
  ai.className="ai-explanation";
  ai.setAttribute("aria-label","التحليل الآلي");
  addText(ai,"h3","التحليل الآلي — منفصل عن التفسير");
  addText(ai,"p","غير مفعّل. لم يُنشئ مُبين تفسيرًا آليًا أو حكمًا شرعيًا لهذه الآية.");
  card.appendChild(ai);
}
function renderHit(item){
  const card=document.createElement("article");card.className="ayah";
  const ref=document.createElement("small");
  ref.textContent="مرجع السورة والآية: "+item.reference;
  const text=document.createElement("p");text.className="verse";text.dir="rtl";
  // SECURITY: Quran text is an untrusted string; never insert as HTML.
  text.textContent=item.text;
  const meta=document.createElement("small");
  meta.textContent=(sourceType==="synthetic_fixture" ?
    "نص اصطناعي للتجربة؛ ليس آية قرآنية" :
    (sourceType==="tanzil_domain_unattested_export" ?
      "نص من استجابة نطاق Tanzil، مثبت البصمة؛ ليس إصدارًا معتمدًا" :
      "نص مرآة غير موثّقة رسميًا؛ منسوب إلى Tanzil"))
    +" · مصدر: "+item.source_id;
  const scripture=document.createElement("section");
  scripture.className="quran-text-block";
  scripture.setAttribute("aria-label","النص القرآني وبيانات مصدره");
  scripture.append(ref,text,meta);
  card.appendChild(scripture);
  renderTafsir(item,card);
  hits.append(card);
}
function renderMany(results){
  clearHits();
  for(const item of results)if(item.found)renderHit(item);
  showMessage(results.length ? "عدد النتائج المعروضة: "+results.length :
    "لم تُعثر على نتيجة في الملف المحمّل.");
}
async function init(){
  try{
    const data=await api("/api/status");
    sourceType=data.source_kind;
    $("source-details").textContent=
      "المصدر: "+data.source_id+" · السور: "+data.chapter_count+
      " · السجلات: "+data.verse_count+
      " · SHA-256: "+data.raw_sha256+
      " · اعتماد أصالة النص: لا · مراجعة حقوق الاستخدام: غير مكتملة";
    if(sourceType==="synthetic_fixture"){
      showMessage("ملف الاختبار اصطناعي؛ أي نص معروض هنا ليس آية.");
    }
  }catch(e){showMessage("تعذّر تحميل حالة المصدر: "+e.message);}
}
$("lookup-form").addEventListener("submit",async event=>{
  event.preventDefault();clearHits();showMessage("جارٍ الاسترجاع…");
  try{
    const value=$("reference").value.trim();
    const d=await api("/api/get?ref="+encodeURIComponent(value));
    renderMany(d.result.found?[d.result]:[]);
  }catch(e){showMessage("تعذر الاسترجاع: "+e.message);}
});
$("search-form").addEventListener("submit",async event=>{
  event.preventDefault();clearHits();showMessage("جارٍ البحث…");
  try{
    const q=$("query").value.trim();
    const mode=$("fold-marks").checked?"folded":"exact";
    const d=await api("/api/find?q="+encodeURIComponent(q)+"&mode="+mode+"&limit=20");
    renderMany(d.results);
  }catch(e){showMessage("تعذر البحث: "+e.message);}
});
$("notice-details").addEventListener("toggle",async event=>{
  if(!event.target.open||$("source-notice").dataset.loaded==="yes")return;
  try{
    const d=await api("/api/notice");
    // Preserve the original notice bytes' decoded text, without markup.
    $("source-notice").textContent=d.notice;
    $("source-notice").dataset.loaded="yes";
  }catch(e){$("source-notice").textContent="تعذّر عرض إشعار المصدر.";}
});
init();
