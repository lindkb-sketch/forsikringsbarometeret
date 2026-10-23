"""Q3 release-aware E2E checks: unpublished is not failed import."""
import sys
import unittest
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from e2e_seven_insurers import publication_state

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
  self.assertEqual(publication_state('Gjensidige',date(2026,10,23),CALENDAR,[])[0],'publication_due')
 def test_new_official_candidate_changes_undated_issuer_to_due(self):
  candidate=[{'company':'Frende','year':2026,'quarter':3,'document_url':'https://frende.wrep.it/q3-2026'}]
  self.assertEqual(publication_state('Frende',date(2026,10,23),CALENDAR,candidate)[0],'publication_due')
 def test_future_dated_report_not_due(self):
  self.assertEqual(publication_state('Sampo',date(2026,11,3),CALENDAR,[])[0],'awaiting_publication')
  self.assertEqual(publication_state('Sampo',date(2026,11,4),CALENDAR,[])[0],'publication_due')

if __name__=='__main__':unittest.main()
