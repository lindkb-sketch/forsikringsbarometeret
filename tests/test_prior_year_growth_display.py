"""Guard explicit prior-year revenue growth for current and future periods."""
import unittest
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class PriorGrowthDisplayTests(unittest.TestCase):
 def test_growth_has_separate_current_and_previous_year_lines(self):
  js=(ROOT/'scripts/quarterly_runtime.js').read_text(encoding='utf-8')
  self.assertIn("const previousGrowth=currentReported?d.growthPrev:null;",js)
  self.assertIn("'<div class=\"table-prior\">('+escape(previousGrowth)+')</div>'",js)
  self.assertIn("const growthCell=tr.cells[1]",js)
  self.assertIn("const thisGrowth=growthFor(year),lastGrowth=growthFor(year-1)",js)
  self.assertIn("const currentGrowth=currentReported?d.growth:null;",js)
  self.assertIn("if(lastGrowth){",js)
  self.assertIn("data.growthPrev=fmt(lastGrowth.value,true)",js)

 def test_real_js_growth_rolls_correctly_across_new_years(self):
  runtime=(ROOT/'scripts/quarterly_runtime.js').read_text(encoding='utf-8')
  source=runtime.split('        function growthFor(targetYear){',1)[1].split('        const thisGrowth=',1)[0]
  js = """
  const data=[];
  function quote(name,type,year,quarter,metric){
    return data.find(row=>row.company===name&&row.type===type&&row.year===year&&row.quarter===quarter&&row.metric===metric)||null;
  }
  function isSameBasis(a,b){return a&&b&&a.unit===b.unit&&a.basis===b.basis;}
  const name='Tryg';
  let type='quarter',quarter=1;
  function growthFor(targetYear){""" + source + """
  function set(year,q,kind,value,basis='ifrs'){
    data.push({company:'Tryg',year,quarter:q,type:kind,metric:'insurance_revenue',
               value,unit:'MDKK',basis});
  }
  for(const kind of ['quarter','ytd']){
    set(2025,1,kind,100);
    set(2026,1,kind,110);
    set(2027,1,kind,121);
    set(2028,1,kind,145.2);
  }
  for(const kind of ['quarter','ytd']){
    type=kind;quarter=1;
    const thisGrowth=growthFor(2027),lastGrowth=growthFor(2026);
    if(Math.abs(thisGrowth.value-10)>1e-8||Math.abs(lastGrowth.value-10)>1e-8)
      throw Error('Q1 2027 wrong growth '+JSON.stringify({thisGrowth,lastGrowth}));
    const next=growthFor(2028),nextPrior=growthFor(2027);
    if(Math.abs(next.value-20)>1e-8||Math.abs(nextPrior.value-10)>1e-8)
      throw Error('Q1 2028 wrong growth '+JSON.stringify({next,nextPrior}));
  }
  type='quarter';quarter=4;
  set(2025,4,type,250);set(2026,4,type,300);set(2027,4,type,330);
  if(Math.abs(growthFor(2027).value-10)>1e-8||Math.abs(growthFor(2026).value-20)>1e-8)
    throw Error('Q4 2027 rollover compares wrong year');
  data.find(r=>r.year===2025&&r.quarter===4&&r.type==='quarter').basis='operating_revenue';
  if(growthFor(2026)!==null)throw Error('Mixed IFRS and operating revenue compared');
  """
  result=subprocess.run(['node','-e',js],text=True,capture_output=True)
  self.assertEqual(result.returncode,0,result.stderr)

 def test_frende_future_pdf_cannot_be_skipped_silently(self):
  code=(ROOT/'scripts/import_frende_holding.py').read_text(encoding='utf-8')
  self.assertIn("Newer official Frende quarter discovered but not verified/imported",code)
  self.assertIn("all_periods and max(all_periods)>max(map(tuple,verified))",code)

if __name__=='__main__':
 unittest.main()
