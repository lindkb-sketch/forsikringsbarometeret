/* Real mobile-browser checks, using the same financial data as desktop. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const BASE=process.env.BAROMETER_URL||'https://lindkb-sketch.github.io/forsikringsbarometeret/';
const COMPANIES=['Fremtind','Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand','KLP Skadeforsikring','Alm. Brand'];
async function main(){
 const browser=await chromium.launch({channel:'chrome',headless:true,args:['--no-sandbox']});
 let checks=0;
 const verify=(ok,name,detail='')=>{checks++;assert.ok(ok,name+' '+detail)};
 async function viewport(page,label){
  const result=await page.evaluate(()=>({width:innerWidth,doc:document.documentElement.scrollWidth,body:document.body.scrollWidth,app:document.getElementById('app').getBoundingClientRect().right}));
  verify(result.doc<=result.width+1&&result.body<=result.width+1&&result.app<=result.width+1,'No whole-page horizontal overflow: '+label,JSON.stringify(result));
 }
 async function screenshot(page,name){
  fs.mkdirSync('data',{recursive:true});
  await page.screenshot({path:'data/browser_mobile_'+name+'.png',fullPage:true,animations:'disabled'});
 }
 try{
  for(const width of [320,390,430]){
   const page=await browser.newPage({viewport:{width,height:844},isMobile:true,hasTouch:true,deviceScaleFactor:1});
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.goto(BASE,{waitUntil:'domcontentloaded',timeout:45000});
   await page.waitForFunction(()=>window.FBQuarterly?.period&&document.querySelector('#market-overview[data-period]:not([data-period=""])'),null,{timeout:45000});
   await page.evaluate(()=>FBMarketOverview.refresh());
   await viewport(page,width+' home');
   const home=await page.evaluate(()=>{
    const bar=document.querySelector('.mo-bars'),chart=document.querySelector('#mo-cr-history .mo-line-svg'),area=document.querySelector('.mo-line-scroll');
    const labels=chart?[...chart.querySelectorAll('.mo-line-quarter')].map(x=>{const b=x.getBBox();return [b.x,b.x+b.width]}):[];
    const rows=[...document.querySelectorAll('.mo-company')];
    return {bar:bar&&getComputedStyle(bar).flexDirection,rows:rows.length,allFit:rows.every(el=>{const r=el.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth+1&&el.scrollWidth<=el.clientWidth+1}),mobileValues:rows.every(el=>{const cr=el.querySelector('.mo-mobile-cr'),split=el.querySelector('.mo-mobile-split');return cr&&split&&cr.getClientRects().length&&split.getClientRects().length}),lineFit:area&&area.scrollWidth<=area.clientWidth+1,chartWidth:chart?.viewBox.baseVal.width,labels:labels.length,labelsFit:labels.every(([a,b])=>a>=0&&b<=chart.viewBox.baseVal.width)};
   });
   verify(home.bar==='column'&&home.rows>0&&home.allFit&&home.mobileValues,'All market rows fit phone '+width,JSON.stringify(home));
   verify(home.lineFit&&home.chartWidth===320&&home.labels===5&&home.labelsFit,'CR chart and all five labels fit phone '+width,JSON.stringify(home));
   if(width===390)await screenshot(page,'market_390');
   const toggle=page.locator('#mo-cr-history [data-mo-cr-toggle]');
   if(await toggle.count()){await toggle.click();await viewport(page,width+' full CR chart');await toggle.click();}
   // Actual menu navigation rather than programmatic show() for the first page.
   await page.locator('.exec-mobile-toggle').click();
   await page.locator('#nav-summary').click();
   await page.waitForFunction(()=>document.querySelector('#results-comparison table tbody tr'));
   await viewport(page,width+' summary');
   verify(await page.locator('#results-comparison td[data-mobile-label]').count()>0,'Summary cards have visible metric labels');
   for(const company of COMPANIES){
    await page.evaluate(c=>show(c,true),company);
    for(const type of ['Q3','H3']){
     await page.locator('.company-period-actions select').selectOption(type);
     const title=company+' '+type+' '+width;
     await viewport(page,title);
     verify(await page.locator('.company-profitability .profit-quarter').count()===5,title+' has five historical quarters');
     verify(await page.locator('.company-profitability select').count()===0,title+' chart is issuer locked');
     const layout=await page.evaluate(()=>{
      const tables=[...document.querySelectorAll('.company-segments table')],grid=document.querySelector('.kpi-seven.dynamic-kpis');
      const overflow=el=>el.scrollWidth>el.clientWidth+2;
      return {cards:!!grid&&[...grid.children].every(el=>!overflow(el)),segments:tables.every(t=>[...t.tBodies].every(b=>[...b.rows].every(tr=>!overflow(tr)&&[...tr.cells].slice(1).every(td=>td.dataset.mobileLabel&&getComputedStyle(td).display==='flex'))))};
     });
     verify(layout.cards&&layout.segments,title+' KPI and segment cards fit',JSON.stringify(layout));
    }
    if(width===390&&company==='Gjensidige'){await page.locator('.company-period-actions select').selectOption('Q3');await screenshot(page,'gjensidige_390');}
   }
   await page.locator('.exec-mobile-toggle').click();
   await page.locator('#admin-entry').click();
   await page.locator('#admin-overlay').waitFor({state:'visible'});
   const geometry=await page.evaluate(()=>{const d=document.querySelector('.admin-dialog'),s=document.querySelector('.admin-scroll');return {dialog:d.scrollWidth-d.clientWidth,table:s.scrollWidth-s.clientWidth,fields:document.querySelectorAll('#admin-values input').length}});
   verify(geometry.dialog<=1&&geometry.table<=1&&geometry.fields===48,width+' mobile market share editor',JSON.stringify(geometry));
   if(width===390)await screenshot(page,'admin_390');
   await page.locator('#admin-overlay').getByRole('button',{name:'Lukk ×',exact:true}).click();
   await page.goto(new URL('#metode',BASE).href,{waitUntil:'domcontentloaded'});
   await page.waitForFunction(()=>document.querySelector('#nav-methodology.active')&&window.FBQuarterly?.period);
   await viewport(page,width+' methodology');
   verify(errors.length===0,width+' browser runtime errors',errors.join('; '));
   await page.close();
  }
  console.log('MOBILE_BROWSER_PASS',checks,'checks at widths 320/390/430, all nine companies, both modes, market charts, summary, admin and method');
 }finally{await browser.close();}
}
main().catch(e=>{console.error('MOBILE_BROWSER_FAIL',e.stack||e);process.exitCode=1});
