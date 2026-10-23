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
       'official_news.json','stock_prices.json','live.json'].map(async f=>{
   const r=await page.request.get(BASE+'data/'+f+'?browser_audit='+Date.now());
   if(r.status()!==200)throw Error(f+' HTTP '+r.status());
   return r.json();
  }));
  const [feed,editorial,news,stocks,calendarFeed]=files;
  await page.waitForFunction(()=>window.FBQuarterly?.period&&
       document.querySelector('#results-comparison tbody tr')&&
       window.FBNews?.editorial && document.querySelector('.mon-calendar'),null,{timeout:35000});
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
     calendar:document.querySelector('.mon-calendar')?.innerText||'',
     newsGroups:FBNews.newsGroups(),
     technical:!!document.querySelector('#verified-financial-panel, #automated-editorial, .live-market-updates')
  }));
  check('Original KPI card/grid design remains intact',!view.oldReplacement&&view.kpis>=6&&view.tableRows>=7,JSON.stringify({kpis:view.kpis,rows:view.tableRows}));
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
  check('Quarter labels never disappear when data are missing',view.plotLabels.length===5,view.plotLabels.join(','));
  check('Strategic original cards present',view.strategic.includes('Strategiske bevegelser')&&view.media.includes('Forsikring i mediebildet'),view.strategic.slice(0,150));
  check('Quarterly brief actually rendered',editorial.brief.length===0||editorial.brief.some(x=>displayed(view.brief).includes(displayed(x.text))),view.brief.slice(0,250));
  check('Technical duplicate sections removed',!view.technical);
  check('Strategic news visible in original cards',view.newsGroups.strategic.length===0||
     view.newsGroups.strategic.some(n=>view.strategic.includes(n.headline)),view.strategic.slice(0,280));
  check('News visible in original media cards',view.newsGroups.other.length===0||
     view.newsGroups.other.some(n=>view.media.includes(n.headline)),view.media.slice(0,280));
  check('No repeated headlines across news sections',!view.newsGroups.strategic.some(a=>
     view.newsGroups.other.some(b=>a.source_url===b.source_url||a.headline===b.headline)));
  const missing=companies.filter(c=>['combined_ratio','insurance_revenue'].some(metric=>
    !feed.observations.some(r=>r.company===c&&r.scope==='group'&&
      r.year===year&&r.quarter===quarter&&r.period_type==='quarter'&&
      r.metric===metric&&['reported','calculated'].includes(r.status)&&r.source_url)));
  const calendarName=c=>c==='Sampo'?'Sampo / If':c;
  check('All missing issuers shown, including those without dates',
    missing.every(c=>view.calendar.includes(calendarName(c))),view.calendar.slice(0,400));
  const announced=Object.entries(calendarFeed.companies||{});
  const future=announced.filter(([name,config])=>{
    const next=config.next_event;
    const match=/^Q([1-4]) (\d{4})$/.exec(next?.period||'');
    return next&&!next.locked&&match&&Number(match[2])*4+Number(match[1])>year*4+quarter;
  });
  check('Future reports are preserved when current results are published',
    future.every(([name,config])=>view.calendar.includes(name+'\n'+config.next_event.period)),
    view.calendar.slice(0,400));
  const alreadyPublished=announced.filter(([name,config])=>
    config.next_event?.period==='Q'+quarter+' '+year&&
    !missing.includes(name==='Sampo / If'?'Sampo':name));
  check('Published current quarter is not repeated in calendar',
    alreadyPublished.every(([name])=>!view.calendar.includes(name+'\nQ'+quarter+' '+year)),
    view.calendar.slice(0,400));
  await page.evaluate(()=>show('Gjensidige',true));
  const companyComment=await page.locator('.quarter-comment').first().innerText();
  const companyBrief=editorial.periods?.['Q'+quarter+' '+year]?.by_company?.Gjensidige;
  if(companyBrief)check('Company page has current sourced financial commentary',
       displayed(companyComment).includes(displayed(companyBrief.comment))&&displayed(companyComment).includes(displayed(companyBrief.summary)),
       companyComment.slice(0,400));
  check('Company commentary has no duplicated quarter prefix',!companyComment.includes('Q'+quarter+' Q'+quarter+' '+(year-1)),companyComment.slice(0,350));
  const quotesOnCompany=await page.locator('.stock-section').first().innerText();
  const quote=stocks.prices?.Gjensidige;
  if(quote)check('Last delayed closing price in existing company stock panel',
       quotesOnCompany.includes(String(quote.close))&&quotesOnCompany.includes(quote.trading_date),
       quotesOnCompany.slice(0,420));
  await page.evaluate(()=>show('home',true));
  const tableQ=norm(await page.locator('#results-comparison').innerText());
  for(const c of ['Fremtind','Storebrand']){
   const r=feed.observations.find(x=>x.company===c&&x.year===year&&x.quarter===quarter&&
     x.scope==='group'&&x.period_type==='quarter'&&x.metric==='insurance_revenue');
   if(r)check(c+' revenue visible in original comparison table',tableQ.includes(nf(r.value)),tableQ.slice(-700));
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
    const arrows=await cell.locator('.qoq').count();
    check(c+' source-based prior-year revenue and arrow',txt.includes(nf(prev.value))&&arrows===1,txt.slice(0,250));
   }
  }
  const subsidiaryQ=feed.observations.find(r=>r.company==='Storebrand'&&r.scope==='norway'&&
     r.source_entity==='Storebrand Forsikring AS'&&r.year===year&&r.quarter===quarter&&
     r.period_type==='quarter'&&r.metric==='insurance_revenue');
  if(subsidiaryQ)check('Storebrand Forsikring AS IFRS17 quarter revenue beside group APM',
    tableQ.includes(nf(subsidiaryQ.value))&&tableQ.includes('Storebrand Forsikring AS')&&tableQ.includes('IFRS 17'),tableQ.slice(-900));
  await page.screenshot({path:'data/browser_home_q3.png',fullPage:true});
  report.screenshots.push('data/browser_home_q3.png');
  await page.selectOption('#results-comparison select','H3');
  const ytdText=norm(await page.locator('#results-comparison').innerText());
  const ytd=feed.observations.filter(x=>x.scope==='group'&&x.year===year&&x.quarter===quarter&&x.period_type==='ytd');
  for(const c of companies){
   const metric=ytd.find(x=>x.company===c&&x.metric==='insurance_revenue');
   if(metric)check(c+' HIÅ revenue visible',ytdText.includes(nf(metric.value)),ytdText.slice(-300));
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
    check(company+' HIÅ prior-year comparison and arrow',
      norm(await cell.innerText()).includes(nf(prior.value))&&(await cell.locator('.qoq').count())===1,company);
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