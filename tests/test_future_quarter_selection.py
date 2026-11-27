"""Exercise the production period-selection function with future-quarter data."""
import json
import subprocess
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class PeriodSelectionTests(unittest.TestCase):
    def test_incomplete_future_quarter_never_becomes_homepage_default(self):
        runtime=(ROOT/'scripts/quarterly_runtime.js').read_text(encoding='utf-8')
        function=runtime.split('  function calcPeriods(){',1)[1].split('  function lookup(',1)[0]
        # Evaluate the real production function body, not a parallel reimplementation.
        js="""
const METRICS=['combined_ratio','loss_ratio','expense_ratio','insurance_revenue','insurance_service_result'];
let observations=[];
const EXTENDED_NAMES=['KLP Skadeforsikring','Alm. Brand'];
let extendedInsurerFeed={};
const extendedRecord=(name,p)=>[extendedInsurerFeed[name],...(extendedInsurerFeed[name]?.periods||[])].find(r=>r?.year===p.year&&r?.quarter===p.quarter&&r.status==='verified_official_pdf_reconciled'&&Number.isFinite(r.metrics?.insurance_revenue)&&Number.isFinite(r.metrics?.combined_ratio));
const rows=()=>observations;
function calcPeriods(){""" + function + """
const period=(year,quarter,company,metric)=>({year,quarter,company,metric,period_type:'quarter'});
observations=[
  period(2026,3,'Tryg','insurance_revenue'),
  period(2026,3,'Tryg','combined_ratio'),
  period(2026,4,'Tryg','insurance_revenue'),
  period(2026,4,'Sampo','combined_ratio'),
  period(2027,1,'Protector','loss_ratio')
];
let actual=calcPeriods();
if(JSON.stringify(actual)!==JSON.stringify([{year:2026,quarter:3}]))
  throw Error('Incomplete next quarters selected: '+JSON.stringify(actual));
observations.push(period(2026,4,'Tryg','combined_ratio'));
actual=calcPeriods();
if(JSON.stringify(actual)!==JSON.stringify([{year:2026,quarter:4},{year:2026,quarter:3}]))
  throw Error('Complete Q4 quarter did not roll over: '+JSON.stringify(actual));
observations.push(period(2027,1,'Protector','insurance_revenue'));
observations.push(period(2027,1,'Protector','combined_ratio'));
actual=calcPeriods();
if(actual[0].year!==2027||actual[0].quarter!==1)
  throw Error('2027 rollover failed: '+JSON.stringify(actual));
extendedInsurerFeed['KLP Skadeforsikring']={year:2027,quarter:2,status:'unverified',metrics:{insurance_revenue:100,combined_ratio:80}};
if(calcPeriods()[0].quarter!==1)throw Error('Unverified extended issuer opened future quarter');
extendedInsurerFeed['KLP Skadeforsikring'].status='verified_official_pdf_reconciled';
if(calcPeriods()[0].quarter!==2)throw Error('Verified extended issuer cannot open new quarter');
"""
        result=subprocess.run(['node','-e',js],text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':
    unittest.main()
