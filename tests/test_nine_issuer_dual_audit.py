"""Conservative issuer/period/type discovery, not synthetic production evidence."""
import hashlib
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from audit_nine_issuer_documents import archive_links,period_label,trusted,report_sources,verify_pdf_identity

class NineIssuerAuditTests(unittest.TestCase):
    def test_quarter_and_year_are_explicit(self):
        for label in ('Q3 2026','Q1-Q3 2026','2026 Q3','3Q 2026','3. kvartal 2026','January–September 2026','Q3-2026'):
            self.assertTrue(period_label(label,2026,3),label)
        for label in ('Q2 2026','Q3 2025','Q3 2025 full year 2026'):
            self.assertFalse(period_label(label,2026,3),label)
    def test_archive_directory_does_not_turn_reports_into_presentations(self):
        index='https://www.klp.no/om-klp/finans-og-ir/rapporter-og-presentasjoner'
        markup='<a href="/rapporter-og-presentasjoner/KLP-Skadeforsikring-Q3-2026.pdf">Kvartalsrapport 3. kvartal 2026</a>'
        self.assertEqual(archive_links('KLP Skadeforsikring',markup,index,2026,3),[])
        markup='<a href="/rapporter-og-presentasjoner/KLP-Konsern-Q3-2026-presentation.pdf">KLP konsern Q3 2026 presentation</a>'
        self.assertEqual(archive_links('KLP Skadeforsikring',markup,index,2026,3),[])
    def test_explicit_tryg_and_storebrand_quarter_links(self):
        index='https://tryg.com/en/downloads-2026'
        markup='<a href="/files/Q3-2026-Investor-presentation.pdf">Q3 2026 Investor presentation</a><a href="/files/Q2-2026-Investor-presentation.pdf">Q2 2026 Investor presentation</a>'
        links=archive_links('Tryg',markup,index,2026,3)
        self.assertEqual(len(links),1)
        self.assertEqual(links[0]['document_type'],'results_presentation')
        index='https://www.storebrand.com/welcome/investor-relations/quarterly-reporting/storebrand-asa/2026'
        markup='<h2>3rd quarter</h2><a href="/p.pdf">Analyst presentation</a><h2>2nd quarter</h2><a href="/p2.pdf">Analyst presentation</a>'
        self.assertEqual([x['url'] for x in archive_links('Storebrand',markup,index,2026,3)],['https://www.storebrand.com/p.pdf'])
    def test_trust_boundary_and_cover(self):
        self.assertFalse(trusted('Alm. Brand','https://s29.q4cdn.com/other/files/a.pdf'))
        self.assertFalse(trusted('Tryg','https://tryg.com.evil.test/a.pdf'))
        self.assertFalse(trusted('Tryg','https://attachment.news.eu.nasdaq.com/x'))
        self.assertTrue(trusted('Tryg','https://attachment.news.eu.nasdaq.com/x',exchange=True))
        self.assertTrue(verify_pdf_identity('Alm. Brand',['Alm. Brand Group Q3 2026 investor presentation'],2026,3,'results_presentation'))
        with self.assertRaises(ValueError):verify_pdf_identity('KLP Skadeforsikring',['KLP konsern Q3 2026','KLP Skadeforsikring segment'],2026,3,'results_presentation')
        with self.assertRaises(ValueError):verify_pdf_identity('Tryg',['Tryg Q2 2026 presentation'],2026,3,'results_presentation')
    def test_ytd_source_fingerprints_and_extended_documents(self):
        feed={'observations':[{'company':'Sampo','year':2026,'quarter':3,'scope':'group','period_type':'ytd',
            'metric':'return_on_equity','status':'reported','source_url':'https://www.sampo.com/report.pdf','source_sha256':'a'*64,'source_page':8}]}
        docs=report_sources(feed,{'insurers':{}},'Sampo',2026,3)
        self.assertEqual(docs[0]['expected_sha256'],['a'*64])
        self.assertEqual(docs[0]['source_pages'],[8])
        ext={'insurers':{'Alm. Brand':{'year':2026,'quarter':3,'ytd_pdf_evidence':{'source_url':'https://attachment.news.eu.nasdaq.com/x','source_sha256':'a'*64,'source_pages':{'solvency_ratio':5}},
              'presentation_evidence':{'source_url':'https://s29.q4cdn.com/228553818/files/p.pdf','source_sha256':'b'*64,'source_page':19}}}}
        docs=report_sources({},ext,'Alm. Brand',2026,3)
        self.assertEqual({x['document_type'] for x in docs},{'quarterly_report','results_presentation'})

    def test_presentation_explicit_reported_not_forecast(self):
        from reconcile_issuer_presentation_metrics import extract
        text='''Reported figures Q3 2026 and Consensus 2026-2028
Q3 2026 Q3 2026 2026 2027 2028
DKKm Reported Consensus Consensus Consensus Consensus
Insurance revenue 10,591 10,577 42,182 43,851 45,596
Combined ratio 76.8 78.3 83.1 80.5 80.3'''
        values={r['metric']:r['value'] for r in extract('Tryg',[text],2026,3)}
        self.assertEqual(values,{'insurance_revenue':10591.,'combined_ratio':76.8})
        self.assertEqual(extract('Tryg',[text.replace('DKKm Reported','DKKm Consensus')],2026,3),[])
        self.assertEqual(extract('Tryg',[text],2026,2),[])
    def test_sampo_different_periods_and_no_segment_leakage(self):
        from reconcile_issuer_presentation_metrics import extract
        text='''Group: results and key figures
EURm 1–9/2026 Q3/2026 Q3/2025 FY 2025
Insurance revenue, net 7,303 2,503 2,303 9,078
Underwriting result 1,221 435 392 1,485
Combined ratio, % 83.3 82.6 83.0 83.6'''
        rows=extract('Sampo',[text],2026,3)
        values={(r['metric'],r['period_type']):r['value'] for r in rows}
        self.assertEqual(values['insurance_revenue','quarter'],2503.)
        self.assertEqual(values['insurance_revenue','ytd'],7303.)
        self.assertEqual(values['combined_ratio','ytd'],83.3)
        self.assertEqual(extract('Sampo',[text.replace('Group:','Private Nordic:')],2026,3),[])
    def test_conflict_and_distinct_document_fingerprints(self):
        from reconcile_issuer_presentation_metrics import reconcile
        text='''Reported figures Q3 2026 and Consensus 2026-2028
Q3 2026 Q3 2026 2026 2027 2028
DKKm Reported Consensus Consensus Consensus Consensus
Combined ratio 76.8 78.3 83.1 80.5 80.3'''
        row=dict(company='Tryg',year=2026,quarter=3,scope='group',metric='combined_ratio',period_type='quarter',unit='percent',
                 source_sha256='a'*64,source_url='https://tryg.com/r.pdf',source_page=4,value=77.1)
        report=dict(expected_fingerprint_matches=True,source_sha256='a'*64,requested_url=row['source_url'])
        pres=dict(source_sha256='b'*64,url='https://tryg.com/p.pdf')
        self.assertEqual(reconcile('Tryg',2026,3,{'observations':[row]},[report],pres,[text])[0]['status'],'conflict')
        self.assertEqual(reconcile('Tryg',2026,3,{'observations':[row]},[report],dict(pres,source_sha256='a'*64),[text]),[])
if __name__=='__main__':unittest.main()

