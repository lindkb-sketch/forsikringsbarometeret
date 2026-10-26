/* Real Chrome: seven issuer detail pages, quarter/YTD, source-backed values,
   publication gating, and historic reference on BOTH cards. */
const {chromium}=require('playwright');
const base=process.env.BAROMETER_URL||'http://127.0.0.1:8765/';
const companies=['Fremtind','Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand'];
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage();
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.FBQuarterly?.period&&window.FBQuarterly?.verified&&document.querySelector('#results-comparison tbody tr'),null,{timeout:30000});
  let checked=0;
  for(const mode of ['quarter','ytd']){
   for(const company of companies){
    const state=await page.evaluate(({mode,company})=>{
      period=mode==='ytd'?'H3':'Q3';
      show(company);
      const model=FBQuarterly.selectedData[mode][company]||{};
      const cards=Array.from(document.querySelectorAll('.dynamic-kpis > .metric')).slice(0,2).map(el=>({
       name:el.querySelector('.name')?.innerText,
       value:el.querySelector('.value')?.innerText,
       previous:el.querySelector('.prior')?.innerText,
       source:el.getAttribute('data-financial-source'),
       mode:el.getAttribute('data-financial-period')
      }));
      return {model,cards,title:document.querySelector('.section-head h2')?.innerText};
    },{company,mode});
    const [growth,result]=state.cards;
    const required=state.model.revenue;
    if(!growth||!result||growth.mode!==mode||result.mode!==mode||
       growth.source!=='verified-quarterly-feed'||result.source!=='verified-quarterly-feed')
      throw Error(company+' '+mode+' missing source-driven cards: '+JSON.stringify(state));
    if(!required){
      if(growth.value!=='Ikke publisert'||result.value!=='Ikke publisert'||
        growth.previous!=='(—)'||result.previous!=='(—)')
        throw Error(company+' '+mode+' leaked current/prior value without issuer report: '+JSON.stringify(state));
    }else{
      if(state.model.growth && !growth.value.includes(state.model.growth))
       throw Error(company+' '+mode+' growth mismatches verified model: '+JSON.stringify(state));
      if(state.model.growthPrev&&!growth.previous.includes(state.model.growthPrev))
       throw Error(company+' '+mode+' prior growth mismatch: '+JSON.stringify(state));
      if(state.model.result&&!result.value.includes(state.model.result))
       throw Error(company+' '+mode+' result mismatch: '+JSON.stringify(state));
      if(state.model.resultPrev&&!result.previous.includes(state.model.resultPrev))
       throw Error(company+' '+mode+' prior result mismatch: '+JSON.stringify(state));
    }
    if(company==='Fremtind'){
      // A generic seven-company green E2E must not hide missing 2024
      // comparatives after Q3 2026 has been reported.
      if(state.model.revenue){
        const prior=state.model.growthPrev;
        if(!prior || !growth.previous.includes(prior) || prior==='—')
          throw Error('Fremtind prior-year growth absent for '+mode+': '+JSON.stringify(state));
        if(mode==='quarter'&&prior!=='11,1 %')
          throw Error('Fremtind Q3 2025/Q3 2024 growth differs from audited issuer data: '+prior);
        if(mode==='ytd'&&prior!=='26,4 %')
          throw Error('Fremtind HIÅ Q3 2025/2024 growth differs from audited issuer data: '+prior);
      }
    }
    if(company==='Fremtind'&&state.model.revenue){
      const expectedPrior=mode==='quarter'?'11,1 %':'26,4 %';
      const homepage=await page.evaluate(({company})=>{
        show('home');
        const row=[...document.querySelectorAll('#results-comparison tbody tr')]
           .find(tr=>tr.cells[0]?.textContent?.includes(company));
        return row?.cells[1]?.textContent?.replace(/\\s+/g,' ').trim()||'';
      },{company});
      if(!homepage.includes(expectedPrior))
        throw Error('Fremtind previous-year growth missing on homepage '+mode+': '+homepage);
      console.log('FREMTIND_HISTORICAL_GROWTH_VERIFIED',mode,expectedPrior,homepage);
    }
    checked++;
    console.log('SEVEN_COMPANY_DETAIL_PASS',company,mode,growth.value,result.value);
   }
  }
  await page.evaluate(()=>{period='Q3';show('home')});
  if((await page.locator('#results-comparison tbody tr').count())!==7)
   throw Error('Seven company rows not rendered on homepage');
  if(errors.length)throw Error('Uncaught page exceptions: '+errors.join(' | '));
  console.log('SEVEN_COMPANY_DETAIL_E2E_PASS',checked,'source-driven company cards; main table 7 rows');
 }finally{await browser.close()}
})().catch(e=>{console.error('SEVEN_COMPANY_DETAIL_E2E_FAIL',e.stack);process.exit(1)});
