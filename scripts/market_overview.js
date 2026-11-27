/* Source-only overview. Rank reported quarterly income in NOK, then sort by CR.
   No historical/Group fallback for an unpublished geography or business line. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else {root.FBMarketOverview=api;api.start();}
})(typeof window==='undefined'?globalThis:window,function(){
  'use strict';
  const COMPANIES=['Fremtind','Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand','KLP Skadeforsikring','Alm. Brand'];
  const METRICS=['insurance_revenue','combined_ratio','loss_ratio','expense_ratio'];
  const CORE=['combined_ratio','loss_ratio','expense_ratio'];
  const EXTENDED=['KLP Skadeforsikring','Alm. Brand'];
  const NORWAY_EQUIVALENT=['Frende','KLP Skadeforsikring','Storebrand'];
  const SCOPE_RULES={
    'Gjensidige':['group/all','group/pm','group/bm','norway/all','norway/pm','norway/bm'],
    'Tryg':['group/all','group/pm','group/bm','norway/all'],
    'Fremtind':['group/all','group/pm','group/bm','norway/all','norway/pm','norway/bm'],
    'Sampo':['group/all'],
    'Protector':['group/all','group/bm','norway/all','norway/bm'],
    'Frende':['group/all','norway/all'],
    'Storebrand':['group/all','norway/all'],
    'KLP Skadeforsikring':['group/all','norway/all'],
    'Alm. Brand':['group/all','group/pm','group/bm']
  };
  const BUSINESS_SEGMENT_ISSUERS=['Gjensidige','Tryg','Fremtind','Alm. Brand'];
  // Exact published segment labels only. Nordic segments are explicitly
  // identified, not mislabeled as Norway or as the whole consolidated group.
  const SEGMENTS={
    group:{pm:['private','private nordic','private group','privat','privat nordisk','privat konsern'],
           bm:['commercial','nordic commercial','commercial nordic','commercial group','bedrift','bedrift nordisk','bedrift konsern']},
    norway:{pm:['private norway','norway private','privat norge','norge pm','pm norge'],
            bm:['commercial norway','norway commercial','bedrift norge','norge bm','bm norge']}
  };
  const safe=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const source=v=>typeof v==='string'&&/^https:\/\//.test(v);
  const num=v=>typeof v==='number'&&Number.isFinite(v);
  const format=(v,d=1)=>num(v)?new Intl.NumberFormat('nb-NO',{minimumFractionDigits:d,maximumFractionDigits:d}).format(v):'–';
  const pct=v=>num(v)?format(v)+' %':'Ikke rapportert';
  const growthText=v=>num(v)?(v>0?'+':'')+pct(v):'Ikke rapportert';
  const title=p=>p?'Q'+p.quarter+' '+p.year:'';
  const pretty=c=>c==='Sampo'?'Sampo / If':c;
  const currency=unit=>({NOKm:'NOK',MNOK:'NOK',DKKm:'DKK',MDKK:'DKK',EURm:'EUR',MEUR:'EUR',SEKm:'SEK',MSEK:'SEK'})[unit]||null;
  const basis=r=>{
    const d=(r?.source_definition||'').toLowerCase();
    if(d.startsWith('fremtind apm:'))return 'Forsikringsinntekter (Fremtind APM)';
    if(r?.company==='Storebrand'&&/premiums f\.o\.a\./.test(d))return 'Insurance premiums f.o.a.';
    return /sum driftsinntekter|group operating revenue/.test(d)?'Driftsinntekter':
      /not ifrs insurance revenue|segment premiums|premiums f\.o\.a\.|apm/.test(d)?'Segmentpremier (APM)':'Forsikringsinntekter';
  };
  const valid=r=>COMPANIES.includes(r.company)&&['quarter','ytd'].includes(r.period_type)&&
    ['reported','calculated'].includes(r.status)&&
    ['official_quarterly_report','official_annual_report'].includes(r.source_type)&&
    (r.source_type!=='official_annual_report'||r.quarter===4)&&
    source(r.source_url)&&/^[0-9a-f]{64}$/.test(r.source_sha256||'')&&
    Number.isInteger(r.source_page)&&r.source_page>0&&num(r.value);
  const periodOf=s=>{const m=/^Q([1-4]) (\d{4})$/.exec(s||'');return m?{year:+m[2],quarter:+m[1]}:null;};
  const samePeriod=(a,b)=>a&&b&&a.year===b.year&&a.quarter===b.quarter;
  const cmpPeriod=(a,b)=>a.year-b.year||a.quarter-b.quarter;
  const key=r=>[r.company,r.year,r.quarter,r.period_type,r.scope,r.segment||'',r.metric].join('|');
  function allRows(feed,segments,comparison,context){
    const rows=(feed?.observations||[]).filter(valid);
    const anchors=new Set(rows.filter(r=>r.scope==='group').map(r=>[r.company,r.source_url,r.source_sha256].join('|')));
    for(const c of comparison?.companies||[]){
      const evidence=c.metric_sources?.insurance_revenue;
      if(c.company==='Alm. Brand'&&c.status==='verified_official_pdf_reconciled'&&source(c.source_url)&&
        evidence?.source_url===c.source_url&&/^[0-9a-f]{64}$/.test(evidence.source_sha256||''))
        anchors.add([c.company,c.source_url,evidence.source_sha256].join('|'));
    }
    const index=new Map(rows.map(r=>[key(r),r]));
    for(const r of segments?.observations||[]){
      const note=r.company==='Fremtind'&&r.calculation==='fremtind_reported_apm_segment';
      const anchor=note?r.market_anchor:r;
      if(!valid(r)||r.scope!=='reported_segment'||
        !BUSINESS_SEGMENT_ISSUERS.includes(r.company)||
        !['Private','Commercial'].includes(r.segment)||
        !anchors.has([r.company,anchor?.source_url,anchor?.source_sha256].join('|')))continue;
      if(note&&(!Array.isArray(r.source_documents)||!r.source_documents.length||!r.source_documents.every(d=>source(d.source_url)&&/^[0-9a-f]{64}$/.test(d.source_sha256||'')&&Number.isInteger(d.source_page)&&d.source_page>0)))continue;
      const k=key(r),old=index.get(k);
      if(!old)index.set(k,r);
      else if(Math.abs(old.value-r.value)>.001||old.unit!==r.unit)index.delete(k);
    }
    // Add independently sourced cumulative observations without replacing
    // a verified main-feed observation or accepting a different report hash.
    for(const r of context?.observations||[]){
      if(!valid(r)||r.period_type!=='ytd'||!['reported_segment','norway'].includes(r.scope)||
         !anchors.has([r.company,r.market_anchor?.source_url||r.source_url,r.market_anchor?.source_sha256||r.source_sha256].join('|')))continue;
      if(r.scope==='reported_segment'&&!['Private','Commercial','Private Norway','Commercial Norway'].includes(r.segment))continue;
      const k=key(r);if(!index.has(k))index.set(k,r);
    }
    return [...index.values()];
  }
  function selectUnique(rows,metric){
    const matches=rows.filter(r=>r.metric===metric);
    return matches.length===1?matches[0]:null;
  }
  function choosePeriod(rows,comparison){
    const grouped=new Map();
    for(const r of rows){
      if(r.period_type!=='quarter'||r.scope!=='group'||!['insurance_revenue','combined_ratio'].includes(r.metric))continue;
      const key=[r.company,r.year,r.quarter].join('|');
      if(!grouped.has(key))grouped.set(key,{year:r.year,quarter:r.quarter,metrics:new Set()});
      grouped.get(key).metrics.add(r.metric);
    }
    const choices=[...grouped.values()].filter(x=>x.metrics.size===2).map(({year,quarter})=>({year,quarter}));
    for(const c of comparison?.companies||[]){
      if(!EXTENDED.includes(c.company)||c.status!=='verified_official_pdf_reconciled'||
        !num(c.metrics?.insurance_revenue)||!num(c.metrics?.combined_ratio)||!source(c.source_url))continue;
      const p=periodOf(c.period);if(p)choices.push(p);
    }
    return choices.sort((a,b)=>cmpPeriod(b,a))[0]||null;
  }
  function groupsFor(rows,company,p,scope,market){
    if(!SCOPE_RULES[company]?.includes(scope+'/'+market))return [];
    const current=rows.filter(r=>r.company===company&&samePeriod(r,p));
    // Fremtind's PM/BM note is owner-confirmed to cover the same Norway business.
    // Do not treat the whole Holding result as an observed geographic total.
    if(company==='Fremtind'&&scope==='norway'&&market!=='all'){
      const segment=market==='pm'?'Private':'Commercial';
      return [{rows:current.filter(r=>r.scope==='reported_segment'&&r.segment===segment),
        scope:'reported_segment',segment,displaySegment:segment+' · Norge (rapportert APM)'}];
    }
    if(market==='all'){
      const exact=current.filter(r=>r.scope===scope);
      const income=selectUnique(exact,'insurance_revenue');
      const use=company==='Storebrand'&&!(income?.source_entity==='Storebrand ASA / Insurance segment'||(income?.source_definition||'').includes('Insurance segment'))?[]:exact;
      return [{rows:use,scope,segment:null}];
    }
    // Owner-approved market classification: Protector is commercially
    // oriented (commercial/public/affinity); report totals are its BM proxy.
    // Never reuse Group totals for Norway. No PM allocation is inferred.
    if(company==='Protector'){
      if(market==='pm')return [];
      return [{rows:current.filter(r=>r.scope===scope),scope,segment:null,
        displaySegment:'BM / offentlig og affinity · rapportert total'}];
    }
    const labels=SEGMENTS[scope][market];
    const matching=[...new Set(current.filter(r=>r.scope==='reported_segment'&&labels.includes(String(r.segment||'').toLowerCase().trim())).map(r=>r.segment))];
    if(matching.length!==1)return [];
    return [{rows:current.filter(r=>r.scope==='reported_segment'&&r.segment===matching[0]),scope:'reported_segment',segment:matching[0]}];
  }
  function rowFor(rows,company,p,scope,market){
    const choices=groupsFor(rows,company,p,scope,market);
    if(choices.length!==1)return null;
    const g=choices[0], values=Object.fromEntries(METRICS.map(m=>[m,selectUnique(g.rows,m)]));
    const partialAllowed=company==='Fremtind'&&g.scope==='reported_segment'&&market!=='all';
    if(!values.insurance_revenue||!values.combined_ratio)return null;
    const split=Boolean(values.loss_ratio&&values.expense_ratio);
    if(!split&&!partialAllowed)return null;
    if(Boolean(values.loss_ratio)!==Boolean(values.expense_ratio))return null;
    const revenue=values.insurance_revenue,cur=currency(revenue.unit);
    const cr=values.combined_ratio.value,loss=values.loss_ratio?.value??null,cost=values.expense_ratio?.value??null;
    if(!cur||revenue.value<=0||values.combined_ratio.unit!=='percent'||cr<0||
      (split&&(values.loss_ratio.unit!=='percent'||values.expense_ratio.unit!=='percent'||Math.min(loss,cost)<0||Math.abs(cr-loss-cost)>.25)))return null;
    const prior=rows.filter(r=>r.company===company&&r.year===p.year-1&&r.quarter===p.quarter&&r.scope===g.scope&&(g.scope!=='reported_segment'||r.segment===g.segment));
    const priorRev=selectUnique(prior,'insurance_revenue');
    const reported=selectUnique(g.rows,'insurance_revenue_growth');
    const growth=company==='Fremtind'&&g.scope==='reported_segment'&&reported?.unit==='percent'&&reported.status==='reported'?reported.value:priorRev&&priorRev.value>0&&priorRev.unit===revenue.unit&&basis(priorRev)===basis(revenue)?
      (revenue.value/priorRev.value-1)*100:reported?.unit==='percent'?reported.value:null;
    const deltas={};
    for(const key of CORE){
      const old=selectUnique(prior,key);
      deltas[key]=values[key]&&old&&old.unit==='percent'&&basis(old)===basis(values[key])?values[key].value-old.value:null;
    }
    const evidence=[...Object.values(values).filter(Boolean),...prior.filter(r=>METRICS.includes(r.metric)),...g.rows.filter(r=>r.metric==='insurance_revenue_growth')];
    const sources=[...new Map(evidence.flatMap(r=>[r,...(r.source_documents||[])]).filter(d=>source(d.source_url)).map(d=>[[d.source_url,d.source_sha256,d.source_page].join('|'),{url:d.source_url,sha256:d.source_sha256,page:d.source_page}])).values()];
    return {company,segment:g.displaySegment||g.segment,source:revenue.source_url,sources,revenue:revenue.value,currency:cur,
      revenueBasis:basis(revenue),cr,loss,cost,growth,deltas,split,calculatedCR:values.combined_ratio.status==='calculated'};
  }
  function fremtindNorway(rows,p){
    const pm=rowFor(rows,'Fremtind',p,'norway','pm'),bm=rowFor(rows,'Fremtind',p,'norway','bm');
    if(!pm||!bm||pm.currency!=='NOK'||bm.currency!=='NOK'||pm.source!==bm.source)return rowFor(rows,'Fremtind',p,'norway','all');
    if(!pm.split||!bm.split){
      // Owner confirms both business segments equal Norway. APM segment
      // amounts must reconcile to the reported complete Group total before
      // it can be reused. The partial-CR exception remains PM/BM only.
      const group=rowFor(rows,'Fremtind',p,'group','all');
      if(group?.split&&pm.revenueBasis==='Forsikringsinntekter (Fremtind APM)'&&bm.revenueBasis===pm.revenueBasis&&
         group.currency==='NOK'&&group.source===pm.source&&Math.abs(group.revenue-pm.revenue-bm.revenue)<=3)
        return {...group,segment:'PM + BM · Norge (rapportert APM-total)'};
      return rowFor(rows,'Fremtind',p,'norway','all');
    }
    const revenue=pm.revenue+bm.revenue;
    const weighted=k=>(pm[k]*pm.revenue+bm[k]*bm.revenue)/revenue;
    let growth=null;
    if(num(pm.growth)&&num(bm.growth)&&pm.growth>-100&&bm.growth>-100){
      const old=pm.revenue/(1+pm.growth/100)+bm.revenue/(1+bm.growth/100);
      growth=(revenue/old-1)*100;
    }
    const deltas={};
    for(const [k,short] of [['combined_ratio','cr'],['loss_ratio','loss'],['expense_ratio','cost']]){
      if(num(pm.deltas[k])&&num(bm.deltas[k])&&num(pm.growth)&&num(bm.growth)&&pm.growth>-100&&bm.growth>-100){
        const a=pm.revenue/(1+pm.growth/100),b=bm.revenue/(1+bm.growth/100);
        deltas[k]=weighted(short)-((pm[short]-pm.deltas[k])*a+(bm[short]-bm.deltas[k])*b)/(a+b);
      }
    }
    return {company:'Fremtind',segment:'PM + BM · Norge (beregnet)',source:pm.source,sources:[...(pm.sources||[]),...(bm.sources||[])],revenue,currency:'NOK',revenueBasis:pm.revenueBasis,
      cr:weighted('cr'),loss:weighted('loss'),cost:weighted('cost'),growth,deltas,split:true};
  }
  function extendedRow(c,p){
    if(!EXTENDED.includes(c.company)||c.status!=='verified_official_pdf_reconciled'||!samePeriod(periodOf(c.period),p)||!source(c.source_url))return null;
    const m=p.mode==='ytd'?(c.ytd_metrics||{}):(c.metrics||{});
    if(METRICS.some(k=>!num(m[k]))||m.insurance_revenue<=0||
      !['NOK','DKK','EUR','SEK'].includes(c.currency)||Math.min(m.loss_ratio,m.expense_ratio,m.combined_ratio)<0||
      Math.abs(m.combined_ratio-m.loss_ratio-m.expense_ratio)>.25)return null;
    return {company:c.company,segment:null,source:c.source_url,sources:Object.values(p.mode==='ytd'?(c.ytd_metric_sources||{}):(c.metric_sources||{})).filter(d=>source(d.source_url)).map(d=>({url:d.source_url,sha256:d.source_sha256,page:d.source_page})),revenue:m.insurance_revenue,currency:c.currency,
      revenueBasis:'Forsikringsinntekter',cr:m.combined_ratio,loss:m.loss_ratio,cost:m.expense_ratio,
      growth:num(m.insurance_revenue_growth)?m.insurance_revenue_growth:null,deltas:{}};
  }
  function model(feed,comparison,fx,scope='group',market='all',segments=null,mode='quarter',context=null){
    mode=mode==='ytd'?'ytd':'quarter';
    const all=allRows(feed,segments,comparison,context),period=choosePeriod(all,comparison);
    const p=period?{...period,mode}:null;
    const rows=all.filter(r=>r.period_type===mode);
    if(!p)return {period:null,eligible:[],selected:[],missing:COMPANIES.slice(),fxMissing:[],reported:0};
    const eligible=[];
    for(const company of COMPANIES){
      if(!SCOPE_RULES[company]?.includes(scope+'/'+market))continue;
      const equivalent=scope==='norway'&&market==='all'&&NORWAY_EQUIVALENT.includes(company);
      const actualScope=equivalent?'group':scope;
      let r=company==='Fremtind'&&scope==='norway'&&market==='all'?fremtindNorway(rows,p):rowFor(rows,company,p,actualScope,market);
      if(!r&&actualScope==='group'&&market==='all'&&EXTENDED.includes(company)){
        r=extendedRow((comparison?.companies||[]).find(c=>c.company===company)||{},p);
      }
      if(r)eligible.push({...r,scope,market,periodType:mode});
    }
    const rates=(mode==='ytd'?fx?.periods?.[title(p)]?.ytd_rates:fx?.periods?.[title(p)]?.rates)||{};
    const rate=cur=>cur==='NOK'?1:(num(rates[cur])&&rates[cur]>0?rates[cur]:null);
    const fxMissing=eligible.filter(r=>rate(r.currency)===null).map(r=>r.company);
    // Ranking is not a "top five" if some eligible issuers are unrankable.
    const ranked=fxMissing.length?[]:eligible.map(r=>({...r,revenueNok:r.revenue*rate(r.currency)}))
      .sort((a,b)=>b.revenueNok-a.revenueNok||a.company.localeCompare(b.company,'nb'));
    const selected=ranked.slice(0,5).sort((a,b)=>a.cr-b.cr||b.revenueNok-a.revenueNok||a.company.localeCompare(b.company,'nb'));
    const reported=COMPANIES.filter(c=>rowFor(rows,c,p,'group','all')||
      extendedRow((comparison?.companies||[]).find(r=>r.company===c)||{},p)).length;
    return {period,mode,eligible,selected,missing:COMPANIES.filter(c=>!eligible.some(r=>r.company===c)),fxMissing,reported};
  }
  const median=values=>{
    const v=values.filter(num).sort((a,b)=>a-b),i=Math.floor(v.length/2);
    return !v.length?null:v.length%2?v[i]:(v[i-1]+v[i])/2;
  };
  const pp=v=>format(Math.abs(v))+' prosentpoeng';
  const DRIVER_LABELS={
    price:'premie- og prisjusteringer',
    volume_up:'økt forsikringsvolum',
    volume_down:'lavere volum i deler av porteføljen',
    customer_inflow:'kundetilgang gjennom distribusjonssamarbeid',
    customer_growth:'vekst i kundebestanden',
    policy_count_growth:'vekst i antall forsikringer',
    uk_lcp_growth:'vekst i rapportert britisk LCP-bestand',
    retail_growth:'vekst i privatkundesegmentet',
    gwp_lcy_higher:'valutaeffekt på bruttopremievekst',
    volume_pm_products:'volumvekst innen eiendom, person og reise',
    portfolio_growth:'porteføljevekst i utvalgte segmenter',
    retention_up:'bedret kundelojalitet',
    risk_selection:'selektiv risikoutvelgelse og prioritering av lønnsom vekst',
    competition:'konkurransepress i enkelte næringssegmenter'
  };
  const joinNatural=xs=>xs.length<2?(xs[0]||''):xs.slice(0,-1).join(', ')+' og '+xs.at(-1);
  function scopedInsights(m,scope,market,context){
    const names=new Set(m.eligible.map(r=>r.company)),period=title(m.period),mode=m.mode||'quarter';
    return (context?.insights||[]).filter(x=>x.period===period&&x.source_document_period===period&&x.period_type===mode&&names.has(x.company)&&source(x.source_url)&&
      ['official_quarterly_report','official_results_presentation'].includes(x.source_type)&&
      /^[0-9a-f]{64}$/.test(x.source_sha256||'')&&Number.isInteger(x.source_page)&&x.source_page>0&&
      Array.isArray(x.views)&&x.views.includes(scope+'/'+market)&&typeof x.text==='string');
  }
  // Prefer specific, sourced explanations to label-only keyword lists.
  // Keep the numeric opening compact; never pad sparse early-quarter coverage.
  const wordCount=s=>String(s||'').trim().split(/\s+/).filter(Boolean).length;
  function explanatoryText(scoped,theme){
    const items=scoped.filter(x=>x.theme===theme&&typeof x.topic==='string'&&num(x.priority)&&typeof x.evidence==='string'&&x.evidence.trim()&&x.text.trim());
    const sorted=[...items].sort((a,b)=>b.priority-a.priority||a.company.localeCompare(b.company,'nb')||a.source_page-b.source_page);
    return [...new Map(sorted.reverse().map(x=>[x.topic,x])).values()].reverse().sort((a,b)=>b.priority-a.priority);
  }
  function appendWithin(target,items,maxWords,maxItems=3){
    let added=0;
    for(const item of items){
      const t=typeof item==='string'?item:item.text;
      if(!t||target.includes(t)||added>=maxItems)continue;
      if(wordCount(target.join(' '))+wordCount(t)>maxWords&&added>0)continue;
      if(wordCount(target.join(' '))+wordCount(t)>maxWords+12)continue;
      target.push(t);added++;
    }
    return added;
  }
  function richerComments(scoped,market,growth,cr,special){
    const gs=explanatoryText(scoped,'growth_explanation'),ls=explanatoryText(scoped,'loss_explanation'),cs=explanatoryText(scoped,'cost_explanation'),es=explanatoryText(scoped,'event_explanation');
    if(gs.length){
      const original=growth.slice(),opening=original[0];
      growth.splice(0,growth.length,opening);
      const positive=gs.filter(x=>!['restraint','currency'].includes(x.category));
      const restraint=gs.filter(x=>x.category==='restraint');
      const priceVolume=positive.find(x=>['pm_product_volumes','pm_price_volume'].includes(x.topic));
      const first=market==='bm'?(restraint[0]||positive[0]):(priceVolume||positive[0]||restraint[0]);
      const used=new Set();
      const offer=x=>{
        if(!x||used.has(x.topic))return;
        if(appendWithin(growth,[x],95,1))used.add(x.topic);
      };
      offer(first);
      if(market==='all')offer(restraint[0]);
      // Prioritise a distinct causal mechanism rather than another sentence
      // repeating price or lower volumes. A named counterexample adds value.
      if(market!=='bm')offer(gs.find(x=>x.category==='distribution'));
      if(market==='bm'){
        offer(restraint.find(x=>x.topic==='bm_churn_renewals'||x.topic==='bm_soft_market'));
        offer(positive.find(x=>x.category==='price'));
      }else{
        if(!priceVolume)offer(positive.find(x=>x.category==='price'));
        if(market==='all')offer(gs.find(x=>x.topic==='uk_volume'));
      }
      if(market!=='pm')offer(gs.find(x=>x.category==='currency'));
      if(market==='pm')offer(gs.find(x=>x.topic==='pm_inflation_moderation'&&!used.has(x.topic)));
      if(growth.length===1)appendWithin(growth,gs,95,2);
      const trend=original.find(x=>/fra forrige kvartal|HIÅ-tempoet/.test(x));
      if(trend&&/\b(?:[1-9]\d*),\d+ prosentpoeng/.test(trend))appendWithin(growth,[trend],98,1);
      if(growth.length===1)appendWithin(growth,original.slice(1),95,2);
    }
    if(ls.length||cs.length){
      const original=cr.slice(),opening=original[0];
      const component=original.find(x=>x.startsWith('Skadeprosenten'));
      cr.splice(0,cr.length,opening);
      if(component){
        const split=component.includes('Basert på tilgjengelig sammenlignbar splitt.');
        const text=component.replace(/ Målt som medianendringer på samme utvalg\.| Basert på tilgjengelig sammenlignbar splitt\./,'');
        cr.push(split?'Der sammenlignbar splitt er rapportert, '+text.charAt(0).toLowerCase()+text.slice(1):text);
      }
      const adverse=ls.find(x=>x.category==='adverse');
      const structural=ls.find(x=>['frequency','pricing'].includes(x.category));
      const temporary=ls.find(x=>['weather','temporary'].includes(x.category));
      // Explain deterioration first, then the countervailing improvement.
      // Otherwise cover both the recurring and the temporary claims drivers.
      if(adverse)appendWithin(cr,[adverse],111,1);
      if(structural)appendWithin(cr,[structural],111,1);
      else if(ls[0]&&ls[0]!==adverse)appendWithin(cr,[ls[0]],111,1);
      if(cs[0])appendWithin(cr,[cs[0]],111,1);
      // The word budget, not the number of sentences, controls whether a
      // distinct temporary driver fits. This matters especially when the
      // adverse, structural and cost drivers all need to be explained.
      if(temporary&&!cr.includes(temporary.text))appendWithin(cr,[temporary],113,1);
      if(!ls.length)appendWithin(cr,original.filter(x=>/lønnsomhetsdrivere|storskadebelastning/.test(x)),110,1);
      if(!cs.length&&component){
        const stable=component.includes('kostnadsprosenten er omtrent uendret');
        appendWithin(cr,[stable?'Kostnadsandelen er stabil i tilgjengelig splitt; rapportene gir ikke grunnlag for å tilskrive CR-endringen kostnadsbesparelser.':'Kvartalsrapporteringen gir foreløpig ikke en entydig forklaring på kostnadsutviklingen i dette utvalget.'],116,1);
      }
    }
    if(es.length){
      special.splice(0,special.length);
      const chosen=[];
      // Distinguish the fire total from the broader quarterly large-loss
      // burden. In total views prefer the fire plus a genuinely distinct event.
      const rank=x=>x.priority+(market==='all'&&x.topic==='named_fire'?12:0)-(market==='all'&&/^(bm_large_loss|pm_fire)$/.test(x.topic)?22:0)+(x.topic==='workers_comp_provision'?8:0);
      const eventOrder=[...es].sort((a,b)=>rank(b)-rank(a));
      const family=x=>/^(named_fire|pm_fire|bm_large_loss)$/.test(x.topic)?'large_loss':/workers_comp/.test(x.topic)?'ruling':x.topic;
      for(const e of eventOrder){
        if(chosen.some(x=>family(x)===family(e)))continue;
        chosen.push(e);
      }
      appendWithin(special,chosen,99,3);
    }
    for(const arr of [growth,cr,special]){
      if(arr.length>1)arr.splice(0,arr.length,arr.filter(Boolean).join(' '));
    }
  }
  function comments(m,editorial,scope,market,context=null,otherMode=null,priorView=null){
    const rows=m.eligible,period=title(m.period),mode=m.mode||'quarter';
    // Market commentary only uses period-specific reports and results decks.
    // Editorial/news remains available on the existing summary page, not here.
    const scoped=scopedInsights(m,scope,market,context);
    const driverRows=scoped.filter(x=>x.theme==='growth_driver'&&Object.hasOwn(DRIVER_LABELS,x.driver)&&
      /^[0-9a-f]{64}$/.test(x.source_sha256||'')&&Number.isInteger(x.source_page)&&x.source_page>0&&typeof x.evidence==='string'&&x.evidence.length>0);
    const drivers=new Set(driverRows.map(x=>x.driver));
    const growth=[],cr=[],special=[];
    const comparable=rows.filter(r=>num(r.growth)),med=median(comparable.map(r=>r.growth));
    if(num(med)){
      const positive=comparable.filter(r=>r.growth>.05).length;
      const negative=comparable.filter(r=>r.growth<-.05).length;
      const breadth=comparable.length>=3?(positive/comparable.length>=.8?'Veksten er bredt fundert. ':negative/comparable.length>=.8?'Inntektsnedgangen er bredt fundert. ':'Vekstbildet er sammensatt. '):'';
      const measure=comparable.length>1?'Medianveksten blant aktørene er ':'Rapportert inntektsvekst er ';
      growth.push(breadth+measure+growthText(med)+' mot samme periode i fjor.');
      // Adjacent archived quarter, same issuers and revenue definitions.
      const prior=priorView?.model;
      const adjacent=prior?.period&&m.period&&m.period.year*4+m.period.quarter===prior.period.year*4+prior.period.quarter+1;
      let comparedHistory=false;
      if(mode==='quarter'&&prior?.mode==='quarter'&&adjacent){
        const pairs=comparable.map(r=>[r,prior.eligible.find(x=>x.company===r.company&&x.revenueBasis===r.revenueBasis&&num(x.growth))]).filter(([,x])=>x);
        const dif=median(pairs.map(([a,b])=>a.growth-b.growth));
        if(pairs.length>=2&&num(dif)&&Math.abs(dif)>=.3){
          growth.push('Årsveksttakten har '+(dif>0?'økt':'avtatt')+' med '+pp(dif)+' fra forrige kvartal på samme sammenlignbare utvalg (median).');
          comparedHistory=true;
        }
      }
      if(!comparedHistory&&m.period?.quarter>1&&otherMode&&samePeriod(m.period,otherMode.period)&&otherMode.mode!==mode){
        const pairs=comparable.map(r=>[r,otherMode.eligible.find(x=>x.company===r.company&&x.revenueBasis===r.revenueBasis&&num(x.growth))]).filter(([,x])=>x);
        const dif=median(pairs.map(([a,b])=>mode==='quarter'?a.growth-b.growth:b.growth-a.growth));
        if(pairs.length>=2&&num(dif)&&Math.abs(dif)>=.3)
          growth.push('Veksttakten i siste kvartal ligger '+pp(dif)+' '+(dif>0?'over':'under')+' HIÅ-tempoet målt på samme aktører (median).');
      }
    }else growth.push('Inntektsvekst er foreløpig ikke tilgjengelig.');
    const positiveDrivers=['price',drivers.has('volume_pm_products')?'volume_pm_products':'volume_up','customer_inflow','customer_growth','policy_count_growth','portfolio_growth','retail_growth'].filter(k=>drivers.has(k)).map(k=>DRIVER_LABELS[k]);
    const limitations=['volume_down','risk_selection','competition'].filter(k=>drivers.has(k)).map(k=>DRIVER_LABELS[k]);
    if(positiveDrivers.length)growth.push('Rapporterte vekstdrivere omfatter '+joinNatural(positiveDrivers)+'.');
    if(drivers.has('retention_up'))growth.push('Bedret kundelojalitet er også rapportert i deler av porteføljen.');
    const ukLcp=driverRows.filter(x=>x.driver==='uk_lcp_growth'&&num(x.reported_change_pct)&&x.reported_change_pct>0);
    const lcpValues=[...new Set(ukLcp.map(x=>x.reported_change_pct))];
    if(lcpValues.length===1)growth.push('I britisk privatmarked rapporteres '+pct(lcpValues[0])+' årsvekst i LCP-bestanden (selskapets rapporterte bestandsmål).');
    const commercialGwp=[...new Set(driverRows.filter(x=>x.driver==='gwp_lcy_higher'&&num(x.reported_change_pct)).map(x=>x.reported_change_pct))];
    if(commercialGwp.length===1)growth.push('I en kommersielt orientert portefølje er bruttopremieveksten '+pct(commercialGwp[0])+' i lokal valuta, høyere enn i rapporteringsvaluta. Dette er ikke vekst i antall forsikringer.');
    if(limitations.length)growth.push('Samtidig beskriver rapporteringen '+joinNatural(limitations)+'.');
    if(drivers.has('price')&&['volume_up','volume_pm_products','volume_down','customer_inflow','customer_growth','policy_count_growth','portfolio_growth'].some(k=>drivers.has(k)))
      growth.push('Pris- og volumbidragene er ikke fullt tallfestet på tvers av aktørene.');
    if(!drivers.size&&comparable.length)growth.push('En sammenlignbar pris- og volumsplitt er foreløpig ikke dokumentert i kvartalsrapportene og presentasjonene for dette utvalget.');
    const crRows=rows.filter(r=>num(r.deltas?.combined_ratio));
    const dcr=median(crRows.map(r=>r.deltas.combined_ratio));
    if(num(dcr)){
      cr.push('Lønnsomheten '+(dcr<-.05?'er styrket':dcr>.05?'er svekket':'er omtrent uendret')+' mot samme periode i fjor'+
        (Math.abs(dcr)>.05?', med '+pp(dcr)+' '+(dcr<0?'lavere':'høyere')+' CR målt som '+(crRows.length>1?'medianendring':'rapportert endring'):'')+'.');
      const paired=crRows.filter(r=>num(r.deltas.loss_ratio)&&num(r.deltas.expense_ratio));
      const dl=median(paired.map(r=>r.deltas.loss_ratio)),dc=median(paired.map(r=>r.deltas.expense_ratio));
      if(num(dl)&&num(dc)){
        const change=(label,x)=>label+' er '+(x<-.05?pp(x)+' lavere':x>.05?pp(x)+' høyere':'omtrent uendret');
        cr.push(change('Skadeprosenten',dl)+', mens '+change('kostnadsprosenten',dc)+'. '+(paired.length>1?'Målt som medianendringer på samme utvalg.':'Basert på tilgjengelig sammenlignbar splitt.'));
      }
    }else{
      const level=median(rows.map(r=>r.cr));
      cr.push(num(level)?'CR ligger på '+pct(level)+' '+(rows.length>1?'målt som median':'i tilgjengelig rapportering')+'. Sammenlignbare endringstall mangler.':'CR er foreløpig ikke tilgjengelig.');
    }
    const profitEvidence=scoped.filter(x=>x.theme==='profit_driver'&&/^[0-9a-f]{64}$/.test(x.source_sha256||'')&&Number.isInteger(x.source_page)&&x.source_page>0&&typeof x.evidence==='string'&&x.evidence.length);
    const factors=new Set(profitEvidence.map(x=>x.driver));
    const explanations=[['lower_claim_frequency','lavere skadefrekvens'],['underlying_loss_improved','bedre underliggende skadeprosent'],['weather_lower','lavere værskadebelastning'],['runoff_gains','avviklingsgevinster']].filter(([k])=>factors.has(k)).map(([,v])=>v);
    if(explanations.length)cr.push('Rapporterte lønnsomhetsdrivere omfatter '+joinNatural(explanations)+'.');
    const lowerClaims=scoped.some(x=>x.theme==='large_claims'&&/lavere storskad/i.test(x.text));
    const higherClaims=scoped.some(x=>x.theme==='large_claims'&&/høyere storskad/i.test(x.text));
    if(lowerClaims||higherClaims)
      cr.push(lowerClaims&&higherClaims?'Storskadeutviklingen varierer mellom aktørene.':lowerClaims?'Lavere storskadebelastning er rapportert i deler av markedet.':'Høyere storskadebelastning er rapportert i deler av markedet.');
    // Keep source-specific material events, but never enumerate firms or repeat
    // routine reported amounts merely because a source happens to be available.
    const events=[...scoped.filter(x=>/^(regulation|material_event)$/.test(x.theme||'')),...scoped.filter(x=>/^(weather|strategy|operations|investment|inflation|competition|large_claims)$/.test(x.theme||'')&&!/lavere storskad|høyere storskad|oppgir netto storskader på/i.test(x.text))];
    for(const e of events){
      if(special.includes(e.text))continue;
      if(e.theme==='large_claims'&&special.some(x=>/Krokstadelva/i.test(x))&&/Krokstadelva/i.test(e.text))continue;
      special.push(e.text);
      if(special.length>=2)break;
    }
    if(!special.length&&(lowerClaims||higherClaims))special.push('Kvartalsrapporteringen viser '+(lowerClaims&&higherClaims?'ulik storskadeutvikling mellom aktørene':lowerClaims?'lavere storskadebelastning i deler av markedet':'høyere storskadebelastning i deler av markedet')+'.');
    if(!special.length)special.push('Ingen vesentlig særhendelse er dokumentert for valgt marked og periode.');
    richerComments(scoped,market,growth,cr,special);
    return [{label:'Inntektsvekst',paragraphs:growth.map(safe)},{label:'CR – skade- og kostnadsprosent',paragraphs:cr.map(safe)},{label:'Enkelthendelser og særtrekk',paragraphs:special.map(safe)}];
  }
  const viewKey=(scope,market,mode)=>[scope,market,mode].join('/');
  function makeView(feed,comparison,fx,segments,context,editorial,scope,market,mode,priorView=null){
    const m=model(feed,comparison,fx,scope,market,segments,mode,context);
    const otherMode=m.period?.quarter>1?model(feed,comparison,fx,scope,market,segments,mode==='ytd'?'quarter':'ytd',context):null;
    const notes=scopedInsights(m,scope,market,context);
    const links=[...(priorView?.sources||[]).filter(d=>/^[0-9a-f]{64}$/.test(d.sha256||'')&&Number.isInteger(d.page)&&d.page>0),...(otherMode?.eligible||[]).flatMap(r=>(r.sources||[]).map(d=>({...d,name:pretty(r.company)}))),...m.eligible.flatMap(r=>[{name:pretty(r.company),url:r.source},...(r.sources||[]).map(d=>({...d,name:pretty(r.company)}))]),...notes.map(x=>({name:pretty(x.company),url:x.source_url,sha256:x.source_sha256,page:x.source_page,source_type:x.source_type}))];
    return {model:m,comments:comments(m,editorial,scope,market,context,otherMode,priorView),sources:[...new Map(links.filter(x=>source(x.url)).map(x=>[[x.url,x.sha256||'',x.page||''].join('|'),x])).values()]};
  }
  function archivedView(archive,requested,scope,market,mode){
    const label=requested==='latest'?archive?.active_period:requested,entry=archive?.periods?.[label],view=entry?.views?.[viewKey(scope,market,mode)];
    if(!periodOf(label)||!view||title(view.model?.period)!==label||view.model.mode!==mode)return null;
    return {...view,locked:entry.locked===true};
  }
  // Both trend charts use the SAME five consecutive isolated quarters.
  function timeline(p,count=5){
    if(!p||!Number.isInteger(p.year)||!Number.isInteger(p.quarter)||p.quarter<1||p.quarter>4)return [];
    const n=p.year*4+p.quarter-1;
    return Array.from({length:count},(_,i)=>{const v=n-count+1+i;return 'Q'+(v%4+1)+' '+Math.floor(v/4);});
  }
  function profitabilityHistory(feed,context,archive,p){
    const periods=timeline(p),observations=(feed?.observations||[]).filter(valid);
    const historic=context?.profitability_history?.points||[];
    const series=COMPANIES.map(company=>{
      const points=periods.map(label=>{
        const q=periodOf(label);
        const rows=observations.filter(r=>r.company===company&&samePeriod(r,q)&&r.scope==='group'&&r.period_type==='quarter'&&r.unit==='percent');
        const read=metric=>selectUnique(rows,metric);
        const cr=read('combined_ratio'),loss=read('loss_ratio'),cost=read('expense_ratio');
        let point=cr?{cr:cr.value,loss:loss?.value??null,cost:cost?.value??null,roe:read('return_on_equity')?.value??null,source_url:cr.source_url,source_sha256:cr.source_sha256,source_page:cr.source_page,method:cr.status}:null;
        if(point&&!num(point.roe)){
          const ytd=observations.filter(r=>r.company===company&&samePeriod(r,q)&&r.scope==='group'&&r.period_type==='ytd'&&r.unit==='percent');
          const roe=selectUnique(ytd,'return_on_equity');
          if(roe){point.roe=roe.value;point.roeBasis='HIÅ';}
        }
        if(EXTENDED.includes(company)){
          const matches=historic.filter(r=>r.company===company&&r.period===label&&r.period_type==='quarter'&&r.status==='verified'&&source(r.source_url)&&/^[0-9a-f]{64}$/.test(r.source_sha256||'')&&Number.isInteger(r.source_page)&&r.source_page>0&&num(r.cr)&&r.cr>=0);
          point=matches.length===1?{...matches[0]}:null;
          if(point&&!num(point.roe)){
            const roe=selectUnique(supplementaryCompanyRows(context).filter(r=>r.company===company&&r.scope==='group'&&r.period_type==='quarter'&&samePeriod(r,q)),'return_on_equity');
            if(roe){point.roe=roe.value;point.roe_evidence=roe;}
          }
        }
        // Archive is authoritative for its own quarter; especially do not
        // show an unreported issuer's latest point in an incomplete snapshot.
        const snapshot=archive?.periods?.[label]?.views?.['group/all/quarter'];
        if(snapshot){
          const row=snapshot.model?.eligible?.find(r=>r.company===company);
          if(!row)return null;
          point={...point,cr:row.cr,loss:row.loss,cost:row.cost,source_url:point?.source_url||row.source};
        }
        return point&&num(point.cr)&&point.cr>=0?point:null;
      });
      return {company,points};
    });
    return {periods,series};
  }
  function reportQueues(label,reported,calendar,locked=false){
    const p=periodOf(label);
    if(!p)return {pending:[],next:[],nextPeriod:''};
    const following=title({year:p.year+(p.quarter===4?1:0),quarter:p.quarter===4?1:p.quarter+1});
    const done=new Set(reported);
    const rows=COMPANIES.map(company=>{
      const published=done.has(company),target=published?following:label;
      const config=calendar?.[pretty(company)]||calendar?.[company]||{};
      const events=(config.events||[]).filter(e=>e.period===target&&validDate(e.date));
      const dates=[...new Set(events.map(e=>e.date))];
      const date=dates.length===1?dates[0]:null;
      const url=events.find(e=>e.date===date)?.source_url||config.calendar_url;
      return {company,published,period:target,date,url:source(url)?url:null};
    });
    const sort=items=>items.sort((a,b)=>(a.date||'9999-99-99').localeCompare(b.date||'9999-99-99')||pretty(a.company).localeCompare(pretty(b.company),'nb'));
    return {pending:locked?[]:sort(rows.filter(x=>!x.published)),next:sort(rows.filter(x=>x.published)),nextPeriod:following};
  }
  function validDate(s){
    if(!/^\d{4}-\d{2}-\d{2}$/.test(s||''))return false;
    const d=new Date(s+'T00:00:00Z');return Number.isFinite(d.valueOf())&&d.toISOString().slice(0,10)===s;
  }
  function reportCalendarHtml(items,kind,label,locked=false){
    if(!items.length)return '';
    const upcoming=kind==='next',heading=upcoming?'Neste kvartal – publiseringsdatoer · '+label:'Avventer kvartalstall · '+label;
    const cards=items.map(x=>{
      const date=x.date?x.date.slice(8,10)+'.'+x.date.slice(5,7)+'.'+x.date.slice(0,4):'Ingen dato oppgitt';
      const content='<span class="mon-cal-company"><strong>'+safe(pretty(x.company))+'</strong><small>'+safe(x.period)+' · '+safe(date)+'</small></span>'+
        (x.date?'<span class="mon-cal-countdown" data-report-date="'+safe(date)+'"'+(locked?' data-historical="true"':'')+'>Beregner …</span>':'');
      const attrs=' class="mon-cal-row" data-company="'+safe(x.company)+'" data-target-period="'+safe(x.period)+'"';
      return x.url?'<a'+attrs+' href="'+safe(x.url)+'" target="_blank" rel="noopener noreferrer">'+content+'</a>':'<div'+attrs+'>'+content+'</div>';
    }).join('');
    return '<section class="mon-calendar mo-report-calendar" id="mo-calendar-'+kind+'" data-report-period="'+safe(label)+'" aria-label="'+safe(heading)+'"><div class="mon-calendar-top"><div><div class="eyebrow">FINANSIELL KALENDER</div><h2>'+safe(heading)+'</h2></div></div><div class="mon-cal-grid">'+cards+'</div></section>';
  }
  const LINE_COLORS=['#126f73','#3455a4','#b65f16','#8c4a92','#b63246','#457638','#137eb4','#6c6570','#996d14'];
  const LINE_DASH=['','7 3','2 3','10 3 2 3','5 3','','8 4','3 3','10 5'];
  const crValues=series=>series.flatMap(s=>s.points.filter(p=>p&&num(p.cr)&&p.cr>=0).map(p=>p.cr));
  const crRange=values=>values.length?Math.max(...values)-Math.min(...values):0;
  function crQuantile(sorted,q){
    const i=(sorted.length-1)*q,lo=Math.floor(i),hi=Math.ceil(i);
    return sorted[lo]+(sorted[hi]-sorted[lo])*(i-lo);
  }
  function crAxis(values){
    if(!values.length)return null;
    const min=Math.min(...values),max=Math.max(...values),pad=Math.max(0.75,(max-min)*.04);
    // A minimum ten-percentage-point window avoids exaggerating tiny differences.
    const middle=(min+max)/2,half=Math.max(5,(max-min)/2+pad);
    const from=Math.max(0,middle-half),to=middle+half;
    const steps=[1,2,2.5,5,10,20,25,50,100,200,250,500,1000];
    const step=steps.find(v=>(to-from)/v<=7)||Math.pow(10,Math.ceil(Math.log10((to-from)/7)));
    const low=Math.floor(from/step)*step,high=Math.max(low+step,Math.ceil(to/step)*step);
    return {low,high,step};
  }
  function crTrendView(history,showAll=false){
    const available=history.series.filter(s=>crValues([s]).length);
    const values=crValues(available),sorted=values.slice().sort((a,b)=>a-b);
    let excluded=[];
    // Visual selection only: robust pooled quartiles, enough peers, whole series.
    // Never omit an individual observation or change a source value.
    if(available.length>=6&&sorted.length>=15){
      const q1=crQuantile(sorted,.25),q3=crQuantile(sorted,.75);
      const fence=Math.max(12,2.5*(q3-q1)),low=q1-fence,high=q3+fence;
      const candidates=available.flatMap(s=>{
        const points=s.points.map((p,i)=>p&&num(p.cr)&&p.cr>=0?{cr:p.cr,period:history.periods[i],distance:Math.max(low-p.cr,p.cr-high)}:null).filter(p=>p&&p.distance>0);
        points.sort((a,b)=>b.distance-a.distance);
        return points.length?[{company:s.company,cr:points[0].cr,period:points[0].period}]:[];
      });
      const kept=available.filter(s=>!candidates.some(c=>c.company===s.company));
      const range=crRange(values),remaining=crRange(crValues(kept));
      if(candidates.length&&kept.length>=Math.max(5,Math.ceil(available.length*2/3))&&range-remaining>=Math.max(8,range*.2))excluded=candidates;
    }
    const visible=showAll?available:available.filter(s=>!excluded.some(e=>e.company===s.company));
    return {visible,excluded,available,axis:crAxis(crValues(visible)),showAll:Boolean(showAll)};
  }
  function trendChart(history,showAll=false){
    const {periods,series}=history;
    if(periods.length!==5)return '<p class="mo-empty">Avventer verifisert kvartal.</p>';
    const view=crTrendView(history,showAll);
    if(!view.axis)return '<p class="mo-empty">Historiske CR-tall er foreløpig ikke tilgjengelige.</p>';
    const {low,high,step}=view.axis,w=620,h=330,left=55,right=34,top=18,bottom=38;
    const x=i=>left+i*(w-left-right)/4,y=v=>top+(high-v)/(high-low)*(h-top-bottom);
    const ticks=[];for(let i=low;i<=high;i+=step)ticks.push(i);
    const title='Utvikling i CR · '+(view.visible.length===series.length?'alle selskaper':view.visible.length+' selskaper');
    const style=s=>{const i=Math.max(0,COMPANIES.indexOf(s.company));return {color:LINE_COLORS[i],dash:LINE_DASH[i]};};
    let svg='<svg class="mo-line-svg" viewBox="0 0 '+w+' '+h+'" role="img" data-cr-low="'+low+'" data-cr-high="'+high+'" data-cr-step="'+step+'" data-cr-mode="'+(showAll?'all':'focus')+'" aria-label="'+safe(title+' · '+low+'–'+high+' % · fem kvartaler')+'">';
    svg+=ticks.map(v=>'<line x1="'+left+'" x2="'+(w-right)+'" y1="'+y(v)+'" y2="'+y(v)+'" stroke="'+(v===100?'#aabcc6':'#e2e9ee')+'" stroke-dasharray="'+(v===100?'5 4':'')+'"/><text x="'+(left-9)+'" y="'+(y(v)+4)+'" text-anchor="end">'+format(v,Number.isInteger(v)?0:1)+' %</text>').join('');
    if(low<100&&high>100&&!ticks.includes(100))svg+='<line x1="'+left+'" x2="'+(w-right)+'" y1="'+y(100)+'" y2="'+y(100)+'" stroke="#aabcc6" stroke-dasharray="5 4"/>';
    svg+=periods.map((p,i)=>'<text x="'+x(i)+'" y="'+(h-10)+'" text-anchor="middle" class="mo-line-quarter" data-period="'+safe(p)+'">'+safe(p)+'</text>').join('');
    svg+=view.visible.map(s=>{
      const {color,dash}=style(s);let path='',prev=false,marks='';
      s.points.forEach((p,i)=>{if(!p||!num(p.cr)||p.cr<0){prev=false;return;}const cx=x(i),cy=y(p.cr);
        path+=(prev?' L':' M')+cx.toFixed(2)+' '+cy.toFixed(2);prev=true;
        marks+='<circle class="mo-line-point" data-company="'+safe(s.company)+'" data-period="'+safe(periods[i])+'" data-cr="'+p.cr+'" cx="'+cx+'" cy="'+cy+'" r="3.5" fill="'+color+'" stroke="white" stroke-width="1.1" tabindex="0" aria-label="'+safe(pretty(s.company)+' · '+periods[i]+' · CR '+pct(p.cr))+'"><title>'+safe(pretty(s.company)+' · '+periods[i]+' · CR '+pct(p.cr))+'</title></circle>';
      });
      return '<g class="mo-line-series" data-company="'+safe(s.company)+'"><path d="'+path+'" fill="none" stroke="'+color+'" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"'+(dash?' stroke-dasharray="'+dash+'"':'')+'/>'+marks+'</g>';
    }).join('')+'</svg>';
    const legend=view.visible.map(s=>{const {color,dash}=style(s);return '<span class="mo-line-legend-item" data-company="'+safe(s.company)+'"><svg viewBox="0 0 24 8" width="24" height="8" aria-hidden="true"><line x1="1" x2="23" y1="4" y2="4" stroke="'+color+'" stroke-width="2.6" stroke-linecap="round"'+(dash?' stroke-dasharray="'+dash+'"':'')+'/></svg>'+safe(pretty(s.company))+'</span>';}).join('');
    const toggle=view.excluded.length?'<button type="button" class="mo-cr-toggle" data-mo-cr-toggle aria-pressed="'+Boolean(showAll)+'" onclick="FBMarketOverview.selectCrHistory('+(!showAll)+')">'+(showAll?'Tilpass utsnitt':'Vis alle '+view.available.length)+'</button>':'';
    const note=view.excluded.length?'<p class="mo-cr-note" role="status">'+(showAll?'Alle tilgjengelige selskaper vises.':'Skjult i utsnittet på grunn av stort utslag: '+view.excluded.map(e=>safe(pretty(e.company)+' · '+e.period+' '+pct(e.cr))).join('; ')+'. Alle tall er beholdt nedenfor.')+'</p>':'';
    const table='<details class="mo-history-values"><summary>Se kvartalstall og kilder · alle selskaper</summary><div class="tablewrap"><table><thead><tr><th>Selskap</th>'+periods.map(p=>'<th>'+safe(p)+'</th>').join('')+'</tr></thead><tbody>'+series.map(s=>'<tr data-company="'+safe(s.company)+'"><th>'+safe(pretty(s.company))+'</th>'+s.points.map(p=>'<td>'+(p?(source(p.source_url)?'<a href="'+safe(p.source_url)+'" target="_blank" rel="noopener noreferrer" title="'+safe(p.method||'Verifisert rapport')+'">'+pct(p.cr)+'</a>':pct(p.cr)):'—')+'</td>').join('')+'</tr>').join('')+'</tbody></table></div></details>';
    return '<div class="section-head mo-cr-head"><div><h2>'+safe(title)+'</h2><p class="hint">Konsern / rapportert total · isolerte kvartaler</p></div>'+toggle+'</div>'+note+'<div class="mo-line-scroll">'+svg+'</div><div class="mo-line-legend">'+legend+'</div>'+table;
  }
  function financialNumber(value){
    if(num(value))return value;
    if(typeof value!=='string')return null;
    const m=value.trim().replace(/[\s\u00a0\u202f]/g,'').replace(/−/g,'-').replace(',','.').match(/^([+-]?\d+(?:\.\d+)?)(?:%|MNOK|NOKm|MDKK|DKKm|MEUR|EURm|MSEK|SEKm)?$/i);
    return m&&Number.isFinite(Number(m[1]))?Number(m[1]):null;
  }
  function financialTrend(now,prior,lowerIsBetter=false){
    const a=financialNumber(now),b=financialNumber(prior);
    if(a===null||b===null)return null;
    const diff=a-b,direction=diff>0.00001?'up':diff< -0.00001?'down':'flat';
    return {direction,icon:direction==='up'?'▲':direction==='down'?'▼':'→',tone:direction==='flat'?'flat':(lowerIsBetter?direction==='down':direction==='up')?'good':'bad'};
  }
  function supplementaryCompanyRows(contextValue=context){
    return (contextValue?.company_segment_details?.observations||[]).filter(valid);
  }
  function companyDetailRows(feed,segmentData,comparisonData,contextValue){
    const index=new Map(allRows(feed,segmentData,comparisonData,contextValue).map(r=>[key(r),r]));
    for(const r of supplementaryCompanyRows(contextValue)){
      if(!index.has(key(r)))index.set(key(r),r);
    }
    return [...index.values()];
  }
  function companyHistoricalMetrics(name,p,type='quarter'){
    const found=(context?.profitability_history?.points||[]).filter(r=>r.company===name&&r.period===title(p)&&r.status==='verified'&&source(r.source_url)&&/^[0-9a-f]{64}$/.test(r.source_sha256||'')&&Number.isInteger(r.source_page)&&r.source_page>0);
    if(found.length!==1)return {};
    const r=found[0],out=type==='ytd'?{...(r.ytd_metrics||{})}:{...(r.metrics||{}),combined_ratio:r.cr,loss_ratio:r.loss,expense_ratio:r.cost,...(num(r.roe)?{return_on_equity:r.roe}:{})};
    const roe=selectUnique(supplementaryCompanyRows().filter(x=>x.company===name&&x.scope==='group'&&samePeriod(x,p)&&x.period_type===type),'return_on_equity');
    if(!num(out.return_on_equity)&&roe)out.return_on_equity=roe.value;
    return out;
  }
  function companyExtraObservations(){
    return (context?.company_comparisons?.observations||[]).filter(valid).filter(r=>r.scope==='group');
  }
  function profitabilityOptions(name,p,history=null){
    history=history||profitabilityHistory(window.FBQuarterly?.verified,context,archive,p);
    const s=history.series.find(s=>s.company===name),selected={},returns={};
    s?.points.forEach((r,i)=>{if(!r)return;const label=history.periods[i];if(num(r.loss)&&num(r.cost))selected[label]=[r.loss,r.cost,r.cr];if(num(r.roe))returns[label]={value:r.roe,label:r.roeBasis==='HIÅ'?'Rapportert annualisert HIÅ':'Rapportert annualisert avkastning'};});
    return {quarters:history.periods,selected,returns};
  }
  // Company-detail segments are independent of the market ranking's
  // Norway/PM/BM population. Sampo's named Nordic segments must not be
  // relabelled as Norwegian or treated as the full Group's PM/BM.
  function sampoNordicSegments(feed,p,mode='quarter'){
    if(!p||!periodOf(title(p)))return [];
    const metrics=['insurance_revenue','insurance_service_result',...CORE];
    const index=new Map((feed?.observations||[]).filter(valid).map(r=>[key(r),r]));
    for(const r of supplementaryCompanyRows())if(!index.has(key(r)))index.set(key(r),r);
    const rows=[...index.values()].filter(r=>r.company==='Sampo'&&r.scope==='reported_segment'&&['Private Nordic','Nordic Commercial'].includes(r.segment));
    const sameSourceBasis=r=>/^Sampo interim statement; (Private Nordic|Nordic Commercial) reported financial table/.test(r.source_definition||'');
    function block(segment,y,q,type){
      const rr=rows.filter(r=>r.segment===segment&&r.year===y&&r.quarter===q&&r.period_type===type&&sameSourceBasis(r));
      const by=Object.fromEntries(metrics.map(k=>[k,selectUnique(rr,k)]));
      if(metrics.some(k=>!by[k]))return null;
      if(['insurance_revenue','insurance_service_result'].some(k=>by[k].unit!=='EURm')||CORE.some(k=>by[k].unit!=='percent'))return null;
      const m=Object.fromEntries(metrics.map(k=>[k,by[k].value]));
      if(m.insurance_revenue<=0||Math.min(m.combined_ratio,m.loss_ratio,m.expense_ratio)<0||Math.abs(m.combined_ratio-m.loss_ratio-m.expense_ratio)>.25)return null;
      const sourceRows=metrics.map(k=>by[k]);
      return {metrics:m,sourceRows,method:type==='ytd'?'reported_ytd':'reported_quarter'};
    }
    function aggregate(segment,y){
      const direct=block(segment,y,p.quarter,mode);
      if(direct||mode!=='ytd')return direct;
      const parts=Array.from({length:p.quarter},(_,i)=>block(segment,y,i+1,'quarter'));
      if(parts.some(x=>!x))return null;
      const total=parts.reduce((a,b)=>a+b.metrics.insurance_revenue,0);
      const m={insurance_revenue:total,insurance_service_result:parts.reduce((a,b)=>a+b.metrics.insurance_service_result,0)};
      for(const key of CORE)m[key]=parts.reduce((a,b)=>a+b.metrics[key]*b.metrics.insurance_revenue,0)/total;
      return {metrics:m,sourceRows:parts.flatMap(b=>b.sourceRows),method:p.quarter===1?'reported_quarter':'calculated_ytd'};
    }
    return ['Private Nordic','Nordic Commercial'].map(segment=>{
      const current=aggregate(segment,p.year),prior=aggregate(segment,p.year-1),older=aggregate(segment,p.year-2);
      const m=current?.metrics,prev=prior?.metrics;
      const revenue=(y)=>{const direct=selectUnique(rows.filter(r=>r.segment===segment&&r.year===y&&r.quarter===p.quarter&&r.period_type===mode&&sameSourceBasis(r)),'insurance_revenue');
        if(direct?.value>0)return direct.value;
        if(mode!=='ytd')return null;
        const parts=Array.from({length:p.quarter},(_,i)=>selectUnique(rows.filter(r=>r.segment===segment&&r.year===y&&r.quarter===i+1&&r.period_type==='quarter'&&sameSourceBasis(r)),'insurance_revenue'));
        return parts.every(r=>r?.value>0&&r.unit==='EURm')?parts.reduce((s,r)=>s+r.value,0):null;};
      const a=revenue(p.year),b=revenue(p.year-1),c=revenue(p.year-2);
      return {segment,metrics:m||null,prior:prev||null,
        growth:a>0&&b>0?100*(a/b-1):null,
        growthPrev:b>0&&c>0?100*(b/c-1):null,
        method:current?.method||null,sources:current?.sourceRows||[]};
    });
  }
  function companySegmentRows(name,p,periodType='quarter',scope='group',markets=['pm','bm']){
    if(!p||!COMPANIES.includes(name))return [];
    const rows=companyDetailRows(window.FBQuarterly?.verified,segments,comparison,context).filter(r=>r.period_type===periodType);
    return markets.map(m=>{
      const live=rowFor(rows,name,p,scope,m);
      const snap=archive?.periods?.[title(p)]?.views?.[viewKey(scope,m,periodType)];
      const row=live||(snap?snap.model.eligible.find(r=>r.company===name):null);
      if(!row)return {market:m,row:null,prior:null};
      const priorPeriod={year:p.year-1,quarter:p.quarter};
      const direct=rowFor(rows,name,priorPeriod,scope,m);
      const prior=direct&&direct.revenueBasis===row.revenueBasis&&direct.currency===row.currency?{...direct}:{};
      const g=groupsFor(rows,name,p,scope,m)[0],old=groupsFor(rows,name,priorPeriod,scope,m)[0],older=groupsFor(rows,name,{year:p.year-2,quarter:p.quarter},scope,m)[0];
      const rev=selectUnique(old?.rows||[],'insurance_revenue'),base=selectUnique(older?.rows||[],'insurance_revenue'),growth=selectUnique(old?.rows||[],'insurance_revenue_growth');
      if(!num(prior.growth)){
        if(growth?.unit==='percent')prior.growth=growth.value;
        else if(rev?.value>0&&base?.value>0&&currency(rev.unit)===currency(base.unit)&&basis(rev)===basis(base))prior.growth=100*(rev.value/base.value-1);
      }
      for(const [metric,field] of [['combined_ratio','cr'],['loss_ratio','loss'],['expense_ratio','cost']]){
        if(!num(prior[field])&&num(row[field])&&num(row.deltas?.[metric]))prior[field]=row[field]-row.deltas[metric];
      }
      const result=selectUnique(g?.rows||[],'insurance_service_result'),priorResult=selectUnique(old?.rows||[],'insurance_service_result');
      return {market:m,row,prior,result:result?.value??null,priorResult:priorResult&&result&&currency(priorResult.unit)===currency(result.unit)?priorResult.value:null,resultUnit:result?.unit||null};
    });
  }
  function companyQuarterNarrative(name,period,feed=null,ctx=null){
    const p=periodOf(period);if(!p||!COMPANIES.includes(name))return null;
    const data=feed||(typeof window!=='undefined'?window.FBQuarterly?.verified:null),cx=ctx||context;
    const rows=(data?.observations||[]).filter(valid).filter(r=>r.company===name&&r.scope==='group'&&r.period_type==='quarter');
    const at=(y)=>rows.filter(r=>r.year===y&&r.quarter===p.quarter);
    const current=at(p.year),previous=at(p.year-1);
    const cr=selectUnique(current,'combined_ratio'),income=selectUnique(current,'insurance_revenue'),result=selectUnique(current,'insurance_service_result');
    const oldCR=selectUnique(previous,'combined_ratio'),oldIncome=selectUnique(previous,'insurance_revenue'),oldResult=selectUnique(previous,'insurance_service_result');
    const point=(y)=>(cx?.profitability_history?.points||[]).find(r=>r.company===name&&r.year===y&&r.quarter===p.quarter&&r.status==='verified'&&source(r.source_url)&&/^[0-9a-f]{64}$/.test(r.source_sha256||'')&&r.source_page>0);
    const hp=EXTENDED.includes(name)?point(p.year):null,op=EXTENDED.includes(name)?point(p.year-1):null;
    if(!hp&&(!cr||!income))return null;
    const nowCR=hp?.cr??cr?.value,prevCR=hp?op?.cr:oldCR?.value;
    const nowIncome=hp?.metrics?.insurance_revenue??income?.value,prevIncome=hp?op?.metrics?.insurance_revenue:oldIncome&&income&&currency(oldIncome.unit)===currency(income.unit)&&basis(oldIncome)===basis(income)?oldIncome.value:null;
    const nowResult=hp?.metrics?.insurance_service_result??result?.value,prevResult=hp?op?.metrics?.insurance_service_result:oldResult&&result&&currency(oldResult.unit)===currency(result.unit)?oldResult.value:null;
    const unit=hp?(name==='Alm. Brand'?'MDKK':'MNOK'):({NOK:'MNOK',DKK:'MDKK',EUR:'MEUR',SEK:'MSEK'}[currency(result?.unit)]||'');
    let sentences=[];
    if(num(nowCR))sentences.push('Rapportert CR var '+pct(nowCR)+(num(prevCR)?' mot '+pct(prevCR)+' i samme kvartal året før':'')+'.');
    if(num(nowIncome)&&num(prevIncome)&&prevIncome>0)sentences.push('Rapporterte inntekter '+(nowIncome>=prevIncome?'økte':'falt')+' med '+pct(Math.abs(100*(nowIncome/prevIncome-1)))+' sammenlignet med samme kvartal i fjor.');
    if(num(nowResult)&&unit)sentences.push('Forsikringsresultatet var '+format(nowResult,1)+' '+unit+(num(prevResult)?' mot '+format(prevResult,1)+' '+unit+' året før':'')+'.');
    const qualitative=(cx?.insights||[]).filter(x=>x.company===name&&x.period===period&&x.source_document_period===period&&x.period_type==='quarter'&&['growth_explanation','loss_explanation','cost_explanation','event_explanation','material_event','large_claims','regulation'].includes(x.theme)&&['official_quarterly_report','official_results_presentation'].includes(x.source_type)&&source(x.source_url)&&/^[0-9a-f]{64}$/.test(x.source_sha256||'')&&Number.isInteger(x.source_page)&&x.source_page>0&&typeof x.text==='string'&&x.text.length>30).sort((a,b)=>(b.priority||0)-(a.priority||0));
    const selected=[];for(const x of qualitative){if(selected.some(y=>y.theme===x.theme||y.text===x.text))continue;selected.push(x);if(selected.length===2)break;}
    const evidence=[hp||cr,...selected].filter(Boolean);
    return {paragraphs:[sentences.join(' '),...selected.map(x=>x.text)].filter(Boolean),sources:[...new Map(evidence.filter(x=>source(x.source_url)).map(x=>[[x.source_url,x.source_page].join('|'),{url:x.source_url,page:x.source_page}])).values()]};
  }
  function trendPanels(p){
    const history=profitabilityHistory(window.FBQuarterly?.verified,context,archive,p);
    const left=typeof profitabilityChart==='function'?profitabilityChart(profitCompany,{...profitabilityOptions(profitCompany,p,history),onChange:'FBMarketOverview.selectProfitability(this.value)'}):'<p>Henter lønnsomhetsgraf …</p>';
    return '<div class="profitability-duo mo-trend-duo" id="mo-trend-charts"><section class="panel" id="mo-profitability-panel">'+left+'</section><section class="panel" id="mo-cr-history">'+trendChart(history,crShowAll)+'</section></div>';
  }
  let comparison=null,fx=null,segments=null,context=null,archive=null,calendar=null,scope='group',market='all',mode='quarter',reportPeriod='latest',profitCompany='Fremtind',crShowAll=false,pending=null,failed=false;
  function currentView(){
    if(archive?.active_period){
      return archivedView(archive,reportPeriod,scope,market,mode)||{model:{period:null,mode,eligible:[],selected:[],missing:COMPANIES.slice(),fxMissing:[],reported:0},comments:[],sources:[],locked:false};
    }
    return makeView(window.FBQuarterly?.verified,comparison,fx,segments,context,window.FBNews?.editorial,scope,market,mode);
  }
  function controls(){
    const group=(id,caption,options,current)=>'<fieldset class="mo-filter" id="'+id+'"><legend>'+caption+'</legend><div role="group" aria-label="'+caption+'">'+options.map(([key,label])=>
      '<button type="button" data-mo-'+id+'="'+key+'" aria-pressed="'+(current===key)+'" onclick="FBMarketOverview.select(\''+id+'\',\''+key+'\')">'+label+'</button>').join('')+'</div></fieldset>';
    const periods=Object.keys(archive?.periods||{}).filter(x=>periodOf(x)).sort((a,b)=>cmpPeriod(periodOf(b),periodOf(a)));
    const chosen=reportPeriod==='latest'?(archive?.active_period||''):reportPeriod;
    const periodControl=periods.length?'<fieldset class="mo-filter mo-report-filter"><legend>Rapportkvartal</legend><select id="mo-report-period" aria-label="Rapportkvartal" onchange="FBMarketOverview.select(\'reportPeriod\',this.value)">'+periods.map(label=>'<option value="'+safe(label)+'" '+(label===chosen?'selected':'')+'>'+safe(label)+(archive.periods[label].locked?' · Låst':'')+'</option>').join('')+'</select></fieldset>':'';
    return '<div class="mo-filters">'+periodControl+group('scope','Geografi',[['group','Gruppe'],['norway','Norge']],scope)+
      group('market','Marked',[['all','Totalt'],['pm','PM'],['bm','BM']],market)+group('mode','Periode',[['quarter','Kvartal'],['ytd','HIÅ']],mode)+'</div>';
  }
  function graph(m){
    if(m.fxMissing.length)return '<p class="mo-empty">Valutagrunnlaget for '+safe(title(m.period))+' er foreløpig ikke tilgjengelig for '+safe(m.fxMissing.map(pretty).join(', '))+'. Topp 5 vises når NOK-rangeringen kan beregnes korrekt.</p>';
    if(!m.selected.length)return '<p class="mo-empty">Ingen selskaper har komplett kildeverifisert inntekt, CR, skadeprosent og kostnadsprosent for dette valget i '+safe(title(m.period))+'.</p>';
    const cap=Math.max(100,Math.ceil(Math.max(...m.selected.map(r=>num(r.loss)&&num(r.cost)?r.loss+r.cost:r.cr))/20)*20);
    const bars=m.selected.map((r,i)=>{
      const split=num(r.loss)&&num(r.cost);
      const stack=split?r.loss+r.cost:r.cr;
      const accessible=pretty(r.company)+': CR '+pct(r.cr)+', skadeprosent '+pct(r.loss)+', kostnadsprosent '+pct(r.cost)+', vekst '+growthText(r.growth);
      return '<div class="mo-company" data-company="'+safe(r.company)+'" data-cr="'+r.cr+'" data-income-nok="'+r.revenueNok+'">'+
        '<div class="mo-bar-area" role="img" aria-label="'+safe(accessible)+'">'+
        '<div class="mo-stack" style="height:'+stack/cap*100+'%">'+
        '<span class="mo-cr">'+pct(r.cr)+'</span>'+
        (split?'<div class="mo-cost" style="height:'+(stack?r.cost/stack*100:0)+'%"><span>'+format(r.cost)+'</span></div>'+
        '<div class="mo-loss" style="height:'+(stack?r.loss/stack*100:0)+'%"><span>'+format(r.loss)+'</span></div>':
        '<div class="mo-cr-only" style="height:100%" title="Fremtind rapportert samlet CR (APM). Skade-/kostnadssplitt ikke rapportert."><span>CR</span></div>')+'</div></div>'+
        '<div class="mo-name"><button type="button" onclick="show(\''+safe(r.company)+'\')">'+safe(pretty(r.company))+'</button>'+
        (i<3?'<span class="mo-medal mo-medal-'+(i+1)+'" data-cr-rank="'+(i+1)+'" role="img" aria-label="'+(i+1)+'. plass – lavest CR" title="'+(i+1)+'. plass – lavest CR">'+['🥇','🥈','🥉'][i]+'</span>':'<span class="mo-medal-placeholder" aria-hidden="true"></span>')+
        '</div>'+
        '<div class="mo-growth '+(num(r.growth)?r.growth>0?'positive':r.growth<0?'negative':'':'')+'"><span>Inntektsvekst</span><strong>'+growthText(r.growth)+'</strong></div>'+
        '<div class="mo-income" title="'+safe(r.revenueBasis)+' · '+format(r.revenue,0)+' mill. '+r.currency+'">'+format(r.revenueNok,0)+' mill. NOK</div></div>';
    }).join('');
    const ticks=Array.from({length:6},(_,i)=>Math.round(cap*i/5));
    return '<div class="mo-legend"><span><i class="mo-loss-key"></i> Skadeprosent</span><span><i class="mo-cost-key"></i> Kostnadsprosent</span>'+(m.selected.some(r=>!num(r.loss)||!num(r.cost))?'<span><i class="mo-cr-only-key"></i> CR uten splitt (Fremtind PM/BM)</span>':'')+'</div>'+
      '<div class="mo-scroll"><div class="mo-chart" style="--mo-columns:'+m.selected.length+'"><div class="mo-axis" aria-hidden="true">'+ticks.map(t=>'<span style="bottom:'+t/cap*100+'%">'+t+' %</span>').join('')+'</div>'+
      '<div class="mo-chart-body"><div class="mo-guides" aria-hidden="true">'+ticks.map(t=>'<i style="bottom:'+t/cap*100+'%"></i>').join('')+'</div><div class="mo-bars">'+bars+'</div></div></div></div>';
  }
  function html(){
    const view=currentView(),m=view.model;
    const latest=title(m.period);
    const contextual=scope==='norway'?'Norge':'Gruppe';
    const filter=market==='all'?'Totalt':market==='pm'?'PM':'BM';
    const descriptor=contextual+' · '+filter+' · '+(mode==='ytd'?'HIÅ':'Kvartal');
    const count=m.selected.length;
    const groupSnapshot=m.period&&(archive?.periods?.[latest]?.views?.['group/all/quarter']?.model||model(window.FBQuarterly?.verified,comparison,fx,'group','all',segments,'quarter',context));
    const reported=groupSnapshot?.eligible?.map(r=>r.company)||[];
    const queue=calendar&&latest?reportQueues(latest,reported,calendar,view.locked):null;
    const topCal=queue?reportCalendarHtml(queue.pending,'pending',latest):'';
    const nextCal=queue?reportCalendarHtml(queue.next,'next',queue.nextPeriod,view.locked):'';
    const media=typeof mediaNews==='function'?mediaNews(latest):'';
    return '<div class="top mo-top"><div><div class="eyebrow">MARKEDSOVERSIKT</div><h1>Forsikringsbarometeret</h1><p class="sub">Lønnsomhet og vekst i forsikringsmarkedet</p></div>'+
      '<div class="tag" id="mo-period">'+safe(latest||'Laster rapportperiode')+'</div></div>'+topCal+
      '<section id="market-overview" class="panel mo-panel" data-period="'+safe(latest)+'" data-scope="'+scope+'" data-market="'+market+'" data-mode="'+mode+'" data-locked="'+Boolean(view.locked)+'">'+
      controls()+'<div class="section-head mo-heading"><div><h2>'+ (count<5&&count>0?count+' største selskaper':'Topp 5 selskaper')+' · '+safe(descriptor)+'</h2></div>'+
      (latest?'<span class="pill">'+(view.locked?'Låst · ':'')+m.reported+' / 9 rapportert</span>':'')+'</div>'+
      (!m.period?'<p class="mo-empty">'+(failed?'Datagrunnlaget er midlertidig utilgjengelig.':'Henter siste verifiserte kvartal …')+'</p>':graph(m))+
      '</section>'+
      '<section id="market-overview-comments" class="panel mo-panel mo-comments"><div class="section-head"><div><h2>Kommentarer · '+safe(descriptor)+'</h2></div></div>'+
      (latest?'<div class="mo-comment-grid">'+view.comments.map(c=>'<article><h3>'+safe(c.label)+'</h3>'+c.paragraphs.map(p=>'<p>'+p+'</p>').join('')+'</article>').join('')+'</div>':'<p class="mo-empty">Kommentarer genereres når verifiserte kvartalstall er tilgjengelige.</p>')+'</section>'+ (m.period?trendPanels(m.period):'')+media+nextCal;
  }
  function render(){
    if(typeof current!=='undefined'&&typeof show==='function'&&(current==='home'||COMPANIES.includes(current)))show(current,true);
  }
  function select(kind,value){
    if(kind==='scope'&&['group','norway'].includes(value))scope=value;
    else if(kind==='market'&&['all','pm','bm'].includes(value))market=value;
    else if(kind==='mode'&&['quarter','ytd'].includes(value))mode=value;
    else if(kind==='reportPeriod'&&archive?.periods?.[value])reportPeriod=value===archive.active_period?'latest':value;
    else return;
    render();
    if(kind==='reportPeriod')document.querySelector('#mo-report-period')?.focus({preventScroll:true});
    else document.querySelector('[data-mo-'+kind+'="'+value+'"]')?.focus({preventScroll:true});
  }
  function selectCrHistory(showAll){crShowAll=Boolean(showAll);render();document.querySelector('#mo-cr-history [data-mo-cr-toggle]')?.focus({preventScroll:true});}
  function selectProfitability(name){if(COMPANIES.includes(name)){profitCompany=name;render();document.querySelector('#mo-profitability-panel select')?.focus({preventScroll:true});}}
  function refresh(){
    if(pending)return pending;
    pending=(async()=>{
    try{
      const results=await Promise.allSettled(['nine_insurer_comparison.json','market_overview_fx.json','market_overview_segments.json','market_overview_context.json','market_overview_archive.json','calendar.json'].map(async f=>{
        const r=await fetch('data/'+f+'?t='+Date.now(),{cache:'no-store'});
        if(!r.ok)throw Error('HTTP '+r.status);return r.json();
      }));
      if(results[0].status==='fulfilled')comparison=results[0].value;
      if(results[1].status==='fulfilled')fx=results[1].value;
      if(results[2].status==='fulfilled')segments=results[2].value;
      if(results[3].status==='fulfilled')context=results[3].value;
      if(results[4].status==='fulfilled'&&results[4].value?.active_period)archive=results[4].value;
      if(results[5].status==='fulfilled')calendar=results[5].value;
      failed=results.slice(0,5).some(r=>r.status==='rejected');
    }finally{pending=null;render();}
    })();
    return pending;
  }
  function start(){refresh();setInterval(refresh,300000);}
  function methodology(){
    const view=currentView(),m=view.model,sourceLinks=view.sources;
    return '<div class="panel" id="market-overview-methodology"><h2>Markedsoversikt – rangering, avgrensninger og kilder</h2>'+
      '<p>De fem største selskapene velges etter rapporterte inntekter omregnet til NOK. Selskapene sorteres deretter etter stigende CR. Kvartal viser isolert kvartal; HIÅ viser fra årets start til rapporteringskvartalets slutt. Inntektsveksten beregnes mot samme periode året før i rapportert valuta. Valutakursene er gjennomsnittlige dagskurser for den valgte perioden fra <a href="https://www.norges-bank.no/tema/Statistikk/Valutakurser/" target="_blank" rel="noopener noreferrer">Norges Bank</a>.</p>'+
      '<p>Frende Holding, KLP Skadeforsikring AS og Storebrand ASA (Insurance) inngår i Gruppe totalt og Norge totalt med samme tallgrunnlag etter avgrensningen av markedsoversikten, men ikke PM eller BM. KLP gjelder skadeforsikringsselskapet, ikke hele KLP-konsernet. Frendes inntektsmål er samlede driftsinntekter, ikke et rent IFRS 17-premiemål. Storebrand gjelder Insurance-segmentet i ASA med rapportert Insurance premiums f.o.a. (APM). Protector bruker rapportert total for den geografien i BM, som omfatter offentlig sektor og affinity. Fremtind bruker de samme PM/BM-segmentene for Gruppe og Norge. Kun Fremtind PM/BM kan vises med CR uten separat skade-/kostnadssplitt. Fremtinds isolerte kvartalsinntekter kommer fra differansen mellom kumulative APM-tabeller, mens CR og vekst hentes fra rapporterte APM-tall.</p>'+
      '<p>HIÅ bruker rapporterte kumulative beløp og prosenter når de finnes. Der bare komplette kvartalstall finnes, beregnes inntekt som sum og CR-komponenter som inntektsvektet gjennomsnitt. Avrunding og ulike APM-/IFRS-definisjoner kan gi mindre avvik. Ingen eldre perioder eller konserntall brukes for et urelatert segment. Selskaper uten komplett grunnlag utelates. Kommentarene oppsummerer sammenlignbare nøkkeltall i valgt marked; hendelser brukes bare når rapportens periode og virksomhet støtter avgrensningen.</p>'+
      '<p>CR-historikken viser fem isolerte kvartaler. Y-aksen tilpasses de viste verdiene, med minst ti prosentpoeng i spenn. Ved tydelige uteliggere kan hele selskapsserier skjules i standardutsnittet: kvartilgrensen er 2,5 ganger interkvartilbredden (minst 12 prosentpoeng), og utelatelsen må redusere spennet vesentlig. Minst fem og minst to tredeler av tilgjengelige selskaper beholdes. Skjulte selskaper er navngitt, «Vis alle» gjenoppretter hele grafen, og samtlige tall og kilder beholdes i tabellen. Dette endrer ikke rangeringen, finansverdiene eller øvrige visninger.</p>'+
      '<p>Det aktive rapportkvartalet oppdateres når nye verifiserte rapporter kommer. Når neste kvartal åpnes, fryses forrige publiserte kvartals rangeringer, tall, valutagrunnlag og kommentarer. Velg et låst kvartal for å se det opprinnelige bildet.</p>'+
      (m.period?'<p><strong>Kilder for sist valgte markedsvisning · '+safe(title(m.period))+' · '+safe(mode==='ytd'?'HIÅ':'Kvartal')+'</strong></p><ul>'+sourceLinks.map(r=>'<li><a href="'+safe(r.url)+'" target="_blank" rel="noopener noreferrer">'+safe(r.name)+(r.page?' · side '+safe(r.page):'')+'</a></li>').join('')+'</ul>'+
      '<p>Uten tilstrekkelig grunnlag eller utenfor valgt avgrensning: '+safe(m.missing.map(pretty).join(', ')||'Ingen')+'.</p>':'')+'</div>';
  }
  return {model,comments,makeView,archivedView,viewKey,html,methodology,select,selectProfitability,refresh,start,timeline,profitabilityHistory,profitabilityOptions,companySegmentRows,sampoNordicSegments,financialNumber,financialTrend,companyHistoricalMetrics,companyExtraObservations,reportQueues,trendChart,crTrendView,selectCrHistory,companyQuarterNarrative,companyDetailRows};
});
