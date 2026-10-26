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
  const basis=row=>/not ifrs insurance revenue|segment premiums|premiums f\.o\.a\./i.test(row?.source_definition||'')?'apm':'ifrs_or_other';
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
      pts.set(r.year+'-'+r.quarter,{year:r.year,quarter:r.quarter});
    }
    return [...pts.values()].sort((a,b)=>b.year-a.year||b.quarter-a.quarter);
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
              if(name==='Frende')data.revenueBasis='Sum driftsinntekter (Frende Holding AS konsern) – ikke rene forsikringsinntekter';
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
        if(name==='Frende')data.growthMetricLabel='Vekst i driftsinntekter';
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
  company=c=>relabel(previousCompany(c));
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
    heading.textContent=isYtd?'Forsikringsinntekter · HIÅ':'Forsikringsinntekter · Q'+q;
    head.insertBefore(heading,head.children[1]||null);
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
      if(d.revenue){
        const title=escape(d.revenue)+' <small>'+escape(d.revenueUnit||'')+'</small>';
        const basis=d.revenueBasis?'<div class="table-prior">'+escape(d.revenueBasis)+'</div>':'';
        const lastYear=isYtd?'HIÅ '+(year-1):'Q'+q+' '+(year-1);
        const prior=d.revenuePrev
          ?'<span class="table-prior">'+lastYear+': '+escape(d.revenuePrev)+'</span>'
          :'<span class="table-prior">'+lastYear+': ikke verifisert</span>';
        const now=number(d.revenue),then=number(d.revenuePrev);
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
        td.innerHTML='<strong>'+title+'</strong>'+basis+subsidiary+prior+delta;
      }else td.innerHTML='<span class="muted">Ikke rapportert</span>';
      tr.insertBefore(td,tr.cells[1]||null);
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