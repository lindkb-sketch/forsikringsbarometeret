const test=require('node:test'),assert=require('node:assert/strict');
const {model,comments}=require('../scripts/market_overview.js');
const date={year:2026,quarter:3};
const rows=(company,revenue,cr,loss,cost,unit='NOKm',scope='group',segment=null,year=2026,quarter=3)=>
 Object.entries({insurance_revenue:revenue,combined_ratio:cr,loss_ratio:loss,expense_ratio:cost}).map(([metric,value])=>({company,year,quarter,scope,segment,metric,value,unit:metric==='insurance_revenue'?unit:'percent',period_type:'quarter',status:'reported',source_type:'official_quarterly_report',source_url:'https://issuer.invalid/report.pdf',source_sha256:'a'.repeat(64),source_page:3}));
const fx={periods:{'Q3 2026':{rates:{EUR:11,DKK:1.5,SEK:1}}}};
const feed={observations:[...rows('Fremtind',6000,73,52,21),...rows('Gjensidige',11000,74,62,12),...rows('Tryg',10000,77,64,13,'DKKm'),...rows('Sampo',2500,82,57,25,'EURm'),...rows('Protector',3800,83,72,11),...rows('Frende',1000,70,50,20),...rows('Storebrand',2900,80,60,20),...rows('Fremtind',5000,80,59,21,'NOKm','group',null,2025),...rows('Protector',1200,79,68,11,'NOKm','norway'),...rows('Tryg',2200,77,64,13,'DKKm','norway'),...rows('Gjensidige',5000,65,53,12,'NOKm','norway'),...rows('Gjensidige',3000,60,48,12,'NOKm','reported_segment','Private Norway'),...rows('Gjensidige',2000,72,60,12,'NOKm','reported_segment','Commercial Norway'),...rows('Sampo',1000,75,53,22,'EURm','reported_segment','Private Nordic')]};
const comp={companies:[{company:'Alm. Brand',status:'verified_official_pdf_reconciled',period:'Q3 2026',currency:'DKK',source_url:'https://issuer.invalid/alm.pdf',metrics:{insurance_revenue:3000,combined_ratio:75,loss_ratio:59,expense_ratio:16,insurance_revenue_growth:1.6}}]};
test('top five by converted income, sorted by ascending reported CR, not top five by CR',()=>{
 const m=model(feed,comp,fx);
 assert.deepEqual(m.selected.map(c=>c.company),['Fremtind','Gjensidige','Alm. Brand','Tryg','Sampo']);
 assert.ok(Math.abs(m.selected[0].growth-20)<1e-9);
 assert.equal(m.selected.find(c=>c.company==='Sampo').revenueNok,27500);
});
test('Norway and segment filters never substitute group data',()=>{
 assert.deepEqual(model(feed,comp,fx,'norway','all').selected.map(c=>c.company),['Gjensidige','Frende','Tryg','Protector']);
 assert.deepEqual(model(feed,comp,fx,'norway','pm').selected.map(c=>c.company),['Gjensidige']);
 assert.deepEqual(model(feed,comp,fx,'norway','bm').selected.map(c=>c.company),['Gjensidige','Protector']);
 assert.deepEqual(model(feed,comp,fx,'group','pm').selected.map(c=>c.company),[]);
 assert.deepEqual(model(feed,comp,fx,'group','bm').selected.map(c=>c.company),['Protector']);
});
test('no false income rank when foreign FX missing',()=>{
 const m=model(feed,comp,{periods:{}});
 assert.equal(m.selected.length,0);assert.ok(m.fxMissing.includes('Sampo'));
});
test('new verified quarter never carries previous quarter company or event forward',()=>{
 const next={observations:[...feed.observations,...rows('Protector',4000,80,68,12,'NOKm','group',null,2026,4)]};
 const m=model(next,comp,fx);
 assert.deepEqual(m.period,{year:2026,quarter:4});assert.deepEqual(m.selected.map(c=>c.company),['Protector']);
 const old={period:'Q3 2026',brief:[{theme:'large_claims',companies:['Protector'],period:'Q3 2026',text:'OLD EVENT',source_url:'https://issuer.invalid'}]};
 assert.ok(!JSON.stringify(comments(m,old,'group','all')).includes('OLD EVENT'));
});
test('missing CR components and mismatched totals excluded; missing growth never zero',()=>{
 const x={observations:[...rows('Fremtind',6000,73,52,21).filter(r=>r.metric!=='expense_ratio'),...rows('Gjensidige',11000,70,62,12),...rows('Protector',3800,83,72,11)]};
 const m=model(x,{},fx);assert.deepEqual(m.selected.map(r=>r.company),['Protector']);assert.equal(m.selected[0].growth,null);
});
test('source commentary scoped to current quarter and eligible issuers',()=>{
 const m=model(feed,comp,fx);
 const editorial={period:'Q3 2026',brief:[{period:'Q3 2026',theme:'large_claims',companies:['Fremtind'],text:'Dokumentert hendelse',source_url:'https://issuer.invalid'},{period:'Q3 2026',theme:'weather',companies:['Unknown'],text:'BAD',source_url:'https://issuer.invalid'}]};
 const c=JSON.stringify(comments(m,editorial,'group','all'));assert.ok(!c.includes('Dokumentert hendelse'));assert.ok(!c.includes('BAD'));
 const context={insights:[{company:'Fremtind',period:'Q3 2026',source_document_period:'Q3 2026',period_type:'quarter',views:['group/all'],theme:'material_event',text:'Dokumentert rapporthendelse',source_type:'official_quarterly_report',source_url:'https://issuer.invalid/report.pdf',source_sha256:'a'.repeat(64),source_page:9}]};
 assert.match(JSON.stringify(comments(m,editorial,'group','all',context)),/Dokumentert rapporthendelse/);
 assert.doesNotMatch(JSON.stringify(comments(model(feed,comp,fx,'norway','all'),editorial,'norway','all',context)),/Dokumentert rapporthendelse/);
});

test('owner examples: Protector BM, Tryg split group only, Gjensidige all six',()=>{
 const segments={observations:[
  ...rows('Tryg',7000,78,65,13,'DKKm','reported_segment','Private'),
  ...rows('Tryg',3000,74,59,15,'DKKm','reported_segment','Commercial'),
  ...rows('Gjensidige',5000,70,59,11,'NOKm','reported_segment','Private'),
  ...rows('Gjensidige',6000,67,58,9,'NOKm','reported_segment','Commercial')
 ]};
 const eligible=(scope,market)=>model(feed,comp,fx,scope,market,segments).eligible;
 const matrix={Protector:[true,false,true,true,false,true],Tryg:[true,true,true,true,false,false],Gjensidige:[true,true,true,true,true,true]};
 const filters=[['group','all'],['group','pm'],['group','bm'],['norway','all'],['norway','pm'],['norway','bm']];
 for(const [name,want] of Object.entries(matrix)){
  assert.deepEqual(filters.map(([s,m])=>eligible(s,m).some(x=>x.company===name)),want,name);
 }
 for(const s of ['group','norway']){
  const total=eligible(s,'all').find(x=>x.company==='Protector');
  const bm=eligible(s,'bm').find(x=>x.company==='Protector');
  for(const k of ['revenue','cr','loss','cost','growth'])assert.equal(total[k],bm[k]);
 }
 assert.equal(eligible('group','pm').find(x=>x.company==='Gjensidige').revenue,5000);
 assert.equal(eligible('norway','pm').find(x=>x.company==='Gjensidige').revenue,3000);
 const corrupt={observations:segments.observations.map(r=>({...r,source_sha256:'b'.repeat(64)}))};
 assert.ok(!model(feed,comp,fx,'group','pm',corrupt).eligible.some(c=>c.company==='Tryg'));
});

test('explicit owner scope register overrides unrelated available segments',()=>{
 const almSource=comp.companies[0].source_url;
 const comparison={companies:[{...comp.companies[0],metric_sources:{insurance_revenue:{source_url:almSource,source_sha256:'a'.repeat(64)}}},
  {company:'KLP Skadeforsikring',status:'verified_official_pdf_reconciled',period:'Q3 2026',currency:'NOK',source_url:'https://issuer.invalid/klp.pdf',metrics:{insurance_revenue:1000,combined_ratio:89,loss_ratio:77,expense_ratio:12}}]};
 const segments={observations:[
  ...rows('Tryg',7000,78,65,13,'DKKm','reported_segment','Private'),
  ...rows('Tryg',3000,74,59,15,'DKKm','reported_segment','Commercial'),
  ...rows('Gjensidige',5000,70,59,11,'NOKm','reported_segment','Private'),
  ...rows('Gjensidige',6000,67,58,9,'NOKm','reported_segment','Commercial'),
  ...rows('Fremtind',3500,70,50,20,'NOKm','reported_segment','Private'),
  ...rows('Fremtind',2500,80,60,20,'NOKm','reported_segment','Commercial'),
  ...rows('Alm. Brand',2000,74,60,14,'DKKm','reported_segment','Private').map(r=>({...r,source_url:almSource})),
  ...rows('Alm. Brand',1000,77,60,17,'DKKm','reported_segment','Commercial').map(r=>({...r,source_url:almSource}))
 ]};
 const f={observations:[...feed.observations.map(r=>r.company==='Storebrand'&&r.metric==='insurance_revenue'?{...r,source_entity:'Storebrand ASA / Insurance segment'}:r),
 ...rows('Storebrand',1000,90,70,20,'NOKm','norway'),...rows('Frende',500,80,60,20,'NOKm','norway')]};
 const filters=[['group','all'],['group','pm'],['group','bm'],['norway','all'],['norway','pm'],['norway','bm']];
 const want={'Gjensidige':[1,1,1,1,1,1],'Tryg':[1,1,1,1,0,0],'Fremtind':[1,1,1,1,1,1],'Sampo':[1,0,0,0,0,0],'Protector':[1,0,1,1,0,1],'Frende':[1,0,0,1,0,0],'Storebrand':[1,0,0,1,0,0],'KLP Skadeforsikring':[1,0,0,1,0,0],'Alm. Brand':[1,1,1,0,0,0]};
 for(const [name,expected] of Object.entries(want))assert.deepEqual(filters.map(([s,m])=>+model(f,comparison,fx,s,m,segments).eligible.some(r=>r.company===name)),expected,name);
 const a=model(f,comparison,fx,'group','pm',segments).eligible.find(r=>r.company==='Fremtind');
 const b=model(f,comparison,fx,'norway','pm',segments).eligible.find(r=>r.company==='Fremtind');
 assert.equal(a.revenue,b.revenue);assert.equal(a.cr,b.cr);
 const n=model(f,comparison,fx,'norway','all',segments).eligible.find(r=>r.company==='Fremtind');
 assert.equal(n.revenue,6000);assert.equal(n.cr,(3500*70+2500*80)/6000);
});

test('only Fremtind PM/BM permits total CR without components',()=>{
 const obs=[...rows('Fremtind',3500,70,50,20,'NOKm','reported_segment','Private'),
  ...rows('Fremtind',2500,80,60,20,'NOKm','reported_segment','Commercial'),
  ...rows('Tryg',7000,78,65,13,'DKKm','reported_segment','Private')].filter(r=>!['loss_ratio','expense_ratio'].includes(r.metric));
 const s={observations:obs};
 for(const scope of ['group','norway'])for(const market of ['pm','bm']){
   const m=model(feed,comp,fx,scope,market,s);
   const a=m.eligible.find(r=>r.company==='Fremtind');
   assert.ok(a);assert.equal(a.loss,null);assert.equal(a.cost,null);assert.equal(a.split,false);
   assert.ok(!m.eligible.some(r=>r.company==='Tryg'));
 }
 const total=model(feed,comp,fx,'group','all',s).eligible.find(r=>r.company==='Fremtind');
 assert.equal(total.split,true);
 assert.ok(!model(feed,comp,fx,'norway','all',s).eligible.some(r=>r.company==='Fremtind'));
});

test('Frende, KLP and Storebrand group/Norway total share source metrics; no PM/BM substitution',()=>{
 const c={companies:[...comp.companies,{company:'KLP Skadeforsikring',status:'verified_official_pdf_reconciled',period:'Q3 2026',currency:'NOK',source_url:'https://issuer.invalid/klp.pdf',metrics:{insurance_revenue:1041,combined_ratio:89,loss_ratio:77,expense_ratio:12}}]};
 const f={observations:feed.observations.map(r=>r.company==='Storebrand'&&r.metric==='insurance_revenue'?{...r,source_entity:'Storebrand ASA / Insurance segment'}:r)};
 for(const company of ['Frende','KLP Skadeforsikring','Storebrand']){
  const g=model(f,c,fx,'group','all').eligible.find(r=>r.company===company);
  const n=model(f,c,fx,'norway','all').eligible.find(r=>r.company===company);
  assert.equal(n.revenue,g.revenue);assert.equal(n.cr,g.cr);
  for(const market of ['pm','bm'])assert.ok(!model(feed,c,fx,'norway',market).eligible.some(r=>r.company===company));
 }
 assert.equal(model(feed,c,fx,'norway','all').selected.length,5);
});
test('YTD uses period-matched values and FX, never an isolated quarter',()=>{
 const f={observations:[...feed.observations,...rows('Fremtind',18500,77,55,22).map(r=>({...r,period_type:'ytd'})),...rows('Tryg',30000,81,66,15,'DKKm').map(r=>({...r,period_type:'ytd'})),...rows('Frende',2700,88,65,23).map(r=>({...r,period_type:'ytd'}))]};
 const rates={periods:{'Q3 2026':{rates:{DKK:1.5,EUR:11},ytd_rates:{DKK:1.4,EUR:10.8}}}};
 const m=model(f,comp,rates,'group','all',null,'ytd');
 assert.equal(m.eligible.find(r=>r.company==='Fremtind').cr,77);
 assert.equal(m.selected.find(r=>r.company==='Tryg').revenueNok,42000);
 assert.ok(!m.eligible.some(r=>r.company==='Sampo'));
 assert.equal(model(f,comp,fx,'group','all',null,'ytd').selected.length,0);
});
test('scoped commentary is period, company, geography and business-line specific',()=>{
 const m=model(feed,comp,fx,'norway','pm');
 const context={insights:[
  {company:'Gjensidige',period:'Q3 2026',period_type:'quarter',views:['norway/pm'],theme:'large_claims',text:'Relevant PM hendelse',source_type:'official_quarterly_report',source_document_period:'Q3 2026',source_sha256:'a'.repeat(64),source_page:9,source_url:'https://issuer.invalid/a'},
  {company:'Gjensidige',period:'Q3 2026',period_type:'quarter',views:['group/bm'],theme:'large_claims',text:'BAD BM',source_type:'official_quarterly_report',source_document_period:'Q3 2026',source_sha256:'a'.repeat(64),source_page:9,source_url:'https://issuer.invalid/a'},
  {company:'Gjensidige',period:'Q3 2026',period_type:'ytd',views:['norway/pm'],theme:'weather',text:'BAD HIÅ',source_type:'official_quarterly_report',source_document_period:'Q3 2026',source_sha256:'a'.repeat(64),source_page:9,source_url:'https://issuer.invalid/a'}
 ]};
 const c=JSON.stringify(comments(m,{},'norway','pm',context));
 assert.ok(c.includes('Relevant PM hendelse'));assert.ok(!c.includes('BAD'));
});

test('trend commentary uses fixed headings, medians, matched periods and names isolated issuer drivers',()=>{
 const make=(mode,values)=>({period:{year:2026,quarter:3},mode,eligible:values.map(([company,growth,delta])=>({company,growth,cr:80,revenueBasis:'Forsikringsinntekter',deltas:{combined_ratio:delta,loss_ratio:delta,expense_ratio:0}}))});
 const q=make('quarter',[['Fremtind',8,-3],['Gjensidige',10,-4],['Tryg',12,-5]]);
 const y=make('ytd',[['Fremtind',6,-2],['Gjensidige',7,-2],['Tryg',8,-2],['Sampo',99,-2]]);
 const evidence=(company,driver,views,period_type='quarter')=>({company,driver,views,period_type,theme:'growth_driver',period:'Q3 2026',source_document_period:'Q3 2026',source_type:'official_results_presentation',text:driver,evidence:'reported phrase',source_url:'https://issuer.invalid/report.pdf',source_sha256:'a'.repeat(64),source_page:8});
 const ctx={insights:[evidence('Fremtind','price',['group/all']),evidence('Gjensidige','volume_up',['group/all']),evidence('Gjensidige','customer_inflow',['norway/pm']),evidence('Tryg','volume_down',['group/all'],'ytd')]};
 const c=comments(q,{},'group','all',ctx,y),t=JSON.stringify(c);
 assert.deepEqual(c.map(x=>x.label),['Inntektsvekst','CR – skade- og kostnadsprosent','Enkelthendelser og særtrekk']);
 assert.match(t,/Medianveksten blant aktørene er \+10,0/);
 assert.match(t,/3,0 prosentpoeng over HIÅ/);
 assert.match(t,/Fremtind rapporterer premie- og prisjusteringer/);
 assert.match(t,/Gjensidige rapporterer økt forsikringsvolum/);
 assert.doesNotMatch(t,/kundetilgang|lavere volum|Tryg|\d+ av \d+|\d+\/\d+|høyest vekst/);
 assert.match(t,/4,0 prosentpoeng lavere CR/);
 const bad={insights:[{...evidence('Fremtind','price',['group/all']),source_sha256:'bad'}]};
 assert.doesNotMatch(JSON.stringify(comments(q,{},'group','all',bad)),/premie- og prisjusteringer/);
});

test('quarter trend uses adjacent archived matched data rather than a changed issuer population',()=>{
 const mk=(year,quarter,mode,values)=>({period:{year,quarter},mode,eligible:values.map(([company,growth])=>({company,growth,cr:80,revenueBasis:'Forsikringsinntekter',deltas:{}}))});
 const curr=mk(2027,1,'quarter',[['Fremtind',7],['Tryg',9]]);
 const prev=mk(2026,4,'quarter',[['Fremtind',4],['Tryg',6],['Sampo',50]]);
 const text=JSON.stringify(comments(curr,{},'group','all',{},null,{model:prev}));
 assert.match(text,/økt med 3,0 prosentpoeng fra forrige kvartal/);
 assert.doesNotMatch(JSON.stringify(comments(curr,{},'group','all',{},null,{model:mk(2026,3,'quarter',[['Fremtind',4],['Tryg',6]])})),/fra forrige kvartal/);
});

test('only verified quarter reports and result presentations enter all three market comments',()=>{
 const m=model(feed,comp,fx);
 const base={company:'Fremtind',period:'Q3 2026',source_document_period:'Q3 2026',period_type:'quarter',views:['group/all'],source_url:'https://issuer.invalid/doc.pdf',source_sha256:'a'.repeat(64),source_page:8,evidence:'verified phrase'};
 const ctx={insights:[
  {...base,source_type:'official_results_presentation',theme:'growth_driver',driver:'price',text:'price'},
  {...base,source_type:'official_results_presentation',theme:'profit_driver',driver:'underlying_loss_improved',text:'underlying'},
  {...base,source_type:'official_quarterly_report',theme:'material_event',text:'Dokumentert hendelse i rapport'},
  {...base,source_type:'official_press_release',theme:'material_event',text:'FORBIDDEN NEWS'},
  {...base,source_type:'market_statistics',theme:'growth_driver',driver:'customer_growth',text:'FORBIDDEN MARKET DATA'},
  {...base,source_type:'official_results_presentation',source_document_period:'Q2 2026',theme:'material_event',text:'FORBIDDEN PREVIOUS'},
  {...base,source_type:'official_results_presentation',source_sha256:'invalid',theme:'material_event',text:'FORBIDDEN HASH'}
 ]};
 const view=JSON.stringify(comments(m,{period:'Q3 2026',brief:[{period:'Q3 2026',companies:['Fremtind'],theme:'regulation',text:'FORBIDDEN EDITORIAL',source_url:'https://issuer.invalid/news'}]},'group','all',ctx));
 assert.match(view,/premie- og prisjusteringer/);
 assert.match(view,/bedre underliggende skadeprosent/);
 assert.match(view,/Dokumentert hendelse i rapport/);
 assert.doesNotMatch(view,/FORBIDDEN|vekst i kundebestanden/);
});

test('causal commentary prioritises why, covers the expense ratio and selects material events without duplicating themes',()=>{
 const m={period:{year:2026,quarter:3},mode:'quarter',eligible:[{company:'Fremtind',growth:8,cr:75,deltas:{combined_ratio:-4,loss_ratio:-3,expense_ratio:-1}},{company:'Gjensidige',growth:6,cr:74,deltas:{combined_ratio:-2,loss_ratio:-2,expense_ratio:0}}]};
 const base={company:'Fremtind',period:'Q3 2026',source_document_period:'Q3 2026',period_type:'quarter',views:['group/all'],source_type:'official_quarterly_report',source_sha256:'a'.repeat(64),source_page:9,source_url:'https://issuer.invalid/report.pdf',evidence:'exact original source fragment'};
 const e=(theme,topic,priority,text,category='')=>({...base,theme,topic,priority,text,category});
 const ctx={insights:[
  e('growth_explanation','pm_volume',100,'Prisøkninger og høyere volum innen boligforsikring støtter inntektene.','volume'),
  e('growth_explanation','bm_restraint',99,'I bedriftsmarkedet reduserer strengere risikoutvelgelse volumveksten.','restraint'),
  e('loss_explanation','frequency',100,'Lavere skadefrekvens på bil reduserer skadeprosenten.','frequency'),
  e('cost_explanation','reclassification',100,'Lavere kostnadsprosent skyldes omklassifisering av lånerenter, ikke bare effektivisering.'),
  e('event_explanation','named_fire',100,'Brannen i Krokstadelva kostet 176 mill. kroner netto i kvartalet.'),
  e('event_explanation','pm_fire',99,'Brannen i Krokstadelva kostet 175 mill. kroner i privatporteføljen.'),
  {...e('event_explanation','bad',120,'FORBIDDEN'),source_document_period:'Q2 2026'}
 ]};
 const c=comments(m,{},'group','all',ctx);
 assert.equal(c[0].paragraphs.length,1);
 assert.match(c[0].paragraphs[0],/Prisøkninger.*volum.*risikoutvelgelse/);
 assert.match(c[1].paragraphs[0],/skadefrekvens.*omklassifisering/);
 assert.match(c[2].paragraphs[0],/Fremtind: Brannen.*176 mill/);
 assert.doesNotMatch(JSON.stringify(c),/FORBIDDEN|175 mill|Rapporterte vekstdrivere omfatter/);
});

test('causal editorial selection retains contrasting drivers and avoids repeating the same large-loss story',()=>{
 const m={period:{year:2026,quarter:3},mode:'ytd',eligible:[{company:'Tryg',growth:3,cr:89,deltas:{combined_ratio:14,loss_ratio:14,expense_ratio:0}},{company:'Fremtind',growth:5,cr:81,deltas:{combined_ratio:-1,loss_ratio:-1,expense_ratio:0}}]};
 const b={company:'Tryg',period:'Q3 2026',source_document_period:'Q3 2026',period_type:'ytd',views:['group/all'],source_type:'official_quarterly_report',source_sha256:'a'.repeat(64),source_page:6,source_url:'https://issuer.invalid/report.pdf',evidence:'source fragment'};
 const e=(theme,topic,priority,text,category='')=>({...b,theme,topic,priority,text,category});
 const ctx={insights:[
 e('growth_explanation','pm_product_volumes',104,'Privatveksten støttes av pris og volum innen eiendom.','volume'),
 e('growth_explanation','premium_adjustment',86,'GJENTATT PRIS','price'),
 e('growth_explanation','bm_selectivity',105,'Strengere risikoutvelgelse bremser veksten i bedrift.','restraint'),
 e('loss_explanation','workers_comp_adjusted',115,'Dansk avsetning forklarer rapportert svekkelse.','adverse'),
 e('loss_explanation','motor_frequency',102,'Lavere skadefrekvens gir motvirkende effekt.','frequency'),
 e('loss_explanation','weather',94,'Lavere værskader gir en midlertidig gevinst.','weather'),
 e('cost_explanation','control',99,'Kostnadskontrollen er stram.'),
 e('event_explanation','named_fire',105,'Brannen belastet netto storskader med 176 mill. kroner.'),
 e('event_explanation','bm_large_loss',107,'GJENTATT STORSKADE'),
 e('event_explanation','revenue_recognition_base',98,'En endring i inntektsføring påvirker sammenligningen.')
 ]};
 const c=comments(m,{},'group','all',ctx),s=JSON.stringify(c);
 assert.doesNotMatch(s,/GJENTATT/);
 assert.match(c[1].paragraphs[0],/Dansk avsetning.*Lavere skadefrekvens.*Kostnadskontrollen.*Lavere værskader/);
 assert.ok(c[1].paragraphs[0].split(/\s+/).length<=125);
 assert.match(c[2].paragraphs[0],/176 mill.*inntektsføring/);
});

test('market profitability uses five contiguous quarters and all nine issuers without filling missing periods',()=>{
 const {timeline,profitabilityHistory,trendChart}=require('../scripts/market_overview.js');
 assert.deepEqual(timeline({year:2026,quarter:3}),['Q3 2025','Q4 2025','Q1 2026','Q2 2026','Q3 2026']);
 assert.deepEqual(timeline({year:2026,quarter:4}),['Q4 2025','Q1 2026','Q2 2026','Q3 2026','Q4 2026']);
 assert.deepEqual(timeline({year:2027,quarter:1}),['Q1 2026','Q2 2026','Q3 2026','Q4 2026','Q1 2027']);
 const f={observations:[...rows('Fremtind',100,80,60,20,'NOKm','group',null,2026,1),...rows('Fremtind',100,75,55,20,'NOKm','group',null,2026,3)]};
 const h=profitabilityHistory(f,{},null,{year:2026,quarter:3});
 assert.equal(h.series.length,9);
 assert.deepEqual(h.series[0].points.map(p=>p?.cr??null),[null,null,80,null,75]);
 const html=trendChart(h);
 assert.equal((html.match(/class="mo-line-point"/g)||[]).length,2);
 assert.match(html,/d=" M[^"]+ M[^"]+"/);
 assert.doesNotMatch(html,/data-period="Q2 2026" data-cr=/);
 const next=profitabilityHistory(f,{},null,{year:2026,quarter:4});
 assert.equal(next.periods[0],'Q4 2025');assert.equal(next.series[0].points.at(-1),null);
});

test('CR chart uses a focused adaptive range, hides only whole extreme series and preserves every source value',()=>{
 const {crTrendView,trendChart}=require('../scripts/market_overview.js');
 const periods=['Q3 2025','Q4 2025','Q1 2026','Q2 2026','Q3 2026'];
 const fixture={
  Fremtind:[76.7,77,79.8,77.5,73],
  Gjensidige:[79.7,88.3,79.2,78.9,73.6],
  Tryg:[78.6,81.4,84,88.8,76.8],
  Sampo:[83,84.3,84.4,82.9,82.6],
  Frende:[85.3,90.8,93.9,81.3,84],
  Protector:[83.1,85,84.9,81.5,82.7],
  Storebrand:[89,93,93,87,87],
  'KLP Skadeforsikring':[85.9,124.019,100.37,99.3,89.09],
  'Alm. Brand':[82.2,82.49,83.1,101.7,75.3]
 };
 const history={periods,series:Object.entries(fixture).map(([company,values])=>({company,points:values.map(cr=>({cr,source_url:'https://example.com/official.pdf'}))}))};
 const before=JSON.stringify(history),focus=crTrendView(history),full=crTrendView(history,true);
 assert.deepEqual(focus.excluded.map(e=>e.company),['KLP Skadeforsikring']);
 assert.equal(focus.visible.length,8);
 assert.deepEqual(focus.axis,{low:70,high:105,step:5});
 assert.equal(full.visible.length,9);
 assert.ok(full.axis.high>=124.019&&full.axis.low<=73);
 assert.ok(focus.axis.high-focus.axis.low<full.axis.high-full.axis.low);
 for(const v of [focus,full])assert.ok(v.visible.every(s=>s.points.every(p=>p.cr>=v.axis.low&&p.cr<=v.axis.high)));
 const html=trendChart(history);
 assert.match(html,/Utvikling i CR · 8 selskaper/);
 assert.match(html,/Vis alle 9/);
 assert.match(html,/KLP Skadeforsikring · Q4 2025/);
 assert.doesNotMatch(html,/class="mo-line-series" data-company="KLP Skadeforsikring"/);
 assert.doesNotMatch(html,/class="mo-line-legend-item" data-company="KLP Skadeforsikring"/);
 assert.match(html,/<tr data-company="KLP Skadeforsikring">/);
 const fullHtml=trendChart(history,true);
 assert.match(fullHtml,/Tilpass utsnitt/);
 assert.match(fullHtml,/class="mo-line-series" data-company="KLP Skadeforsikring"/);
 assert.match(fullHtml,/data-cr="124.019"/);
 assert.equal(JSON.stringify(history),before,'Source history must never be modified');
 const calm={periods,series:history.series.map(s=>({...s,points:periods.map((_,i)=>({cr:80+i*.2}))}))};
 const calmView=crTrendView(calm);
 assert.equal(calmView.visible.length,9);assert.equal(calmView.excluded.length,0);
 assert.ok(calmView.axis.high-calmView.axis.low>=10);
 assert.ok(calmView.axis.high-calmView.axis.low<=15);
 const sparse={periods,series:history.series.slice(6)};
 assert.equal(crTrendView(sparse).excluded.length,0,'Do not hide companies when there are too few comparable peers');
 const lower={periods,series:history.series.map(s=>({...s,points:s.company==='KLP Skadeforsikring'?s.points.map((p,i)=>({...p,cr:i===1?30:83})):s.points.map(p=>({...p,cr:80+(p.cr%8)}))}))};
 assert.deepEqual(crTrendView(lower).excluded.map(e=>e.company),['KLP Skadeforsikring']);
});

test('calendar moves only reported issuers, matches exact next quarter, and hides completed pending list',()=>{
 const {reportQueues}=require('../scripts/market_overview.js');
 const calendar={'Fremtind':{events:[{period:'Q4 2026',date:'2027-02-01'},{period:'Q1 2027',date:'2027-04-29'}]},'Tryg':{events:[{period:'Q4 2026',date:'2027-01-22'}]},'Sampo / If':{events:[{period:'Q1 2027',date:'2027-05-05'}]}};
 const before=reportQueues('Q4 2026',['Tryg'],calendar);
 assert.equal(before.pending.length,8);assert.equal(before.nextPeriod,'Q1 2027');
 assert.equal(before.pending.find(r=>r.company==='Fremtind').date,'2027-02-01');
 assert.equal(before.next.find(r=>r.company==='Tryg').date,null);
 assert.equal(before.pending.find(r=>r.company==='Frende').date,null);
 const after=reportQueues('Q4 2026',['Tryg','Fremtind','Frende'],calendar);
 assert.equal(after.pending.length,6);assert.equal(after.next.length,3);
 assert.equal(after.next.find(r=>r.company==='Fremtind').date,'2027-04-29');
 assert.equal(after.next.find(r=>r.company==='Frende').date,null);
 const all=reportQueues('Q4 2026',after.pending.map(r=>r.company).concat(after.next.map(r=>r.company)),calendar);
 assert.equal(all.pending.length,0);assert.equal(all.next.length,9);
});

test('Sampo company detail has exact Nordic segment scope, quarter and complete income-weighted HIÅ',()=>{
 const {sampoNordicSegments}=require('../scripts/market_overview.js');
 const data=[];
 for(const y of [2025,2026])for(let q=1;q<=3;q++)for(const [seg,base] of [['Private Nordic',100],['Nordic Commercial',50]]){
   const revenue=base+(y===2026?10*q:0),cr=80+q,loss=60+q;
   data.push(...rows('Sampo',revenue,cr,loss,20,'EURm','reported_segment',seg,y,q).concat({...rows('Sampo',revenue,cr,loss,20,'EURm','reported_segment',seg,y,q)[0],metric:'insurance_service_result',value:revenue*.2}).map(x=>({...x,source_definition:'Sampo interim statement; '+seg+' reported financial table'})));
 }
 data.push(...rows('Sampo',9999,1,1,0,'EURm','group',null,2026,3));
 const h=sampoNordicSegments({observations:data},{year:2026,quarter:3},'ytd');
 assert.deepEqual(h.map(x=>x.segment),['Private Nordic','Nordic Commercial']);
 assert.equal(h[0].metrics.insurance_revenue,360);
 assert.equal(h[0].metrics.insurance_service_result,72);
 assert.ok(Math.abs(h[0].metrics.combined_ratio-(110*81+120*82+130*83)/360)<1e-10);
 assert.equal(h[0].method,'calculated_ytd');
 const q=sampoNordicSegments({observations:data},{year:2026,quarter:3});
 assert.equal(q[0].metrics.insurance_revenue,130);assert.equal(q[1].metrics.combined_ratio,83);
 const missing=sampoNordicSegments({observations:data.filter(x=>!(x.segment==='Private Nordic'&&x.year===2026&&x.quarter===2))},{year:2026,quarter:3},'ytd');
 assert.equal(missing[0].metrics,null);assert.ok(missing[1].metrics);
});

test('uniform financial arrows are based on the same-year comparison, never missing values',()=>{
 const {financialNumber,financialTrend}=require('../scripts/market_overview.js');
 assert.equal(financialNumber('1\u00a0234,5 MNOK'),1234.5);
 assert.equal(financialNumber('−3,2 %'),-3.2);
 assert.equal(financialNumber('Q3 2025: —'),null);
 assert.equal(financialTrend('—',0),null);
 assert.deepEqual(financialTrend(73,76.7,true),{direction:'down',icon:'▼',tone:'good'});
 assert.deepEqual(financialTrend(85,80,true),{direction:'up',icon:'▲',tone:'bad'});
 assert.deepEqual(financialTrend(4.2,3),{direction:'up',icon:'▲',tone:'good'});
 assert.equal(financialTrend(7,7).tone,'flat');
});


test('commentary names each exceptional issuer and puts shared trends first',()=>{
 const m={period:{year:2026,quarter:3},mode:'quarter',eligible:['Tryg','Fremtind','Gjensidige','Protector'].map(company=>({company,growth:8,cr:80,deltas:{combined_ratio:-2,loss_ratio:-2,expense_ratio:0}}))};
 const base={period:'Q3 2026',source_document_period:'Q3 2026',period_type:'quarter',views:['group/all'],source_type:'official_quarterly_report',source_sha256:'a'.repeat(64),source_page:8,source_url:'https://issuer.invalid/doc.pdf',evidence:'verified original report fragment'};
 const driver=(company,driver)=>({...base,company,theme:'growth_driver',driver,text:driver});
 const explain=(company,theme,topic,text,priority=100,category='')=>({...base,company,theme,topic,driver:topic,text,priority,category});
 const ctx={insights:[
  driver('Fremtind','price'),driver('Gjensidige','price'),
  {...driver('Gjensidige','price'),source_page:9,source_type:'official_results_presentation'},
  driver('Protector','volume_up'),
  explain('Gjensidige','growth_explanation','premium_adjustment','Premiejusteringer er en sentral driver i den rapporterte porteføljen.',80,'price'),
  explain('Tryg','event_explanation','motor_distribution','Nye bilforsikringspartnerskap med Mercedes-Benz i Sverige og XPENG i Norge.',110),
  explain('Fremtind','event_explanation','named_fire','Brannen i Krokstadelva ga storskader på 176 mill. kroner.',105),
  {...explain('Tryg','loss_explanation','workers_comp_adjusted','Dansk yrkesskadeavsetning påvirker CR.',105,'adverse')},
  {...explain('Gjensidige','event_explanation','stale','FORBIDDEN',120),source_document_period:'Q2 2026'}
 ]};
 const c=comments(m,{},'group','all',ctx),g=c[0].paragraphs.join(' '),cr=c[1].paragraphs.join(' '),events=c[2].paragraphs.join(' ');
 assert.match(g,/Medianveksten.*Flere selskaper rapporterer premie- og prisjusteringer/);
 assert.doesNotMatch(g,/Gjensidige: Premiejusteringer/);
 assert.match(events,/Tryg: Nye bilforsikringspartnerskap med Mercedes-Benz/);
 assert.match(events,/Fremtind: Brannen i Krokstadelva/);
 assert.match(cr,/Tryg: Dansk yrkesskadeavsetning/);
 assert.doesNotMatch(JSON.stringify(c),/FORBIDDEN/);
 const one={insights:[driver('Tryg','price'),{...driver('Tryg','price'),source_page:12,source_type:'official_results_presentation'}]};
 const singleton=comments(m,{},'group','all',one)[0].paragraphs.join(' ');
 assert.match(singleton,/Tryg rapporterer premie- og prisjusteringer/);
 assert.doesNotMatch(singleton,/Flere selskaper rapporterer/);
 const fallback={insights:[{...base,company:'Tryg',theme:'material_event',text:'Samarbeid med Mercedes-Benz.'}]};
 assert.match(comments(m,{},'group','all',fallback)[2].paragraphs.join(' '),/Tryg: Samarbeid med Mercedes-Benz/);
 const later={...m,period:{year:2026,quarter:4}};
 assert.doesNotMatch(JSON.stringify(comments(later,{},'group','all',ctx)),/Mercedes-Benz|Krokstadelva|yrkesskadeavsetning|premie- og prisjusteringer/);
});
