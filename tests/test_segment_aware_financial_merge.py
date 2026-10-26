"""Segment-identity regression: unrelated reported segments must survive importer merge."""
import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from ingest_official_pdf import merge
class ReportedSegmentIdentityTests(unittest.TestCase):
 def test_two_sampo_segments_survive_gjensidige_merge(self):
  def row(company,scope,segment,value,metric):
   return dict(company=company,scope=scope,segment=segment,source_scope=scope,
    year=2025,quarter=4,period_type='quarter',metric=metric,value=value,
    unit='percent',status='reported',source_url='https://example.com/official.pdf',
    source_type='official_quarterly_report',source_page=1,source_sha256='a'*64)
  a=row('Sampo','reported_segment','Private Nordic',82.2,'combined_ratio')
  b=row('Sampo','reported_segment','Nordic Commercial',82.8,'combined_ratio')
  original={'observations':[a,b]}
  merged,added=merge(original,[])
  self.assertEqual(added,0)
  self.assertEqual(merged['observations'],[a,b])
if __name__=='__main__':unittest.main()
