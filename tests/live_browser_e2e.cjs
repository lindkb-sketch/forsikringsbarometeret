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
  await page.waitForFunction(()=>window.FBQuarterly?.period&&document.querySelector('#market-overview[data-period]:not([data-period=""])'),null,{timeout:35000});
  check('New market overview is the landing page',await page.locator('#nav-home.active').count()===1&&await page.locator('#market-overview-comments').count()===1);
  check('Old summary not appended to new overview',await page.locator('#results-comparison,#nine-company-kpi-comparison').count()===0);
  const fxResponse=await page.request.get(BASE+'data/market_overview_fx.json?browser_audit='+Date.now());
  const marketFx=fxResponse.ok()?await fxResponse.json():{periods:{}};
  const compResponse=await page.request.get(BASE+'data/nine_insurer_comparison.json?browser_audit='+Date.now());
  const marketComparison=compResponse.ok()?await compResponse.json():{};
  const segmentResponse=await page.request.get(BASE+'data/market_overview_segments.json?browser_audit='+Date.now());
  const marketSegments=segmentResponse.ok()?await segmentResponse.json():{};
  const contextResponse=await page.request.get(BASE+'data/market_overview_context.json?browser_audit='+Date.now());
  const marketContext=contextResponse.ok()?await contextResponse.json():{};
  const archiveResponse=await page.request.get(BASE+'data/market_overview_archive.json?browser_audit='+Date.now());
  const marketArchive=archiveResponse.ok()?await archiveResponse.json():{};
  check('Market quarter snapshot available',Boolean(marketArchive.active_period&&marketArchive.periods?.[marketArchive.active_period]));
  await page.evaluate(()=>FBMarketOverview.refresh());
  const verifyMarket=async(scope,market,mode='quarter')=>{
   await page.locator('[data-mo-mode="'+mode+'"]').click();
   await page.locator('[data-mo-scope="'+scope+'"]').click();
   await page.locator('[data-mo-market="'+market+'"]').click();
   const state=await page.evaluate(({marketFx,marketComparison,marketSegments,marketContext,marketArchive,scope,market,mode})=>{
    const model=FBMarketOverview.archivedView(marketArchive,'latest',scope,market,mode)?.model||FBMarketOverview.model(FBQuarterly.verified,marketComparison,marketFx,scope,market,marketSegments,mode,marketContext);
    return {expected:model.selected.map(c=>c.company),actual:[...document.querySelectorAll('.mo-company')].map(c=>c.dataset.company),cr:[...document.querySelectorAll('.mo-company')].map(c=>Number(c.dataset.cr)),missing:model.fxMissing,period:document.getElementById('mo-period').textContent,growth:document.querySelectorAll('.mo-company .mo-growth').length,empty:!!document.querySelector('#market-overview .mo-empty'),comments:document.querySelectorAll('.mo-comment-grid article').length,medals:[...document.querySelectorAll('.mo-company')].map(el=>({rank:el.querySelector('.mo-name .mo-medal')?.dataset.crRank||null,text:el.querySelector('.mo-name .mo-medal')?.textContent||null,afterName:!!el.querySelector('.mo-name button + .mo-medal')}))};
   },{marketFx,marketComparison,marketSegments,marketContext,marketArchive,scope,market,mode});
   check('Market '+scope+'/'+market+' uses exact eligible income-ranked companies',JSON.stringify(state.expected)===JSON.stringify(state.actual),JSON.stringify(state));
   check('Market '+scope+'/'+market+' sorts CR ascending and aligns growth',state.cr.every((v,i)=>!i||v>=state.cr[i-1])&&state.growth===state.actual.length&&state.actual.length<=5);
   check('Market '+scope+'/'+market+'/'+mode+' has three comment groups',state.comments===3);
   check('CR medals under company names '+scope+'/'+market+'/'+mode,state.medals.length===state.actual.length&&state.medals.every((m,i)=>i<3?m.rank===String(i+1)&&m.text===['🥇','🥈','🥉'][i]&&m.afterName:m.rank===null),JSON.stringify(state.medals));
   if(state.missing.length)check('FX missing: no misleading ranking',state.empty&&state.actual.length===0);
   if(state.period==='Q3 2026'){const expected={'group/all':5,'group/pm':4,'group/bm':5,'norway/all':5,'norway/pm':2,'norway/bm':3};check('Complete Q3 displayed '+scope+'/'+market+'/'+mode,state.actual.length===expected[scope+'/'+market],JSON.stringify(state));}
  };
  for(const mode of ['quarter','ytd'])for(const scope of ['group','norway'])for(const market of ['all','pm','bm'])await verifyMarket(scope,market,mode);
  for(const label of Object.keys(marketArchive.periods||{})){
   await page.locator('#mo-report-period').selectOption(label);
   check('Select archived reporting quarter '+label,await page.locator('#mo-period').textContent()===label&&await page.locator('#market-overview').getAttribute('data-locked')===String(marketArchive.periods[label].locked));
  }
  if(marketArchive.active_period)await page.locator('#mo-report-period').selectOption(marketArchive.active_period);
  await verifyMarket('norway','all');
  check('Five companies in Norway total for baseline quarter',await page.locator('#mo-period').textContent()!=='Q3 2026'||await page.locator('.mo-company').count()===5);
  check('Market footnotes moved off overview',await page.locator('.mo-note,.mo-excluded,.mo-source,.mo-name small').count()===0);
  await verifyMarket('group','all');
  const eligibility=await page.evaluate(({marketFx,marketComparison,marketSegments})=>{
    const f=[['group','all'],['group','pm'],['group','bm'],['norway','all'],['norway','pm'],['norway','bm']];
    return {period:document.getElementById('mo-period').textContent,byCompany:Object.fromEntries(['Protector','Tryg','Gjensidige','Fremtind','Alm. Brand','Sampo','Frende','Storebrand','KLP Skadeforsikring'].map(c=>[c,f.map(([s,m])=>FBMarketOverview.model(FBQuarterly.verified,marketComparison,marketFx,s,m,marketSegments).eligible.some(r=>r.company===c))]))};
  },{marketFx,marketComparison,marketSegments});
  if(eligibility.period==='Q3 2026'){
    check('Protector BM uses its own country/group totals',JSON.stringify(eligibility.byCompany.Protector)===JSON.stringify([true,false,true,true,false,true]),JSON.stringify(eligibility));
    check('Tryg group segments only; no Norway PM/BM substitution',JSON.stringify(eligibility.byCompany.Tryg)===JSON.stringify([true,true,true,true,false,false]),JSON.stringify(eligibility));
    check('Gjensidige eligible for all six views with distinct segment figures',eligibility.byCompany.Gjensidige.every(Boolean),JSON.stringify(eligibility));
    check('Fremtind PM and BM use reported quarter CR in group and Norway',JSON.stringify(eligibility.byCompany.Fremtind)===JSON.stringify([true,true,true,true,true,true]),JSON.stringify(eligibility));
    check('Alm Brand has group Personal and Commercial only',JSON.stringify(eligibility.byCompany['Alm. Brand'])===JSON.stringify([true,true,true,false,false,false]),JSON.stringify(eligibility));
    for(const c of ['Sampo'])
      check(c+' is group only',JSON.stringify(eligibility.byCompany[c])===JSON.stringify([true,false,false,false,false,false]),JSON.stringify(eligibility));
    for(const c of ['Frende','KLP Skadeforsikring','Storebrand'])check(c+' group and Norway total only',JSON.stringify(eligibility.byCompany[c])===JSON.stringify([true,false,false,true,false,false]),JSON.stringify(eligibility));
    check('Current Q3 FX covers all required currencies',Boolean(marketFx.periods?.['Q3 2026']?.rates?.EUR&&marketFx.periods?.['Q3 2026']?.rates?.DKK));
    const f=await page.evaluate(({marketFx,marketComparison,marketSegments})=>Object.fromEntries(['pm','bm'].map(m=>[m,FBMarketOverview.model(FBQuarterly.verified,marketComparison,marketFx,'group',m,marketSegments).eligible.find(r=>r.company==='Fremtind')])),{marketFx,marketComparison,marketSegments});
    check('Fremtind published APM quarter CR and revenue (not IFRS note)',f.pm?.cr===71.6&&f.bm?.cr===80.8&&f.pm?.revenue===5341&&f.bm?.revenue===965&&f.pm?.growth===4.4&&f.bm?.growth===3.6&&f.pm?.loss===null&&f.bm?.cost===null,JSON.stringify(f));
  }
  const marketSections=await page.evaluate(()=>{
    const ids=['market-overview-comments','mo-trend-charts','media-news','mo-calendar-next'];
    return {order:ids.every((id,i)=>document.getElementById(id)&&(!i||Boolean(document.getElementById(ids[i-1]).compareDocumentPosition(document.getElementById(id))&Node.DOCUMENT_POSITION_FOLLOWING))),
      pending:document.querySelectorAll('#mo-calendar-pending .mon-cal-row').length,
      next:document.querySelectorAll('#mo-calendar-next .mon-cal-row').length,
      labels:[...document.querySelectorAll('#mo-cr-history .mo-line-quarter')].map(x=>x.dataset.period),
      left:[...document.querySelectorAll('#mo-profitability-panel .profit-quarter')].map(x=>x.textContent),
      companies:[...document.querySelectorAll('.mo-line-legend-item')].map(x=>x.dataset.company),
      points:document.querySelectorAll('.mo-line-point').length};
  });
  check('Market supplementary panels in requested order',marketSections.order,JSON.stringify(marketSections));
  check('Both market charts display the same five consecutive periods',marketSections.labels.length===5&&JSON.stringify(marketSections.labels)===JSON.stringify(marketSections.left)&&marketSections.labels.at(-1)===marketArchive.active_period,JSON.stringify(marketSections));
  check('Market CR line chart covers all nine issuers',marketSections.companies.length===9&&new Set(marketSections.companies).size===9,JSON.stringify(marketSections));
  check('Market report calendar partitions all nine issuers',marketSections.pending+marketSections.next===9,JSON.stringify(marketSections));
  if(marketArchive.periods[marketArchive.active_period].views['group/all/quarter'].model.reported===9)check('No pending calendar when all nine have reported',await page.locator('#mo-calendar-pending').count()===0&&marketSections.next===9);
  await page.locator('#mo-profitability-panel select').selectOption('Tryg');
  check('Market profitability selector works without changing CR chart',await page.locator('#mo-profitability-panel h2').innerText()==='Utvikling i lønnsomhet · Tryg'&&await page.locator('.mo-line-legend-item').count()===9);
  await page.locator('#mo-profitability-panel select').selectOption('Fremtind');
  await page.screenshot({path:'data/browser_market_overview.png',fullPage:true});
  report.screenshots.push('data/browser_market_overview.png');
  await page.locator('#nav-summary').click();
  await page.waitForFunction(()=>window.FBQuarterly?.period&&
       document.querySelector('#results-comparison tbody tr')&&
       window.FBNews?.editorial && window.FBReportCalendar?.ready &&
       document.querySelector('.mon-calendar'),null,{timeout:35000});
  // A published broker summary must be visible on its company's page, not home.
  const brokerFeedResponse=await page.request.get(BASE+'data/broker_commentary.json?browser_audit='+Date.now());
  check('Approved broker feed reachable',brokerFeedResponse.status()===200,'HTTP '+brokerFeedResponse.status());
  if(brokerFeedResponse.status()===200){
   const brokerFeed=await brokerFeedResponse.json();
   const gjensidige=brokerFeed.entries?.find(e=>e.company==='Gjensidige'&&e.quarter==='Q3 2026');
   if(gjensidige){
    check('Broker commentary absent on homepage',(await page.locator('#broker-commentary-panel').count())===0);
    await page.locator('#nav-Gjensidige').click();
    await page.waitForTimeout(1200);
    const panel=page.locator('#broker-commentary-panel');
    check('Gjensidige broker panel exists',await panel.count()===1);
    check('Approved Gjensidige Q3 commentary visible',await panel.isVisible(),
      'panel='+await panel.count()+'; hidden='+(await panel.count()?await panel.getAttribute('hidden'):'missing')+
      '; text='+(await panel.count()?String(await panel.textContent()).slice(0,180):''));
    await page.locator('#nav-summary').click();
   }
  }
  // An approved safety headline must survive the frontend's material-news filter.
  const newsResponse=await page.request.get(BASE+'data/official_news.json?browser_audit='+Date.now());
  if(newsResponse.status()===200){
   const newsFeed=await newsResponse.json();
   const trygSafety=(newsFeed.items||[]).find(x=>x.approved&&/Tryg/i.test(x.headline)&&/elsparkesykkel/i.test(x.headline));
   if(trygSafety){
    await page.locator('#nav-Tryg').click();
    await page.waitForTimeout(350);
    check('Approved Tryg traffic-safety news visible on company page',
      (await page.locator('.company-media-news').allTextContents()).join(' ').includes(trygSafety.headline));
    await page.locator('#nav-summary').click();
   }
  }
  // The news surface must be present for every insurer, even when no
  // recent source-backed article exists. Homepage always shows the sector feed.
  await page.locator('#nav-summary').click();
  check('Insurance news section exists on homepage',
    await page.locator('#media-news').count()===1);
  for(const insurer of ['Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand']){
   await page.locator('#nav-'+insurer).click();
   check(insurer+' media section exists',
     await page.locator('.company-media-news').count()===1);
   await page.locator('#nav-summary').click();
  }
  // New issuer pages must render without relying on legacy seven-company data.
  for(const name of ['KLP Skadeforsikring','Alm. Brand']){
    await page.locator('[id="nav-'+name+'"]').click();
    check(name+' company page renders', (await page.locator('#app').innerText()).includes(name));
    check(name+' uses standard company KPIs and profitability chart',await page.locator('.dynamic-kpis').count()===1&&await page.locator('.company-profitability .profit-quarter').count()===5);
    await page.locator('.company-period-actions select').selectOption('H3');
    check(name+' HIÅ selection stays on company tab',await page.locator('[id="nav-'+name+'"].active').count()===1&&await page.locator('.dynamic-kpis [data-financial-period="ytd"]').count()>0);
    await page.locator('.company-period-actions select').selectOption('Q3');
    check(name+' primary-source link exists', await page.locator('#app a[href^="https://"]').count()>0);
    await page.locator('#nav-summary').click();
  }
  // The nine-company table has its own explicit period selector.
  const nineResponse=await page.request.get(BASE+'data/nine_insurer_comparison.json?browser_audit='+Date.now());
  if(nineResponse.ok()){
    const nine=await nineResponse.json();
    if(nine.companies?.every(c=>c.ytd_metrics)){
      await page.locator('#nine-company-kpi-comparison').waitFor({state:'visible',timeout:15000});
      const quarterButton=page.locator('#nine-kpi-view-quarter');
      const ytdButton=page.locator('#nine-kpi-view-ytd');
      await ytdButton.click();
      check('Nine-company HIÅ selected',await ytdButton.getAttribute('aria-pressed')==='true');
      const table=page.locator('#nine-company-kpi-comparison table tbody');
      check('Nine-company HIÅ comparison has nine rows',await table.locator('tr').count()===9);
      const fields=['insurance_revenue','insurance_revenue_growth','insurance_service_result','loss_ratio','expense_ratio','combined_ratio','return_on_equity','solvency_ratio','profit_before_tax'];
      for(const company of nine.companies){
        const tr=table.locator('tr').filter({hasText:company.company});
        for(const [i,key] of fields.entries()){
          const value=company.ytd_metrics[key];
          const text=norm(await tr.locator('td').nth(i+2).innerText());
          if(typeof value==='number'){
            const expected=norm(new Intl.NumberFormat('nb-NO',{maximumFractionDigits:1,minimumFractionDigits:['insurance_revenue','insurance_service_result','profit_before_tax'].includes(key)?0:1}).format(value));
            check(company.company+' nine-company HIÅ '+key,text.startsWith(expected),text+' expected '+expected);
          }else check(company.company+' missing HIÅ '+key,/Ikke rapportert|—/.test(text),text);
        }
      }
      await quarterButton.click();
      check('Nine-company quarter view restored',await quarterButton.getAttribute('aria-pressed')==='true');
    }
  }
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
  await page.evaluate(()=>show('summary',true));
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
  check('Calendar separates reported and pending companies',calendarColumns.total===9 &&
    calendarColumns.pending+calendarColumns.reported===9,
    JSON.stringify(calendarColumns));
  const calendarMembership=await page.evaluate(()=>{
    const p=FBQuarterly.available[0],names=['Fremtind','Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand','KLP Skadeforsikring','Alm. Brand'];
    const read=kind=>[...document.querySelectorAll('[data-calendar-group="'+kind+'"] .mon-cal-company strong')].map(el=>el.textContent==='Sampo / If'?'Sampo':el.textContent).sort();
    return {actualPending:read('pending'),actualReported:read('reported'),
      expectedPending:names.filter(n=>!FBQuarterly.isReportPublished(n,p)).sort(),
      expectedReported:names.filter(n=>FBQuarterly.isReportPublished(n,p)).sort()};
  });
  check('Summary calendar agrees with verified group reports for all nine',
    JSON.stringify(calendarMembership.actualPending)===JSON.stringify(calendarMembership.expectedPending)&&
    JSON.stringify(calendarMembership.actualReported)===JSON.stringify(calendarMembership.expectedReported),JSON.stringify(calendarMembership));
  check('Every insurer has a report countdown or explicit unknown date',
    calendarColumns.total===9 && calendarColumns.dates.length===9 &&
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
    // The original seven-company feed does not certify KLP/Alm Brand as published.
    // Their nine-company comparison has a separate verified source and status.
    if(!companies.includes(name))return false;
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
  // Listing eligibility is based on the configured equity, not on debt
  // notices or the presence/absence of a stock quote.
  for(const name of ['Fremtind','Frende','KLP Skadeforsikring']){
    await page.evaluate(c=>{window.FBNewsWeb.notices[c]=[{source:'NewsWeb',url:'https://newsweb.oslobors.no/message/123456',title:'Test debt notice',published_at:new Date().toISOString()}];show(c,true);},name);
    check(name+' has no irrelevant stock or exchange section',await page.locator('.stock-section,.company-exchange-notices').count()===0&&await page.locator('.company-media-news').count()===1);
    await page.evaluate(c=>{delete window.FBNewsWeb.notices[c]},name);
  }
  await page.evaluate(()=>show('Sampo',true));
  await page.locator('.company-period-actions select').selectOption('Q3');
  const sam=await page.evaluate(()=>{
    const chart=document.querySelector('.company-profitability'),segments=document.querySelector('.company-segments');
    return {placement:chart?.nextElementSibling===segments,labels:[...document.querySelectorAll('.company-segments tbody tr')].map(r=>r.dataset.segment),values:[...document.querySelectorAll('.company-segments tbody tr')].map(r=>[...r.cells].slice(1).map(c=>c.innerText))};
  });
  check('Sampo Nordic segments directly below profitability chart',sam.placement&&JSON.stringify(sam.labels)===JSON.stringify(['Private Nordic','Nordic Commercial']),JSON.stringify(sam));
  if(marketArchive.active_period==='Q3 2026')check('Sampo official isolated quarter segment ratios',sam.values[0]?.[2]?.includes('79,5')&&sam.values[1]?.[2]?.includes('82,1'),JSON.stringify(sam));
  await page.locator('.company-period-actions select').selectOption('H3');
  check('Sampo HIÅ uses complete source-based Nordic segment figures',await page.locator('.company-segments tr[data-financial-source="calculated_ytd"],.company-segments tr[data-financial-source="reported_ytd"]').count()===2);
  await page.locator('.company-period-actions select').selectOption('Q3');
  // Inspect actual computed styles, comparison values and direction on all
  // nine issuer pages in both modes, not merely the shared CSS declaration.
  let standardStyle=null;
  for(const c of ['Fremtind','Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand','KLP Skadeforsikring','Alm. Brand']){
    await page.evaluate(name=>show(name,true),c);
    for(const type of ['Q3','H3']){
      await page.locator('.company-period-actions select').selectOption(type);
      const result=await page.evaluate(()=>{
        const cards=[...document.querySelectorAll('.company-financial-card:not(.market-card)')];
        const cr=cards.find(n=>n.dataset.financialMetric==='combined_ratio');
        const style=n=>{const s=getComputedStyle(n);return [s.fontFamily,s.fontSize,s.fontWeight,s.lineHeight];};
        const numeric=s=>FBMarketOverview.financialNumber(s.replace(/^\(|\)$/g,''));
        const rows=cards.map(n=>{
          const now=numeric(n.querySelector('.financial-current')?.textContent||''),prior=numeric(n.querySelector('.prior')?.textContent||'');
          const metric=n.dataset.financialMetric,expected=FBMarketOverview.financialTrend(now,prior,['combined_ratio','loss_ratio','expense_ratio'].includes(metric));
          const arrow=n.querySelector('.qoq');
          return {metric,now,prior,correct:expected?arrow?.textContent===expected.icon&&arrow.classList.contains(expected.tone):!arrow};
        });
        return {rows,style:cr?['.name','.financial-current','.prior'].map(s=>style(cr.querySelector(s))):null};
      });
      if(!standardStyle&&result.style)standardStyle=JSON.stringify(result.style);
      check(c+' '+type+' shared KPI typography',!!result.style&&JSON.stringify(result.style)===standardStyle,JSON.stringify(result.style));
      check(c+' '+type+' consistent same-period trend arrows',result.rows.length>=5&&result.rows.every(r=>r.correct),JSON.stringify(result.rows));
      console.log('COMPANY_COMPARISON_COVERAGE',c,type,JSON.stringify(result.rows.map(r=>[r.metric,r.now,r.prior])));
      if(marketArchive.active_period==='Q3 2026'){
        const core=['insurance_revenue_growth','insurance_service_result','combined_ratio','loss_ratio','expense_ratio'];
        check(c+' '+type+' complete current and previous-year core comparisons',core.every(k=>result.rows.some(r=>r.metric===k&&Number.isFinite(r.now)&&Number.isFinite(r.prior))),JSON.stringify(result.rows));
        if(['KLP Skadeforsikring','Alm. Brand'].includes(c))check(c+' '+type+' original prior-year solvency available',result.rows.some(r=>r.metric==='solvency_ratio'&&Number.isFinite(r.prior)),JSON.stringify(result.rows));
        if(['Fremtind','Gjensidige'].includes(c)&&type==='H3')check(c+' comparable annualised HIÅ return present',result.rows.some(r=>r.metric==='return_on_equity'&&Number.isFinite(r.prior)),JSON.stringify(result.rows));
      }
    }
    await page.locator('.company-period-actions select').selectOption('Q3');
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
  for(const issuer of ['Fremtind','Gjensidige','Protector']){
    await page.locator('[id="nav-'+issuer+'"]').click();
    check(issuer+' own navigation tab active',await page.locator('[id="nav-'+issuer+'"].active').count()===1);
    if(issuer==='Fremtind'){
      await page.locator('.company-period-actions select').selectOption('H3');
      check('Fremtind HIÅ selector retains own page',await page.locator('#nav-Fremtind.active').count()===1&&await page.locator('.dynamic-kpis [data-financial-period="ytd"]').count()>0);
      await page.locator('.company-period-actions select').selectOption('Q3');
      if(marketArchive.active_period==='Q3 2026')check('Fremtind PM/BM verified segment CR',await page.locator('tr[data-financial-source="verified-fremtind-apm"]').count()===2&&(await page.locator('tr[data-financial-source="verified-fremtind-apm"]').allTextContents()).join(' ').includes('71,6'));
    }
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
    check(issuer+' has no duplicate revenue growth section',
      await page.locator('.source-growth-matrix').count()===0,issuer);
    if(prior&&older&&older.value>0&&prior.unit===older.unit){
      const expected=((prior.value/older.value-1)*100).toLocaleString('nb-NO',
        {minimumFractionDigits:1,maximumFractionDigits:1});
      const card=page.locator('.dynamic-kpis > .metric').filter({has:page.locator('.name', {hasText:'Inntektsvekst'})}).first();
      const cardText=await card.innerText();
      check(issuer+' displays verified last-year revenue growth in result overview',
        cardText.includes(expected),JSON.stringify({expected,cardText}));
    }
  }
  await page.evaluate(()=>show('summary',true));
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
  check('Storebrand duplicate quarterly note removed',
    !tableQ.includes('Storebrand Forsikring AS – IFRS 17-forsikringsinntekter'),'Quarterly table');
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
  check('Storebrand duplicate HIÅ note removed',
    !ytdText.includes('Storebrand Forsikring AS – IFRS 17-forsikringsinntekter'),'HIÅ table');
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