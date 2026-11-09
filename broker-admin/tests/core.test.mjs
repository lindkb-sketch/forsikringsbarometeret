import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {Script} from 'node:vm';
import {
  COMPANIES,MAX_PDF_BYTES,assertFolder,periodsFromFeed,periodSort,
  normalizedSummary,mergePublicFeed,decodeAiSummary,safeFileName,
  publicContainsPrivateData,textSchema
} from '../src/core.js';
import {ADMIN_HTML,ADMIN_JS,ADMIN_CSS} from '../src/ui.js';

test('only known insurers and canonical quarters can create folders',()=>{
  assert.deepEqual(assertFolder('Gjensidige','Q4 2026'),{company:'Gjensidige',quarter:'Q4 2026'});
  for(const input of [['Unknown','Q3 2026'],['Gjensidige','Q9 2026'],['Gjensidige','../../../etc/passwd']]){
    assert.throws(()=>assertFolder(...input),TypeError);
  }
  assert.equal(COMPANIES.length,7);
});
test('quarter folders arise from verified group-quarter observations, not analyst notes',()=>{
  const feed={observations:[
    {company:'Tryg',scope:'group',period_type:'quarter',year:2026,quarter:3},
    {company:'Tryg',scope:'group',period_type:'quarter',year:2026,quarter:4},
    {company:'Sampo',scope:'group',period_type:'quarter',year:2026,quarter:4},
    {company:'Tryg',scope:'norway',period_type:'quarter',year:2027,quarter:1},
    {company:'Tryg',scope:'group',period_type:'ytd',year:2027,quarter:1},
    {company:'Tryg',scope:'group',period_type:'quarter',year:2027,quarter:9},
  ]};
  assert.deepEqual(periodsFromFeed(feed),['Q3 2026','Q4 2026']);
  assert.equal(periodSort('Q4 2026','Q1 2027')<0,true);
});
test('public summaries contain no raw PDF, filenames, keys or analysis',()=>{
  const source={schema_version:1,entries:[]};
  const summary={reaction:'Meglerhusene vurderte premieinntekter og kombinertprosent opp mot forventningene.',drivers:'Skadetrend og kostnader.',outlook:'Prognoser spriker; ingen sikker enighet.'};
  const result=mergePublicFeed(source,'Tryg','Q3 2026',summary,'2026-11-09T10:00:00Z');
  assert.equal(result.entries.length,1);
  assert.deepEqual(Object.keys(result.entries[0]).sort(),
    ['company','quarter','reaction','drivers','outlook','updated_at'].sort());
  assert.equal(publicContainsPrivateData(result),false);
  assert.equal(JSON.stringify(result).includes('research.pdf'),false);
  assert.equal(source.entries.length,0);
  const replaced=mergePublicFeed(result,'Tryg','Q3 2026',{...summary,outlook:'Ingen estimatendringer.'},'2026-11-09T10:01:00Z');
  assert.equal(replaced.entries.length,1);
  assert.equal(replaced.entries[0].outlook,'Ingen estimatendringer.');
});
test('AI response must be completed structured JSON with source-grounded text',()=>{
  const sample={reaction:'Sammenliknet med forventningene var resultatet noe lavere enn ventet.',drivers:'Større skader.',outlook:'Neste kvartal: ikke omtalt.'};
  const good={status:'completed',output:[{type:'message',content:[{type:'output_text',text:JSON.stringify(sample)}]}]};
  assert.deepEqual(decodeAiSummary(good),sample);
  assert.throws(()=>decodeAiSummary({...good,status:'in_progress'}));
  assert.throws(()=>decodeAiSummary({status:'completed',output:[]}));
  assert.throws(()=>decodeAiSummary({status:'completed',output:[{type:'message',content:[{type:'output_text',text:'not json'}]}]}));
  assert.throws(()=>normalizedSummary({...sample,reaction:'kort'}));
  assert.deepEqual(textSchema().required,['reaction','drivers','outlook']);
});
test('untrusted filenames are limited to PDF without path traversal',()=>{
  assert.equal(safeFileName(' megler.pdf '),'megler.pdf');
  assert.throws(()=>safeFileName('malware.exe'));
  assert.throws(()=>safeFileName('a'.repeat(182)+'.pdf'));
  assert.equal(MAX_PDF_BYTES,10485760);
});
test('admin page uses local scripts and no third-party CDN',()=>{
  assert.match(ADMIN_HTML,/\/admin\.js/);
  assert.match(ADMIN_HTML,/\/admin\.css/);
  assert.doesNotMatch(ADMIN_HTML,/http[s]?:\/\/cdn\./);
  assert.match(ADMIN_HTML,/Godkjenn og publiser/);
  assert.match(ADMIN_JS,/\/api\/reports/);
  assert.match(ADMIN_JS,/\/api\/publish/);
  assert.match(ADMIN_JS,/Bekreft/iu);
  assert.match(ADMIN_CSS,/\.pane/);
  new Script(ADMIN_JS,{filename:'admin.js'});
});
test('worker verifies JWT and origin before any private route',()=>{
  const script=readFileSync(new URL('../src/index.js',import.meta.url),'utf8');
  for(const literal of ['jwtVerify(','createRemoteJWKSet(','Cf-Access-Jwt-Assertion',
    'ADMIN_EMAILS','ACCESS_AUD','assertSameOrigin(req)','MAX_PDF_BYTES',
    'await requireAccess(req,env)','OPENAI_API_KEY','GITHUB_TOKEN',
    "if(!jwt)","store:false","input_file","model:env.OPENAI_MODEL",
    "filename:'research.pdf'",'await env.REPORTS.put(','await env.REPORTS.delete(',
    "await env.BROKER_JOBS.send({id})","'draft'","'analyzed'",
    "await publishGitHub(env,company,quarter,summary)"])
    assert.ok(script.includes(literal),'missing '+literal);
  assert.ok(script.indexOf('const actor=await requireAccess(req,env)')<script.indexOf("if(req.method==='GET'&&path==='/api/bootstrap')"));
  assert.doesNotMatch(script,/GET.+\/api\/download-pdf/);
});
test('manifest never exposes secrets in checked-in config',()=>{
  const config=readFileSync(new URL('../wrangler.toml',import.meta.url),'utf8');
  assert.match(config,/binding = "REPORTS"/);
  assert.match(config,/binding = "DB"/);
  assert.match(config,/binding = "BROKER_JOBS"/);
  assert.doesNotMatch(config,/OPENAI_API_KEY\s*=/);
  assert.doesNotMatch(config,/GITHUB_TOKEN\s*=/);
  assert.match(config,/00000000-0000-0000-0000-000000000000/);
});
