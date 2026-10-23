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
assert(info.graph.length===5&&info.graph.at(-1)==='Q4 2026','Graph period mismatch: '+info.graph);
assert(info.brief==='Q4 2026','Editorial period mismatch: '+info.brief);
for(let i=0;i<companies.length;i++){
const c=companies[i],view=info.companies[c];
const parse=v=>Number(String(v).replace(/[\s\u00a0]/g,'').replace('%','').replace(',','.'));
assert(view,'Missing '+c+' in browser state');
assert(Math.abs(parse(view.cr)-(80+i))<0.15,c+' CR mismatch: '+view.cr);
assert(Math.abs(parse(view.revenue)-(1000+110*i))<0.6,c+' revenue mismatch: '+view.revenue);
assert(view.source?.includes('simulation.invalid'),c+' missing isolated synthetic source');
}
console.log('FUTURE_BROWSER PASS 7/7 company prices, 2026 Q4 selected, graph and editorial period');
}finally{await browser.close()}
})().catch(err=>{console.error('FUTURE_BROWSER FAIL',err.message);process.exit(1)});
