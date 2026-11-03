"""Q4 safety: do not synthesize isolated Q4 or non-additive metrics from YTD."""
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'scripts/quarterly_runtime.js'

class Q4IsolatedSourceGuard(unittest.TestCase):
    def test_no_escaped_newline_swallowing_q4_guard(self):
        js=RUNTIME.read_text(encoding='utf-8')
        self.assertIn('if(quarter===4)return null;',js)
        self.assertNotIn(r'official\n    // Q4',js)
        self.assertNotIn(r'YTD.\n    if(quarter===4)',js)

    def test_runtime_fallback_refuses_q4_and_nonadditive_ytd(self):
        js=String= r"""
const fs=require('node:fs');
const assert=require('node:assert/strict');
const source=fs.readFileSync(process.argv[1],'utf8');
const start=source.indexOf('  function addQuarter(');
const end=source.indexOf('  function addYtd(',start);
const quoteStart=source.indexOf('  function quote(');
const quoteEnd=source.indexOf('  function quarterTimeline(',quoteStart);
assert(start>=0&&end>start&&quoteStart>=0&&quoteEnd>quoteStart);
const addQuarterSource=source.slice(start,end);
const quoteSource=source.slice(quoteStart,quoteEnd);
const sample=[
 {company:'Frende',year:2026,quarter:3,metric:'insurance_revenue',
  period_type:'ytd',scope:'group',value:300,unit:'NOKm',source_definition:'Group operating revenue'},
 {company:'Frende',year:2026,quarter:4,metric:'insurance_revenue',
  period_type:'ytd',scope:'group',value:440,unit:'NOKm',source_definition:'Group operating revenue'},
 {company:'Frende',year:2026,quarter:3,metric:'combined_ratio',
  period_type:'ytd',scope:'group',value:91,unit:'percent'},
 {company:'Frende',year:2026,quarter:4,metric:'combined_ratio',
  period_type:'ytd',scope:'group',value:85,unit:'percent'},
 {company:'Frende',year:2026,quarter:2,metric:'insurance_revenue',
  period_type:'ytd',scope:'group',value:170,unit:'NOKm',source_definition:'Group operating revenue'}
];
const lookup=(company,type,year,quarter,metric)=>sample.find(
 r=>r.company===company&&r.period_type===type&&r.year===year&&r.quarter===quarter&&r.metric===metric);
const isSameBasis=(a,b)=>a&&b&&a.unit===b.unit&&a.source_definition===b.source_definition;
const addQuarter=new Function('lookup','isSameBasis',
  addQuarterSource+';return addQuarter;')(lookup,isSameBasis);
assert.equal(addQuarter('Frende',2026,4,'insurance_revenue'),null,'Q4 cannot be YTD subtraction');
assert.equal(addQuarter('Frende',2026,4,'insurance_service_result'),null,'Q4 result cannot be derived');
assert.equal(addQuarter('Frende',2026,4,'combined_ratio'),null,'Q4 ratio cannot be derived');
assert.equal(addQuarter('Frende',2026,3,'insurance_revenue').value,130,'Q3 additive YTD fallback must still work');
assert.equal(addQuarter('Frende',2026,3,'combined_ratio'),null,'nonadditive YTD ratio cannot be subtracted');
const addYtd=()=>null;
const quote=new Function('lookup','addYtd','addQuarter',
  quoteSource+';return quote;')(lookup,addYtd,addQuarter);
assert.equal(quote('Frende','quarter',2026,4,'insurance_revenue'),null,'No invented Q4 quote');
sample.push({company:'Frende',year:2026,quarter:4,metric:'insurance_revenue',
 period_type:'quarter',scope:'group',value:140,unit:'NOKm',source_definition:'Reported isolated Q4'});
assert.equal(quote('Frende','quarter',2026,4,'insurance_revenue').value,140,
 'Official isolated Q4 should display when imported');
console.log('Q4_SOURCE_GUARD_PASS');
"""
        run=subprocess.run(['node','-e',js,str(RUNTIME)],cwd=ROOT,
                           capture_output=True,text=True,timeout=20)
        self.assertEqual(run.returncode,0,run.stdout+'\n'+run.stderr)
        self.assertIn('Q4_SOURCE_GUARD_PASS',run.stdout)

if __name__=='__main__':
    unittest.main()
