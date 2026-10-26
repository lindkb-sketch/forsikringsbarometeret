import json
import unittest
from scripts.prior_year_growth_coverage import evidence, COMPANIES, active_period

def row(company,year,kind,value,unit='MNOK',description='Insurance revenue'):
    return {'company':company,'year':year,'quarter':3,'period_type':kind,'scope':'group',
            'metric':'insurance_revenue','status':'reported','value':value,'unit':unit,
            'source_url':'https://issuer.example/report.pdf','source_type':'official_quarterly_report',
            'source_definition':description}

class PriorYearEvidenceTests(unittest.TestCase):
 def test_all_seven_issuers_reported_without_fake_growth(self):
    result=evidence([])
    self.assertEqual({r['company'] for r in result['companies']},set(COMPANIES))
    self.assertTrue(all(r['quarter']['growth_percent'] is None for r in result['companies']))
 def test_q3_and_ytd_are_independent(self):
    rows=[row('Tryg',2024,'quarter',100),row('Tryg',2025,'quarter',110),
          row('Tryg',2024,'ytd',300),row('Tryg',2025,'ytd',360)]
    result=next(r for r in evidence(rows)['companies'] if r['company']=='Tryg')
    self.assertEqual(result['quarter']['growth_percent'],10.0)
    self.assertEqual(result['ytd']['growth_percent'],20.0)
 def test_reject_mixed_revenue_definitions(self):
    rows=[row('Storebrand',2024,'quarter',100),
          row('Storebrand',2025,'quarter',110,description='APM: Insurance segment premiums f.o.a.; not IFRS insurance revenue')]
    result=next(r for r in evidence(rows)['companies'] if r['company']=='Storebrand')
    self.assertEqual(result['quarter']['status'],'incomparable_basis')
 def test_auto_rollover_follows_latest_qualified_issuer_quarter(self):
    rows=[row('Tryg',2025,'quarter',100),row('Tryg',2024,'quarter',90)]
    rows.append({**row('Fremtind',2027,'quarter',130),'quarter':1})
    rows.append({**row('Fremtind',2027,'quarter',0),'quarter':1,'metric':'combined_ratio'})
    self.assertEqual(active_period(rows),(2027,1))

 def test_does_not_cross_quarters_or_scopes(self):
    rows=[row('Fremtind',2024,'quarter',100),row('Fremtind',2025,'quarter',120)]
    rows[0]['quarter']=2
    result=next(r for r in evidence(rows)['companies'] if r['company']=='Fremtind')
    self.assertEqual(result['quarter']['missing_years'],[2024])

if __name__=='__main__':unittest.main()
