"""Q3 release-aware E2E checks: unpublished is not failed import."""
import sys
import unittest
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from e2e_seven_insurers import publication_state,current_report_candidates

CALENDAR={
 'Gjensidige':{'events':[{'period':'Q3 2026','date':'2026-10-23'}]},
 'Sampo / If':{'events':[{'period':'Q3 2026','date':'2026-11-04'}]},
 'Frende':{'events':[]}
}

class PublicationStateTests(unittest.TestCase):
 def test_sampo_not_yet_due(self):
  self.assertEqual(publication_state('Sampo',date(2026,10,23),CALENDAR,[])[0],'awaiting_publication')
 def test_frende_not_confirmed_does_not_fail(self):
  self.assertEqual(publication_state('Frende',date(2026,10,23),CALENDAR,[])[0],'publication_unconfirmed')
 def test_gjensidige_due_today(self):
  self.assertEqual(publication_state('Gjensidige',date(2026,10,23),CALENDAR,[])[0],'publication_expected')
 def test_new_official_candidate_changes_undated_issuer_to_due(self):
  candidate=[{'company':'Frende','year':2026,'quarter':3,'document_url':'https://frende.wrep.it/q3-2026'}]
  self.assertEqual(publication_state('Frende',date(2026,10,23),CALENDAR,candidate)[0],'publication_due')
 def test_real_release_beats_future_calendar(self):
  candidate=[{'company':'Sampo','year':2026,'quarter':3,'document_url':'https://www.sampo.com/q3-2026.pdf'}]
  self.assertEqual(publication_state('Sampo',date(2026,10,23),CALENDAR,candidate)[0],'publication_due')
 def test_discovery_from_any_issuer_overrides_calendar(self):
  generic=[{'company':'Sampo','link_text':'Interim Statement Q3 2026','document_url':'https://www.sampo.com/report.pdf'}]
  found=current_report_candidates([],generic)
  self.assertEqual(publication_state('Sampo',date(2026,10,23),CALENDAR,found)[0],'publication_due')
 def test_norwegian_filing_link(self):
  generic=[{'company':'Frende','link_text':'3. kvartal Frende Holding AS 2026','document_url':'https://www.frende.no/rapport.pdf'}]
  self.assertEqual(len(current_report_candidates([],generic)),1)
 def test_future_dated_report_not_due(self):
  self.assertEqual(publication_state('Sampo',date(2026,11,3),CALENDAR,[])[0],'awaiting_publication')
  self.assertEqual(publication_state('Sampo',date(2026,11,4),CALENDAR,[])[0],'publication_expected')

if __name__=='__main__':unittest.main()
