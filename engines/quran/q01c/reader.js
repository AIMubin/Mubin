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
// External tafsir is optional navigation only: no KSU API call or text import.
const KSU_BASE="https://quran.ksu.edu.sa/index.php";
function plain(parent,tag,value){
  const el=document.createElement(tag);
  el.textContent=value;
  parent.appendChild(el);
  return el;
}
function externalLink(parent,label,url){
  const a=document.createElement("a");
  a.textContent=label;
  a.href=url;
  a.target="_blank";
  a.rel="noopener noreferrer";
  a.referrerPolicy="no-referrer";
  parent.appendChild(a);
}
async function loadTafsirMetadata(item,panel){
  try{
    const d=await api("/api/tafsir-catalog?ref="+encodeURIComponent(item.reference));
    if(!panel.isConnected)return; // stale search results must not be rehydrated
    if(d.reference!==item.reference || d.use_scope!=="external_navigation_only" ||
       d.text_import_allowed!==false || d.rights_verified!==false ||
       d.edition_verified!==false || d.p1_admitted!==false ||
       d.scholarly_verification!==false || d.ai_tafsir_generated!==false ||
       !Array.isArray(d.sources) || d.sources.length!==6 ||
       !d.links || typeof d.links!=="object"){
      throw new Error("unqualified_catalog");
    }
    const parts=/^([1-9][0-9]{0,2}):([1-9][0-9]{0,2})$/.exec(item.reference);
    if(!parts)throw new Error("invalid_reference");
    const base=KSU_BASE+"#aya="+parts[1]+"_"+parts[2]+"&m=hafs";
    if(d.links.choose_tafsir!==base ||
       d.links.muyassar!==base+"&qaree=husary&trans=ar_mu"){
      throw new Error("unexpected_external_host_or_path");
    }
    // Validate all rows before adding any item. No partial approved-looking list.
    for(const src of d.sources){
      if(typeof src.title_ar!=="string" || typeof src.id!=="string" ||
         src.edition!==null || src.source_status!=="metadata_only_unreviewed" ||
         src.rights_status!=="not_verified" || src.text_ingested!==false ||
         src.allowed_for_local_quotation!==false || src.p1_eligible!==false ||
         src.link_scope!=="ksu_navigation_not_book_text"){
        throw new Error("invalid_source_claim");
      }
    }
    panel.replaceChildren();
    plain(panel,"h3","التفسير — روابط خارجية، وليس نصوصًا مستوردة");
    plain(panel,"p","مراجع وصفية غير مُحققة الطبعة أو الحقوق. عند فتح الرابط تنتقل إلى موقع «آيات» الخارجي.");
    const links=document.createElement("div");
    links.className="tafsir-outbound";
    externalLink(links,"عرض الآية مع خيار التفسير الميسر في آيات",d.links.muyassar);
    externalLink(links,"فتح آيات لاختيار تفسير آخر",d.links.choose_tafsir);
    panel.appendChild(links);
    const list=document.createElement("ul");
    list.className="tafsir-bibliography";
    for(const src of d.sources){
      const author=src.author_ar || "المؤلف غير محدد في السجل";
      plain(list,"li",src.title_ar+" — "+author+" · الطبعة غير محددة · الحقوق غير متحقق منها");
    }
    panel.appendChild(list);
  }catch(_e){
    if(!panel.isConnected)return;
    panel.replaceChildren();
    plain(panel,"p","سجل التفاسير غير متاح؛ لا توجد إحالة موثقة لهذه الآية.");
  }
}
function appendTafsir(item,card){
  const panel=document.createElement("section");
  panel.className="tafsir-links";
  panel.setAttribute("aria-label","إحالات تفاسير خارجية غير محققة");
  if(sourceType!=="unverified_github_mirror"){
    plain(panel,"p","إحالات التفسير معطلة لبيانات الاختبار الاصطناعية أو للمصادر غير المؤهلة.");
  }else{
    plain(panel,"p","جارٍ تحميل الإحالات الببليوغرافية المحلية…");
  }
  card.appendChild(panel);
  const ai=document.createElement("section");
  ai.className="ai-explanation";
  plain(ai,"strong","التحليل الآلي — غير مفعّل");
  plain(ai,"p","لم يُنشئ مُبين تفسيرًا آليًا أو حكمًا شرعيًا لهذه الآية.");
  card.appendChild(ai);
  if(sourceType==="unverified_github_mirror")void loadTafsirMetadata(item,panel);
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
  card.append(ref,text,meta);
  appendTafsir(item,card);
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
