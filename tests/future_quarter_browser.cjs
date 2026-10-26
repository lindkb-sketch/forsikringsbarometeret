/* Exact synthetic Q4 2026 end-to-end UI assertions; never contacts issuers. */
const {chromium}=require('playwright');
const base=process.env.BAROMETER_URL;
if(!base)throw Error('BAROMETER_URL required');
(async()=>{
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--no-sandbox']});
try{
const page=await browser.newPage();
const res=await page.goto(base,{waitUntil:'domcontentloaded',timeout:40000});
if(res.status()!==200)throw Error('Homepage HTTP '+res.status());
await page.waitForFunction(()=>window.FBQuarterly?.period&&typeof MON_Q3!=='undefined'&&window.FBNews?.editorial,null,{timeout:35000});
const info=await page.evaluate(()=>({period:FBQuarterly.period,companies:JSON.parse(JSON.stringify(MON_Q3)),graph:profitabilityQuarters.slice(),brief:FBNews.editorial?.period}));
const companies=['Fremtind','Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand'];
const assert=(condition,message)=>{if(!condition)throw Error(message)};
assert(info.period.year===2026&&info.period.quarter===4,'Wrong selected quarter: '+JSON.stringify(info.period));
assert(info.graph.length===4&&info.graph.join(',')==='Q1 2026,Q2 2026,Q3 2026,Q4 2026','Graph period mismatch: '+info.graph);
assert(info.brief==='Q4 2026','Editorial period mismatch: '+info.brief);
for(let i=0;i<companies.length;i++){
const c=companies[i],view=info.companies[c];
const parse=v=>Number(String(v).replace(/[\s\u00a0]/g,'').replace('%','').replace(',','.'));
assert(view,'Missing '+c+' in browser state');
assert(Math.abs(parse(view.cr)-(80+i))<0.15,c+' CR mismatch: '+view.cr);
assert(Math.abs(parse(view.revenue)-(1000+110*i))<0.6,c+' revenue mismatch: '+view.revenue);
assert(view.source?.includes('simulation.invalid'),c+' missing isolated synthetic source');
}
for(const mode of ['quarter','ytd']){
 for(const company of companies){
  const detail=await page.evaluate(({mode,company})=>{
   period=mode==='ytd'?'H3':'Q3';
   show(company);
   const expected=FBQuarterly.selectedData[mode][company]||{};
   const cards=Array.from(document.querySelectorAll('.dynamic-kpis > .metric')).slice(0,2)
     .map(el=>({value:el.querySelector('.value')?.textContent?.trim(),
       previous:el.querySelector('.prior')?.textContent?.trim(),
       period:el.getAttribute('data-financial-period'),
       source:el.getAttribute('data-financial-source')}));
   return {expected,cards};
  },{company,mode});
  assert(detail.cards.length===2,company+' '+mode+' detail cards missing');
  for(const card of detail.cards)
   assert(card.source==='verified-quarterly-feed'&&card.period===mode,
     company+' '+mode+' has stale/fixed company card');
  if(detail.expected.revenue){
   assert(detail.cards[0].value?.includes(detail.expected.growth||'') && detail.cards[1].value?.includes(detail.expected.result||''),
     company+' '+mode+' figures do not match source model');
   if(detail.expected.growthPrev)
    assert(detail.cards[0].previous.includes(detail.expected.growthPrev),company+' '+mode+' wrong prior growth');
   if(detail.expected.resultPrev)
    assert(detail.cards[1].previous.includes(detail.expected.resultPrev),company+' '+mode+' wrong prior result');
  }else{
   assert(detail.cards.every(c=>c.value==='Ikke publisert'),company+' '+mode+' leaked unreleased report');
  }
 }
}
await page.evaluate(()=>{period='Q3';show('home')});
console.log('FUTURE_BROWSER PASS 7/7 Q4 group figures + 14 issuer Q4 quarter/HIÅ detail views, graph and editorial');
}finally{await browser.close()}
})().catch(err=>{console.error('FUTURE_BROWSER FAIL',err.message);process.exit(1)});
