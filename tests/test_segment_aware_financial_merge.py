"""Every reported Sampo segment must remain intact through a no-op importer merge."""
import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from ingest_official_pdf import merge
class SegmentIdentityTests(unittest.TestCase):
 def test_noop_merge_preserves_all_existing_segments(self):
  source=json.loads((ROOT/'data/financial_observations.json').read_text())
  before=[r for r in source['observations'] if r.get('company')=='Sampo' and r.get('scope')=='reported_segment']
  self.assertGreater(len(before),0,'Expected distinct audited Sampo segments in the baseline')
  self.assertGreater(len({r.get('segment') for r in before}),1)
  merged,added=merge(source,[])
  after=[r for r in merged['observations'] if r.get('company')=='Sampo' and r.get('scope')=='reported_segment']
  self.assertEqual(added,0)
  self.assertEqual(after,before)
  self.assertEqual(merged['observations'],source['observations'])
if __name__=='__main__':unittest.main()
