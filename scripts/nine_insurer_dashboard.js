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
    ['return_on_equity','ROE / ROOF','percent'],
    ['solvency_ratio','Solvensgrad','percent'],
    ['profit_before_tax','Resultat før skatt','amount'],
  ];
  let lastData=null;
  let completeness=null;
  let fetching=false;
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
    const home=document.getElementById('nav-home')?.classList.contains('active');
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
    desc.textContent='Kildeverifiserte isolerte kvartaler. Inntektsvekst er mot samme kvartal året før. KLP gjelder Skadeforsikring AS, ikke KLP-konsernet. Alm. Brand er DKK-konsern. Manglende ROE, solvens eller andre tall vises som «Ikke rapportert». Finans- og forvaltningsavkastning brukes ikke som ROE eller ROOF.';
    section.appendChild(desc);
    if (completeness && method) {
      const expected=completeness.expected_metric_count;
      const present=completeness.present_metric_count;
      const missing=completeness.missing_metric_count;
      const exempt=completeness.reporting_exception_count;
      if (Number.isInteger(expected) && Number.isInteger(present) &&
          Number.isInteger(missing) && Number.isInteger(exempt) &&
          expected===present+missing && expected+exempt===81 &&
          Array.isArray(completeness.companies) && completeness.companies.length===9) {
        const status=document.createElement('p');
        status.className='hint';
        status.id='nine-company-kpi-completeness';
        status.textContent='Automatisk dekningskontroll for siste rapporterte kvartal: '+
          present+' av '+expected+' forventede nøkkeltall finnes; '+missing+
          ' mangler og '+exempt+' er dokumenterte rapporteringsunntak. '+
          'Tilstedeværelse er ikke bevis på ubetjent kildeimport.';
        section.appendChild(status);
        const list=document.createElement('ul');
        list.setAttribute('aria-label','Manglende nøkkeltall per selskap');
        for (const issuer of completeness.companies) {
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
      for(const [key,,kind] of FIELDS){
        if(key==='return_on_equity' && (company.metrics?.[key]===null || company.metrics?.[key]===undefined)){
          td(row,'—');
        }else{
          td(row,fmt(company.metrics?.[key],kind));
        }
      }
      const status={
        verified_official_pdf_reconciled:'Offisiell PDF avstemt',
        verified_quarterly_feed:'Kildeverifisert kvartal',
        issuer_announcement_only:'Kun utsteder­melding',
        unverified_missing:'Mangler kildeverifiserte data'
      }[company.status]||'Ikke verifisert';
      td(row,status);
      body.appendChild(row);
    }
    table.appendChild(body);wrap.appendChild(table);section.appendChild(wrap);
    const note=document.createElement('p');note.className='hint';
    note.textContent='Beløp er i selskapets rapporterte valuta og enhet. Inntekter kan ikke summeres på tvers av NOK, DKK eller ulike IFRS-definisjoner. ROE og solvens kan ha ulike utstederdefinisjoner.';
    section.appendChild(note);
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
