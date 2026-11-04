import io,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import sampo_publish

class FakeResponse(io.BytesIO):
 def __enter__(self):return self
 def __exit__(self,*args):self.close()

class DiscoveryTests(unittest.TestCase):
 def test_current_archive_january_september_filename(self):
  url='https://www.sampo.com/globalassets/investors/quarterly-reporting/2026/q3/sampo-groups-results-for-january-september-2026.pdf'
  markup=('<html><a href="'+url+'">Interim Statement</a></html>').encode()
  with patch.object(sampo_publish.urllib.request,'urlopen',side_effect=lambda *a,**k:FakeResponse(markup)):
   self.assertEqual(sampo_publish.discover(2026,3),url)
 def test_factbook_does_not_make_official_report_ambiguous(self):
  good='https://www.sampo.com/globalassets/investors/quarterly-reporting/2026/q3/interim-statement_q3_2026.pdf'
  bad='https://www.sampo.com/globalassets/investors/quarterly-reporting/2026/q3/sustainability_factbook_q3_2026.pdf'
  html=('<a href="'+good+'">Interim Statement</a><a href="'+bad+'">Factbook</a>').encode()
  with patch.object(sampo_publish.urllib.request,'urlopen',side_effect=lambda *a,**k:FakeResponse(html)):
   self.assertEqual(sampo_publish.discover(2026,3),good)
 def test_does_not_accept_presentation_as_report(self):
  markup=b'<a href="/q3-2026-investor-presentation.pdf">presentation</a>'
  with patch.object(sampo_publish.urllib.request,'urlopen',side_effect=lambda *a,**k:FakeResponse(markup)):
   self.assertIsNone(sampo_publish.discover(2026,3))

if __name__=='__main__':unittest.main()
