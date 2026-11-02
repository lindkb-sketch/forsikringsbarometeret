import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from frende_skade_pdf_cells import extract_cells
class Page:
 def extract_words(self,**kwargs):
  def word(text,x,y):
   return {'text':text,'x0':x,'x1':x+25,'top':y}
  data=[word('Resultatregnskap',10,10),word('1.kv.',210,10),
        word('2026',250,10),word('1.kv.',310,10),word('2025',350,10)]
  labels=['Premieinntekter for egen regning','Resultat av teknisk regnskap i skadeforsikring','Kostnadsandel %','Skade % E/R','Combined Ratio']
  values=[('893535','773391'),('58095','-16410'),('16,8','18,2'),('76,7','83,9'),('93,5','102,1')]
  for i,(label,pair) in enumerate(zip(labels,values)):
   y=30+20*i
   data.append(word(label,10,y))
   data.extend([word(pair[0],250,y),word(pair[1],350,y)])
  return data
class CoordinateTests(unittest.TestCase):
 def test_separate_pdf_columns(self):
  values=extract_cells(Page(),['Premieinntekter for egen regning','Resultat av teknisk regnskap i skadeforsikring','Kostnadsandel %','Skade % E/R','Combined Ratio'],2026,1)
  self.assertEqual(values['Premieinntekter for egen regning'],['893535','773391'])
  self.assertEqual(values['Resultat av teknisk regnskap i skadeforsikring'],['58095','-16410'])
