const test=require('node:test'),assert=require('node:assert/strict');
const {build,validate}=require('../scripts/build_market_overview_archive.cjs');
const {archivedView}=require('../scripts/market_overview.js');
const rows=(year,q,rev,cr)=>Object.entries({insurance_revenue:rev,combined_ratio:cr,loss_ratio:cr-15,expense_ratio:15}).flatMap(([metric,value])=>['quarter','ytd'].map(period_type=>({company:'Fremtind',year,quarter:q,scope:'group',metric,value,unit:metric==='insurance_revenue'?'MNOK':'percent',period_type,status:'reported',source_type:'official_quarterly_report',source_url:'https://issuer.invalid/report.pdf',source_sha256:'a'.repeat(64),source_page:3})));
const input=(observations,period,text)=>({feed:{observations},comparison:{companies:[]},fx:{periods:{}},segments:{observations:[]},context:{observations:[],insights:[{company:'Fremtind',period,source_document_period:period,period_type:'quarter',views:['group/all'],theme:'material_event',text,source_type:'official_quarterly_report',source_url:'https://issuer.invalid/report.pdf',source_sha256:'a'.repeat(64),source_page:3}]},editorial:{}});
test('Q3 freezes across Q4 and Q1 including comparisons, source links and commentary',()=>{
 const a=build(input(rows(2026,3,6000,73),'Q3 2026','Q3 hendelse'));
 const q3=JSON.stringify(a.periods['Q3 2026'].views);
 const b=build(input([...rows(2026,3,9000,90),...rows(2026,4,6500,75)],'Q4 2026','Q4 hendelse'),a);
 assert.equal(b.active_period,'Q4 2026');assert.equal(b.periods['Q3 2026'].locked,true);
 assert.equal(JSON.stringify(b.periods['Q3 2026'].views),q3);
 assert.equal(archivedView(b,'Q3 2026','group','all','quarter').model.selected[0].cr,73);
 assert.equal(archivedView(b,'latest','group','all','quarter').model.selected[0].cr,75);
 assert.ok(JSON.stringify(archivedView(b,'Q3 2026','group','all','quarter').comments).includes('Q3 hendelse'));
 assert.equal(archivedView(b,'Q2 2026','group','all','quarter'),null);
 const frozen=JSON.stringify(b.periods['Q3 2026']);
 const c=build(input([...rows(2026,3,9999,99),...rows(2027,1,7000,70)],'Q1 2027','Q1 hendelse'),b);
 assert.equal(c.active_period,'Q1 2027');assert.equal(c.periods['Q4 2026'].locked,true);
 assert.equal(JSON.stringify(c.periods['Q3 2026']),frozen);validate(c);
});
test('active quarter can update, rewind and skipped quarters fail, damaged history rejected',()=>{
 const a=build(input(rows(2026,3,6000,73),'Q3 2026','a'));
 const b=build(input(rows(2026,3,6500,72),'Q3 2026','b'),a);
 assert.equal(b.periods['Q3 2026'].locked,false);assert.equal(archivedView(b,'latest','group','all','quarter').model.selected[0].cr,72);
 assert.throws(()=>build(input(rows(2027,1,7000,70),'Q1 2027','c'),b),/skip/);
 assert.throws(()=>build(input(rows(2026,2,7000,70),'Q2 2026','c'),b),/rewind/);
 b.periods['Q3 2026'].views['group/all/quarter'].model.selected[0].cr=99;assert.throws(()=>validate(b),/content changed/);
});
