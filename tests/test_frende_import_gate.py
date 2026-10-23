import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from import_frende_holding import extract,extract_revenue,number,read

def table(q):
    if q==1:
        head=['Tall i 1000','Q1 2026','Q1 2025']
        rows=[['Kostnads %','21,6 %','22,2 %'],['Skadeprosent f.e.r','72,2 %','80,5 %'],['Combined ratio','93,9 %','102,7 %'],['Resultat før skatt','90 346','40 799']]
    else:
        head=['Tall i 1000','Q2 2026','Q2 2025','Pr Q2 2026','Pr Q2 2025']
        rows=[['Kostnads %','18,6 %','20,4 %','20,1 %','21,4 %'],['Skadeprosent f.e.r','62,8 %','64,1 %','67,4 %','72,1 %'],['Combined ratio','81,3 %','84,5 %','87,5 %','93,5 %'],['Resultat før skatt','347 322','307 631','437 669','348 429']]
    return '<h1>Nøkkeltall konsern</h1><table>'+''.join('<tr>'+''.join('<td>'+v+'</td>' for v in row)+'</tr>' for row in [head]+rows)+'</table>'

class FrendeTests(unittest.TestCase):
    def test_audit_rejects_frende_revenue_without_ifrs_definition(self):
        from audit_financials import audit
        row=dict(company='Frende',year=2026,quarter=2,scope='group',period_type='quarter',
                 metric='insurance_revenue',value=100,unit='NOKm',source_type='official_quarterly_report',
                 source_url='https://frende.wrep.it/q2-2026-frende-holding-as/sec/7',
                 source_page=7,source_definition='Sum driftsinntekter')
        self.assertTrue(any('Frende insurance revenue requires' in x for x in audit({'observations':[row]})['errors']))
    def test_real_q1_q2_kpi_golden_values(self):
        for q,quarter,ytd in [(1,93.9,93.9),(2,81.3,87.5)]:
            rows=extract(table(q),f'https://frende.wrep.it/q{q}-2026-frende-holding-as/sec/6',2026,q)
            index={(r['period_type'],r['metric']):r['value'] for r in rows}
            self.assertEqual(index['quarter','combined_ratio'],quarter)
            self.assertEqual(index['ytd','combined_ratio'],ytd)
            self.assertEqual(len(rows),6)
    def test_income_statement_q2_quarter_and_ytd(self):
        markup='<h1>Resultatregnskap</h1><table><tr><th>Resultatregnskap</th><th>2. kv 2026</th><th>2. kv 2025</th><th>30.06.26</th></tr><tr><td>Sum driftsinntekter</td><td>935 132</td><td>823 863</td><td>2 758 452</td></tr></table>'
        with self.assertRaisesRegex(ValueError,'not verified IFRS insurance_revenue'):
            extract_revenue(markup,'https://frende.wrep.it/q2-2026-frende-holding-as/sec/7',2026,2)
    def test_q4_omitted_expense_is_explicitly_calculated(self):
        markup='<h1>Nøkkeltall konsern</h1><table><tr><td>Tall i 1000</td><td>Q4 2025</td><td>Q4 2024</td><td>2025</td></tr><tr><td>Resultat før skatt</td><td>206 975</td><td>117 695</td><td>785 288</td></tr><tr><td>Skadeprosent f.e.r</td><td>62,8 %</td><td>67,6 %</td><td>67,2 %</td></tr><tr><td>Combined ratio</td><td>90,8 %</td><td>90,7 %</td><td>90,7 %</td></tr></table>'
        rows=extract(markup,'https://frende.wrep.it/q4-2025-frende-holding-as/sec/6',2025,4)
        expense=[r for r in rows if r['metric']=='expense_ratio']
        self.assertEqual([(r['period_type'],r['value'],r['status']) for r in expense],[('quarter',28.0,'calculated'),('ytd',23.5,'calculated')])
    def test_q4_missing_annual_column_fails_closed(self):
        markup='<h1>Nøkkeltall konsern</h1><table><tr><td>Tall i 1000</td><td>Q4 2025</td><td>Q4 2024</td></tr><tr><td>Kostnads %</td><td>20,0 %</td><td>21,0 %</td></tr><tr><td>Skadeprosent f.e.r</td><td>70,0 %</td><td>70,0 %</td></tr><tr><td>Combined ratio</td><td>90,0 %</td><td>91,0 %</td></tr><tr><td>Resultat før skatt</td><td>100</td><td>90</td></tr></table>'
        with self.assertRaisesRegex(ValueError,'Missing YTD column'):
            extract(markup,'https://frende.wrep.it/q4-2025-frende-holding-as/sec/6',2025,4)
    def test_2025_income_ytd_date_range(self):
        markup='<h1>Resultatregnskap</h1><table><tr><th>Resultatregnskap</th><th>2. kv 2025</th><th>2. kv 2024</th><th>01.01-30.06.25</th></tr><tr><td>Sum driftsinntekter</td><td>823 863</td><td>656 381</td><td>1 700 000</td></tr></table>'
        with self.assertRaisesRegex(ValueError,'not verified IFRS insurance_revenue'):
            extract_revenue(markup,'https://frende.wrep.it/q2-2025-frende-holding-as/sec/7',2025,2)
    def test_future_q3_publisher_layout(self):
        q2=table(2)
        q3=q2.replace('Q2 2026','Q3 2026').replace('Pr Q2 2026','Pr Q3 2026').replace('Q2 2025','Q3 2025').replace('Pr Q2 2025','Pr Q3 2025')
        rows=extract(q3,'https://frende.wrep.it/q3-2026-frende-holding-as/sec/6',2026,3)
        self.assertEqual({r['period_type'] for r in rows},{'quarter','ytd'})
        self.assertEqual({r['quarter'] for r in rows},{3})
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
