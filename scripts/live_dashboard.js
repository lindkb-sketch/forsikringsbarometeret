/* Source-driven primary homepage dashboard, independent of legacy quarterly snapshots. */
(function(){
'use strict';
const ROOT='data/';
const COMPANIES=['Fremtind','Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand'];
const METRICS=[['insurance_revenue','Inntekter'],['insurance_service_result','Forsikringsresultat'],['combined_ratio','Combined ratio'],['loss_ratio','Skadeprosent'],['expense_ratio','Kostnadsprosent']];
const RATE=new Set(['combined_ratio','loss_ratio','expense_ratio','return_on_equity','solvency_ratio']);
const esc=v=>String(v==null?'':v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=v=>new Intl.NumberFormat('nb-NO',{maximumFractionDigits:1}).format(v);
const pct=v=>new Intl.NumberFormat('nb-NO',{maximumFractionDigits:1,minimumFractionDigits:1}).format(v)+' %';
const safeUrl=v=>typeof v==='string'&&/^https:\/\//.test(v)?esc(v):'#';
const metricValue=r=>r?(RATE.has(r.metric)?pct(r.value):money(r.value)+' '+esc(r.unit||'')):'—';
let state={feed:null,news:null,editorial:null,stocks:null,selected:null,lastSync:null,errors:[]};
let manuallySelected=false;
function periods(){
 const all=state.feed?.observations||[];
 return [...new Set(all.filter(r=>r.scope==='group'&&r.period_type==='quarter'&&r.status==='reported')
 .map(r=>r.year+'-'+r.quarter))].sort((a,b)=>{const [ay,aq]=a.split('-').map(Number),[by,bq]=b.split('-').map(Number);return by-ay||bq-aq});
}
function activePeriod(){const ps=periods();if(!ps.length)return null;if(!manuallySelected||!ps.includes(state.selected))state.selected=ps[0];const [year,quarter]=state.selected.split('-').map(Number);return {year,quarter,label:'Q'+quarter+' '+year};}
function get(company,periodType,metric,year,quarter,scope='group'){
 return (state.feed?.observations||[]).find(r=>r.company===company&&r.scope===scope&&r.period_type===periodType&&r.metric===metric&&r.year===year&&r.quarter===quarter&&['reported','calculated'].includes(r.status)&&Number.isFinite(r.value));
}
function change(cur,prev,metric){
 if(!cur||!prev||cur.unit!==prev.unit)return '<span class="live-muted">Sammenligning ikke verifisert</span>';
 const diff=cur.value-prev.value;
 const flat=Math.abs(diff)<0.00001;
 const lowerBetter=['combined_ratio','loss_ratio','expense_ratio'].includes(metric);
 const better=!flat&&(lowerBetter?diff<0:diff>0);
 const unit=RATE.has(metric)?'pp':esc(cur.unit||'');
 const delta=RATE.has(metric)?Math.abs(diff):Math.abs(diff);
 return '<span class="live-change '+(flat?'flat':better?'good':'bad')+'">'+(flat?'→':diff>0?'▲':'▼')+' '+(flat?'0':(diff>0?'+':'−')+money(delta))+' '+unit+'</span>';
}
function definition(r){
 if(!r)return '';
 const d=(r.source_definition||'').toLowerCase();
 if(/not ifrs insurance revenue|premiums f\.o\.a\.|segment premiums/.test(d))
  return 'Insurance premiums f.o.a. (APM) – ikke IFRS 17-forsikringsinntekter; ikke direkte sammenlignbart';
 if(r.company==='Storebrand'&&r.scope==='norway'&&r.metric==='insurance_revenue')
  return 'Storebrand Forsikring AS – IFRS 17-forsikringsinntekter';
 return '';
}
function renderFinancial(){
 const selected=activePeriod();
 if(!selected)return '<p>Ingen kildeverifiserte rapporttall tilgjengelig.</p>';
 const {year,quarter,label}=selected;
 const choices=periods().map(p=>{const [y,q]=p.split('-');return '<option value="'+p+'" '+(p===state.selected?'selected':'')+'>Q'+q+' '+y+'</option>';}).join('');
 const thead='<tr><th>Selskap</th>'+METRICS.map(([,name])=>'<th>'+name+'</th>').join('')+'</tr>';
 const table=type=>'<div class="live-scroll"><table class="live-fin-table"><thead>'+thead+'</thead><tbody>'+COMPANIES.map(c=>{
   let cells=METRICS.map(([metric])=>{
     const now=get(c,type,metric,year,quarter);
     const prior=get(c,type,metric,year-1,quarter);
     const note=definition(now);
     return '<td data-company="'+esc(c)+'" data-metric="'+metric+'" data-period="'+type+'">'+
       (now?'<div class="live-primary">'+metricValue(now)+'</div>':'<span class="live-muted">Ikke rapportert</span>')+
       (note?'<div class="live-disclaimer">'+esc(note)+'</div>':'')+
       '<div class="live-prior">'+(prior?'Q'+quarter+' '+(year-1)+': '+metricValue(prior):'Fjorår: ikke verifisert')+'</div>'+
       (now?'<div>'+change(now,prior,metric)+'</div>':'')+
       (now?'<a class="live-source" target="_blank" rel="noopener noreferrer" href="'+safeUrl(now.source_url)+'">Rapportkilde ↗</a>':'')+
       '</td>';
   }).join('');
   return '<tr><th>'+esc(c)+(c==='Sampo'?'/If':'')+'</th>'+cells+'</tr>';
 }).join('')+'</tbody></table></div>';
 const groupRow=METRICS.map(([metric])=>{
   const r=get('Storebrand','quarter',metric,year,quarter,'norway');
   return '<td data-metric="'+metric+'">'+(r?'<strong>'+metricValue(r)+'</strong><div class="live-disclaimer">'+esc(definition(r))+'</div><a class="live-source" target="_blank" rel="noopener noreferrer" href="'+safeUrl(r.source_url)+'">Kilde ↗</a>':'—')+'</td>';
 }).join('');
 const norway='<details class="live-norway" open><summary>Storebrand Forsikring AS – norske IFRS 17-tall ('+label+')</summary><div class="live-scroll"><table class="live-fin-table"><thead>'+thead+'</thead><tbody><tr><th>Storebrand Forsikring AS</th>'+groupRow+'</tr></tbody></table></div><p class="live-disclaimer">Storebrand ASA konsern: «Insurance premiums f.o.a.» er et alternativt resultatmål (APM). Storebrand Forsikring AS: «Forsikringsinntekter» følger IFRS 17. Tallene representerer ulike avgrensninger og skal ikke sammenlignes direkte.</p></details>';
 return '<section class="live-complete-financial" aria-label="Automatisk rapporterte kvartals- og HIÅ-tall"><div class="live-section-head"><div><div class="eyebrow">KILDEVERIFISERTE RESULTATER</div><h2>Rapporterte finansielle nøkkeltall</h2><p>Automatisk fra offisielle kvartalsrapporter. «—» betyr at et sammenlignbart tall ikke er verifisert.</p></div><label>Velg kvartal <select id="live-quarter-select" aria-label="Velg kildeverifisert kvartal">'+choices+'</select></label></div><h3>Kvartalet isolert · '+label+'</h3>'+table('quarter')+'<h3>HIÅ · Q1–Q'+quarter+' '+year+'</h3>'+table('ytd')+norway+'</section>';
}
function newsItems(){
 const now=activePeriod();
 const entries=(state.news?.items||[]).filter(x=>x.approved&&x.headline&&/^https:\/\//.test(x.source_url||''));
 const strategic=/partner|samarbeid|oppkjøp|kjøper|fusjon|distribusjon|avtale|marked|strateg|pris|vekst|produkt|konkurran|overtar|acqui|partnership/i;
 const selected=entries.filter(x=>strategic.test(x.headline)).slice(0,4);
 const fallback=selected.length?selected:entries.slice(0,4);
 const tiles=fallback.map(x=>'<article class="live-strategy-card"><div class="live-muted">'+esc(x.publisher||'Nyhetskilde')+' · '+esc((x.published_at||'').slice(0,10))+'</div><h4>'+esc(x.headline)+'</h4><a href="'+safeUrl(x.source_url)+'" target="_blank" rel="noopener noreferrer">Les originaloverskrift ↗</a></article>').join('');
 return '<section class="live-strategy" aria-label="Strategiske nyheter"><div class="live-section-head"><div><div class="eyebrow">NYHETER OG STRATEGI</div><h2>Strategiske bevegelser i markedet</h2><p>Automatisk utvalgte, kildeattribuerte overskrifter. Innholdet i hele artiklene er ikke kontrollert.</p></div></div><div class="live-strategy-grid">'+(tiles||'<p class="live-muted">Ingen nye kildeattribuerte nyheter.</p>')+'</div></section>';
}
function editorial(){
 const p=activePeriod();
 const facts=(state.editorial?.brief||[]).filter(x=>x.text?.includes(p?.label||'')).slice(0,8);
 const interpret=(state.editorial?.implications||[]).slice(0,4);
 const list=items=>items.map(x=>'<li>'+esc(x.text)+' <a href="'+safeUrl(x.source_url)+'" target="_blank" rel="noopener noreferrer">Kilde ↗</a></li>').join('');
 return '<section class="live-quarterly-editorial" aria-label="Automatisk kvartalsbrief og kvartalskommentar"><div class="live-section-head"><div><div class="eyebrow">KVARTALSANALYSE · '+esc(p?.label||'')+'</div><h2>Kvartalsbrief og kvartalskommentar</h2><p>Automatisk genererte fakta og regelbaserte kommentarer, med rapportlenker.</p></div></div><div class="live-editorial-cols"><div><h3>Kvartalsbrief</h3><ul>'+list(facts)+'</ul></div><div><h3>Kvartalskommentar</h3><ul>'+list(interpret)+'</ul></div></div></section>';
}
function market(){
 const prices=state.stocks?.prices||{};
 const quotes=Object.entries(prices).map(([company,q])=>{
   const freshness=q.trading_date?'Kursdato '+esc(q.trading_date):'Ukjent kursdato';
   return '<div class="live-quote"><b>'+esc(company)+'</b><strong>'+money(q.close)+' '+esc(q.currency)+'</strong><small>'+freshness+' · forsinket sluttkurs</small><a target="_blank" rel="noopener noreferrer" href="'+safeUrl(q.source_url)+'">Datakilde ↗</a></div>';
 }).join('');
 const updated=state.stocks?.updated_at?new Date(state.stocks.updated_at).toLocaleString('nb-NO',{dateStyle:'short',timeStyle:'short'}):'Ukjent';
 const errs=Object.entries(state.stocks?.errors||{});
 return '<section class="live-stock-panel" aria-label="Aksjekurser og oppdateringsstatus"><div class="live-section-head"><div><div class="eyebrow">BØRSKURSER</div><h2>Forsinkede aksjekurser</h2><p>Siste vellykkede innhentingsforsøk: '+esc(updated)+'. Prisene er ikke sanntidskurser, og datoen kan være eldre enn dagens dato.</p></div></div><div class="live-quote-grid">'+quotes+'</div>'+(errs.length?'<p class="live-disclaimer">Innhentingsfeil: '+esc(errs.map(([c])=>c).join(', '))+'</p>':'')+'</section>';
}
function html(){
 if(!state.feed)return '<div class="live-status">Henter verifiserte kvartalstall, HIÅ, nyheter og aksjekurser …</div>';
 return renderFinancial()+editorial()+newsItems()+market();
}
function install(){
 const app=document.getElementById('app');
 if(!app||typeof home!=='function'||typeof company!=='function')return;
 if(!window.__liveDashboardInstalled){
  const originalHome=home,originalCompany=company;
  home=function(){return '<div id="live-primary-dashboard">'+html()+'</div>'+originalHome();};
  company=function(c){return '<div id="live-primary-dashboard">'+renderFinancial()+'</div>'+originalCompany(c);};
  window.__liveDashboardInstalled=true;
  document.addEventListener('change',e=>{if(e.target?.id==='live-quarter-select'){state.selected=e.target.value;manuallySelected=true;show(current,true);}});
 }
 if(typeof show==='function')show(current,true);
}
async function refresh(){
 const sources=['verified_financial_feed.json','quarterly_editorial.json','official_news.json','stock_prices.json'];
 const result=await Promise.allSettled(sources.map(async x=>{
  const response=await fetch(ROOT+x+'?t='+Date.now(),{cache:'no-store'});
  if(!response.ok)throw Error(x+' HTTP '+response.status);
  return response.json();
 }));
 const names=['feed','editorial','news','stocks'];
 state.errors=[];
 result.forEach((r,i)=>{if(r.status==='fulfilled')state[names[i]]=r.value;else state.errors.push(sources[i]+': '+String(r.reason));});
 state.lastSync=new Date().toISOString();
 install();
}
window.ForsikringsbarometerLive={refresh,periods,activePeriod,get,change,definition,state};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>{install();refresh();});
else{install();refresh();}
setInterval(refresh,300000);
})();