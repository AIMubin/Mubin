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
    "نص مرآة غير موثّقة رسميًا؛ منسوب إلى Tanzil")
    +" · مصدر: "+item.source_id;
  card.append(ref,text,meta);hits.append(card);
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
