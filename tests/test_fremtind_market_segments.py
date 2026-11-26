import hashlib
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from fremtind_market_segments import parse_note,derive,records,check_batch
URL='https://cdn.sanity.io/files/rppnrdtw/production/example.pdf'
SHA='a'*64

def doc(y,q,pm,bm):
    header=f'Fremtind Holding Kvartalsrapport Q{q} {y}'
    amounts={'revenue':(pm,bm),'expenses':(-pm*7//10,-bm*8//10),'reinsurance':(-pm//100,-bm//100)}
    amounts['result']=tuple(sum(amounts[k][i] for k in ('revenue','expenses','reinsurance')) for i in range(2))
    labels={'revenue':'Inntekter fra forsikringstjenester','expenses':'Kostnader fra forsikringstjenester','reinsurance':'Netto resultat fra gjenforsikringskontrakter','result':'Resultat av forsikringstjenester'}
    fmt=lambda n:f'{n:,}'.replace(',',' ')
    note='Note 2 Segmentopplysninger\nNOK 1 000 PM BM Totalt\n'+'\n'.join(labels[k]+' '+' '.join(map(fmt,(*v,sum(v)))) for k,v in amounts.items())
    return parse_note([(1,header),(20,note)],y,q,URL,SHA)

class FremtindNoteTests(unittest.TestCase):
    def test_isolated_quarter_amounts_and_cr(self):
        a,b=doc(2026,3,15600000,3000000),doc(2026,2,10000000,2000000)
        self.assertEqual(derive(a,b,'Private'),(5600,71))
        self.assertEqual(derive(a,b,'Commercial'),(1000,81))
        anchor=dict(year=2026,quarter=3,source_url=URL,source_sha256=SHA)
        rows=records(a,b,anchor)+records(doc(2025,3,15000000,2800000),doc(2025,2,9800000,1800000),anchor)
        self.assertTrue(check_batch(rows,anchor))
        self.assertEqual({r['metric'] for r in rows},{'insurance_revenue','combined_ratio'})
        self.assertEqual(len(rows),8)
        rows[0]['value']+=1
        self.assertFalse(check_batch(rows,anchor))
    def test_q1_q4_and_wrong_period(self):
        a=doc(2026,1,4000000,800000)
        self.assertEqual(derive(a,None,'Private'),(4000,71))
        with self.assertRaises(ValueError):derive(doc(2026,3,12000000,2400000),a,'Private')
        self.assertEqual(derive(doc(2026,4,16000000,3200000),doc(2026,3,12000000,2400000),'Commercial'),(800,81))
if __name__=='__main__':unittest.main()
