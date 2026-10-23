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