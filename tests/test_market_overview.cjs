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
 assert.deepEqual(model(feed,comp,fx,'norway','all').selected.map(c=>c.company),['Gjensidige','Tryg','Protector']);
 assert.deepEqual(model(feed,comp,fx,'norway','pm').selected.map(c=>c.company),['Gjensidige']);
 assert.deepEqual(model(feed,comp,fx,'norway','bm').selected.map(c=>c.company),['Gjensidige','Protector']);
 assert.deepEqual(model(feed,comp,fx,'group','pm').selected.map(c=>c.company),['Sampo']);
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
 const c=JSON.stringify(comments(m,editorial,'group','all'));assert.ok(c.includes('Dokumentert hendelse'));assert.ok(!c.includes('BAD'));
 assert.ok(!JSON.stringify(comments(model(feed,comp,fx,'norway','all'),editorial,'norway','all')).includes('Dokumentert hendelse'));
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
