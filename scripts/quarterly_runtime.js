/* Rolling source-verified quarterly model for the ORIGINAL Forsikringsbarometeret UI.
   This file changes data bindings only, never the dashboard's card/grid markup.
   No reported financial value is hardcoded here. */
(function () {
  'use strict';
  const COMPANY_NAMES=['Fremtind','Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand'];
  const EXTENDED_NAMES=['KLP Skadeforsikring','Alm. Brand'];
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
  function extendedRecord(name,p){
    const data=typeof extendedInsurerFeed==='object'?extendedInsurerFeed[name]:null;
    if(!data||!p)return null;
    return [data,...(data.periods||[])].find(r=>r.year===p.year&&r.quarter===p.quarter&&r.status==='verified_official_pdf_reconciled'&&
      ['official_quarterly_report','official_annual_report'].includes(r.source_type)&&
      /^https:\/\//.test(r.source_url||'')&&/^[0-9a-f]{64}$/.test(r.source_sha256||'')&&
      Number.isFinite(r.metrics?.insurance_revenue)&&Number.isFinite(r.metrics?.combined_ratio))||null;
  }
  // Calendar uses the same period-specific, source-verified admission as the financial cards.
  function isReportPublished(name,p){
    if(!p)return false;
    if(EXTENDED_NAMES.includes(name))return Boolean(extendedRecord(name,p));
    const found=new Set(rows().filter(r=>r.company===name&&r.year===p.year&&
      r.quarter===p.quarter&&r.period_type==='quarter').map(r=>r.metric));
    return found.has('combined_ratio')&&found.has('insurance_revenue');
  }
  function extendedMetrics(name,p,type){
    const row=extendedRecord(name,p);if(!row)return {};
    if(type==='quarter')return row.metrics||{};
    if(row.ytd_metrics)return row.ytd_metrics;
    const published=extendedInsurerFeed[name]?.ytd_pdf_evidence;
    if(published?.year===p.year&&published?.quarter===p.quarter&&published.source_sha256===row.source_sha256)return published.metrics||{};
    if(p.quarter===1)return row.metrics||{};
    // Cumulative KLP ratios are already verified in its quarter records.
    return row.reported_ytd_ratios||{};
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
    for(const name of EXTENDED_NAMES){
      const data=typeof extendedInsurerFeed==='object'?extendedInsurerFeed[name]:null;
      for(const item of [data,...(data?.periods||[])].filter(Boolean)){
        const p={year:item.year,quarter:item.quarter};
        if(!extendedRecord(name,p))continue;
        const key=p.year+'-'+p.quarter;
        if(!pts.has(key))pts.set(key,{...p,issuers:new Map()});
        pts.get(key).issuers.set(name,new Set(['insurance_revenue','combined_ratio']));
      }
    }
    // A solitary comparator, ratio or partial import must not switch the
    // entire homepage to a nearly empty future quarter. One issuer must
    // have BOTH verified revenue and a combined ratio for that quarter.
    return [...pts.values()]
      .filter(p=>[...p.issuers.values()].some(metrics=>
        metrics.has('insurance_revenue')&&metrics.has('combined_ratio')))
      .map(({year,quarter})=>({year,quarter}))
      .filter(p=>p.year>2026||(p.year===2026&&p.quarter>=1))
      .sort((a,b)=>b.year-a.year||b.quarter-a.quarter);
  }
  function lookup(company,type,year,quarter,metric){
    const match=r=>r.company===company&&r.year===year&&r.quarter===quarter&&r.period_type===type&&r.metric===metric;
    return rows().find(match)||window.FBMarketOverview?.companyExtraObservations().find(match);
  }
  function addQuarter(company,year,quarter,metric){
    // A standalone quarter may be reconstructed from two consecutive issuer
    // YTD columns. Only additive amounts, identical units and entity scopes.
    // Q4 must be explicitly reported as an isolated quarter in an official
    // Q4, full-year or annual report; never derive Q4 by subtracting YTD.
    if(quarter===4)return null;
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
    if(metric==='solvency_ratio') {
      const q=lookup(company,'quarter',year,quarter,metric);
      const y=lookup(company,'ytd',year,quarter,metric);
      if(q&&y&&q.value!==y.value)return null;
      return q||y;
    }
    return lookup(company,type,year,quarter,metric)||
      (type==='ytd'?addYtd(company,year,quarter,metric):
       addQuarter(company,year,quarter,metric));
  }
  function quarterTimeline({year,quarter},count=5){
    const result=[];
    for(let i=count-1;i>=0;i--){
      const code=year*4+(quarter-1)-i;
      const y=Math.floor(code/4),q=(code%4)+1;
      result.push('Q'+q+' '+y);
    }
    return result;
  }
  // Profitability is issuer-specific. Every issuer always has five fixed
  // chronological slots ending at the selected reporting quarter. Missing
  // quarters stay open, never filled from older static data or other issuers.
  function issuerProfitabilityTimeline(name){
    if(!selection)return [];
    return quarterTimeline(selection,5);
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
        else {
          const sample=periodRows[0];
          const cumulative=sample&&lookup(name,'ytd',sample.year,sample.quarter,'return_on_equity');
          if(cumulative&&Number.isFinite(cumulative.value))profitabilityReturns[name][l]={label:'Rapportert annualisert avkastning HIÅ',value:cumulative.value};
        }
      }
    }
    profitabilityQuarters.splice(0,profitabilityQuarters.length,...issuerProfitabilityTimeline(profitabilityCompany));
    // The chart reads the selected issuer's last five timeline positions.
    // Restore the older Q4/Q1/Q2 values only when they exist in the verified feed;
    // the latest reporting quarter remains an empty slot until issuer publication.
    window.FBActivePeriod={...selection,label:label(selection),priorLabel:'Q'+quarter+' '+(year-1)};
    // Rebind the existing company segment table to audited feed observations.
    // Keep the original HTML/CSS and segment labels; never reuse static Q2 values.
    const segmentSpecs={
      Fremtind:[['Privatmarkedet','reported_segment','Private'],['Bedriftsmarkedet','reported_segment','Commercial']],
      Tryg:[['Norge total','norway',null]],
      Protector:[['Norge total','norway',null]],
      Storebrand:[['Norge total','norway',null]],
      Gjensidige:[['Norge total','norway',null],['Norge PM','reported_segment','Private Norway'],['Norge BM','reported_segment','Commercial Norway']],
      Sampo:[['Private Nordic','reported_segment','Private Nordic'],['Nordic Commercial','reported_segment','Nordic Commercial']]
    };
    const metrics={combined_ratio:'cr',loss_ratio:'loss',expense_ratio:'cost',
      insurance_service_result:'underwriting'};
    const evidence=(company,scope,segment,yr,metric)=>
      (verified?.observations||[]).find(r=>valid(r)&&r.company===company&&
        r.scope===scope&&(scope!=='reported_segment'||r.segment===segment)&&
        r.year===yr&&r.quarter===quarter&&r.period_type===(ytdMode()?'ytd':'quarter')&&r.metric===metric);
    function segmentView(company,title,scope,segment){
      // Only observations from the selected quarter are eligible.
      // Missing Norway figures must never be replaced by an older quarter.
      const row={name:title};
      const currentRevenue=evidence(company,scope,segment,year,'insurance_revenue');
      const priorRevenue=evidence(company,scope,segment,year-1,'insurance_revenue');
      const currentRows=Object.entries(metrics).map(([metric,key])=>
        [key,evidence(company,scope,segment,year,metric),metric]);
      const published=Boolean(currentRevenue||currentRows.some(([,now])=>now));
      if(!published){
        for(const key of Object.values(metrics))row[key]='Ikke publisert';
        row.growth='Ikke publisert';
        row.note='Ikke publisert · '+label(selection)+' · ingen kildeverifiserte Norge-tall';
        return row;
      }
      for(const [key,now,metric] of currentRows){
        const prev=evidence(company,scope,segment,year-1,metric);
        row[key]=now?fmt(now.value,key!=='underwriting')+
          (key==='underwriting'?' '+(now.unit||''):''):'Ikke publisert';
        if(prev)row[key+'Prev']=fmt(prev.value,key!=='underwriting')+
          (key==='underwriting'?' '+(prev.unit||''):'');
      }
      if(currentRevenue&&priorRevenue&&priorRevenue.value>0&&
         isSameBasis(currentRevenue,priorRevenue))
        row.growth=fmt((currentRevenue.value/priorRevenue.value-1)*100,true);
      else row.growth='Ikke publisert';
      const older=evidence(company,scope,segment,year-2,'insurance_revenue');
      if(priorRevenue&&older&&older.value>0&&isSameBasis(priorRevenue,older))
        row.growthPrev=fmt((priorRevenue.value/older.value-1)*100,true);
      const source=evidence(company,scope,segment,year,'combined_ratio')||currentRevenue||
        currentRows.find(([,now])=>now)?.[1];
      row.note='Kildeverifisert '+label(selection)+' · '+source.source_url;
      return row;
    }
    for(const [company,specs] of Object.entries(segmentSpecs)){
      segmentData[company]=specs.map(([title,scope,segment])=>
        segmentView(company,title,scope,segment));
    }
    // Clear old Q2-only company segment figures rather than masquerade them as current.
    for(const [name,oldRows] of Object.entries(MON_Q2_SEGMENTS)){
      if(!segmentData[name]||segmentSpecs[name])continue;
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
  function trendArrow(now,prior,lowerIsBetter=false){
    const trend=window.FBMarketOverview?.financialTrend(now,prior,lowerIsBetter);
    if(!trend)return '';
    return '<span class="qoq '+trend.tone+'" data-yoy-direction="'+trend.direction+'" aria-label="'+
      (trend.direction==='up'?'Opp':trend.direction==='down'?'Ned':'Uendret')+
      ' mot tilsvarende periode i fjor" title="Sammenlignet med tilsvarende periode i fjor">'+trend.icon+'</span>';
  }
  function growthMatrixHtml(c){
    if(!selection)return '';
    const esc=s=>String(s??'').replace(/[&<>"']/g,k=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[k]));
    const q=MON_Q3[c]||{},h=MON_YTD_Q3[c]||{};
    // Compute the previous-year growth from the official 2025 and 2024
    // revenues when the presentation adapter omits the comparison field.
    const priorGrowth=type=>{
      const metric='insurance_revenue_growth',y=selection.year-1,quarter=selection.quarter;
      const stated=quote(c,type,y,quarter,metric);
      if(stated&&Number.isFinite(stated.value))return fmt(stated.value,true);
      const a=quote(c,type,y,quarter,'insurance_revenue');
      const b=quote(c,type,y-1,quarter,'insurance_revenue');
      return a&&b&&b.value>0&&isSameBasis(a,b)?fmt(100*(a.value/b.value-1),true):null;
    };
    if(!q.growthPrev)q.growthPrev=priorGrowth('quarter');
    if(!h.growthPrev)h.growthPrev=priorGrowth('ytd');
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
  const companyEsc=s=>String(s??'').replace(/[&<>"']/g,k=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[k]));
  function companyBasisSelector(){
    return '<label class="company-period-actions">Periode <select aria-label="Rapporteringsperiode" onchange="FBQuarterly.selectBasis(this.value)"><option value="Q3"'+(!ytdMode()?' selected':'')+'>Kvartal</option><option value="H3"'+(ytdMode()?' selected':'')+'>HIÅ</option></select></label>';
  }
  const displayUnit=u=>({NOKm:'MNOK',DKKm:'MDKK',EURm:'MEUR',SEKm:'MSEK'})[u]||u||'';
  function comparisonMarkup(now,prior,percent=true,unit='',lower=false,table=false){
    const a=window.FBMarketOverview?.financialNumber(now)??null,b=window.FBMarketOverview?.financialNumber(prior)??null;
    const print=v=>v===null?'—':fmt(v,percent)+(!percent&&unit?' '+displayUnit(unit):'');
    const arrow=trendArrow(a,b,lower),primary=companyEsc(print(a)),previous=companyEsc(print(b));
    return table?'<strong class="financial-current">'+primary+arrow+'</strong><div class="table-prior">('+previous+')</div>':
      '<div class="value"><span class="financial-current">'+primary+'</span>'+arrow+'</div><div class="prior">('+previous+')</div>';
  }
  function companyFinancialCard(metric,caption,now,prior,percent=true,unit='',type='quarter',source='verified-quarterly-feed',lower=false){
    return '<div class="metric fremtind company-financial-card" data-financial-metric="'+metric+'" data-financial-period="'+type+'" data-financial-source="'+source+'"><div class="name">'+companyEsc(caption)+'</div>'+
      comparisonMarkup(now,prior,percent,unit,lower)+'</div>';
  }
  function companyStandardCards(c,d){
    const p=selection,type=ytdMode()?'ytd':'quarter',src='verified-quarterly-feed';
    const currentRevenue=quote(c,type,p.year,p.quarter,'insurance_revenue');
    const prevRevenue=quote(c,type,p.year-1,p.quarter,'insurance_revenue');
    const olderRevenue=quote(c,type,p.year-2,p.quarter,'insurance_revenue');
    const rate=(a,b)=>a&&b&&b.value>0&&isSameBasis(a,b)?100*(a.value/b.value-1):null;
    const data={...d};
    if(!data.growth)data.growth=rate(currentRevenue,prevRevenue);
    if(!data.growthPrev)data.growthPrev=rate(prevRevenue,olderRevenue);
    for(const [metric,k] of Object.entries(KEYS)){
      const now=quote(c,type,p.year,p.quarter,metric),old=quote(c,type,p.year-1,p.quarter,metric);
      if(data[k]==null&&now)data[k]=now.value;
      if(data[k+'Prev']==null&&old&&(!now||isSameBasis(now,old)))data[k+'Prev']=old.value;
    }
    const get=k=>currentRevenue?data[k]:null;
    const cards=[
      companyFinancialCard('insurance_revenue_growth',c==='Frende'?'Inntektsvekst (IFRS 4)':'Inntektsvekst',get('growth'),get('growthPrev'),true,'',type,src),
      companyFinancialCard('insurance_service_result',c==='Storebrand'?'Forsikringsresultat · Cash equivalent earnings':c==='Frende'?'Forsikringsdriftsresultat':'Forsikringsresultat',get('result'),get('resultPrev'),false,d.resultUnit,type,src)
    ];
    for(const [key,metric,caption] of [['cr','combined_ratio','Combined ratio'],['loss','loss_ratio','Skadeprosent'],['cost','expense_ratio','Kostnadsprosent']]){
      cards.push(companyFinancialCard(metric,caption,get(key),get(key+'Prev'),true,'',type,src,true));
    }
    let returnType=c==='Gjensidige'?'ytd':type,roe=quote(c,returnType,p.year,p.quarter,'return_on_equity');
    if(!roe&&type==='quarter'){returnType='ytd';roe=quote(c,'ytd',p.year,p.quarter,'return_on_equity');}
    if(roe){
      const old=quote(c,returnType,p.year-1,p.quarter,'return_on_equity');
      const caption=c==='Fremtind'?'Justert EK-avkastning':c==='Tryg'?'ROOF (annualisert)':c==='Sampo'?'RoEOF (annualisert)':c==='Storebrand'?'Cash ROE (annualisert)':'ROE (annualisert)';
      cards.push(companyFinancialCard('return_on_equity',caption+(returnType==='ytd'?' · HIÅ':''),roe.value,old&&isSameBasis(roe,old)?old.value:null,true,'',returnType,src));
    }
    const sol=quote(c,type,p.year,p.quarter,'solvency_ratio'),old=quote(c,type,p.year-1,p.quarter,'solvency_ratio');
    if(sol||old||c!=='Frende')cards.push(companyFinancialCard('solvency_ratio','Solvensgrad',sol?.value,sol&&old&&isSameBasis(sol,old)?old.value:null,true,'',type,src));
    if(typeof marketShares!=='undefined'&&marketShares[c]){
      const root=document.createElement('div');root.innerHTML=marketCard(c);
      const card=root.firstElementChild;
      if(card){
        const old=marketPrevious[c]?.total;
        card.querySelector('.value').innerHTML='<span class="financial-current">'+companyEsc(marketShares[c])+'</span>'+trendArrow(marketShares[c],old);
        card.querySelector('.prior').textContent='('+(old||'—')+')';
        card.querySelector('.delta')?.remove();card.classList.add('company-financial-card');card.dataset.financialMetric='market_share';cards.push(card.outerHTML);
      }
    }
    return cards.join('');
  }
  function extendedCompany(c){
    const p=selection,type=ytdMode()?'ytd':'quarter',row=extendedRecord(c,p);
    const at=period=>period?{...(window.FBMarketOverview?.companyHistoricalMetrics(c,period,type)||{}),...extendedMetrics(c,period,type)}:{};
    const m=at(p),prior=at(p&&{year:p.year-1,quarter:p.quarter}),older=at(p&&{year:p.year-2,quarter:p.quarter});
    if(!Number.isFinite(m.insurance_revenue_growth)&&m.insurance_revenue>0&&prior.insurance_revenue>0)m.insurance_revenue_growth=100*(m.insurance_revenue/prior.insurance_revenue-1);
    if(!Number.isFinite(prior.insurance_revenue_growth)&&prior.insurance_revenue>0&&older.insurance_revenue>0)prior.insurance_revenue_growth=100*(prior.insurance_revenue/older.insurance_revenue-1);
    const unit=c==='Alm. Brand'?'MDKK':'MNOK';
    const fields=[['insurance_revenue_growth','Inntektsvekst',true],['insurance_service_result','Forsikringsresultat',false],
      ['combined_ratio','Combined ratio',true],['loss_ratio','Skadeprosent',true],['expense_ratio','Kostnadsprosent',true],
      ['return_on_equity','ROE (annualisert)',true],['solvency_ratio','Solvensgrad',true]];
    const cards=fields.filter(([k])=>k!=='return_on_equity'||Number.isFinite(m[k])).map(([k,caption,pct])=>
      companyFinancialCard(k,caption,m[k],prior[k],pct,unit,type,'verified-original-report',['combined_ratio','loss_ratio','expense_ratio'].includes(k))).join('');
    const opts=p&&window.FBMarketOverview?.profitabilityOptions(c,p);
    const chart=profitabilityChart(c,opts||{quarters:p?quarterTimeline(p):[],selected:{},returns:{}});
    const segs=c==='Alm. Brand'&&p?window.FBMarketOverview?.companySegmentRows(c,p,type)||[]:[];
    const segmentTable=segs.some(s=>s.row)?'<section class="panel company-segments" aria-label="Segmentoversikt for Alm. Brand"><div class="section-head"><h2>Segmentoversikt · Danmark</h2></div><div class="tablewrap"><table><thead><tr><th>Virksomhet</th><th>Inntektsvekst</th><th>Forsikringsteknisk resultat</th><th>Combined ratio</th><th>Skadeprosent</th><th>Kostnadsprosent</th></tr></thead><tbody>'+segs.filter(s=>s.row).map(({market,row:r,prior,result,priorResult,resultUnit})=>'<tr><td>'+(market==='pm'?'Privatmarkedet':'Bedriftsmarkedet')+(r.source?'<small class="frende-skade-source"><a href="'+companyEsc(r.source)+'" target="_blank" rel="noopener noreferrer">Offisiell rapport ↗</a></small>':'')+'</td><td>'+comparisonMarkup(r.growth,prior?.growth,true,'',false,true)+'</td><td>'+comparisonMarkup(result,priorResult,false,resultUnit,false,true)+'</td>'+['cr','loss','cost'].map(k=>'<td>'+comparisonMarkup(r[k],prior?.[k],true,'',true,true)+'</td>').join('')+'</tr>').join('')+'</tbody></table></div></section>':'';
    return MON_SELECT()+'<button class="back" onclick="show(\'home\')">← Tilbake til oversikten</button>'+shell(c,'Offisielle kvartalsrapporter og kildeverifiserte resultater','SELSKAPSANALYSE / '+c.toUpperCase()).replace(/Q2 2026 · Kildekontrollerte utdrag/,companyEsc(p?label(p):'Avventer kvartal')+' · Kildekontrollerte utdrag')+
      '<div class="section-head"><div><h2 style="margin:0;font-size:16px">'+companyEsc(c)+' | Resultatoversikt</h2></div>'+companyBasisSelector()+'</div>'+quarterComment(c)+
      '<div class="kpi-seven dynamic-kpis">'+cards+'</div><section class="panel company-profitability" aria-label="Lønnsomhetsutvikling for '+companyEsc(c)+'">'+chart+'</section>'+segmentTable+
      (row?'<p class="notice">Kildeverifiserte tall: <a href="'+companyEsc(row.source_url)+'" target="_blank" rel="noopener noreferrer">Åpne offisiell kvartalsrapport ↗</a></p>':'<p class="notice">Kildeverifiserte rapporttall for denne perioden er ennå ikke tilgjengelige.</p>')+
      '<section class="panel broker-summary-panel" id="broker-commentary-panel" hidden></section>'+stockMarketSection(c)+companyMediaNews(c);
  }
  function companyWithVerifiedKpis(c){
    if(EXTENDED_NAMES.includes(c))return extendedCompany(c);
    const fragment=document.createElement('div');
    fragment.innerHTML=relabel(previousCompany(c));
    if(selection){
      const heading=fragment.querySelector('.section-head');
      if(heading){
        const controls=document.createElement('div');
        controls.innerHTML=companyBasisSelector();
        heading.appendChild(controls);
      }
    }
    const d={...((ytdMode()?MON_YTD_Q3:MON_Q3)[c]||{})};
    if(!d.growthPrev&&selection){
      const type=ytdMode()?'ytd':'quarter',y=selection.year-1,q=selection.quarter;
      const prior=quote(c,type,y,q,'insurance_revenue');
      const older=quote(c,type,y-1,q,'insurance_revenue');
      const reported=quote(c,type,y,q,'insurance_revenue_growth');
      if(reported&&Number.isFinite(reported.value))d.growthPrev=fmt(reported.value,true);
      else if(prior&&older&&older.value>0&&isSameBasis(prior,older))
        d.growthPrev=fmt(100*(prior.value/older.value-1),true);
    }
    const kpiPanel=fragment.querySelector('.dynamic-kpis');
    if(kpiPanel&&selection)kpiPanel.innerHTML=companyStandardCards(c,d);
    // Replace the legacy Q2 label with the actual selected quarter.
    const heading=fragment.querySelector('.section-head h2');
    if(heading)heading.textContent=heading.textContent.replace(/Q2 2026/,label(selection));
    const cards=fragment.querySelector('.dynamic-kpis');
    if(cards){
      const panel=document.createElement('section');
      panel.className='panel company-profitability';
      panel.setAttribute('aria-label','Lønnsomhetsutvikling for '+c);
      panel.innerHTML=profitabilityChart(c);
      cards.insertAdjacentElement('afterend',panel);
    }
    if(c==='Sampo'&&selection){
      const rows=window.FBMarketOverview?.sampoNordicSegments(verified,selection,ytdMode()?'ytd':'quarter')||[];
      const table=fragment.querySelector('.tablewrap table');
      if(table&&rows.length===2){
        for(const [i,r] of rows.entries()){
          const tr=table.tBodies[0]?.rows[i];if(!tr)continue;
          tr.dataset.segment=r.segment;
          tr.dataset.financialPeriod=ytdMode()?'ytd':'quarter';
          tr.dataset.financialSource=r.method||'missing';
          const vals=[[r.growth,r.growthPrev,true],...['insurance_service_result','combined_ratio','loss_ratio','expense_ratio'].map(k=>[r.metrics?.[k],r.prior?.[k],k!=='insurance_service_result'])];
          vals.forEach(([now,prev,percent],j)=>{
            const cell=tr.cells[j+1];if(!cell)return;
            cell.innerHTML=comparisonMarkup(now,prev,percent,'MEUR',j>=2,true);
          });
          const sources=[...new Map(r.sources.map(x=>[x.source_url,x])).values()];
          if(sources.length){
            const small=document.createElement('small');small.className='frende-skade-source';
            sources.forEach((s,j)=>{
              const a=document.createElement('a');a.href=s.source_url;a.target='_blank';a.rel='noopener noreferrer';a.textContent=sources.length>1?'Q'+s.quarter+' '+s.year:'Offisiell rapport ↗';
              if(j)small.append(' · ');small.append(a);
            });
            tr.cells[0].append(' ',small);
          }
        }
        const panel=table.closest('.panel');
        if(panel&&rows.some(r=>r.method==='calculated_ytd')){
          const hint=document.createElement('p');hint.className='hint';
          hint.textContent='HIÅ er beregnet fra alle kildeverifiserte isolerte kvartaler. Forsikringsresultat summeres; CR og delprosenter inntektsvektes. Avrunding kan gi avvik fra rapporterte HIÅ-prosenter.';
          panel.append(hint);
        }
      }
    }
    if(c==='Fremtind'&&selection){
      const segs=window.FBMarketOverview?.companySegmentRows(c,selection,ytdMode()?'ytd':'quarter')||[];
      for(const [i,{row,prior,result,priorResult,resultUnit}] of segs.entries()){
        if(!row)continue;
        const tr=fragment.querySelectorAll('.tablewrap tbody tr')[i];
        if(!tr)continue;
        const write=(index,value,previous,percent=true,unit='',lower=false)=>{
          const cell=tr.cells[index];if(cell)cell.innerHTML=comparisonMarkup(value,previous,percent,unit,lower,true);
        };
        write(1,row.growth,prior?.growth);write(2,result,priorResult,false,resultUnit);
        write(3,row.cr,prior?.cr,true,'',true);write(4,row.loss,prior?.loss,true,'',true);write(5,row.cost,prior?.cost,true,'',true);
        const link=document.createElement('a');link.href=row.source;link.target='_blank';link.rel='noopener noreferrer';link.className='frende-skade-source';link.textContent='Offisiell rapport ↗';tr.cells[0].append(' ',link);
        tr.setAttribute('data-financial-source','verified-fremtind-apm');
      }
    }
    if(c==='Frende'){
      // Frende Skadeforsikring belongs IN the existing Norge segment row.
      // Never duplicate the source numbers in a separate standalone table.
      const segmentRow=[...fragment.querySelectorAll('.tablewrap tbody tr')].find(tr=>
        /Frende Skadeforsikring AS/.test(tr.cells[0]?.textContent||''));
      if(segmentRow&&selection){
        const periodType=ytdMode()?'ytd':'quarter';
        const all=Array.isArray(frendeSkadeFinancials?.observations)
          ?frendeSkadeFinancials.observations:[];
        const verifiedSubsidiary=(r,year,metric)=>r&&r.year===year&&
          r.quarter===selection.quarter&&r.period_type===periodType&&
          r.metric===metric&&r.scope==='subsidiary'&&
          r.source_entity==='Frende Skadeforsikring AS'&&r.status==='reported'&&
          Number.isFinite(r.value)&&r.source_type==='official_quarterly_report'&&
          /^https:\/\//.test(r.source_url||'')&&
          /\.pdf(?:\?|$)/i.test(r.source_url||'')&&
          /^[a-f0-9]{64}$/i.test(r.source_sha256||'')&&r.source_page>=1;
        const metricRow=(year,metric)=>all.find(r=>verifiedSubsidiary(r,year,metric));
        const metrics=Object.fromEntries(
          ['insurance_revenue','insurance_service_result','combined_ratio','loss_ratio','expense_ratio']
            .map(metric=>[metric,metricRow(selection.year,metric)]));
        const priorYear=selection.year-1;
        const formatValue=r=>r?fmt(r.value,r.unit==='percent')+
          (r.unit==='NOKm'?' MNOK':''):'—';
        const metricNames=['growth','insurance_service_result','combined_ratio',
          'loss_ratio','expense_ratio'];
        // Render same-quarter, same-entity prior-year comparisons from the
        // original PDF comparison columns. Colours reflect desirability:
        // falling claims/expense/combined ratios are green, rising is red.
        for(let i=0;i<metricNames.length;i++){
          const cell=segmentRow.cells[i+1];
          if(!cell)continue;
          const metric=metricNames[i];
          cell.replaceChildren();
          if(i===0){
            const current=metrics.insurance_revenue;
            const previous=metricRow(priorYear,'insurance_revenue');
            if(current?.unit==='NOKm'&&previous?.unit==='NOKm'&&previous.value>0){
              const growth=100*(current.value/previous.value-1);
              const strong=document.createElement('strong');
              strong.textContent=fmt(growth,true);
              cell.appendChild(strong);
              // Compare current revenue growth to the previous year's RATE.
              // Never substitute an insurance-premium amount for a percentage.
              const older=metricRow(priorYear-1,'insurance_revenue');
              const priorGrowth=older?.unit==='NOKm'&&older.value>0
                ?100*(previous.value/older.value-1):null;
              const comparison=document.createElement('div');
              comparison.className='table-prior';
              comparison.textContent=priorGrowth!==null
                ?'('+fmt(priorGrowth,true)+')'
                :'('+'—'+')';
              cell.appendChild(comparison);
              if(priorGrowth!==null){
                const wrapper=document.createElement('span');
                wrapper.innerHTML=trendArrow(growth,priorGrowth);
                const marker=wrapper.firstElementChild;
                if(marker){
                  marker.title='Endring i premieinntektsvekst mot fjorårets vekst';
                  marker.setAttribute('aria-label',
                    growth>priorGrowth?'Inntektsveksten har økt fra fjoråret':
                    growth<priorGrowth?'Inntektsveksten har avtatt fra fjoråret':
                    'Inntektsveksten er uendret');
                  cell.appendChild(marker);
                }
              }
            }else cell.textContent='—';
          }else{
            const current=metrics[metric];
            const previous=metricRow(priorYear,metric);
            const expectedUnit=i===1?'NOKm':'percent';
            if(current?.unit!==expectedUnit){cell.textContent='—';continue;}
            const strong=document.createElement('strong');
            strong.textContent=formatValue(current);
            cell.appendChild(strong);
            const comparison=document.createElement('div');
            comparison.className='table-prior';
            comparison.textContent=previous?.unit===expectedUnit
              ?'('+formatValue(previous)+')':'(—)';
            cell.appendChild(comparison);
            if(previous?.unit===expectedUnit){
              const wrapper=document.createElement('span');
              wrapper.innerHTML=trendArrow(current.value,previous.value,i>=2);
              if(wrapper.firstElementChild)cell.appendChild(wrapper.firstElementChild);
            }
          }
          cell.setAttribute('data-frende-skade-metric',metric);
        }
        segmentRow.classList.add('frende-skade-verified-row');
        segmentRow.setAttribute('data-frende-skade-period',
          'Q'+selection.quarter+' '+selection.year+(ytdMode()?' HIÅ':''));
        const source=metrics.insurance_service_result||metrics.combined_ratio;
        if(source){
          const caption=document.createElement('small');
          caption.className='frende-skade-source';
          const link=document.createElement('a');
          link.href=source.source_url;
          link.target='_blank';link.rel='noopener noreferrer';
          link.textContent='Offisiell PDF · Q'+selection.quarter+' '+selection.year+' ↗';
          link.setAttribute('aria-label','Frende Skadeforsikring AS offisiell PDF');
          caption.appendChild(document.createTextNode(' '));
          caption.appendChild(link);
          segmentRow.cells[0].appendChild(caption);
          segmentRow.setAttribute('data-financial-source','verified-frende-skade-pdf');
        }
      }
    }
    if(c==='Protector'&&selection){
      // Populate the existing Norge total row using NORWAY-scoped official
      // financial observations. Never reuse the Protector group KPI values.
      const segment=[...fragment.querySelectorAll('.tablewrap tbody tr')].find(tr=>
        (tr.cells[0]?.textContent||'').trim().includes('Norge total'));
      if(segment){
        const evidence=(verified?.observations||[]).filter(r=>r.company==='Protector'&&
          r.scope==='norway'&&r.source_scope==='norway'&&r.period_type===(ytdMode()?'ytd':'quarter')&&
          r.quarter===selection.quarter&&r.status==='reported'&&
          Number.isFinite(r.value)&&r.source_type==='official_quarterly_report'&&
          /^https:\/\//.test(r.source_url||'')&&/\.pdf(?:\?|$)/i.test(r.source_url||'')&&
          /^[a-f0-9]{64}$/i.test(r.source_sha256||'')&&r.source_page>=1);
        const metric=(year,name)=>evidence.find(r=>r.year===year&&r.metric===name);
        const names=['insurance_service_result','combined_ratio','loss_ratio','expense_ratio'];
        const unit=(name)=>name==='insurance_service_result'?'MNOK':'percent';
        const print=r=>fmt(r.value,r.unit==='percent')+(r.unit==='MNOK'?' MNOK':'');
        const render=(cell,current,prior,lowerIsBetter)=>{
          cell.replaceChildren();
          if(!current){cell.textContent='—';return;}
          const value=document.createElement('strong');
          value.textContent=print(current);cell.appendChild(value);
          const comparison=document.createElement('div');
          comparison.className='table-prior';
          comparison.textContent=prior?.unit===current.unit?'('+print(prior)+')':'(—)';
          cell.appendChild(comparison);
          if(prior?.unit===current.unit){
            const wrap=document.createElement('span');
            wrap.innerHTML=trendArrow(current.value,prior.value,lowerIsBetter);
            if(wrap.firstElementChild)cell.appendChild(wrap.firstElementChild);
          }
        };
        const thisYear=selection.year,previousYear=thisYear-1;
        const revenue=metric(thisYear,'insurance_revenue');
        const prevRevenue=metric(previousYear,'insurance_revenue');
        const oldRevenue=metric(previousYear-1,'insurance_revenue');
        const growthCell=segment.cells[1];
        growthCell.replaceChildren();
        if(revenue?.unit==='MNOK'&&prevRevenue?.unit==='MNOK'&&prevRevenue.value>0){
          const now=100*(revenue.value/prevRevenue.value-1);
          const previous=oldRevenue?.unit==='MNOK'&&oldRevenue.value>0
            ?100*(prevRevenue.value/oldRevenue.value-1):null;
          const value=document.createElement('strong');
          value.textContent=fmt(now,true);growthCell.appendChild(value);
          const reference=document.createElement('div');
          reference.className='table-prior';
          reference.textContent=previous===null?'(—)':'('+fmt(previous,true)+')';
          growthCell.appendChild(reference);
          if(previous!==null){
            const wrap=document.createElement('span');
            wrap.innerHTML=trendArrow(now,previous);
            if(wrap.firstElementChild)growthCell.appendChild(wrap.firstElementChild);
          }
        }else growthCell.textContent='—';
        growthCell.setAttribute('data-protector-norway-metric','growth');
        for(const [i,name] of names.entries()){
          const target=segment.cells[i+2];
          if(!target)continue;
          const current=metric(thisYear,name),prior=metric(previousYear,name);
          render(target,current?.unit===unit(name)?current:null,prior,i>0);
          target.setAttribute('data-protector-norway-metric',name);
        }
        segment.classList.add('protector-norway-verified-row');
        const source=metric(thisYear,'insurance_revenue');
        if(source){
          const small=document.createElement('small');
          small.className='frende-skade-source';
          const link=document.createElement('a');
          link.href=source.source_url;link.target='_blank';link.rel='noopener noreferrer';
          link.textContent='Offisiell PDF · Q'+selection.quarter+' '+selection.year+' ↗';
          link.setAttribute('aria-label','Protector Norge offisiell PDF');
          small.appendChild(link);segment.cells[0].appendChild(small);
          segment.setAttribute('data-financial-source','verified-protector-norway-pdf');
        }
      }
    }
    const chartPanel=fragment.querySelector('.company-profitability');
    const segmentPanel=fragment.querySelector('.tablewrap')?.closest('.panel');
    if(chartPanel&&segmentPanel&&segmentPanel!==chartPanel){
      for(const tr of segmentPanel.querySelectorAll('tbody tr')){
        for(const [i,cell] of [...tr.cells].entries()){
          if(i===0||cell.querySelector('.financial-current'))continue;
          const prior=cell.querySelector('.table-prior');
          const copy=cell.cloneNode(true);copy.querySelectorAll('.table-prior,.qoq').forEach(x=>x.remove());
          const now=copy.textContent.trim(),before=prior?.textContent?.trim().replace(/^\(|\)$/g,'')||'';
          const percent=i!==2,unit=percent?'':(now.match(/\b(?:MNOK|NOKm|MDKK|DKKm|MEUR|EURm|MSEK|SEKm)\b/i)?.[0]||'');
          cell.innerHTML=comparisonMarkup(now,before,percent,unit,i>=3,true);
        }
      }
      segmentPanel.classList.add('company-segments');
      segmentPanel.setAttribute('aria-label','Segmentoversikt for '+c);
      chartPanel.insertAdjacentElement('afterend',segmentPanel);
    }
    return fragment.innerHTML;
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
        // Only show the comparable prior-year figure in parentheses;
        // the table header already identifies the selected reporting period.
        const prior=d.resultPrev
          ?'<span class="table-prior">('+escape(d.resultPrev)+')</span>'
          :'<span class="table-prior">(—)</span>';
        const now=number(d.result),then=number(d.resultPrev);
        const delta=now!==null&&then!==null
          ?'<span class="qoq '+(now>then?'good':now<then?'bad':'flat')+
           '" aria-label="Endring mot samme periode i fjor">'+
           (now>then?'▲':now<then?'▼':'→')+'</span>':'';
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
    // Standardized arrow direction in every numeric financial comparison
    // cell. A higher combined/loss/expense ratio is red, not green.
    for(const tr of fragment.querySelectorAll('tbody tr')){
      const raw=(tr.cells[0]?.textContent||'').trim();
      const company=raw==='Frende Holding'?'Frende':raw;
      const d=(isYtd?MON_YTD_Q3:MON_Q3)[company]||{};
      for(const [column,key] of [[1,'growth'],[3,'cr'],[4,'loss'],[5,'cost']]){
        const cell=tr.cells[column];
        if(!cell)continue;
        if(!d.revenue||!d[key]){cell.innerHTML='<span class="muted">—</span>';continue;}
        const current=escape(d[key]),prior=d[key+'Prev'];
        cell.innerHTML='<strong>'+current+'</strong>'+
          (prior?'<div class="table-prior">('+escape(prior)+')</div>':'<div class="table-prior">(—)</div>')+
          trendArrow(d[key],prior,['cr','loss','cost'].includes(key));
      }
    }
    const bucket=(isYtd?MON_YTD_Q3:MON_Q3);
    const notes=[];
    for(const company of ['Storebrand','Frende']){
      if(bucket[company]?.revenue&&bucket[company]?.revenueBasis)
        notes.push(company+' – '+bucket[company].revenueBasis);
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
  let frendeSkadeReports=null;
  let frendeSkadeFinancials=null;
  async function refresh(){
    try{
      const [response, calendarResponse, skadeResponse, skadeFinResponse,extendedResponse]=await Promise.all([
        fetch('data/verified_financial_feed.json?t='+Date.now(),{cache:'no-store'}),
        fetch('data/calendar.json?t='+Date.now(),{cache:'no-store'}).catch(()=>null),
        fetch('data/frende_skade_reports.json?t='+Date.now(),{cache:'no-store'}).catch(()=>null),
        fetch('data/frende_skade_financials.json?t='+Date.now(),{cache:'no-store'}).catch(()=>null),
        fetch('data/extended_insurer_financials.json?t='+Date.now(),{cache:'no-store'}).catch(()=>null)
      ]);
      if(extendedResponse?.ok){const data=await extendedResponse.json();if(data.insurers)extendedInsurerFeed=data.insurers;}
      if(calendarResponse?.ok)calendarData=await calendarResponse.json();
      if(skadeResponse?.ok)frendeSkadeReports=await skadeResponse.json();
      if(skadeFinResponse?.ok)frendeSkadeFinancials=await skadeFinResponse.json();
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
  // Recompute the window on issuer change as well as on quarter selection.
  const originalSetProfitabilityCompany=setProfitabilityCompany;
  setProfitabilityCompany=name=>{
    if(current!=='summary'){if(COMPANY_NAMES.includes(name)||['Alm. Brand','KLP Skadeforsikring'].includes(name))show(name,true);return;}
    originalSetProfitabilityCompany(name);
    if(selection) {
      profitabilityQuarters.splice(0,profitabilityQuarters.length,...issuerProfitabilityTimeline(name));
      document.getElementById('profitability-panel').innerHTML=profitabilityChart();
    }
  };
  window.FBQuarterly={refresh,isReportPublished,selectBasis(value){if(['Q3','H3'].includes(value)){period=value;populate();show(current,true);}},get period(){return selection&&{...selection};},
    get available(){return periodList.map(p=>({...p}));},get verified(){return verified;},
    get selectedData(){return {quarter:MON_Q3,ytd:MON_YTD_Q3};},
    get quarterlyGraph(){return profitabilityQuarters.slice();}};
  refresh();
  setInterval(refresh,300000);
})();