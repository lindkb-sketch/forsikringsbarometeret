/* Test owner entry in a real browser against the PR checkout, never writing published data. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const base=process.env.BAROMETER_URL;
if(!base)throw Error('BAROMETER_URL must identify the test checkout');
async function main(){
 const browser=await chromium.launch({channel:'chrome',headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});
  const response=await page.request.get(new URL('data/market_shares.json',base).href);
  assert(response.ok(),'Existing market data not available');
  const snapshot=await response.json();
  const input=(company,key,period)=>page.locator('[data-ac="'+company+'"][data-ak="'+key+'"][data-ap="'+period+'"]');
  const normalize=v=>v==null?'':Number(String(v).replace(/\s|%/g,'').replace(',','.')).toFixed(1).replace('.',',');
  await page.goto(new URL('?utm_source=chatgpt.com#metode',base).href,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.FBQuarterly?.period&&document.querySelector('#nav-methodology.active')&&document.querySelector('#metode'));
  assert.equal(await page.locator('#app h1').textContent(),'Forutsetninger og kilder');
  assert.equal(await page.locator('#app .top .tag').textContent(),
    await page.evaluate(()=>FBActivePeriod.label+' · Kildekontrollerte utdrag'));
  await page.reload({waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.FBQuarterly?.period&&document.querySelector('#nav-methodology.active')&&document.querySelector('#metode'));
  await page.locator('#nav-summary').click();
  await page.waitForFunction(()=>window.FBReportCalendar?.ready&&document.querySelector('[data-calendar-group="reported"]'));
  assert.equal(await page.evaluate(()=>location.hash),'','Leaving methodology must clear its deep link');
  const extended=await (await page.request.get(new URL('data/extended_insurer_financials.json',base).href)).json();
  const latest=await page.evaluate(()=>FBQuarterly.available[0]);
  const verifiedExtended=['KLP Skadeforsikring','Alm. Brand'].filter(n=>{
    const data=extended.insurers[n];
    return [data,...(data?.periods||[])].some(x=>x&&x.year===latest.year&&x.quarter===latest.quarter&&
      x.status==='verified_official_pdf_reconciled'&&Number.isFinite(x.metrics?.insurance_revenue)&&Number.isFinite(x.metrics?.combined_ratio)&&
      /^https:\/\//.test(x.source_url||'')&&/^[0-9a-f]{64}$/.test(x.source_sha256||''));
  });
  for(const n of verifiedExtended){
    assert.equal(await page.locator('[data-calendar-group="pending"] .mon-cal-company strong').filter({hasText:n}).count(),0,n+' incorrectly pending');
    assert.equal(await page.locator('[data-calendar-group="reported"] .mon-cal-company strong').filter({hasText:n}).count(),1,n+' missing in next-quarter calendar');
  }
  await page.evaluate(()=>{location.hash='metode'});
  await page.waitForFunction(()=>document.querySelector('#nav-methodology.active')&&document.querySelector('#metode'));
  const entry=page.locator('#admin-entry');
  assert(await entry.isVisible(),'Administration entry is not visible on desktop');
  await entry.click();
  await page.locator('#admin-overlay').waitFor({state:'visible'});
  assert.equal(await page.locator('#admin-market-period').inputValue(),snapshot.period);
  assert.equal(await page.locator('#admin-values input').count(),42);
  assert.equal(await page.locator('#admin-prior-label').textContent(),snapshot.prior_period);
  for(const c of Object.keys(snapshot.segments)){
   for(const k of ['total','pm','bm']){
    assert.equal(await input(c,k,'current').inputValue(),normalize(k==='total'?snapshot.shares[c]:snapshot.segments[c]?.[k]));
    assert.equal(await input(c,k,'prior').inputValue(),normalize(snapshot.previous[c]?.[k]));
   }
  }
  const alternate=await page.locator('#admin-market-period').evaluate((el,period)=>[...el.options].map(o=>o.value).find(v=>v!==period),snapshot.period);
  await page.locator('#admin-market-period').selectOption(alternate);
  assert((await page.locator('#admin-values input').evaluateAll(els=>els.map(e=>e.value))).every(v=>v===''),'New period inherited stale values');
  await input('Fremtind','total','current').fill('19,2');
  await input('Fremtind','total','prior').fill('18,1');
  await input('Fremtind','pm','current').fill('0');
  await input('Fremtind','bm','prior').fill('101');
  await page.getByRole('button',{name:'Last ned markedsandelsdata'}).click();
  assert.match(await page.locator('#admin-status').textContent(),/Ugyldig prosent/);
  await input('Fremtind','bm','prior').fill('');
  const downloaded=page.waitForEvent('download');
  await page.getByRole('button',{name:'Last ned markedsandelsdata'}).click();
  const file=await downloaded;
  assert.equal(file.suggestedFilename(),'market_shares.json');
  const data=JSON.parse(await fs.readFile(await file.path(),'utf8'));
  assert.equal(data.period,alternate);
  assert.equal(data.prior_period,alternate.replace(/\d{4}/,y=>String(Number(y)-1)));
  assert.equal(data.status,'published_manual_snapshot');
  assert.equal(data.shares.Fremtind,'19,2 %');
  assert.equal(data.previous.Fremtind.total,'18,1 %');
  assert.equal(data.segments.Fremtind.pm,'0,0 %');
  assert.equal(data.segments.Fremtind.bm,null);
  assert(!('source_sha256' in data));
  await page.getByRole('button',{name:'Forhåndsvis på siden'}).click();
  await page.locator('#admin-overlay').waitFor({state:'hidden'});
  assert.equal(await page.evaluate(()=>marketUpload.period),alternate);
  assert.equal(await page.evaluate(()=>marketShares.Fremtind),'19,2 %');
  await entry.click();
  await page.locator('#admin-overlay').waitFor({state:'visible'});
  assert.equal(await input('Fremtind','total','current').inputValue(),'19,2');
  await page.keyboard.press('Escape');
  await page.locator('#admin-overlay').waitFor({state:'hidden'});
  await page.reload({waitUntil:'domcontentloaded'});
  await entry.click();
  await page.locator('#admin-overlay').waitFor({state:'visible'});
  assert.equal(await input('Fremtind','total','current').inputValue(),normalize(snapshot.shares.Fremtind));
  assert.deepEqual(await (await page.request.get(new URL('data/market_shares.json',base).href)).json(),snapshot);
  await page.close();
  const mobile=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
  await mobile.goto(base,{waitUntil:'domcontentloaded'});
  await mobile.locator('.exec-mobile-toggle').click();
  await mobile.locator('#admin-entry').click();
  await mobile.locator('#admin-overlay').waitFor({state:'visible'});
  assert.equal(await mobile.locator('#admin-values input').count(),42);
  for(const width of [390,320]){
    await mobile.setViewportSize({width,height:844});
    const geometry=await mobile.evaluate(()=>{
      const scroller=document.querySelector('.admin-scroll'),dialog=document.querySelector('.admin-dialog');
      const left=dialog.getBoundingClientRect().left,right=dialog.getBoundingClientRect().right;
      const fields=[...document.querySelectorAll('#admin-values input')];
      return {overflow:scroller.scrollWidth-scroller.clientWidth,dialogOverflow:dialog.scrollWidth-dialog.clientWidth,
        fields:fields.every(el=>{const r=el.getBoundingClientRect();return r.width>0&&r.height>=44&&r.left>=left&&r.right<=right;}),
        labels:[...document.querySelectorAll('.admin-cell-label')].every(el=>getComputedStyle(el).display!=='none')};
    });
    assert(geometry.overflow<=1&&geometry.dialogOverflow<=1&&geometry.fields&&geometry.labels,JSON.stringify({width,...geometry}));
  }
  await mobile.locator('[data-ac="Fremtind"][data-ak="total"][data-ap="current"]').fill('20,1');
  assert.equal(await mobile.locator('[data-ac="Fremtind"][data-ak="total"][data-ap="current"]').inputValue(),'20,1');
  await mobile.getByRole('button',{name:'Lukk ×',exact:true}).click();
  await mobile.locator('#admin-overlay').waitFor({state:'hidden'});
  await mobile.goto(new URL('?admin=1',base).href,{waitUntil:'domcontentloaded'});
  await mobile.locator('#admin-overlay').waitFor({state:'visible'});
  await mobile.close();
  console.log('MARKET_SHARE_ADMIN_BROWSER PASS: desktop, mobile, direct link, existing data, period isolation, validation, JSON download, preview and unchanged published snapshot');
 }finally{await browser.close()}
}
main().catch(e=>{console.error(e);process.exitCode=1});
