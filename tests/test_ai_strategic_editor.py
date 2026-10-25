import json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import ai_strategic_editor as ai
class StrategyHybridTests(unittest.TestCase):
 def setUp(self):
  self.note={'company':'Fremtind','theme':'competition','title':'Konkurransebildet',
   'summary':'Sterk konkurranse ventes.','source_url':'https://example.org/report.pdf',
   'source_page':5,'source_sha256':'abc'}
  self.raw={'basis':'issuer_pdf_verbatim','theme':'competition','companies':['Fremtind'],
   'sources':[{'url':'https://example.org/report.pdf','page':5,'sha256':'abc'}],
   'text':'Fremtind omtaler: «Fremtind forventer sterk konkurranse og fortsatt fokus på lønnsomhet i det norske forsikringsmarkedet.»'}
 def test_rejects_mismatched_evidence(self):
  self.assertTrue(ai.eligible(self.note,self.raw))
  self.assertFalse(ai.eligible({**self.note,'source_sha256':'other'},self.raw))
 def test_two_pass_approval_is_required(self):
  with patch.object(ai,'model',side_effect=[{'text':'Fremtind forventer sterk konkurranse og fortsatt fokus på lønnsomhet i det norske forsikringsmarkedet.'},{'approved':False}]):
   self.assertIsNone(ai.review(self.note,self.raw))
 def test_approved_copy(self):
  copy='Fremtind forventer sterk konkurranse og fortsatt fokus på lønnsomhet i det norske forsikringsmarkedet.'
  with patch.object(ai,'model',side_effect=[{'text':copy},{'approved':True}]):
   self.assertEqual(ai.review(self.note,self.raw),copy)
 def test_no_secret_does_not_change_files(self):
  with patch.dict('os.environ',{},clear=True):
   self.assertEqual(ai.run(Path('/nonexistent'),Path('/nonexistent')),0)
 def test_workflow_wires_ai(self):
  workflow=(Path(__file__).resolve().parents[1]/'.github/workflows/update.yml').read_text()
  self.assertNotIn('python scripts/ai_strategic_editor.py',workflow)
  self.assertNotIn('secrets.OPENAI_API_KEY',workflow)
  self.assertIn('build_strategic_market.py',(Path(__file__).resolve().parents[1]/'scripts/run_pipeline.py').read_text())
if __name__=='__main__':unittest.main()
