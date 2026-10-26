/* Rolling source-verified quarterly model for the ORIGINAL Forsikringsbarometeret UI.
   This file changes data bindings only, never the dashboard's card/grid markup.
   No reported financial value is hardcoded here. */
(function () {
  'use strict';
  const COMPANY_NAMES=['Fremtind','Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand'];
  const KEYS={combined_ratio:'cr',loss_ratio:'loss',expense_ratio:'cost',
    insurance_service_result:'result',return_on_equity:'return',solvency_ratio:'solvency'};
  const PERCENT=new Set(['cr','loss','cost','return','solvency','growth']);
  const METRICS=['combined_ratio','loss_ratio','expense_ratio','insurance_revenue','insurance_service_result'];
  let verified=null, periodList=[], selection=null, manuallySelected=false, calendarData=null;
  const label=({year,quarter})=>'Q'+quarter+' '+year;
  const fmt=(value,pct=false)=>new Intl.NumberFormat('nb-NO',{
      maximumFractionDigits:pct?1:2,minimumFractionDigits:pct?1:0
    }).format(value)+(pct?' %':'');
  const ytdMode=()=>period==='H3';
  const basis=row=>/sum driftsinntekter|group operating revenue/i.test(row?.source_definition||'')?'operating_revenue':/not ifrs insurance revenue|segment premiums|premiums f\.o\.a\./i.test(row?.source_definition||'')?'apm':'ifrs_or_other';
  const hasSource=r=>r&&r.source_url&&/^https:\/\//.test(r.source_url)&&
    (r.source_page||r.source_cell||r.source_sheet||r.source_type==='official_quarterly_report');
  const valid=r=>r&&['reported','calculated'].includes(r.status)&&Number.isFinite(r.value)&&hasSource(r);
  const isSameBasis=(a,b)=>a&&b&&a.unit===b.unit&&basis(a)===basis(b);
  function rows(){
    return (verified?.observations||[]).filter(r=>valid(r)&&r.scope==='group'&&
      (r.period_type==='quarter'||r.period_type==='ytd'));
  }
  function calcPeriods(){
    const pts=new Map();
    for(const r of rows()) {
      if(r.period_type!=='quarter'||!METRICS.includes(r.metric))continue;
      const key=r.year+'-'+r.quarter;
      if(!pts.has(key))pts.set(key,{year:r.year,quarter:r.quarter,issuers:new Map()});
      const period=pts.get(key);
      if(!period.issuers.has(r.company))period.issuers.set(r.company,new Set());
      period.issuers.get(r.company).add(r.metric);
    }
    // A solitary comparator, ratio or partial import must not switch the
    // entire homepage to a nearly empty future quarter. One issuer must
    // have BOTH verified revenue and a combined ratio for that quarter.
    return [...pts.values()]
      .filter(p=>[...p.issuers.values()].some(metrics=>
        metrics.has('insurance_revenue')&&metrics.has('combined_ratio')))
      .map(({year,quarter})=>({year,quarter}))
      .sort((a,b)=>b.year-a.year||b.quarter-a.quarter);
  }
  function lookup(company,type,year,quarter,metric){
    return rows().find(r=>r.company===company&&r.year===year&&r.quarter===quarter&&
      r.period_type===type&&r.metric===metric);
  }
  function addQuarter(company,year,quarter,metric){
    // A standalone quarter may be reconstructed from two consecutive issuer
    // YTD columns. Only additive amounts, identical units and entity scopes.
    if(!['insurance_revenue','insurance_service_result'].includes(metric))return null;
    const end=lookup(company,'ytd',year,quarter,metric);
    const before=quarter>1?lookup(company,'ytd',year,quarter-1,metric):null;
    if(!end||quarter>1&&!before||before&&!isSameBasis(end,before))return null;
    const result=end.value-(before?.value||0);
    if(result<0)return null;
    return {...end,period_type:'quarter',value:result,derived_quarter:true,
      calculation:'difference_of_reported_ytd'};
  }
  function addYtd(company,year,quarter,metric){
    const parts=Array.from({length:quarter},(_,i)=>
      lookup(company,'quarter',year,i+1,metric)||
      addQuarter(company,year,i+1,metric));
    if(parts.some(x=>!x)||parts.some(x=>!isSameBasis(x,parts[0])))return null;
    if(['insurance_revenue','insurance_service_result'].includes(metric))
      return {...parts[quarter-1],period_type:'ytd',
        value:parts.reduce((sum,r)=>sum+r.value,0),
        derived_ytd:true,calculation:'sum_of_verified_isolated_quarters'};
    // A year-to-date ratio may be approximated from every official isolated
    // quarter, weighted by insurance revenue. Never sum/average ratios blindly.
    if(!['combined_ratio','loss_ratio','expense_ratio'].includes(metric))return null;
    const revenues=Array.from({length:quarter},(_,i)=>
      lookup(company,'quarter',year,i+1,'insurance_revenue')||
      addQuarter(company,year,i+1,'insurance_revenue'));
    if(revenues.some(x=>!x)||revenues.some(x=>!isSameBasis(x,revenues[0])))return null;
    const denominator=revenues.reduce((sum,r)=>sum+r.value,0);
    if(denominator<=0)return null;
    return {...parts[quarter-1],period_type:'ytd',
      value:parts.reduce((sum,r,i)=>sum+r.value*revenues[i].value,0)/denominator,
      derived_ytd:true,calculation:'premium_weighted_issued_quarter_ratios'};
  }
  function quote(company,type,year,quarter,metric){
    // Solvency is an as-of-date balance-sheet measurement, not a flow.
    // Reuse the same verified reporting-date value for Quarter and YTD.
    if(metric==='solvency_ratio')
      return lookup(company,type,year,quarter,metric)||
        lookup(company,type==='quarter'?'ytd':'quarter',year,quarter,metric);
    return lookup(company,type,year,quarter,metric)||
      (type==='ytd'?addYtd(company,year,quarter,metric):
       addQuarter(company,year,quarter,metric));
  }
  function quarterTimeline({year,quarter}){
    const result=[];
    for(let i=4;i>=0;i--){
      const code=year*4+(quarter-1)-i;
      const y=Math.floor(code/4),q=(code%4)+1;
      result.push('Q'+q+' '+y);
    }
    return result;
  }
  function populate(){
    if(!selection)return;
    const {year,quarter}=selection;
    for(const name of COMPANY_NAMES) {
      delete MON_Q3[name];delete MON_YTD_Q3[name];
      profitabilityVerified[name]={};profitabilityReturns[name]={};
    }
    const financialRows=rows();
    for(const name of COMPANY_NAMES){
      for(const [type,bucket] of [['quarter',MON_Q3],['ytd',MON_YTD_Q3]]){
        const data={};
        for(const metric of Object.keys(KEYS).concat('insurance_revenue')){
          const current=quote(name,type,year,quarter,metric);
          const prior=quote(name,type,year-1,quarter,metric);
          const k=metric==='insurance_revenue'?'revenue':KEYS[metric];
          if(current){
            data[k]=fmt(current.value,PERCENT.has(k));
            if(current.calculation)data[k+'Method']=current.calculation;
            if(k==='revenue'){
              data.revenueUnit=current.unit||'';
              if(name==='Frende')data.revenueBasis='IFRS 4: premieinntekter fra skade- og livsforsikring (rapportert som sum driftsinntekter for Frende Holding AS konsern)';
              else if(basis(current)==='apm')data.revenueBasis='Insurance premiums f.o.a. (APM) – ikke IFRS 17-forsikringsinntekter';
              if(current.derived_ytd)data.revenueBasis=(data.revenueBasis||'')+
                ' Beregnet HIÅ fra verifiserte kvartaler.';
              if(current.derived_quarter)data.revenueBasis=(data.revenueBasis||'')+
                ' Beregnet kvartal som differanse mellom to rapporterte HIÅ-perioder.';
            }
            if(metric==='insurance_service_result')data.resultUnit=current.unit||'';
            if(metric==='combined_ratio'||metric==='insurance_revenue')data.source=current.source_url;
          }
          if(prior&&(!current||isSameBasis(current,prior))){
            data[k+'Prev']=fmt(prior.value,PERCENT.has(k));
          }
        }
        // Isolated quarter and year-to-date growth use their OWN reporting periods.
        // 2026 vs 2025 gives this year's rate; 2025 vs 2024 gives last year's.
        // Never substitute current-year growth for missing historical growth.
        function growthFor(targetYear){
          const stated=quote(name,type,targetYear,quarter,'insurance_revenue_growth');
          if(stated&&Number.isFinite(stated.value))return {value:stated.value,method:'reported'};
          const now=quote(name,type,targetYear,quarter,'insurance_revenue');
          const before=quote(name,type,targetYear-1,quarter,'insurance_revenue');
          if(!now||!before||before.value<=0||!isSameBasis(now,before))return null;
          return {value:(now.value/before.value-1)*100,method:'calculated'};
        }
        const thisGrowth=growthFor(year),lastGrowth=growthFor(year-1);
        if(thisGrowth){
          data.growth=fmt(thisGrowth.value,true);
          data.growthBasis=thisGrowth.method==='reported'
            ?(name==='Frende'?'Rapportert vekst i driftsinntekter':'Rapportert i selskapets kvartalsrapport')
            :(name==='Frende'?'Beregnet fra kildeverifiserte, sammenlignbare driftsinntekter':'Beregnet fra kildeverifiserte, sammenlignbare forsikringsinntekter');
        }
        if(lastGrowth){
          data.growthPrev=fmt(lastGrowth.value,true);
          data.growthPrevBasis=lastGrowth.method;
        }
        data.growthComparisonPeriod=type;
        if(name==='Frende')data.growthMetricLabel='Vekst i forsikringsinntekter (IFRS 4)';
        if(Object.keys(data).length)bucket[name]=data;
      }
      const group=financialRows.filter(r=>r.company===name&&r.period_type==='quarter');
      const labels=[...new Set(group.map(r=>label(r)))];
      for(const l of labels){
        const periodRows=group.filter(r=>label(r)===l);
        const find=m=>periodRows.find(r=>r.metric===m)?.value;
        const loss=find('loss_ratio'),cost=find('expense_ratio'),cr=find('combined_ratio');
        if([loss,cost,cr].every(Number.isFinite))profitabilityVerified[name][l]=[loss,cost,cr];
        const roe=find('return_on_equity');
        if(Number.isFinite(roe))profitabilityReturns[name][l]={
          label:'Rapportert avkastningsmål fra rapport',value:roe};
      }
    }
    profitabilityQuarters.splice(0,profitabilityQuarters.length,...quarterTimeline(selection));
    window.FBActivePeriod={...selection,label:label(selection),priorLabel:'Q'+quarter+' '+(year-1)};
    // Clear old Q2-only company segment figures rather than masquerade them as current.
    for(const [name,oldRows] of Object.entries(MON_Q2_SEGMENTS)){
      if(!segmentData[name])continue;
      segmentData[name]=oldRows.map(r=>{
        const x={...r};
        for(const k of ['growth','growthPrev','underwriting','underwritingPrev','cr','crPrev','loss','lossPrev','cost','costPrev'])x[k]='';
        return x;
      });
    }
  }
  function choose(key,manual) {
    const chosen=periodList.find(p=>p.year+'-'+p.quarter===key);
    if(!chosen)return;
    selection=chosen;
    if(manual)manuallySelected=true;
    MON_QUARTER='Q3'; // live-data mode, distinct from the obsolete, static Q2 adapter
    // Auto-refresh must not throw the user out of the HIÅ tab.
    if(manual || period!=='H3')period='Q3';
    populate();
    if(typeof show==='function'&&typeof current!=='undefined')show(current,true);
  }
  function relabel(html){
    if(!selection)return html;
    const {year,quarter}=selection;
    return html.replaceAll('Q3 2026',label(selection)).replaceAll('Q3 2025','Q'+quarter+' '+(year-1))
      .replaceAll('Hiå 2026','Hiå '+year)
      .replaceAll('Hiå 2025','Hiå '+(year-1)).replaceAll('HIÅ 2025','HIÅ '+(year-1))
      .replaceAll('Q3 2026 · KILDEOPPDATERT',label(selection)+' · KILDEOPPDATERT')
      .replace('Forsikringsinntekter · Q3','Forsikringsinntekter · Q'+quarter);
  }
  // The reporting date is advisory. Only an actual, verified issuer report
  // makes a company disappear from the next-report queue.
  monCalendar=function(){
    if(!verified||!periodList.length||MON_QUARTER==='Q2')return '';
    const active=periodList[0];
    const selectedPeriod=label(active);
    const pending=COMPANY_NAMES.filter(name=>{
      const group=rows().filter(r=>r.company===name&&r.year===active.year&&
        r.quarter===active.quarter&&r.period_type==='quarter');
      const found=new Set(group.map(r=>r.metric));
      return !found.has('combined_ratio')||!found.has('insurance_revenue');
    });
    if(!pending.length)return '';
    const safe=v=>String(v??'').replace(/[&<>"']/g,c=>({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const links=pending.map(name=>{
      const config=calendarData?.[name==='Sampo'?'Sampo / If':name]||{};
      const event=(config.events||[]).find(e=>e.period===selectedPeriod);
      const date=event?.date||'Dato ikke meldt';
      const address=config.calendar_url&&/^https:\/\//.test(config.calendar_url)?
        config.calendar_url:'#';
      return '<a class="mon-cal-row" href="'+safe(address)+
        '" target="_blank" rel="noopener noreferrer"><span class="mon-cal-company"><strong>'+
        safe(name==='Sampo'?'Sampo / If':name)+'</strong><small>'+safe(date)+
        '</small></span><span class="mon-cal-countdown"'+
        (event?.date?' data-report-date="'+safe(date)+'"':'')+
        '>'+ (event?.date?'Planlagt dato':'Offisiell rapport overvåkes')+
        '</span></a>';
    }).join('');
    return '<section class="mon-calendar" aria-label="Neste rapporter fra selskaper som mangler tall">'+
      '<div class="mon-calendar-top"><div class="eyebrow">NESTE RAPPORTER</div>'+
      '<h2>Avventer '+safe(selectedPeriod)+'</h2>'+
      '<span class="pill">'+pending.length+' selskaper</span></div>'+
      '<div class="mon-cal-grid">'+links+'</div></section>';
  };
  const previousHome=home,previousCompany=company,previousPodium=crPodium;
  MON_SELECT=()=>'<div class="mon-period"><div><b>Rapporteringskvartal</b>'+
    '<div style="font-size:12px;color:#617589;margin-top:3px">Samme opprinnelige design for alle kvartaler</div></div>'+
    '<select aria-label="Velg kvartal" onchange="monSetQuarter(this.value)">'+
    periodList.map(p=>'<option value="'+p.year+'-'+p.quarter+'" '+
      (selection&&p.year===selection.year&&p.quarter===selection.quarter?'selected':'')+'>'+
      label(p)+(selection&&p.year===selection.year&&p.quarter===selection.quarter?' · valgt':'')+
      '</option>').join('')+'</select></div>';
  monSetQuarter=value=>{
    if(value==='Q3'||value==='Q2'){ // legacy DOMContentLoaded call; use latest data
      if(verified){choose((selection||periodList[0]).year+'-'+(selection||periodList[0]).quarter,false);}
      return;
    }
    choose(value,true);
  };
  home=()=>relabel(previousHome());
  // Individual company pages must use the SAME published quarter/YTD
  // observations as the group table; never display the static Q2 cards.
  // Display all four independently verified revenue-growth rates. An absent
  // comparator is unknown, never zero or a copied rate from another period.
  function growthMatrix(c){
    const q=MON_Q3[c]||{},h=MON_YTD_Q3[c]||{};
    return [
      ['Kvartal isolert',q.growth,Boolean(q.revenue),'quarter'],
      ['Kvartal i fjor',q.growthPrev,Boolean(q.revenuePrev),'quarter-prior'],
      ['HIÅ',h.growth,Boolean(h.revenue),'ytd'],
      ['HIÅ i fjor',h.growthPrev,Boolean(h.revenuePrev),'ytd-prior']
    ];
  }
  function trendArrow(now,prior){
    const parse=s=>{const m=String(s??'').replace(/\\s/g,'').replace(',','.').match(/-?\\d+(?:\\.\\d+)?/);return m?Number(m[0]):null;};
    const a=parse(now),b=parse(prior);
    if(a===null||b===null)return '';
    const diff=a-b,dir=diff>0.00001?'up':diff< -0.00001?'down':'flat';
    const sign=dir==='up'?'▲':dir==='down'?'▼':'→';
    return '<span class="qoq '+(dir==='up'?'good':dir==='down'?'bad':'flat')+
      '" aria-label="'+(dir==='up'?'Opp':dir==='down'?'Ned':'Uendret')+
      ' mot tilsvarende periode i fjor" title="Sammenlignet med tilsvarende periode i fjor">'+sign+'</span>';
  }
  function growthMatrixHtml(c){
    if(!selection)return '';
    const esc=s=>String(s??'').replace(/[&<>"']/g,k=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[k]));
    const q=MON_Q3[c]||{},h=MON_YTD_Q3[c]||{};
    return '<section class="panel source-growth-matrix"><h2>Inntektsvekst · Q'+selection.quarter+' '+selection.year+'</h2>'+
      '<div class="dynamic-kpis">'+growthMatrix(c).map(([label,value,available,key])=>
        '<div class="metric" data-growth-period="'+key+'"><div class="name">'+esc(label)+'</div>'+
        '<div class="value">'+(available&&value?esc(value):'—')+
        (key==='quarter'&&available?trendArrow(q.growth,q.growthPrev):
         key==='ytd'&&available?trendArrow(h.growth,h.growthPrev):'')+'</div>'+
        '<div class="prior">'+(available&&value?'Kildeverifisert':'Mangler verifiserte sammenligningstall')+'</div></div>'
      ).join('')+'</div>'+
      '<p class="hint">Vekst sammenligner inntektene med samme periode året før. Pil opp/ned viser om vekstraten har økt eller falt fra fjoråret. Manglende data vises som —.</p></section>';
  }
  function companyWithVerifiedKpis(c){
    const fragment=document.createElement('div');
    fragment.innerHTML=relabel(previousCompany(c));
    const cardNodes=fragment.querySelectorAll('.dynamic-kpis > .metric');
    const d=(ytdMode()?MON_YTD_Q3:MON_Q3)[c]||{};
    if(cardNodes.length>=2){
      const esc=x=>String(x??'').replace(/[&<>"']/g,ch=>({
        '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
      const currentPublished=Boolean(d.revenue);
      const priorLabel=ytdMode()?'HIÅ '+(selection.year-1):'Q'+selection.quarter+' '+(selection.year-1);
      const build=(node,name,current,previous,unit)=>{
        const primary=currentPublished&&current?esc(current)+(unit?' '+esc(unit):''):'Ikke publisert';
        const reference=currentPublished&&previous?esc(previous)+(unit?' '+esc(unit):''):'—';
        const arrow=currentPublished&&current&&previous?trendArrow(current,previous):'';
        node.innerHTML='<div class="name">'+name+'</div>'+
          '<div class="value">'+primary+arrow+'</div>'+
          '<div class="prior">('+reference+')</div>';
        node.setAttribute('data-financial-period',ytdMode()?'ytd':'quarter');
        node.setAttribute('data-financial-source','verified-quarterly-feed');
      };
      build(cardNodes[0],c==='Frende'?'Inntektsvekst (IFRS 4)':'Inntektsvekst',
        d.growth,d.growthPrev,'');
      build(cardNodes[1],c==='Storebrand'?'Forsikringsresultat · Cash equivalent earnings':
          c==='Frende'?'Forsikringsdriftsresultat':'Forsikringsresultat',
        d.result,d.resultPrev,d.resultUnit||'');
    }
    // Replace the legacy Q2 label with the actual selected quarter.
    const heading=fragment.querySelector('.section-head h2');
    if(heading)heading.textContent=heading.textContent.replace(/Q2 2026/,label(selection));
    return fragment.innerHTML+growthMatrixHtml(c);
  }
  company=c=>companyWithVerifiedKpis(c);
  crPodium=()=>relabel(previousPodium());
  function normalizeRevenueTable(html){
    // Extend the EXISTING table; do not add a replacement dashboard.
    if(!selection)return html;
    const fragment=document.createElement('div');
    fragment.innerHTML=html;
    const head=fragment.querySelector('thead tr');
    if(!head)return html;
    const isYtd=ytdMode(), year=selection.year, q=selection.quarter;
    const heading=document.createElement('th');
    heading.textContent=isYtd?'Forsikringsresultat · HIÅ':'Forsikringsresultat · Q'+q;
    head.insertBefore(heading,head.children[2]||null);
    const escape=v=>String(v??'').replace(/[&<>"']/g,c=>({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const number=s=>{
      if(s===undefined||s===null||String(s).trim()==='')return null;
      const n=Number(String(s).replace(/\s/g,'').replace(/\u00a0/g,'')
        .replace(/\u202f/g,'').replace(',','.').replace(/[^0-9.-]/g,''));
      return Number.isFinite(n)?n:null;
    };
    for(const tr of fragment.querySelectorAll('tbody tr')){
      const raw=(tr.cells[0]?.textContent||'').trim();
      const name=raw==='Frende Holding'?'Frende':raw;
      const d=(isYtd?MON_YTD_Q3:MON_Q3)[name]||{};
      const td=document.createElement('td');
      if(d.revenue&&d.result){
        const title=escape(d.result)+' <small>'+escape(d.resultUnit||'')+'</small>';
        const basis='';
        const lastYear=isYtd?'HIÅ '+(year-1):'Q'+q+' '+(year-1);
        const prior=d.resultPrev
          ?'<span class="table-prior">'+lastYear+': '+escape(d.resultPrev)+'</span>'
          :'<span class="table-prior">'+lastYear+': ikke verifisert</span>';
        const now=number(d.result),then=number(d.resultPrev);
        const delta=now!==null&&then!==null
          ?'<span class="qoq '+(now>then?'good':now<then?'bad':'flat')+
           '" aria-label="Endring mot samme periode i fjor">'+
           (now>then?'▲':now<then?'▼':'→')+'</span>':'';
        let subsidiary='';
        if(name==='Storebrand'){
          const local=(verified?.observations||[]).find(r=>
            r.company==='Storebrand'&&r.scope==='norway'&&
            r.source_entity==='Storebrand Forsikring AS'&&
            r.year===year&&r.quarter===q&&
            r.period_type===(isYtd?'ytd':'quarter')&&
            r.metric==='insurance_revenue'&&valid(r)&&
            /IFRS\s*17/i.test(r.source_definition||''));
          if(local){
            subsidiary='<div class="table-prior">Storebrand Forsikring AS – IFRS 17-forsikringsinntekter: '+
              fmt(local.value)+' '+escape(local.unit||'MNOK')+
              ' · <a href="'+escape(local.source_url)+'" target="_blank" rel="noopener noreferrer">Kilde ↗</a></div>';
          }
        }
        td.innerHTML='<strong>'+title+'</strong>'+basis+prior+delta;
      }else td.innerHTML='<span class="muted">Ikke publisert</span>';
      tr.insertBefore(td,tr.cells[2]||null);
      // Explicit, source-derived last-year growth: 2025 vs 2024 for Q3 2026.
      // The original comparison cell obscured whether its second percentage
      // was last year's growth or last year's revenue. Do not use old static
      // half-year figures, and never substitute current-year growth.
      const growthCell=tr.cells[1];
      if(growthCell){
        const currentReported=Boolean(d.revenue);
        const currentGrowth=currentReported?d.growth:null;
        const previousGrowth=currentReported?d.growthPrev:null;
        // Match other comparison columns: main value, prior value in
        // parentheses, and a direction arrow indicating acceleration.
        // If Q3 2026 is unreleased for an issuer, retain its verified 2025
        // comparison without pretending the current year was reported.
        const parseGrowth=value=>{
          const match=String(value||'').replace(',','.').match(/-?\\d+(?:\\.\\d+)?/);
          return match?Number(match[0]):null;
        };
        const now=parseGrowth(currentGrowth),before=parseGrowth(previousGrowth);
        const direction=now!==null&&before!==null
          ?'<span class="qoq '+(now>before?'good':now<before?'bad':'flat')+
            '" aria-label="Endring i vekst mot foregående år">'+
            (now>before?'▲':now<before?'▼':'→')+'</span>':'';
        growthCell.innerHTML=(currentGrowth
          ?'<strong>'+escape(currentGrowth)+'</strong>'
          :'<span class="muted">—</span>')+
          (previousGrowth
            ?'<div class="table-prior">('+escape(previousGrowth)+')</div>'
            :'<div class="table-prior">(—)</div>')+direction;
      }
    }
    // Preserve the verifiable local IFRS 17 disclosure, outside the group
    // income cell, where it cannot be mistaken for group APM revenue.
    const localStorebrand=(verified?.observations||[]).find(r=>
      r.company==='Storebrand'&&r.scope==='norway'&&
      r.source_entity==='Storebrand Forsikring AS'&&
      r.year===year&&r.quarter===q&&r.period_type===(isYtd?'ytd':'quarter')&&
      r.metric==='insurance_revenue'&&valid(r)&&
      /IFRS\s*17/i.test(r.source_definition||''));
    const bucket=(isYtd?MON_YTD_Q3:MON_Q3);
    const notes=[];
    for(const company of ['Storebrand','Frende']){
      if(bucket[company]?.revenue&&bucket[company]?.revenueBasis)
        notes.push(company+' – '+bucket[company].revenueBasis);
    }
    if(localStorebrand&&bucket.Storebrand?.revenue){
      notes.push('Storebrand Forsikring AS – IFRS 17-forsikringsinntekter: '+fmt(localStorebrand.value)+' '+(localStorebrand.unit||'MNOK'));
    }
    if(notes.length){
      const notesRow=document.createElement('div');
      notesRow.className='revenue-basis-notes';
      notesRow.style.cssText='display:flex;flex-wrap:wrap;gap:12px;margin-top:12px';
      for(const value of notes){
        const note=document.createElement('p');
        note.className='notice';
        note.style.cssText='flex:1 1 290px;margin:0';
        note.textContent=value;
        notesRow.appendChild(note);
      }
      fragment.appendChild(notesRow);
    }
    return fragment.innerHTML;
  }
  const oldTable=table;
  table=()=>normalizeRevenueTable(oldTable());
  async function refresh(){
    try{
      const [response, calendarResponse]=await Promise.all([
        fetch('data/verified_financial_feed.json?t='+Date.now(),{cache:'no-store'}),
        fetch('data/calendar.json?t='+Date.now(),{cache:'no-store'}).catch(()=>null)
      ]);
      if(calendarResponse?.ok)calendarData=await calendarResponse.json();
      if(!response.ok)throw Error('Verifisert finansfeed: HTTP '+response.status);
      const incoming=await response.json();
      if(!Array.isArray(incoming.observations))throw Error('Finansfeed mangler observasjoner');
      verified=incoming;
      periodList=calcPeriods();
      if(!periodList.length)throw Error('Ingen verifiserte kvartalstall');
      const latest=periodList[0];
      if(!manuallySelected||!selection||
          !periodList.some(p=>p.year===selection.year&&p.quarter===selection.quarter))
        selection=latest;
      choose(selection.year+'-'+selection.quarter,false);
      // The calendar combines this verified quarter with future issuer dates.
      // Async script timing must not leave an obsolete interim calendar rendered.
      window.FBReportCalendar?.reconcile?.();
    }catch(e){console.error('[Forsikringsbarometeret] Kunne ikke oppdatere kvartalsvisning',e);}
  }
  window.FBQuarterly={refresh,get period(){return selection&&{...selection};},
    get available(){return periodList.map(p=>({...p}));},get verified(){return verified;},
    get selectedData(){return {quarter:MON_Q3,ytd:MON_YTD_Q3};},
    get quarterlyGraph(){return profitabilityQuarters.slice();}};
  refresh();
  setInterval(refresh,300000);
})();