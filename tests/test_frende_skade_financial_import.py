"""Frende Skade report import must never mistake Holding data for subsidiary data."""
import unittest
from scripts.import_frende_skade import verify_period, build, parse_kpis

class FrendeSkadeImporterTests(unittest.TestCase):
    URL='https://frende.wrep.it/q3-2026-frende-skadeforsikring-as'
    def test_requires_correct_entity_and_quarter(self):
        with self.assertRaises(ValueError):
            verify_period('https://frende.wrep.it/q3-2026-frende-holding-as',2026,3,
                          lambda *args:'')
        with self.assertRaises(ValueError):
            verify_period(self.URL,2026,2,lambda *args:'')
    def test_blocks_unverified_numbers_and_keeps_existing(self):
        index={'reports':[{'year':2026,'quarter':3,'source_url':self.URL}]}
        result=build(index,reader=lambda *args:'<html>unverified</html>')
        self.assertEqual(result['observations'],[])
        self.assertEqual(len(result['diagnostics']),1)
    def test_official_kpis_must_reconcile(self):
        markup='''<h2>Nøkkeltall Frende Skadeforsikring AS</h2><table>
        <tr><th>Tall i 1000</th><th>Q3 2026</th><th>Pr Q3 2026</th></tr>
        <tr><td>Skadeprosent f.e.r</td><td>60,0 %</td><td>61,0 %</td></tr>
        <tr><td>Kostnads %</td><td>20,0 %</td><td>19,0 %</td></tr>
        <tr><td>Combined ratio</td><td>80,0 %</td><td>80,0 %</td></tr>
        </table>'''
        rows=parse_kpis(markup,self.URL+'/sec/6',2026,3)
        self.assertEqual(len(rows),6)
        self.assertTrue(all(r['source_entity']=='Frende Skadeforsikring AS' for r in rows))
        with self.assertRaisesRegex(ValueError,'reconcile'):
            parse_kpis(markup.replace('80,0 %','88,0 %'),self.URL+'/sec/6',2026,3)
if __name__=='__main__':
    unittest.main()
