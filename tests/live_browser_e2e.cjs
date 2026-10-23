const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const BASE = process.env.BAROMETER_URL || 'https://lindkb-sketch.github.io/forsikringsbarometeret/';
const RESULTS = process.env.BAROMETER_BROWSER_REPORT || 'data/browser_e2e_report.json';
const sleep = ms => new Promise(r=>setTimeout(r,ms));
async function main() {
 const report={url:BASE,at:new Date().toISOString(),checks:[],errors:[],screenshots:[]};
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const bad=[];
 page.on('pageerror',err=>bad.push(String(err)));
 const check=(name,ok,details='')=>{report.checks.push({name,pass:Boolean(ok),details});if(!ok)report.errors.push(name+': '+details)};
 try{
  const res=await page.goto(BASE,{waitUntil:'domcontentloaded',timeout:45000});
  check('Homepage responds',res && res.status()===200,'HTTP '+res?.status());
  const [feed,editorial,news,stocks] = await Promise.all(
   ['verified_financial_feed.json','quarterly_editorial.json','official_news.json','stock_prices.json']
    .map(async name=>{const resp=await page.request.get(BASE+'data/'+name,{headers:{'Cache-Control':'no-cache'}});assert.equal(resp.status(),200,name);return resp.json()}));
  await page.waitForFunction(()=>document.querySelector('.live-market-updates') &&
    typeof MON_Q3!=='undefined' && document.querySelector('#results-comparison tbody'),null,{timeout:35000}).catch(()=>{});
  const companies=['Fremtind','Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand'];
  const view=await page.evaluate(()=>{
    const text=document.body.innerText;
    return {text,quarter:typeof MON_Q3==='undefined'?null:JSON.parse(JSON.stringify(MON_Q3)),
      ytd:typeof MON_YTD_Q3==='undefined'?null:JSON.parse(JSON.stringify(MON_YTD_Q3)),
      profitability:typeof profitabilityVerified==='undefined'?null:JSON.parse(JSON.stringify(profitabilityVerified)),
      rows:[...document.querySelectorAll('#results-comparison tbody tr')].map(r=>r.innerText),
      newsroom:document.querySelector('.live-market-updates')?.innerText||'',
      select:[...document.querySelectorAll('#results-comparison select option')].map(x=>x.value)};
  });
  check('Q3 comparison table renders',view.rows.length>=7,'rows='+view.rows.length);
  for(const company of companies){
   const metrics=feed.observations.filter(r=>r.company===company&&r.year===2026&&r.quarter===3&&r.scope==='group'&&r.period_type==='quarter'&&r.status==='reported');
   const expected={combined_ratio:'cr',loss_ratio:'loss',expense_ratio:'cost',insurance_revenue:'revenue',insurance_service_result:'result'};
   const bucket=view.quarter?.[company]||{};
   for(const r of metrics){
    const key=expected[r.metric];if(!key)continue;
    const displayed=bucket[key];const numeric=Number(String(displayed||'').replace(/\s/g,'').replace(/%/g,'').replace(',','.'));
    const tolerance=['cr','loss','cost'].includes(key)?0.11:0.51;
    check(company+' Q3 '+r.metric,Number.isFinite(numeric)&&Math.abs(numeric-r.value)<=tolerance,displayed+' vs source '+r.value);
   }
   const priors=feed.observations.filter(r=>r.company===company&&r.year===2025&&r.quarter===3&&r.scope==='group'&&r.period_type==='quarter'&&r.status==='reported');
   for(const r of priors){
    const key=expected[r.metric];if(!key)continue;
    check(company+' Q3 prior '+r.metric,Boolean(bucket[key+'Prev']),String(bucket[key+'Prev']||'missing'));
   }
   if(!metrics.length)check(company+' missing Q3 must not show legacy values',!bucket.cr&&!bucket.revenue,JSON.stringify(bucket));
  }
  const ytd=feed.observations.filter(r=>r.year===2026&&r.quarter===3&&r.scope==='group'&&r.period_type==='ytd'&&r.status==='reported');
  for(const r of ytd.filter(r=>r.metric==='combined_ratio')){
   check(r.company+' HIÅ combined ratio',Boolean(view.ytd?.[r.company]?.cr),String(view.ytd?.[r.company]?.cr));
  }
  const headlines=news.items.filter(x=>x.approved);
  check('Live news visible',!headlines.length||headlines.some(x=>view.newsroom.includes(x.headline)),String(headlines.length));
  const prices=Object.entries(stocks.prices||{});
  check('Delayed stocks visible',prices.every(([c,x])=>view.newsroom.includes(c)&&view.newsroom.includes(String(x.close))),String(prices.length));
  check('Quarter brief source backed',!editorial.brief?.length||view.text.includes(editorial.brief[0].text),'brief count '+editorial.brief?.length);
  check('Quarter/year selectors',view.select.includes('Q3')&&view.select.includes('H3'),JSON.stringify(view.select));
  const calendar=await page.locator('.mon-calendar').first().innerText().catch(()=>'');
  if(view.quarter?.Gjensidige?.cr)
    check('Imported Gjensidige Q3 not listed as upcoming',
       !/Gjensidige[\\s\\S]{0,90}Q3 2026/.test(calendar),
       calendar.slice(0,250));
  const screenshot='data/browser_home_q3.png';await page.screenshot({path:screenshot,fullPage:true});report.screenshots.push(screenshot);
  if(view.select.includes('H3')){
   await page.selectOption('#results-comparison select','H3');
   const hiatxt=await page.locator('#results-comparison').innerText();
   check('HIÅ table shown',hiatxt.includes('Hiå'),hiatxt.slice(0,130));
   const shot='data/browser_home_ytd.png';await page.screenshot({path:shot,fullPage:true});report.screenshots.push(shot);
  }
  await page.waitForFunction(()=>document.querySelector('#live-primary-dashboard .live-fin-table') &&
    document.querySelectorAll('#live-primary-dashboard .live-fin-table').length>=3 &&
    document.querySelectorAll('#live-primary-dashboard .live-strategy-card').length>0,null,{timeout:20000});
  const live=await page.evaluate(()=>{
    const root=document.getElementById('live-primary-dashboard');
    const cells=[...root.querySelectorAll('.live-fin-table')].flatMap(t=>[...t.querySelectorAll('td')]);
    const find=(company,metric,period)=>cells.find(td=>td.getAttribute('data-company')===company &&
       td.getAttribute('data-metric')===metric &&td.getAttribute('data-period')===period)?.innerText||'';
    const norway=root.querySelector('.live-norway')?.innerText||'';
    const quotes=root.querySelector('.live-stock-panel')?.innerText||'';
    const strategy=root.querySelector('.live-strategy')?.innerText||'';
    const brief=root.querySelector('.live-quarterly-editorial')?.innerText||'';
    return {current:ForsikringsbarometerLive.activePeriod()?.label,
     fremtind:find('Fremtind','insurance_revenue','quarter'),
     fremtindYtd:find('Fremtind','insurance_revenue','ytd'),
     storebrand:find('Storebrand','insurance_revenue','quarter'),
     norway,quotes,strategy,brief,
     periods:[...root.querySelectorAll('#live-quarter-select option')].map(o=>o.value)};
  });
  const fm=feed.observations.find(r=>r.company==='Fremtind'&&r.year===2026&&r.quarter===3&&r.scope==='group'&&r.period_type==='quarter'&&r.metric==='insurance_revenue');
  check('Visible Fremtind revenue from source',Boolean(fm)&&live.fremtind.includes(new Intl.NumberFormat('nb-NO').format(fm.value)),live.fremtind.slice(0,250));
  check('Visible Fremtind HIÅ revenue',live.fremtindYtd.includes('18')&&live.fremtindYtd.includes('373'),live.fremtindYtd.slice(0,250));
  check('Visible Storebrand group revenue with APM disclaimer',live.storebrand.includes('2')&&live.storebrand.includes('896')&&live.storebrand.includes('APM'),live.storebrand.slice(0,250));
  check('Visible Storebrand Forsikring AS IFRS revenue',live.norway.includes('Storebrand Forsikring AS')&&live.norway.includes('1')&&live.norway.includes('550')&&live.norway.includes('IFRS 17'),live.norway.slice(0,300));
  check('Storebrand Forsikring AS YTD IFRS revenue',live.norway.includes('HIÅ')&&live.norway.includes('4')&&live.norway.includes('396,1'),live.norway.slice(0,700));
  check('Strategic news cards restored',live.strategy.includes('Strategiske bevegelser')&&live.strategy.includes('Les originaloverskrift'),live.strategy.slice(0,250));
  check('Stock quote date and updates visible',live.quotes.includes('Kursdato')&&live.quotes.includes('innhentingsforsøk'),live.quotes.slice(0,250));
  check('Quarterly brief and comment visibly restored',live.brief.includes('Kvartalsbrief')&&live.brief.includes('Kvartalskommentar'),live.brief.slice(0,250));
  check('Future quarters driven by feed not Q3-only',live.periods.length>1,JSON.stringify(live.periods));
  check('No browser runtime errors',bad.length===0,bad.join(' | ').slice(0,1000));
 }catch(e){report.errors.push('Fatal: '+String(e.stack||e));}
 finally{
  report.passed=report.errors.length===0;
  fs.mkdirSync('data',{recursive:true});
  fs.writeFileSync(RESULTS,JSON.stringify(report,null,2)+'\n');
  await browser.close();
 }
 console.log('BROWSER_E2E',report.passed?'PASS':'FAIL',report.checks.length,'checks',report.errors.slice(0,20));
 process.exitCode=report.passed?0:1;
}
main().catch(e=>{console.error(e);process.exitCode=1});