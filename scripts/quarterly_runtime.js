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
  let verified=null, periodList=[], selection=null, manuallySelected=false;
  const label=({year,quarter})=>'Q'+quarter+' '+year;
  const fmt=(value,pct=false)=>new Intl.NumberFormat('nb-NO',{
      maximumFractionDigits:pct?1:0,minimumFractionDigits:pct?1:0
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
  function addYtd(company,year,quarter,metric) {
    // Only additive money values may be summed. Percent ratios must come from the issuer.
    if(!['insurance_revenue','insurance_service_result'].includes(metric))return null;
    const parts=Array.from({length:quarter},(_,i)=>lookup(company,'quarter',year,i+1,metric));
    if(parts.some(x=>!x)||parts.some(x=>!isSameBasis(x,parts[0])))return null;
    return {...parts[quarter-1],value:parts.reduce((sum,r)=>sum+r.value,0),
      derived_ytd:true};
  }
  function quote(company,type,year,quarter,metric){
    return lookup(company,type,year,quarter,metric)||
      (type==='ytd'?addYtd(company,year,quarter,metric):null);
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
            if(k==='revenue'){
              data.revenueUnit=current.unit||'';
              if(basis(current)==='apm')data.revenueBasis='Insurance premiums f.o.a. (APM) – ikke IFRS 17-forsikringsinntekter';
              if(current.derived_ytd)data.revenueBasis=(data.revenueBasis||'')+' Beregnet HIÅ som sum av kildeverifiserte enkeltkvartaler.';
            }
            if(metric==='insurance_service_result')data.resultUnit=current.unit||'';
            if(metric==='combined_ratio'||metric==='insurance_revenue')data.source=current.source_url;
          }
          if(prior&&(!current||isSameBasis(current,prior))){
            data[k+'Prev']=fmt(prior.value,PERCENT.has(k));
          }
        }
        const income=quote(name,type,year,quarter,'insurance_revenue');
        const previous=quote(name,type,year-1,quarter,'insurance_revenue');
        if(income&&previous&&previous.value>0&&isSameBasis(income,previous)){
          data.growth=fmt((income.value/previous.value-1)*100,true);
          data.growthBasis='Beregnet fra kildeverifiserte, sammenlignbare inntekter';
        }
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
      .replaceAll('Q3 2026 · KILDEOPPDATERT',label(selection)+' · KILDEOPPDATERT')
      .replace('Forsikringsinntekter · Q3','Forsikringsinntekter · Q'+quarter);
  }
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
  company=c=>{const result=previousCompany(c);period='Q3';return relabel(result);};
  crPodium=()=>relabel(previousPodium());
  function normalizeRevenueTable(html){
    if(!selection)return html;
    return html.replace('Forsikringsinntekter · Q3','Forsikringsinntekter · Q'+selection.quarter)
      .replaceAll('Q3 2025:',label({year:selection.year-1,quarter:selection.quarter})+':')
      .replaceAll('HIÅ 2025:','HIÅ '+(selection.year-1)+':');
  }
  const oldTable=table;
  table=()=>normalizeRevenueTable(oldTable());
  async function refresh(){
    try{
      const response=await fetch('data/verified_financial_feed.json?t='+Date.now(),{cache:'no-store'});
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
    }catch(e){console.error('[Forsikringsbarometeret] Kunne ikke oppdatere kvartalsvisning',e);}
  }
  window.FBQuarterly={refresh,get period(){return selection&&{...selection};},
    get available(){return periodList.map(p=>({...p}));},get verified(){return verified;},
    get selectedData(){return {quarter:MON_Q3,ytd:MON_YTD_Q3};},
    get quarterlyGraph(){return profitabilityQuarters.slice();}};
  refresh();
  setInterval(refresh,300000);
})();