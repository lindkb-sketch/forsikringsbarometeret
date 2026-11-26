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
    return /sum driftsinntekter|group operating revenue/.test(d)?'Driftsinntekter':
      /not ifrs insurance revenue|segment premiums|premiums f\.o\.a\.|apm/.test(d)?'Segmentpremier (APM)':'Forsikringsinntekter';
  };
  const valid=r=>COMPANIES.includes(r.company)&&r.period_type==='quarter'&&
    ['reported','calculated'].includes(r.status)&&
    ['official_quarterly_report','official_annual_report'].includes(r.source_type)&&
    (r.source_type!=='official_annual_report'||r.quarter===4)&&
    source(r.source_url)&&/^[0-9a-f]{64}$/.test(r.source_sha256||'')&&
    Number.isInteger(r.source_page)&&r.source_page>0&&num(r.value);
  const periodOf=s=>{const m=/^Q([1-4]) (\d{4})$/.exec(s||'');return m?{year:+m[2],quarter:+m[1]}:null;};
  const samePeriod=(a,b)=>a&&b&&a.year===b.year&&a.quarter===b.quarter;
  const cmpPeriod=(a,b)=>a.year-b.year||a.quarter-b.quarter;
  const key=r=>[r.company,r.year,r.quarter,r.scope,r.segment||'',r.metric].join('|');
  function allRows(feed,segments){
    const rows=(feed?.observations||[]).filter(valid);
    const anchors=new Set(rows.filter(r=>r.scope==='group').map(r=>[r.company,r.source_url,r.source_sha256].join('|')));
    const index=new Map(rows.map(r=>[key(r),r]));
    for(const r of segments?.observations||[]){
      if(!valid(r)||r.scope!=='reported_segment'||
        !['Tryg','Gjensidige'].includes(r.company)||
        !['Private','Commercial'].includes(r.segment)||
        !anchors.has([r.company,r.source_url,r.source_sha256].join('|')))continue;
      const k=key(r),old=index.get(k);
      if(!old)index.set(k,r);
      else if(Math.abs(old.value-r.value)>.001||old.unit!==r.unit)index.delete(k);
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
      if(r.scope!=='group'||!['insurance_revenue','combined_ratio'].includes(r.metric))continue;
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
    const current=rows.filter(r=>r.company===company&&samePeriod(r,p));
    if(market==='all')return [{rows:current.filter(r=>r.scope===scope),scope,segment:null}];
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
    if(METRICS.some(m=>!values[m]))return null;
    const revenue=values.insurance_revenue,cur=currency(revenue.unit);
    const cr=values.combined_ratio.value,loss=values.loss_ratio.value,cost=values.expense_ratio.value;
    if(!cur||revenue.value<=0||CORE.some(m=>values[m].unit!=='percent')||
      Math.min(loss,cost,cr)<0||Math.abs(cr-loss-cost)>.25)return null;
    const prior=rows.filter(r=>r.company===company&&r.year===p.year-1&&r.quarter===p.quarter&&r.scope===g.scope&&(g.scope!=='reported_segment'||r.segment===g.segment));
    const priorRev=selectUnique(prior,'insurance_revenue');
    const reported=selectUnique(g.rows,'insurance_revenue_growth');
    const growth=priorRev&&priorRev.value>0&&priorRev.unit===revenue.unit&&basis(priorRev)===basis(revenue)?
      (revenue.value/priorRev.value-1)*100:reported?.unit==='percent'?reported.value:null;
    const deltas={};
    for(const key of CORE){
      const old=selectUnique(prior,key);
      deltas[key]=old&&old.unit==='percent'&&basis(old)===basis(values[key])?values[key].value-old.value:null;
    }
    return {company,segment:g.displaySegment||g.segment,source:revenue.source_url,revenue:revenue.value,currency:cur,
      revenueBasis:basis(revenue),cr,loss,cost,growth,deltas};
  }
  function extendedRow(c,p){
    if(!EXTENDED.includes(c.company)||c.status!=='verified_official_pdf_reconciled'||!samePeriod(periodOf(c.period),p)||!source(c.source_url))return null;
    const m=c.metrics||{};
    if(METRICS.some(k=>!num(m[k]))||m.insurance_revenue<=0||
      !['NOK','DKK','EUR','SEK'].includes(c.currency)||Math.min(m.loss_ratio,m.expense_ratio,m.combined_ratio)<0||
      Math.abs(m.combined_ratio-m.loss_ratio-m.expense_ratio)>.25)return null;
    return {company:c.company,segment:null,source:c.source_url,revenue:m.insurance_revenue,currency:c.currency,
      revenueBasis:'Forsikringsinntekter',cr:m.combined_ratio,loss:m.loss_ratio,cost:m.expense_ratio,
      growth:num(m.insurance_revenue_growth)?m.insurance_revenue_growth:null,deltas:{}};
  }
  function model(feed,comparison,fx,scope='group',market='all',segments=null){
    const rows=allRows(feed,segments),p=choosePeriod(rows,comparison);
    if(!p)return {period:null,eligible:[],selected:[],missing:COMPANIES.slice(),fxMissing:[],reported:0};
    const eligible=[];
    for(const company of COMPANIES){
      let r=rowFor(rows,company,p,scope,market);
      if(!r&&scope==='group'&&market==='all'&&EXTENDED.includes(company)){
        r=extendedRow((comparison?.companies||[]).find(c=>c.company===company)||{},p);
      }
      if(r)eligible.push(r);
    }
    const rates=fx?.periods?.[title(p)]?.rates||{};
    const rate=cur=>cur==='NOK'?1:(num(rates[cur])&&rates[cur]>0?rates[cur]:null);
    const fxMissing=eligible.filter(r=>rate(r.currency)===null).map(r=>r.company);
    // Ranking is not a "top five" if some eligible issuers are unrankable.
    const ranked=fxMissing.length?[]:eligible.map(r=>({...r,revenueNok:r.revenue*rate(r.currency)}))
      .sort((a,b)=>b.revenueNok-a.revenueNok||a.company.localeCompare(b.company,'nb'));
    const selected=ranked.slice(0,5).sort((a,b)=>a.cr-b.cr||b.revenueNok-a.revenueNok||a.company.localeCompare(b.company,'nb'));
    const reported=COMPANIES.filter(c=>rowFor(rows,c,p,'group','all')||
      extendedRow((comparison?.companies||[]).find(r=>r.company===c)||{},p)).length;
    return {period:p,eligible,selected,missing:COMPANIES.filter(c=>!eligible.some(r=>r.company===c)),fxMissing,reported};
  }
  function groupText(values, noun,positive='opp',negative='ned'){
    const comparable=values.filter(num);
    if(!comparable.length)return 'Det er foreløpig ikke sammenlignbare fjorårstall for '+noun+'.';
    const up=comparable.filter(v=>v>.05).length,down=comparable.filter(v=>v<-.05).length;
    const flat=comparable.length-up-down;
    return noun.charAt(0).toUpperCase()+noun.slice(1)+': '+up+' '+positive+', '+down+' '+negative+(flat?', '+flat+' omtrent uendret':'')+
      ' av '+comparable.length+' med sammenlignbare tall mot samme kvartal i fjor.';
  }
  function comments(m,editorial,scope,market){
    const rows=m.eligible, period=title(m.period);
    const names=new Set(rows.map(r=>r.company));
    const general=scope==='group'&&market==='all';
    const block=editorial?.periods?.[period]||(editorial?.period===period?editorial:null);
    const items=(block?.brief||[]).filter(x=>x.period===period&&typeof x.text==='string'&&source(x.source_url)&&
      Array.isArray(x.companies)&&x.companies.length&&x.companies.every(c=>names.has(c)));
    const links=x=>{
      const urls=[...new Set([x.source_url,...(x.source_urls||[])])].filter(source).slice(0,4);
      return safe(x.text)+' <span class="mo-sources">'+urls.map((u,i)=>'<a href="'+safe(u)+'" target="_blank" rel="noopener noreferrer">Kilde'+(urls.length>1?' '+(i+1):'')+'</a>').join(' · ')+'</span>';
    };
    const growth=[groupText(rows.map(r=>r.growth),'inntektsvekst','øker','faller')];
    const cr=[groupText(rows.map(r=>r.deltas.combined_ratio),'CR','høyere','lavere'),
      groupText(rows.map(r=>r.deltas.loss_ratio),'skadeprosent','høyere','lavere'),
      groupText(rows.map(r=>r.deltas.expense_ratio),'kostnadsprosent','høyere','lavere')];
    if(general){
      const g=items.find(x=>/growth|revenue_direction|revenue_decline/.test(x.theme||''));
      if(g)growth.push(links(g));
      const p=items.find(x=>/profitability|underwriting|reserves|reinsurance/.test(x.theme||''));
      if(p)cr.push(links(p));
    }
    const special=general?items.filter(x=>/large_claims|weather|regulation|strategy|operations|investment|inflation|competition/.test(x.theme||'')).slice(0,2).map(links):[];
    if(!special.length)special.push(general?
      'Ingen særskilt dokumentert hendelse er valgt ut for de rapporterte selskapene i dette kvartalet ennå.':
      'Særskilte hendelser publiseres bare når de kan knyttes til valgt område og segment. Se Oppsummering for konsernkommentarer.');
    return [{label:'Inntektsvekst',paragraphs:growth},{label:'CR – skade- og kostnadsprosent',paragraphs:cr},{label:'Enkelthendelser og særtrekk',paragraphs:special}];
  }
  let comparison=null,fx=null,segments=null,scope='group',market='all',pending=null,failed=false;
  function controls(){
    const group=(id,caption,options,current)=>'<fieldset class="mo-filter" id="'+id+'"><legend>'+caption+'</legend><div role="group" aria-label="'+caption+'">'+options.map(([key,label])=>
      '<button type="button" data-mo-'+id+'="'+key+'" aria-pressed="'+(current===key)+'" onclick="FBMarketOverview.select(\''+id+'\',\''+key+'\')">'+label+'</button>').join('')+'</div></fieldset>';
    return '<div class="mo-filters">'+group('scope','Geografi',[['group','Gruppe'],['norway','Norge']],scope)+
      group('market','Marked',[['all','Totalt'],['pm','PM'],['bm','BM']],market)+'</div>';
  }
  function graph(m){
    if(m.fxMissing.length)return '<p class="mo-empty">Valutagrunnlaget for '+safe(title(m.period))+' er foreløpig ikke tilgjengelig for '+safe(m.fxMissing.map(pretty).join(', '))+'. Topp 5 vises når NOK-rangeringen kan beregnes korrekt.</p>';
    if(!m.selected.length)return '<p class="mo-empty">Ingen selskaper har komplett kildeverifisert inntekt, CR, skadeprosent og kostnadsprosent for dette valget i '+safe(title(m.period))+'.</p>';
    const cap=Math.max(100,Math.ceil(Math.max(...m.selected.map(r=>r.loss+r.cost))/20)*20);
    const bars=m.selected.map(r=>{
      const stack=r.loss+r.cost;
      const accessible=pretty(r.company)+': CR '+pct(r.cr)+', skadeprosent '+pct(r.loss)+', kostnadsprosent '+pct(r.cost)+', vekst '+growthText(r.growth);
      return '<div class="mo-company" data-company="'+safe(r.company)+'" data-cr="'+r.cr+'" data-income-nok="'+r.revenueNok+'">'+
        '<div class="mo-bar-area" role="img" aria-label="'+safe(accessible)+'">'+
        '<div class="mo-stack" style="height:'+stack/cap*100+'%">'+
        '<span class="mo-cr">'+pct(r.cr)+'</span>'+
        '<div class="mo-cost" style="height:'+(stack?r.cost/stack*100:0)+'%"><span>'+format(r.cost)+'</span></div>'+
        '<div class="mo-loss" style="height:'+(stack?r.loss/stack*100:0)+'%"><span>'+format(r.loss)+'</span></div></div></div>'+
        '<div class="mo-name"><button type="button" onclick="show(\''+safe(r.company)+'\')">'+safe(pretty(r.company))+'</button>'+
        (r.segment?'<small>'+safe(r.segment)+'</small>':'')+'</div>'+
        '<div class="mo-growth '+(num(r.growth)?r.growth>0?'positive':r.growth<0?'negative':'':'')+'"><span>Inntektsvekst</span><strong>'+growthText(r.growth)+'</strong></div>'+
        '<div class="mo-income" title="'+safe(r.revenueBasis)+' · '+format(r.revenue,0)+' mill. '+r.currency+'">'+format(r.revenueNok,0)+' mill. NOK</div>'+
        '<a class="mo-source" href="'+safe(r.source)+'" target="_blank" rel="noopener noreferrer">Kvartalsrapport</a></div>';
    }).join('');
    const ticks=Array.from({length:6},(_,i)=>Math.round(cap*i/5));
    return '<div class="mo-legend"><span><i class="mo-loss-key"></i> Skadeprosent</span><span><i class="mo-cost-key"></i> Kostnadsprosent</span></div>'+
      '<div class="mo-scroll"><div class="mo-chart" style="--mo-columns:'+m.selected.length+'"><div class="mo-axis" aria-hidden="true">'+ticks.map(t=>'<span style="bottom:'+t/cap*100+'%">'+t+' %</span>').join('')+'</div>'+
      '<div class="mo-chart-body"><div class="mo-guides" aria-hidden="true">'+ticks.map(t=>'<i style="bottom:'+t/cap*100+'%"></i>').join('')+'</div><div class="mo-bars">'+bars+'</div></div></div></div>';
  }
  function html(){
    const m=model(window.FBQuarterly?.verified,comparison,fx,scope,market,segments);
    const latest=title(m.period);
    const contextual=scope==='norway'?'Norge':'Gruppe';
    const filter=market==='all'?'Totalt':market==='pm'?'PM':'BM';
    const descriptor=contextual+' · '+filter;
    const count=m.selected.length;
    let subtitle='Fem største etter rapportert kvartalsinntekt · sortert etter lavest CR.';
    if(m.period&&m.eligible.length<5)subtitle='Færre enn fem selskaper har komplette tall for valgt område.';
    return '<div class="top mo-top"><div><div class="eyebrow">MARKEDSOVERSIKT</div><h1>Forsikringsbarometeret</h1><p class="sub">Lønnsomhet og vekst i forsikringsmarkedet</p></div>'+
      '<div class="tag" id="mo-period">'+safe(latest||'Laster rapportperiode')+'</div></div>'+
      '<section id="market-overview" class="panel mo-panel" data-period="'+safe(latest)+'" data-scope="'+scope+'" data-market="'+market+'">'+
      controls()+'<div class="section-head mo-heading"><div><h2>'+ (count<5&&count>0?count+' største selskaper':'Topp 5 selskaper')+' · '+safe(descriptor)+'</h2><p class="hint">'+safe(subtitle)+'</p></div>'+
      (latest?'<span class="pill">'+m.reported+' / 9 rapportert</span>':'')+'</div>'+
      (!m.period?'<p class="mo-empty">'+(failed?'Datagrunnlaget er midlertidig utilgjengelig.':'Henter siste verifiserte kvartal …')+'</p>':graph(m))+
      (latest?'<p class="mo-note">Inntekter rangeres i NOK etter gjennomsnittlig dagskurs for kvartalet (<a href="https://www.norges-bank.no/tema/Statistikk/Valutakurser/" target="_blank" rel="noopener noreferrer">Norges Bank</a>); vekst i rapportert valuta mot samme kvartal året før. Inntektsdefinisjoner kan variere (bl.a. segmentpremier). CR kan avvike marginalt fra summen grunnet avrunding. Bare verifiserte tall i valgt kvartal og område vises. Gruppens PM/BM følger selskapets rapporterte forretningssegmenter, som kan utelate andre geografier. Protector vises i BM med rapportert total (inkl. offentlig sektor og affinity), ikke som et separat rapportert BM-segment.</p>':'')+
      (latest&&m.missing.length?'<details class="mo-excluded"><summary>'+m.missing.length+' selskaper uten komplett tallgrunnlag for valget</summary><p>'+safe(m.missing.map(pretty).join(', '))+'. Ingen eldre kvartaler eller urelaterte konserntall brukes som erstatning.</p></details>':'')+'</section>'+
      '<section id="market-overview-comments" class="panel mo-panel mo-comments"><div class="section-head"><div><h2>Kommentarer til kvartalet</h2><p class="hint">'+safe(latest||'Avventer tall')+' · '+safe(descriptor)+' · oppdateres når nye rapporter kommer</p></div></div>'+
      (latest?'<div class="mo-comment-grid">'+comments(m,window.FBNews?.editorial,scope,market).map(c=>'<article><h3>'+safe(c.label)+'</h3>'+c.paragraphs.map(p=>'<p>'+p+'</p>').join('')+'</article>').join('')+'</div>':'<p class="mo-empty">Kommentarer genereres når verifiserte kvartalstall er tilgjengelige.</p>')+'</section>';
  }
  function render(){
    if(typeof current!=='undefined'&&current==='home'&&typeof show==='function')show('home',true);
  }
  function select(kind,value){
    if(kind==='scope'&&['group','norway'].includes(value))scope=value;
    else if(kind==='market'&&['all','pm','bm'].includes(value))market=value;
    else return;
    render();
    document.querySelector('[data-mo-'+kind+'="'+value+'"]')?.focus({preventScroll:true});
  }
  function refresh(){
    if(pending)return pending;
    pending=(async()=>{
    try{
      const results=await Promise.allSettled(['nine_insurer_comparison.json','market_overview_fx.json','market_overview_segments.json'].map(async f=>{
        const r=await fetch('data/'+f+'?t='+Date.now(),{cache:'no-store'});
        if(!r.ok)throw Error('HTTP '+r.status);return r.json();
      }));
      if(results[0].status==='fulfilled')comparison=results[0].value;
      if(results[1].status==='fulfilled')fx=results[1].value;
      if(results[2].status==='fulfilled')segments=results[2].value;
      failed=results.some(r=>r.status==='rejected');
    }finally{pending=null;render();}
    })();
    return pending;
  }
  function start(){refresh();setInterval(refresh,300000);}
  return {model,comments,html,select,refresh,start};
});
