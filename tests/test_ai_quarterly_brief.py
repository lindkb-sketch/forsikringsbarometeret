import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import generate_ai_quarterly_brief as ai
class EditorialAiGates(unittest.TestCase):
 def evidence(self,company='Protector'):
  return {'basis':'issuer_pdf_verbatim','theme':'large_claims',
    'text':company+' omtaler i kvartalsrapporten: «Large claims affected the underwriting result during the quarter.»',
    'companies':[company],
    'sources':[{'company':company,'url':'https://issuer.example.org/report.pdf',
      'kind':'official_quarterly_report','page':4,'sha256':'a'*64}]}
 def test_grounded_claim_is_accepted_and_keeps_original_source(self):
  evidence=self.evidence()
  lookup=ai.evidence_for_period([evidence])
  key=next(iter(lookup))
  claim={'theme':'large_claims','text':'Protector opplyser at større enkeltskader påvirket forsikringsresultatet i kvartalet.',
         'evidence_ids':[key]}
  good=ai.check_claim(claim,lookup,'Q1 2027')
  self.assertEqual(good['sources'][0]['page'],4)
  self.assertEqual(good['sources'][0]['sha256'],'a'*64)
 def test_hallucinated_link_missing_source_and_unrelated_issuer_rejected(self):
  lookup=ai.evidence_for_period([self.evidence()])
  key=next(iter(lookup))
  self.assertIsNone(ai.check_claim({'theme':'large_claims','text':'Fremtind rapporterer en betydelig skadehendelse som påvirket kvartalet.',
    'evidence_ids':[key]},lookup,'Q1 2027'))
  self.assertIsNone(ai.check_claim({'theme':'large_claims','text':'Protector rapporterer en betydelig skadehendelse som påvirket kvartalet.',
    'evidence_ids':['fabricated']},lookup,'Q1 2027'))
  self.assertEqual(ai.evidence_for_period([{**self.evidence(),'sources':[{'url':'https://example.org'}]}]),{})
 def test_no_key_never_touches_existing_data(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'quarterly_insights.json'
   original=json.dumps({'periods':{'Q3 2026':[self.evidence()]}})
   path.write_text(original)
   with patch.object(ai,'PATH',path),patch.dict(ai.os.environ,{'OPENAI_API_KEY':''}):
    ai.main()
   self.assertEqual(path.read_text(),original)
 def test_accepted_new_claim_does_not_erase_curated_or_raw_evidence(self):
  row=self.evidence()
  lookup=ai.evidence_for_period([row])
  key=next(iter(lookup))
  curated={'theme':'weather','text':'Behold menneskelig kvalitetssikret tekst.','basis':'curated_issuer_commentary'}
  storage={'periods':{'Q1 2027':[row,curated]}}
  n=ai.add_verified_claims(storage,'Q1 2027',{'claims':[{
   'theme':'large_claims','text':'Protector opplyser at større enkeltskader påvirket forsikringsresultatet i kvartalet.',
   'evidence_ids':[key]}]},lookup)
  self.assertEqual(n,1)
  self.assertIn(curated,storage['periods']['Q1 2027'])
  self.assertIn(row,storage['periods']['Q1 2027'])
 def test_independent_entailment_rejects_claim_without_approval(self):
  from unittest.mock import MagicMock
  evidence=self.evidence()
  lookup=ai.evidence_for_period([evidence]);key=next(iter(lookup))
  reply={'claims':[{'theme':'large_claims',
   'text':'Protector opplyser at større enkeltskader påvirket forsikringsresultatet i kvartalet.',
   'evidence_ids':[key]}]}
  fake=MagicMock()
  fake.__enter__.return_value=fake
  fake.__exit__.return_value=False
  fake.read.return_value=json.dumps({'choices':[{'message':{'content':'{"approved_indices":[]}'}}]}).encode()
  with patch.dict(ai.os.environ,{'OPENAI_API_KEY':'fake'}),patch.object(ai.urllib.request,'urlopen',return_value=fake):
   checked=ai.verify_entailment('Q1 2027',reply,lookup)
  self.assertEqual(checked['claims'],[])
if __name__=='__main__':unittest.main()
