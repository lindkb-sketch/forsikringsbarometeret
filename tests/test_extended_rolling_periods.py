"""Synthetic future-release replay; no simulated observations are ever published."""
import copy
import json
import sys
import unittest
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from rolling_klp_reports import advance as advance_klp, verify_report as verify_klp
from rolling_alm_brand_reports import advance as advance_alm, verify_report as verify_alm, validate_rolling
from import_klp_production import build_snapshot
from test_klp_production_import import reconciled
from test_klp_q2q3_reconcile import pages as klp_q3_pages
from test_klp_q1_2026_pdf_reconcile import fixture as klp_q1_pages
from build_nine_insurer_comparison import build,COMPANIES,METRICS
from quarterly_kpi_completeness import build as coverage
from audit_financials import audit
from build_verified_feed import build as verified_feed

ROOT=Path(__file__).resolve().parents[1]
KLP='KLP Skadeforsikring'
ALM='Alm. Brand'
KLPU4='https://www.klp.no/opaque-q4.pdf'
KLPU1='https://www.klp.no/opaque-q1.pdf'
ALM_BASE='https://s29.q4cdn.com/228553818/files/'
ALMU4=ALM_BASE+'AB-GROUP-4Q-2026.pdf'
ALMU1=ALM_BASE+'AB-GROUP-1Q-2027.pdf'
PRES4=ALM_BASE+'Investor-presentation-Q4-2026.pdf'
PRES1=ALM_BASE+'Investor-presentation-Q1-2027.pdf'
SHA='a'*64

def klp_fixture(year,q):
    if q==4:
        p=[x.replace('3. kvartal 2026','4. kvartal 2026').replace('3. kvartal 2025','4. kvartal 2025').replace('30.09.','31.12.') for x in klp_q3_pages(3)]
        p[0]='KLP Skadeforsikring AS 4. kvartal 2026'
        return p
    p=[x.replace('2026','2027').replace('2025','2026') for x in klp_q1_pages()]
    p[0]='KLP Skadeforsikring AS 1. kvartal 2027'
    return p

def alm_fixture(year,q):
    # Illustrative values are intentionally synthetic, not new issuer figures.
    values=[
      ('INCOME Insurance revenue','1,000','800','4,000','3,200'),
      ('Claims expenses','500','400','2,000','1,600'),
      ('Insurance operating expenses','150','120','600','480'),
      ('Profit/loss on reinsurance','50','40','200','160'),
      ('Insurance service result','300','240','1,200','960'),
      ('Gross claims ratio','50.0','50.0','50.0','50.0'),
      ('Net reinsurance ratio','5.0','5.0','5.0','5.0'),
      ('Claims ratio','55.0','55.0','55.0','55.0'),
      ('Gross expense ratio','15.0','15.0','15.0','15.0'),
      ('Combined ratio','70.0','70.0','70.0','70.0')]
    columns=f'Q{q} {year} Q{q} {year-1}'
    if q==4:columns+=f' Q1-Q4 {year} Q1-Q4 {year-1}'
    p=[f'Alm. Brand Group interim report Q{q} {year}','','','','']
    p[2]='Total capital as a percentage of solvency capital\nrequirement 240 230'
    p[4]=f'ALM. BRAND GROUP – Q{q} {year}\n'+columns+'\n'+'\n'.join(
        ' '.join([v[0],*(v[1:] if q==4 else v[1:3])]) for v in values)
    p[4]+='\nProfit/loss before tax, continuing\n'+('280 220 1100 880' if q==4 else '280 220')+'\noperations\nReturn on equity after tax\n'+('18.0 16.0 17.0 15.0' if q==4 else '18.0 16.0')+'\n(% p.a.) **'
    return p

def presentation(year,q):
    return [f'Alm. Brand insurance investor presentation Q{q} {year}',
        f'DKKm Q{q} {year} Q3 {year-1}\nTotal capital for the group for SCR 4,800 4,600\nSolvency capital requirement (SCR) 2,000 2,000\nTotal capital ratio 240% 230%']

def base_alm():
    data=json.loads((ROOT/'data/extended_insurer_financials.json').read_text(encoding='utf-8'))
    item=data['insurers'][ALM]
    return copy.deepcopy(item.get('periods',[item])[0])

class ExtendedRolloverTests(unittest.TestCase):
    def test_klp_two_real_parser_period_transitions(self):
        old=build_snapshot(*[reconciled(q) for q in (1,2,3)])
        html=f'<h2>KLP Skadeforsikring</h2><h3>2026</h3><a href="{KLPU4}">Kvartalsrapport 4. kvartal</a><h3>2027</h3><a href="{KLPU1}">Kvartalsrapport 1. kvartal</a>'
        raw={KLPU4:b'%PDF-Q4',KLPU1:b'%PDF-Q1'}
        texts={b'%PDF-Q4':klp_fixture(2026,4),b'%PDF-Q1':klp_fixture(2027,1)}
        opts=dict(today=date(2027,5,1),fetcher=lambda:html,downloader=lambda u,c:raw[u],extractor=lambda x:texts[x])
        result=advance_klp(old,**opts)
        self.assertEqual((result['year'],result['quarter']),(2027,1))
        self.assertEqual(result['periods'][:3],old['periods'])
        self.assertEqual([(p['year'],p['quarter']) for p in result['periods'][-2:]],[(2026,4),(2027,1)])
        self.assertNotIn('return_on_equity',result['metrics'])
        self.assertEqual(result['ytd_metrics']['profit_before_tax'],result['metrics']['profit_before_tax'])
        self.assertEqual(advance_klp(result,**opts),result)
    def test_klp_invalid_note_and_wrong_year_fail(self):
        x=klp_fixture(2026,4)
        with self.assertRaises(ValueError):verify_klp(x,2027,4,KLPU4,SHA)
        x[20]=x[20].replace('96,2 %','80,0 %')
        with self.assertRaisesRegex(ValueError,'reconciliation'):verify_klp(x,2026,4,KLPU4,SHA)
    def test_missing_next_period_cannot_jump(self):
        old=build_snapshot(*[reconciled(q) for q in (1,2,3)])
        html=f'<h2>KLP Skadeforsikring</h2><h3>2027</h3><a href="{KLPU1}">Kvartalsrapport 1. kvartal</a>'
        result=advance_klp(old,today=date(2027,5,1),fetcher=lambda:html,
            downloader=lambda *args: self.fail('Must not jump over missing Q4'))
        self.assertEqual(result,old)
    def test_alm_two_period_transition_and_independent_evidence(self):
        old=base_alm()
        html=''.join(f'<a href="{u}">{u.rsplit("/",1)[-1]}</a>' for u in (ALMU4,ALMU1,PRES4,PRES1))
        raw={u:('%PDF-'+str(i)).encode() for i,u in enumerate((ALMU4,ALMU1,PRES4,PRES1))}
        texts={raw[ALMU4]:alm_fixture(2026,4),raw[ALMU1]:alm_fixture(2027,1),
               raw[PRES4]:presentation(2026,4),raw[PRES1]:presentation(2027,1)}
        opts=dict(today=date(2027,5,1),fetcher=lambda u:html,downloader=lambda u:raw[u],reader=lambda b:(texts[b],{}))
        result=advance_alm(old,**opts)
        self.assertEqual((result['year'],result['quarter']),(2027,1))
        self.assertEqual(result['periods'][0],old)
        self.assertEqual([(x['year'],x['quarter']) for x in result['periods']],[(2026,3),(2026,4),(2027,1)])
        self.assertEqual(result['metrics']['insurance_revenue_growth'],25)
        self.assertEqual(result['metrics']['profit_before_tax'],280)
        self.assertEqual(result['metrics'],result['ytd_metrics'])
        self.assertEqual(validate_rolling(result),[])
        self.assertEqual(advance_alm(result,**opts),result)
        self.assertEqual(result['periods'][1]['ytd_metrics']['profit_before_tax'],1100)
        bad=copy.deepcopy(result);bad['presentation_evidence']['metrics']['solvency_ratio']=999
        self.assertTrue(validate_rolling(bad))
        texts[raw[PRES1]]=presentation(2027,1)
        texts[raw[PRES1]][1]=texts[raw[PRES1]][1].replace('240%','230%')
        with self.assertRaisesRegex(ValueError,'ratio mismatch'):advance_alm(old,**opts)
    def test_alm_wrong_period_or_annual_only_blocks(self):
        with self.assertRaises(ValueError):verify_alm(alm_fixture(2026,4),ALMU4,b'%PDF-Q4',2027,4)
        x=alm_fixture(2026,4)
        x[4]=x[4].replace('Q4 2026 Q4 2025 Q1-Q4 2026 Q1-Q4 2025','2026 2025')
        with self.assertRaisesRegex(ValueError,'column header'):verify_alm(x,ALMU4,b'%PDF-Q4',2026,4)

if __name__=='__main__':unittest.main()
