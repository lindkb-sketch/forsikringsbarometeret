"""Production HTML has no embedded financial snapshots or replacement data.

Known numeric fixtures are appropriate in test files and original data
artifacts. Browser renderers must never use them as financial fallbacks.
"""
import json,re,unittest,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'index.html').read_text(encoding='utf-8')

class NoHardcodedFinancials(unittest.TestCase):
    def test_legacy_data_containers_are_empty_or_labels_only(self):
        for name in ('peerData','groupData','halfYearData','marketShares','MON_Q3_SEGMENTS'):
            self.assertRegex(HTML,r'const '+name+r'=\{\};',name)
        segment=HTML.split('const segmentData=',1)[1].split('function segmentCell(',1)[0]
        self.assertNotRegex(segment,r'\b(?:growth|growthPrev|cr|loss|cost|underwriting|note)\s*:')
        for token in ('const verifiedShares=','const q1Profitability=','const quarterNarratives=','const companyMediaArticles=','function fremtindMetric('):
            self.assertNotIn(token,HTML)
        self.assertNotRegex(HTML,r"metrics:\s*\[\s*\['Forsikringsinntekter',\s*'\d")
        self.assertNotIn("html.replace(/const marketShares=",HTML)
        self.assertIn("fetch('data/market_shares.json?",HTML)
        self.assertIn("a.download='market_shares.json'",HTML)

    def test_market_share_source_and_period(self):
        d=json.loads((ROOT/'data/market_shares.json').read_text())
        self.assertEqual(d['schema_version'],1)
        self.assertIn(d['status'],('published_manual_snapshot','tab5_import'))
        self.assertRegex(d['period'],r'^Q[1-4] 20\d{2}$')
        self.assertEqual(d['prior_period'],d['period'][:3]+str(int(d['period'][3:])-1))
        self.assertIn('Finans Norge',d['source'])
        if d['status']=='tab5_import':
            self.assertRegex(d['source_sha256'],r'^[0-9a-f]{64}$')
            self.assertEqual(d['source_sheet'],'Tab5')
        for v in d['shares'].values():
            if v is not None:self.assertTrue(0<=float(v.replace('%','').strip().replace(',','.'))<=100)
        self.assertTrue(d['shares'])

    def test_fallback_card_templates_have_no_financial_values(self):
        start=HTML.index('function resultServiceCard(c){')
        end=HTML.index('// Tilgjengelighetsstyrt:',start)
        js=HTML[start:end]
        test=js+'''
for(const c of ['Fremtind','Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand','Alm. Brand','KLP Skadeforsikring']){
 for(const k of ['growth','cr','loss','cost']){
  const html=metricCardFor(c,k);
  if(!html.includes('class="value">—')||/\\d+[,.]\\d+\\s*%/.test(html))throw Error('Static KPI fallback '+c);
 }
 if(!resultServiceCard(c).includes('class="value">—'))throw Error('Static service result '+c);
}
'''
        p=subprocess.run(['node','-e',test],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
if __name__=='__main__':unittest.main()
