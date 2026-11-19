import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from klp_q2q3_reconcile import verify_pages

def pages(q):
    if q==2:
        a=('986,8','-834,5','-118,4','-27,0','7,0')
        y=('2 032,5','-1 700,4','-263,2','-65,9','3,1')
        ratios=('83,7','3,2','86,9','12,9','99,8')
        date='30.06.2026'
    else:
        a=('1 041,0','-746,0','-123,6','-57,8','113,6')
        y=('3 073,6','-2 446,4','-386,8','-123,7','116,7')
        ratios=('79,6','4,0','83,6','12,6','96,2')
        date='30.09.2026'
    names=['Forsikringsinntekter','Forsikringskostnader',
           'Forsikringsrelaterte driftskostnader','Gjenforsikringsresultat',
           'Forsikringsresultat etter gjenforsikring']
    result=['Resultatregnskap',
        f'NOTE MILLIONER KRONER {q}. kvartal 2026 {q}. kvartal 2025 {date} 30.09.2025 31.12.2025']
    result += [f'{name} {a[i]} 1,0 {y[i]} 1,0 1,0' for i,name in enumerate(names)]
    note=['Note 10 Nøkkeltall - akkumulert',
          f'MILLIONER KRONER {q}. kvartal 2026 1. kvartal 2026 4. kvartal 2025']
    for name,v in zip(['Skadeprosent brutto','Gjenforsikringsprosent',
        'Skadeprosent etter gjenforsikring','Kostnadsprosent','Totalskadeprosent'],ratios):
        note.append(f'{name} {v} % 90,0 % 80,0 % 70,0 % 60,0 %')
    texts=['']*21
    texts[5]='\n'.join(result)
    texts[20]='\n'.join(note)
    return texts

class KLPQ2Q3RealReconciliation(unittest.TestCase):
    def test_q2_isolated_not_ytd_subtraction(self):
        r=verify_pages(pages(2),2,'https://www.klp.no/q2.pdf','a'*64)
        self.assertAlmostEqual(r['ratios']['combined_ratio'],99.30077,places=4)
        self.assertEqual(r['reported_ytd_ratios']['combined_ratio'],99.8)
        self.assertEqual(r['reported_quarter_amounts']['insurance_revenue'],986.8)
        self.assertEqual(r['reported_ytd_amounts']['insurance_revenue'],2032.5)
    def test_q3_isolated_not_ytd_subtraction(self):
        r=verify_pages(pages(3),3,'https://www.klp.no/q3.pdf','a'*64)
        self.assertAlmostEqual(r['ratios']['combined_ratio'],89.08742,places=4)
        self.assertEqual(r['reported_ytd_ratios']['combined_ratio'],96.2)
    def test_wrong_ytd_blocks(self):
        t=pages(3)
        t[20]=t[20].replace('96,2 %','90,0 %')
        with self.assertRaisesRegex(ValueError,'reconciliation'):verify_pages(t,3,'https://www.klp.no/q3.pdf','a'*64)
    def test_wrong_quarter_header_blocks(self):
        t=pages(2)
        t[5]=t[5].replace('2. kvartal 2026 2. kvartal 2025',
                          '2. kvartal 2025 2. kvartal 2026')
        with self.assertRaisesRegex(ValueError,'column order'):verify_pages(t,2,'https://www.klp.no/q2.pdf','a'*64)
if __name__=='__main__':unittest.main()
