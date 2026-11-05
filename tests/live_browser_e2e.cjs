/* Browser end-to-end checks the ORIGINAL dashboard and the future-quarter rollover.
   Synthetic report observations are injected ONLY into this browser, never committed. */
const {chromium}=require('playwright');
const fs=require('node:fs');
const BASE=process.env.BAROMETER_URL||'https://lindkb-sketch.github.io/forsikringsbarometeret/';
const OUTPUT='data/browser_e2e_report.json';
const nf=x=>new Intl.NumberFormat('nb-NO',{maximumFractionDigits:2}).format(x).replace(/\u00a0/g,' ');
const norm=x=>String(x??'').replace(/\u00a0/g,' ').replace(/\u202f/g,' ').trim();
const displayed=x=>norm(x).replace(/([+-]?\d+(?:[.,]\d+)?)\s*%/g,(_,raw)=>{
 const v=Number(raw.replace(',','.'));
 return Number.isFinite(v)?v.toFixed(1).replace('.',',')+' %':raw+' %';
});
async function main(){
 const report={url:BASE,checked_at:new Date().toISOString(),checks:[],errors:[],screenshots:[]};
 const browser=await chromium.launch({channel:'chrome',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const pageErrors=[];
 const check=(name,ok,detail='')=>{report.checks.push({name,pass:!!ok,detail:String(detail).slice(0,650)});if(!ok)report.errors.push(name+': '+String(detail).slice(0,650));};
 page.on('pageerror',e=>pageErrors.push(String(e)));
 try {
  const first=await page.goto(BASE,{waitUntil:'domcontentloaded',timeout:45000});
  check('Homepage HTTP 200',first?.status()===200,'HTTP '+first?.status());
  const files=await Promise.all(['verified_financial_feed.json','quarterly_editorial.json',
       'official_news.json','stock_prices.json','live.json','investor_readiness.json'].map(async f=>{
   const r=await page.request.get(BASE+'data/'+f+'?browser_audit='+Date.now());
   if(r.status()!==200)throw Error(f+' HTTP '+r.status());
   return r.json();
  }));
  const [feed,editorial,news,stocks,calendarFeed,readiness]=files;
  await page.waitForFunction(()=>window.FBQuarterly?.period&&
       document.querySelector('#results-comparison tbody tr')&&
       window.FBNews?.editorial && window.FBReportCalendar?.ready &&
       document.querySelector('.mon-calendar'),null,{timeout:35000});
  // Publication diagnostics remain machine-readable; they are never a reader-facing
  // investor approval label. The reader sees source-backed figures and dated blanks.
  check('Internal data audit exists independently of dashboard labels',
    readiness.schema_version===1 && readiness.companies.length===7 &&
    typeof readiness.investor_ready==='boolean');
  check('Data audit quarter matches selected source quarter',
    /^Q[1-4] \d{4}$/.test(readiness.reference_quarter),
    readiness.reference_quarter);
  const visibleStatus=await page.locator('#app, aside').allInnerTexts();
  check('No investor approval or disapproval labels on public site',
    !visibleStatus.join(' ').match(/investorgodkjent|ikke godkjent for investorbruk|automatiske datakontroller bestått|kontrollutgave/i),
    visibleStatus.join(' ').slice(0,150));
  check('Investor approval banner is not rendered',
    (await page.locator('#investor-readiness-banner').count())===0);
  const periods=[...new Set(feed.observations.filter(r=>r.scope==='group'&&r.period_type==='quarter'&&r.status==='reported'&&
     ['insurance_revenue','combined_ratio'].includes(r.metric)).map(r=>r.year+'-'+r.quarter))].sort((a,b)=>{
      const aa=a.split('-').map(Number),bb=b.split('-').map(Number);return bb[0]-aa[0]||bb[1]-aa[1];});
  const [year,quarter]=periods[0].split('-').map(Number);
  const selected=await page.evaluate(()=>FBQuarterly.period);
  check('Latest verified period selected automatically',selected?.year===year&&selected?.quarter===quarter,JSON.stringify(selected));
  const view=await page.evaluate(()=>({
     active:FBQuarterly.period,
     quarter:JSON.parse(JSON.stringify(MON_Q3)),
     ytd:JSON.parse(JSON.stringify(MON_YTD_Q3)),
     graph:profitabilityQuarters.slice(),
     plotLabels:[...document.querySelectorAll('.profit-quarter')].map(el=>el.textContent),
     tableRows:document.querySelectorAll('#results-comparison tbody tr').length,
     kpis:document.querySelectorAll('.dynamic-kpis .metric').length,
     oldReplacement:!!document.querySelector('#live-primary-dashboard'),
     media:document.querySelector('#media-news')?.innerText||'',
     strategic:document.querySelector('.quarter-changes')?.innerText||'',
     brief:document.querySelector('.quarter-comment')?.innerText||'',
     calendar:[...document.querySelectorAll('.mon-calendar')].map(el=>el.innerText).join('\n'),
     newsGroups:FBNews.newsGroups(),
     technical:!!document.querySelector('#verified-financial-panel, #automated-editorial, .live-market-updates')
  }));
  check('Original KPI card/grid design remains intact',!view.oldReplacement&&view.kpis>=6&&view.tableRows>=7,JSON.stringify({kpis:view.kpis,rows:view.tableRows}));
  // Frende Skade figures belong inside the EXISTING Norway segment table,
  // not in a second standalone table lower down the company page.
  await page.evaluate(()=>show('Frende',true));
  const frendeSegment=page.locator('.tablewrap tbody tr.frende-skade-verified-row');
  await frendeSegment.waitFor({state:'visible',timeout:15000});
  const subsidiary=await page.evaluate(()=>{
    const row=document.querySelector('tr.frende-skade-verified-row');
    const cells=[...(row?.cells||[])].map(cell=>cell.innerText.trim());
    const source=row?.querySelector('a[aria-label="Frende Skadeforsikring AS offisiell PDF"]');
    return {
      count:document.querySelectorAll('tr.frende-skade-verified-row').length,
      separatePanels:document.querySelectorAll('.frende-skade-pdf-disclosure').length,
      label:cells[0]||'',cells,period:row?.getAttribute('data-frende-skade-period'),
      source:source?.href||'',inNorwayTable:!!row?.closest('.panel .tablewrap'),
      position:[...row?.parentElement?.children||[]].indexOf(row),
      current:[...(row?.cells||[])].map(cell=>cell.querySelector('strong')?.innerText||''),
      prior:[...(row?.cells||[])].map(cell=>cell.querySelector('.table-prior')?.innerText||''),
      arrow:[...(row?.cells||[])].map(cell=>({
        icon:cell.querySelector('.qoq')?.innerText||'',
        className:cell.querySelector('.qoq')?.className||''
      }))
    };
  });
  const skadeFeed=await (await page.request.get(BASE+'data/frende_skade_financials.json')).json();
  const skadeRows=skadeFeed.observations.filter(r=>r.quarter===quarter&&
    r.source_entity==='Frende Skadeforsikring AS'&&r.period_type==='quarter');
  const sourceMetric=(year,metric)=>skadeRows.find(r=>r.year===year&&r.metric===metric)?.value;
  const numeric=value=>{
    const match=norm(value).replace(/\s/g,'').replace(',','.').match(/-?\d+(?:\.\d+)?/);
    return match?Number(match[0]):NaN;
  };
  check('Frende Skade sits in existing Norway segment table, no second panel',
    subsidiary.count===1&&subsidiary.inNorwayTable&&subsidiary.separatePanels===0&&
    subsidiary.cells.length===6,JSON.stringify(subsidiary).slice(0,750));
  const fields=['insurance_service_result','combined_ratio','loss_ratio','expense_ratio'];
  check('Frende subsidiary current values reflect PDF in existing Norway row',
    fields.every((metric,i)=>Math.abs(numeric(subsidiary.current[i+2])-
      sourceMetric(year,metric))<(i===0 ? .06 : .11)),
    JSON.stringify(subsidiary).slice(0,950));
  check('Frende subsidiary same-quarter prior-year comparisons are visible',
    fields.every((metric,i)=>Number.isFinite(sourceMetric(year-1,metric))&&
      Math.abs(numeric(subsidiary.prior[i+2])-sourceMetric(year-1,metric))<(i===0 ? .06 : .11))&&
    subsidiary.prior[1].includes('%')&&!subsidiary.prior[1].includes('premier'),
    JSON.stringify(subsidiary).slice(0,1150));
  check('Frende subsidiary current/prior trend arrows have correct directions and colours',
    fields.every((metric,i)=>{
      const arrow=subsidiary.arrow[i+2];
      const now=sourceMetric(year,metric),prior=sourceMetric(year-1,metric);
      const expected=now>prior?'▲':now<prior?'▼':'→';
      const favourable=i===0?now>prior:now<prior;
      return arrow.icon===expected&&
        arrow.className.includes(now===prior?'flat':favourable?'good':'bad');
    }),JSON.stringify(subsidiary).slice(0,1150));
  const thisRevenue=sourceMetric(year,'insurance_revenue');
  const priorRevenue=sourceMetric(year-1,'insurance_revenue');
  const oldRevenue=skadeFeed.observations.find(r=>r.year===year-2&&
    r.quarter===quarter&&r.period_type==='quarter'&&
    r.source_entity==='Frende Skadeforsikring AS'&&
    r.metric==='insurance_revenue')?.value;
  const previousGrowth=oldRevenue>0?100*(priorRevenue/oldRevenue-1):null;
  check('Frende Q3 prior-year growth is percentage, never prior-year premium amount',
    priorRevenue>0&&previousGrowth!==null&&
    Math.abs(numeric(subsidiary.current[1])-100*(thisRevenue/priorRevenue-1))<.11&&
    Math.abs(numeric(subsidiary.prior[1])-previousGrowth)<.11&&
    subsidiary.prior[1].includes('%')&&!subsidiary.prior[1].includes('premier')&&
    subsidiary.arrow[1].icon===(100*(thisRevenue/priorRevenue-1)>previousGrowth?'▲':'▼'),
    JSON.stringify(subsidiary).slice(0,950));
  check('Frende subsidiary row links to original official PDF',
    subsidiary.source.startsWith('https://')&&/\.pdf(?:\?|$)/i.test(subsidiary.source)&&
    subsidiary.label.includes('Frende Skadeforsikring AS'),
    JSON.stringify(subsidiary).slice(0,750));
  await page.screenshot({path:'data/browser_frende_skade.png',fullPage:true});
  report.screenshots.push('data/browser_frende_skade.png');
  // Protector Norway must be populated from NORWAY data, including
  // verified current/prior-year ratios and previous-year GROWTH rate.
  await page.evaluate(()=>show('Protector',true));
  await page.locator('tr.protector-norway-verified-row').waitFor({state:'visible',timeout:15000});
  const protector=await page.evaluate(()=>{
    const row=document.querySelector('tr.protector-norway-verified-row');
    return {count:document.querySelectorAll('tr.protector-norway-verified-row').length,
      cells:[...(row?.cells||[])].map(c=>({main:c.querySelector('strong')?.innerText||'',
        prior:c.querySelector('.table-prior')?.innerText||'',text:c.innerText,
        arrow:c.querySelector('.qoq')?.innerText||''})),
      pdf:row?.querySelector('a[aria-label="Protector Norge offisiell PDF"]')?.href||''};
  });
  const protFeed=feed.observations.filter(r=>r.company==='Protector'&&
    r.scope==='norway'&&r.quarter===quarter&&r.period_type==='quarter');
  const protMetric=(year,metric)=>protFeed.find(r=>r.year===year&&r.metric===metric)?.value;
  const p2024=protMetric(year-2,'insurance_revenue');
  const p2025=protMetric(year-1,'insurance_revenue');
  const p2026=protMetric(year,'insurance_revenue');
  const priorPct=p2024>0?100*(p2025/p2024-1):null;
  check('Protector Norway has real revenue growth % in 2026 and 2025',
    protector.count===1&&priorPct!==null&&
    Math.abs(numeric(protector.cells[1].main)-100*(p2026/p2025-1))<.11&&
    Math.abs(numeric(protector.cells[1].prior)-priorPct)<.11&&
    protector.cells[1].prior.includes('%')&&protector.cells[1].arrow,
    JSON.stringify(protector).slice(0,1150));
  check('Protector Norway ratio comparisons and PDF source shown in Norway row',
    ['insurance_service_result','combined_ratio','loss_ratio','expense_ratio']
      .every((name,i)=>Math.abs(numeric(protector.cells[i+2].main)-protMetric(year,name))<.12&&
        Math.abs(numeric(protector.cells[i+2].prior)-protMetric(year-1,name))<.12&&
        !!protector.cells[i+2].arrow)&&
    protector.pdf.toLowerCase().includes('.pdf'),
    JSON.stringify(protector).slice(0,1150));
  await page.screenshot({path:'data/browser_protector_norway.png',fullPage:true});
  report.screenshots.push('data/browser_protector_norway.png');
  await page.evaluate(()=>show('home',true));
  const metrics={combined_ratio:'cr',loss_ratio:'loss',expense_ratio:'cost',
      insurance_revenue:'revenue',insurance_service_result:'result'};
  const companies=['Fremtind','Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand'];
  for(const c of companies){
   const current=feed.observations.filter(r=>r.company===c&&r.year===year&&r.quarter===quarter&&
      r.scope==='group'&&r.period_type==='quarter'&&r.status==='reported');
   const previous=feed.observations.filter(r=>r.company===c&&r.year===year-1&&r.quarter===quarter&&
      r.scope==='group'&&r.period_type==='quarter'&&r.status==='reported');
   for(const r of current){
    const key=metrics[r.metric];if(!key)continue;
    const parsed=Number(norm(view.quarter[c]?.[key]).replace(/\s/g,'').replace(/%/g,'').replace(',','.'));
    check(c+' reported Q'+quarter+' '+r.metric,Number.isFinite(parsed)&&Math.abs(parsed-r.value)<((key==='revenue'||key==='result')?0.55:0.12),parsed+' / '+r.value);
   }
   for(const r of previous){
    const key=metrics[r.metric];if(!key||!current.some(x=>x.metric===r.metric))continue;
    check(c+' prior year '+r.metric,!!view.quarter[c]?.[key+'Prev'],JSON.stringify(view.quarter[c]));
   }
   if(!current.length)check(c+' no invented current figures',!view.quarter[c]?.cr&&!view.quarter[c]?.revenue);
  }
  check('Five chronological quarters on chart',view.graph.length===5&&view.graph[4]==='Q'+quarter+' '+year,JSON.stringify(view.graph));
  check('Five quarter labels remain when data are missing',view.plotLabels.length===5,view.plotLabels.join(','));
  check('One unified media and market insight section',!view.strategic&&view.media.includes('Forsikring i mediebildet')&&view.media.includes('Nyheter og innsikt'),view.media.slice(0,200));
  check('Quarterly brief actually rendered',editorial.brief.length===0||editorial.brief.some(x=>displayed(view.brief).includes(displayed(x.text))),view.brief.slice(0,250));
  if(year===2026 && quarter===3 && editorial.period==='Q3 2026' &&
     ['Protector','Storebrand'].every(c=>editorial.periods?.['Q3 2026']?.by_company?.[c])){
    check('Q3 brief excludes redundant financial-only insurer commentary',
      !view.brief.includes('Utviklingen er basert på sammenlignbare rapporterte måltall') &&
      !(editorial.brief||[]).some(x=>x.theme==='additional_insurers'),
      view.brief.slice(0,900));
    check('Q3 brief is concise and free from raw PDF excerpts',
      (editorial.brief||[]).length<=4 &&
      (editorial.brief||[]).reduce((sum,x)=>sum+x.text.trim().split(' ').length,0)<=220 &&
      !view.brief.includes('omtaler i kvartalsrapporten:'),
      view.brief.slice(0,550));
  }
  const calendarColumns=await page.evaluate(()=>{
    const pending=document.querySelector('.mon-cal-column[data-calendar-group="pending"]');
    const reported=document.querySelector('.mon-cal-column[data-calendar-group="reported"]');
    return {pending:pending?.querySelectorAll('.mon-cal-row').length||0,
      reported:reported?.querySelectorAll('.mon-cal-row').length||0,
      total:document.querySelectorAll('.mon-cal-split .mon-cal-row').length,
      dates:[...document.querySelectorAll('.mon-cal-split .mon-cal-row')]
        .map(x=>x.querySelector('.mon-cal-countdown')?.textContent?.trim())};
  });
  check('Calendar separates reported and pending companies',calendarColumns.total===7 &&
    calendarColumns.pending+calendarColumns.reported===7,
    JSON.stringify(calendarColumns));
  check('Every insurer has a report countdown or explicit unknown date',
    calendarColumns.total===7 && calendarColumns.dates.length===7 &&
    calendarColumns.dates.every(x=>x&&x.length>0),
    JSON.stringify(calendarColumns.dates));
  check('Technical duplicate sections removed',!view.technical);
  check('Source-backed market insight appears only in unified media section',view.newsGroups.official.length===0||
     view.newsGroups.official.some(n=>view.media.includes(n.text)),view.media.slice(0,280));
  check('News visible in original media cards',view.newsGroups.other.length===0||
     view.newsGroups.other.some(n=>view.media.includes(n.headline)),view.media.slice(0,280));
  check('No separate strategic headline cards',view.newsGroups.strategic.length===0&&!view.strategic);
  const missing=companies.filter(c=>['combined_ratio','insurance_revenue'].some(metric=>
    !feed.observations.some(r=>r.company===c&&r.scope==='group'&&
      r.year===year&&r.quarter===quarter&&r.period_type==='quarter'&&
      r.metric===metric&&['reported','calculated'].includes(r.status)&&r.source_url)));
  const calendarName=c=>c==='Sampo'?'Sampo / If':c;
  check('All missing issuers shown, including those without dates',
    missing.every(c=>view.calendar.includes(calendarName(c))),view.calendar.slice(0,400));
  const announced=Object.entries(calendarFeed.companies||{});
  const futureScheduled=announced.filter(([name,config])=>{
    const next=config.next_event;
    const match=/^Q([1-4]) (\d{4})$/.exec(next?.period||'');
    return next&&!next.locked&&match&&Number(match[2])*4+Number(match[1])>year*4+quarter;
  });
  check('Future reports are preserved when current results are published',
    futureScheduled.every(([name,config])=>view.calendar.includes(name+'\n'+config.next_event.period)),
    view.calendar.slice(0,400));
  const alreadyPublished=announced.filter(([name,config])=>
    config.next_event?.period==='Q'+quarter+' '+year&&
    !missing.includes(name==='Sampo / If'?'Sampo':name));
  check('Published current quarter is not repeated in calendar',
    alreadyPublished.every(([name])=>!view.calendar.includes(name+'\nQ'+quarter+' '+year)),
    view.calendar.slice(0,400));
  // Test actual rendered copy and source links for every issuer, not JS text fragments.
  for(const issuer of ['Fremtind','Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand']){
    await page.evaluate(name=>show(name,true),issuer);
    const panel=page.locator('.quarter-comment').first();
    const rendered=await panel.innerText();
    const brief=editorial.periods?.['Q'+quarter+' '+year]?.by_company?.[issuer];
    const notes=(brief?.qualitative_notes||[]).filter(x=>x.text&&/^https:\/\//.test(x.source_url||'')&&x.source_page);
    if(brief){
      const expected=brief.editorial_review?.verified ? [brief.editorial_review.text] : [brief.reader_summary,notes[0]?.text].filter(Boolean);
      check(issuer+' quarterly narrative is visible',
        expected.length>0 && expected.every(x=>displayed(rendered).includes(displayed(x))),
        rendered.slice(0,450));
      const urls=await panel.locator('a[href]').evaluateAll(nodes=>nodes.map(n=>n.href));
      check(issuer+' quarterly official source is retained',
        /^https:\/\//.test(brief.editorial_review?.source_url||brief.source_url) &&
        urls.some(url=>url.startsWith('https://')),urls.join(','));
      check(issuer+' quarterly period is correct',
        rendered.includes('Q'+quarter+' '+year),rendered.slice(0,120));
    }else{
      check(issuer+' missing quarter is honestly marked',
        rendered.includes('Ingen kildeverifisert')||rendered.includes('avventer'),rendered.slice(0,200));
    }
  }
  await page.evaluate(()=>show('Gjensidige',true));
  const companyComment=await page.locator('.quarter-comment').first().innerText();
  check('Company commentary has no duplicated quarter prefix',
    !companyComment.includes('Q'+quarter+' Q'+quarter+' '+(year-1)),companyComment.slice(0,350));
  const quotesOnCompany=await page.locator('.stock-section').first().innerText();
  const quote=stocks.prices?.Gjensidige;
  // A legacy or stale quote cannot be presented as a current graph.
  // A current validated quote must display its source date and ticker.
  const validStockQuote=quote?.availability==='available'&&
    quote.symbol==='GJF.OL'&&quote.currency==='NOK'&&
    Array.isArray(quote.history)&&quote.history.length>=2&&
    quote.history.every(row=>/^\d{4}-\d{2}-\d{2}$/.test(row.date)&&
      Number.isFinite(row.price)&&row.price>0)&&
    quote.history.at(-1).price===quote.close;
  if(validStockQuote){
    check('Verified daily quotes show ticker and source observation date',
       quotesOnCompany.includes('GJF.OL')&&
       quotesOnCompany.includes(quote.history.at(-1).date),
       quotesOnCompany.slice(0,420));
  }else{
    check('Unavailable or legacy quotes never render fabricated prices',
       quotesOnCompany.includes('Ingen pålitelige, oppdaterte kursdata')&&
       !quotesOnCompany.includes('SISTE KURSOBSERVASJON'),
       quotesOnCompany.slice(0,420));
  }
  // Each company detail must show its own profitability graph and source-derived
  // prior-year revenue growth; do not accept the homepage's selected issuer.
  for(const issuer of ['Gjensidige','Protector']){
    await page.evaluate(name=>show(name,true),issuer);
    const panel=page.locator('.company-profitability');
    const placement=await page.evaluate(()=>{
      const graph=document.querySelector('.company-profitability');
      const cards=document.querySelector('.dynamic-kpis');
      const segments=document.querySelector('.tablewrap');
      return Boolean(graph&&cards&&segments&&
        (cards.compareDocumentPosition(graph)&Node.DOCUMENT_POSITION_FOLLOWING)&&
        (graph.compareDocumentPosition(segments)&Node.DOCUMENT_POSITION_FOLLOWING));
    });
    check(issuer+' profitability follows group KPI cards before segment table',placement,issuer);
    const panelCount=await panel.count();
    const panelText=panelCount?await panel.first().innerText():'';
    const quarterCount=panelCount?await panel.first().locator('.profit-quarter').count():0;
    check(issuer+' has its own profitability chart',
      panelCount===1 && panelText.includes('Utvikling i lønnsomhet · '+issuer) &&
      quarterCount===5,
      JSON.stringify({issuer,panelCount,quarterCount,heading:panelText.slice(0,160),
        html:await page.locator('body').evaluate(el=>el.innerHTML.includes('company-profitability'))}));
    const prior=feed.observations.find(r=>r.company===issuer&&r.year===year-1&&
      r.quarter===quarter&&r.scope==='group'&&r.period_type==='quarter'&&
      r.metric==='insurance_revenue');
    const older=feed.observations.find(r=>r.company===issuer&&r.year===year-2&&
      r.quarter===quarter&&r.scope==='group'&&r.period_type==='quarter'&&
      r.metric==='insurance_revenue');
    if(prior&&older&&older.value>0&&prior.unit===older.unit){
      const expected=((prior.value/older.value-1)*100).toLocaleString('nb-NO',
        {minimumFractionDigits:1,maximumFractionDigits:1});
      const card=page.locator('.source-growth-matrix [data-growth-period="quarter-prior"] .value');
      check(issuer+' displays verified last-year revenue growth',
        (await card.innerText()).includes(expected),expected);
    }
  }
  await page.evaluate(()=>show('home',true));
  const tableQ=norm(await page.locator('body').innerText());
  for(const c of ['Fremtind','Storebrand']){
   const r=feed.observations.find(x=>x.company===c&&x.year===year&&x.quarter===quarter&&
     x.scope==='group'&&x.period_type==='quarter'&&x.metric==='insurance_service_result');
   if(r)check(c+' insurance result visible in comparison table',tableQ.includes(nf(r.value)),tableQ.slice(-700));
  }
  if(view.quarter.Storebrand?.revenueBasis)
   check('Storebrand APM disclaimer visible',tableQ.includes('APM'),tableQ.slice(-700));
  for(const c of companies){
   const now=feed.observations.find(r=>r.company===c&&r.year===year&&r.quarter===quarter&&
      r.scope==='group'&&r.period_type==='quarter'&&r.metric==='insurance_revenue');
   const prev=feed.observations.find(r=>r.company===c&&r.year===year-1&&r.quarter===quarter&&
      r.scope==='group'&&r.period_type==='quarter'&&r.metric==='insurance_revenue');
   if(now&&prev&&now.unit===prev.unit){
    const cell=await page.locator('#results-comparison tbody tr').filter({hasText:c}).first().locator('td').nth(1);
    const txt=norm(await cell.innerText());
    check(c+' source-based growth in first metric column',txt.includes('%'),txt.slice(0,250));
   }
  }
  const subsidiaryQ=feed.observations.find(r=>r.company==='Storebrand'&&r.scope==='norway'&&
     r.source_entity==='Storebrand Forsikring AS'&&r.year===year&&r.quarter===quarter&&
     r.period_type==='quarter'&&r.metric==='insurance_revenue');
  if(subsidiaryQ)check('Storebrand Forsikring AS IFRS17 quarter revenue beside group APM',
    norm(await page.locator('body').innerText()).includes(nf(subsidiaryQ.value))&&norm(await page.locator('body').innerText()).includes('Storebrand Forsikring AS')&&norm(await page.locator('body').innerText()).includes('IFRS 17'),tableQ.slice(-900));
  await page.screenshot({path:'data/browser_home_q3.png',fullPage:true});
  report.screenshots.push('data/browser_home_q3.png');
  await page.selectOption('#results-comparison select','H3');
  const ytdText=norm(await page.locator('body').innerText());
  const ytd=feed.observations.filter(x=>x.scope==='group'&&x.year===year&&x.quarter===quarter&&x.period_type==='ytd');
  for(const c of companies){
   const metric=ytd.find(x=>x.company===c&&x.metric==='insurance_service_result');
   if(metric)check(c+' HIÅ insurance result visible',ytdText.includes(nf(metric.value)),ytdText.slice(-300));
  }
  check('HIÅ heading and values',ytdText.includes('HIÅ')||ytdText.includes('Hiå'),ytdText.slice(0,190));
  const subsidiaryYTD=feed.observations.find(r=>r.company==='Storebrand'&&r.scope==='norway'&&
      r.source_entity==='Storebrand Forsikring AS'&&r.year===year&&r.quarter===quarter&&
      r.period_type==='ytd'&&r.metric==='insurance_revenue');
  if(subsidiaryYTD)check('Storebrand Forsikring AS IFRS17 HIÅ in original table',
      ytdText.includes(nf(subsidiaryYTD.value))&&ytdText.includes('Storebrand Forsikring AS'),ytdText.slice(-850));
  for(const company of companies){
   const prior=feed.observations.find(r=>r.company===company&&r.year===year-1&&r.quarter===quarter&&
     r.scope==='group'&&r.period_type==='ytd'&&r.metric==='insurance_revenue');
   const cur=feed.observations.find(r=>r.company===company&&r.year===year&&r.quarter===quarter&&
     r.scope==='group'&&r.period_type==='ytd'&&r.metric==='insurance_revenue');
   if(cur&&prior&&cur.unit===prior.unit){
    const cell=await page.locator('#results-comparison tbody tr').filter({hasText:company}).first().locator('td').nth(1);
    check(company+' HIÅ source-derived growth in first metric column',
      norm(await cell.innerText()).includes('%'),company);
   }
  }
  await page.screenshot({path:'data/browser_home_ytd.png',fullPage:true});
  report.screenshots.push('data/browser_home_ytd.png');
  await page.evaluate(()=>FBQuarterly.refresh());
  check('Auto-refresh preserves user-selected HIÅ tab',
        (await page.locator('#results-comparison select').inputValue())==='H3');
  await page.selectOption('#results-comparison select','Q3');
  // Simulate two future reporting cycles with the existing CSS/DOM layout.
  // No synthetic figure is written to repository data or published files.
  const synthetic=structuredClone(feed);
  const seed=feed.observations.filter(x=>x.company==='Fremtind'&&x.year===year&&x.quarter===quarter&&
    x.scope==='group'&&x.period_type==='quarter');
  for(const [yr,q] of [[year,quarter===4?4:quarter+1],[year+1,1]]){
   if(yr===year&&q===quarter)continue;
   for(const row of seed)synthetic.observations.push({...row,year:yr,quarter:q,
      value:row.metric==='insurance_revenue'?row.value+100:row.value});
  }
  await page.route('**/data/verified_financial_feed.json*',route=>route.fulfill({
      status:200,contentType:'application/json',body:JSON.stringify(synthetic)}));
  await page.evaluate(()=>FBQuarterly.refresh());
  const future=await page.evaluate(()=>({
    active:FBQuarterly.period,quarters:profitabilityQuarters.slice(),
    options:[...document.querySelectorAll('.mon-period select option')].map(x=>x.textContent),
    kpis:document.querySelectorAll('.dynamic-kpis .metric').length,
    hasReplacement:!!document.querySelector('#live-primary-dashboard'),
    chart:[...document.querySelectorAll('.profit-quarter')].map(x=>x.textContent)
  }));
  check('Next-year Q1 auto-selection after simulated publication',future.active?.year===year+1&&future.active?.quarter===1,JSON.stringify(future.active));
  const futureCalendar=await page.evaluate(()=>{
    const html=typeof monCalendar==='function'?monCalendar():'';
    const current=FBQuarterly.available?.[0];
    const next=current?.quarter===4?'Q1 '+(current.year+1):
      'Q'+(current.quarter+1)+' '+current.year;
    return {next,heading:html.includes('Neste rapporter · '+next),
      currentHeading:html.includes('Publiseringsdatoer for kvartalsrapporter · Q'+current.quarter+' '+current.year),
      columns:html.includes('data-calendar-group="pending"')&&
        html.includes('data-calendar-group="reported"')};
  });
  check('Calendar right heading follows future verified quarter and year rollover',
    futureCalendar.heading&&futureCalendar.currentHeading&&futureCalendar.columns,
    JSON.stringify(futureCalendar));
  // A closed historical quarter must never inherit the active reporting calendar.
  // Exercise navigation after the synthetic Q1 year rollover, not just string matching.
  const historical=await page.evaluate(()=>{
    const active=FBQuarterly.available[0],old=FBQuarterly.available.find(
      p=>p.year!==active.year||p.quarter!==active.quarter);
    if(!old)return {error:'No earlier verified quarter in selector'};
    monSetQuarter(old.year+'-'+old.quarter);
    return {selected:FBQuarterly.period,calendarCount:document.querySelectorAll('.mon-calendar').length,
      html:monCalendar(),old};
  });
  check('Historical quarter hides financial calendar after year rollover',
    !historical.error&&historical.selected?.year===historical.old.year&&
    historical.selected?.quarter===historical.old.quarter&&
    historical.calendarCount===0&&historical.html==='',JSON.stringify(historical).slice(0,500));
  const restored=await page.evaluate(()=>{
    const latest=FBQuarterly.available[0];
    monSetQuarter(latest.year+'-'+latest.quarter);
    return {selected:FBQuarterly.period,calendarCount:document.querySelectorAll('.mon-calendar').length,
      html:monCalendar()};
  });
  check('Returning to active quarter restores financial calendar',
    restored.selected?.year===year+1&&restored.selected?.quarter===1&&
    restored.calendarCount===2&&restored.html.includes('Neste rapporter'),
    JSON.stringify(restored).slice(0,500));
  check('Rolling graph includes next-year Q1',future.quarters.includes('Q1 '+(year+1)),future.quarters.join(','));
  check('Next quarter and year in dropdown',future.options.some(x=>x.includes('Q1 '+(year+1))),future.options.join(','));
  check('Original design survives future publication',future.kpis>=6&&!future.hasReplacement,future.kpis);
  check('Five graph quarter labels survive rollover',future.chart.length===5,future.chart.join(','));
  check('No JavaScript runtime errors',pageErrors.length===0,pageErrors.join(' | ').slice(0,600));
 }catch(e){report.errors.push('FATAL: '+(e?.stack||e));}
 finally{
  report.passed=report.errors.length===0;
  fs.mkdirSync('data',{recursive:true});
  fs.writeFileSync(OUTPUT,JSON.stringify(report,null,2)+'\n');
  await browser.close();
 }
 console.log('BROWSER_E2E',report.passed?'PASS':'FAIL',report.checks.length,'checks',report.errors.slice(0,12));
 process.exitCode=report.passed?0:1;
}
main().catch(e=>{console.error(e);process.exitCode=1});