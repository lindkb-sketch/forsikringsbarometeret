import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from import_frende_holding import extract,number,read

def table(q):
    if q==1:
        head=['Tall i 1000','Q1 2026','Q1 2025']
        rows=[['Kostnads %','21,6 %','22,2 %'],['Skadeprosent f.e.r','72,2 %','80,5 %'],['Combined ratio','93,9 %','102,7 %'],['Resultat før skatt','90 346','40 799']]
    else:
        head=['Tall i 1000','Q2 2026','Q2 2025','Pr Q2 2026','Pr Q2 2025']
        rows=[['Kostnads %','18,6 %','20,4 %','20,1 %','21,4 %'],['Skadeprosent f.e.r','62,8 %','64,1 %','67,4 %','72,1 %'],['Combined ratio','81,3 %','84,5 %','87,5 %','93,5 %'],['Resultat før skatt','347 322','307 631','437 669','348 429']]
    return '<h1>Nøkkeltall konsern</h1><table>'+''.join('<tr>'+''.join('<td>'+v+'</td>' for v in row)+'</tr>' for row in [head]+rows)+'</table>'

class FrendeTests(unittest.TestCase):
    def test_real_q1_q2_kpi_golden_values(self):
        for q,quarter,ytd in [(1,93.9,93.9),(2,81.3,87.5)]:
            rows=extract(table(q),f'https://frende.wrep.it/q{q}-2026-frende-holding-as/sec/6',2026,q)
            index={(r['period_type'],r['metric']):r['value'] for r in rows}
            self.assertEqual(index['quarter','combined_ratio'],quarter)
            self.assertEqual(index['ytd','combined_ratio'],ytd)
            self.assertEqual(len(rows),6)
    def test_reject_wrong_period(self):
        with self.assertRaisesRegex(ValueError,'header'):
            extract(table(2),'https://frende.wrep.it/q2-2026-frende-holding-as/sec/6',2026,3)
    def test_reject_wrong_entity(self):
        with self.assertRaisesRegex(ValueError,'group'):
            extract(table(1).replace('Nøkkeltall konsern','Nøkkeltall skadeforsikring'),'url',2026,1)
    def test_reject_untrusted_publisher(self):
        with self.assertRaisesRegex(ValueError,'Untrusted'):
            read('https://bad.example/q2-2026-frende-holding-as')
    def test_reject_bad_ratio(self):
        with self.assertRaisesRegex(ValueError,'reconcile'):
            extract(table(1).replace('93,9 %','99,9 %'),'url',2026,1)
if __name__=='__main__':unittest.main()
