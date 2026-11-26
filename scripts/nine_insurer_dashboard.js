/* Nine-insurer source-verified KPI table. Never substitutes Group data for KLP company scope. */
(() => {
  'use strict';
  const FIELDS=[
    ['insurance_revenue','Forsikringsinntekter','amount'],
    ['insurance_revenue_growth','Inntektsvekst','percent'],
    ['insurance_service_result','Forsikringsresultat','amount'],
    ['loss_ratio','Skadeprosent','percent'],
    ['expense_ratio','Kostnadsprosent','percent'],
    ['combined_ratio','Combined ratio','percent'],
    ['return_on_equity','ROE / ROOF / RoEOF','percent'],
    ['solvency_ratio','Solvensgrad','percent'],
    ['profit_before_tax','Resultat før skatt','amount'],
  ];
  let lastData=null;
  let completeness=null;
  let fetching=false;
  let view='quarter';
  const fmt=(value,kind)=>{
    if(typeof value!=='number'||!Number.isFinite(value))return 'Ikke rapportert';
    return new Intl.NumberFormat('nb-NO',{maximumFractionDigits:1,
      minimumFractionDigits:kind==='percent'?1:0}).format(value)+(kind==='percent'?' %':'');
  };
  const td=(row,value)=>{
    const cell=document.createElement('td');
    cell.textContent=value;
    row.appendChild(cell);
    return cell;
  };
  function draw(){
    const root=document.getElementById('app');
    if(!root||!lastData||root.querySelector('#nine-company-kpi-comparison'))return;
    const home=document.getElementById('nav-summary')?.classList.contains('active');
    const method=document.getElementById('nav-methodology')?.classList.contains('active');
    if(!home&&!method)return;
    const section=document.createElement('section');
    section.id='nine-company-kpi-comparison';
    section.className='panel';
    const title=document.createElement('h2');
    title.textContent='Ni forsikringsselskaper · finansielle nøkkeltall';
    section.appendChild(title);
    const desc=document.createElement('p');
    desc.className='hint';
    desc.textContent='Kildeverifiserte kvartals- og HIÅ-verdier. Avkastning som kun rapporteres HIÅ er særskilt merket. Inntektsvekst er mot samme periode året før. KLP gjelder Skadeforsikring AS, ikke KLP-konsernet. Alm. Brand er DKK-konsern. Manglende ROE, solvens eller andre tall vises som «Ikke rapportert». Finans- og forvaltningsavkastning brukes ikke som ROE eller ROOF.';
    section.appendChild(desc);
    const controls=document.createElement('div');
    controls.setAttribute('role','group');controls.setAttribute('aria-label','Rapportgrunnlag for ni selskaper');
    for(const [key,label] of [['quarter','Kvartal'],['ytd','HIÅ']]){
      const btn=document.createElement('button');btn.type='button';btn.textContent=label;
      btn.id='nine-kpi-view-'+key;btn.setAttribute('aria-pressed',String(view===key));btn.className='btn';
      btn.addEventListener('click',()=>{view=key;section.remove();draw();});
      controls.appendChild(btn);
    }
    section.appendChild(controls);
    if (completeness && method) {
      const selected=view==='ytd'?completeness.ytd:completeness;
      const expected=selected?.expected_metric_count;
      const present=selected?.present_metric_count;
      const missing=selected?.missing_metric_count;
      const exempt=selected?.reporting_exception_count;
      if (Number.isInteger(expected) && Number.isInteger(present) &&
          Number.isInteger(missing) && Number.isInteger(exempt) &&
          expected===present+missing && expected+exempt===81 &&
          Array.isArray(selected.companies) && selected.companies.length===9) {
        const status=document.createElement('p');
        status.className='hint';
        status.id='nine-company-kpi-completeness';
        status.textContent='Automatisk dekningskontroll for '+(view==='ytd'?'HIÅ':'siste rapporterte kvartal')+': '+
          present+' av '+expected+' forventede nøkkeltall finnes; '+missing+
          ' mangler og '+exempt+' er dokumenterte rapporteringsunntak. '+
          'Tilstedeværelse er ikke bevis på ubetjent kildeimport.';
        section.appendChild(status);
        if(completeness.all_nine_same_period===false){
          const periodWarning=document.createElement('p');
          periodWarning.className='hint';
          periodWarning.textContent='Selskapene har ulike siste rapportperioder. Samlet KPI-dekning betyr ikke at alle har rapportert samme kvartal.';
          section.appendChild(periodWarning);
        }
        const list=document.createElement('ul');
        list.setAttribute('aria-label','Manglende nøkkeltall per selskap');
        if(view==='quarter'&&Number.isInteger(completeness.isolated_quarter_metric_count)&&completeness.ytd_only_return_metrics?.length){
          const detail=document.createElement('p');detail.className='hint';
          detail.textContent=completeness.isolated_quarter_metric_count+' isolerte kvartals-/punktverdier; '+completeness.ytd_only_return_metrics.map(x=>x.company+' (avkastning HIÅ)').join(', ')+' rapporterer avkastning HIÅ.';section.appendChild(detail);
        }
        for (const issuer of selected.companies) {
          if (!Array.isArray(issuer.missing_metrics) || !issuer.missing_metrics.length) continue;
          const item=document.createElement('li');
          item.textContent=issuer.company+' ('+(issuer.period||'periode ukjent')+'): '+
            issuer.missing_metrics.map(key=>FIELDS.find(f=>f[0]===key)?.[1]||key).join(', ');
          list.appendChild(item);
        }
        if(list.children.length)section.appendChild(list);
      }
    }
    const wrap=document.createElement('div');wrap.className='tablewrap';
    const table=document.createElement('table');table.setAttribute('aria-label','Ni selskaper med ni finansielle nøkkeltall');
    const head=document.createElement('thead'),headRow=document.createElement('tr');
    ['Selskap og kilde','Rapportperiode',...FIELDS.map(x=>x[1]),'Datastatus'].forEach(label=>{
      const cell=document.createElement('th');cell.textContent=label;headRow.appendChild(cell);
    });
    head.appendChild(headRow);table.appendChild(head);
    const body=document.createElement('tbody');
    for(const company of lastData.companies||[]){
      const row=document.createElement('tr');
      const companyCell=td(row,company.company);
      if(typeof company.source_url==='string'&&/^https:\/\//.test(company.source_url)){
        companyCell.textContent='';
        const a=document.createElement('a');a.href=company.source_url;a.target='_blank';a.rel='noopener noreferrer';a.textContent=company.company;companyCell.appendChild(a);
      }
      td(row,company.period||'Ikke rapportert');
      const metrics=view==='ytd'?(company.ytd_metrics||{}):company.metrics;
      const sources=view==='ytd'?(company.ytd_metric_sources||{}):(company.metric_sources||{});
      for(const [key,,kind] of FIELDS){
        if(key==='return_on_equity' && (metrics?.[key]===null || metrics?.[key]===undefined)){
          td(row,'—');
        }else{
          const label=view==='quarter'&&company.metric_periods?.[key]==='ytd'?' (HIÅ)':view==='ytd'&&key==='solvency_ratio'&&metrics[key]!=null?' (periodens slutt)':'';
          const calculated=(view==='ytd'?sources[key]?.method==='calculated':company.metric_methods?.[key]==='calculated')?' (beregnet)':'';
          const cell=td(row,fmt(metrics?.[key],kind)+label+calculated);
          if(sources[key]?.source_definition)cell.title=sources[key].source_definition;
        }
      }
      const status={
        verified_official_pdf_reconciled:'Offisiell PDF avstemt',
        verified_quarterly_feed:'Kildeverifisert kvartal',
        issuer_announcement_only:'Kun utsteder­melding',
        unverified_missing:'Mangler kildeverifiserte data'
      }[company.status]||'Ikke verifisert';
      td(row,view==='ytd'?(Object.values(metrics).some(v=>typeof v==='number')?'Kildeverifisert HIÅ':'Mangler kildeverifisert HIÅ'):company.metric_methods?.profit_before_tax==='calculated'?'Kildeavstemt, Q4 beregnet fra helår − HIÅ Q3':status);
      body.appendChild(row);
    }
    table.appendChild(body);wrap.appendChild(table);section.appendChild(wrap);
    const note=document.createElement('p');note.className='hint';
    note.textContent='Beløp er i selskapets rapporterte valuta og enhet. Inntekter kan ikke summeres på tvers av NOK, DKK eller ulike IFRS-definisjoner. ROE og solvens kan ha ulike utstederdefinisjoner.';
    section.appendChild(note);
    if ((lastData.companies||[]).some(c=>c.metric_methods?.profit_before_tax==='calculated')) {
      const calcNote=document.createElement('p');calcNote.className='hint';
      calcNote.textContent='KLP Q4: Beløp = helår minus HIÅ per Q3; skade-, kostnads- og combined ratio beregnes fra isolerte beløp. Solvens er rapportert ved årsslutt. Årsoppgjørsjusteringer kan inngå i Q4.';
      section.appendChild(calcNote);
    }
    root.appendChild(section);
  }
  async function load(){
    if(fetching)return;
    fetching=true;
    try{
      const response=await fetch('data/nine_insurer_comparison.json',{cache:'no-store'});
      if(!response.ok)throw Error('HTTP '+response.status);
      const data=await response.json();
      if(data.count!==9||!Array.isArray(data.companies)||data.companies.length!==9)throw Error('Ni-selskapsdata mangler');
      lastData=data;
      try {
        const coverageResponse=await fetch('data/quarterly_kpi_completeness.json',{cache:'no-store'});
        if(coverageResponse.ok)completeness=await coverageResponse.json();
      } catch(error) { console.warn('Dekningskontroll utilgjengelig',error); }
      draw();
    }catch(err){console.warn('Kildekontroll for ni selskap utilgjengelig',err);}
    finally{fetching=false;}
  }
  function begin(){
    const root=document.getElementById('app');
    if(!root)return;
    new MutationObserver(draw).observe(root,{childList:true});
    load();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',begin);
  else begin();
})();
