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
    def test_owner_confirmed_report_only_issuers(self):
        from audit_nine_issuer_documents import presentation_policy,REPORT_ONLY_ISSUERS
        self.assertEqual(REPORT_ONLY_ISSUERS,{'Fremtind','KLP Skadeforsikring','Frende'})
        for company in REPORT_ONLY_ISSUERS:
            p=presentation_policy(company,[{'document_type':'quarterly_report','status':'verified_document'}])
            self.assertFalse(p['presentation_required'])
            self.assertEqual(p['presentation_exception'],'owner_confirmed_no_separate_results_presentation')
            self.assertFalse(p['presentation_exception_under_review'])
            # A new candidate is investigated even before it is verified.
            changed=presentation_policy(company,[{'document_type':'results_presentation','status':'unverified'}])
            self.assertTrue(changed['presentation_required'])
            self.assertTrue(changed['presentation_exception_under_review'])
            self.assertIsNone(changed['presentation_exception'])
        for company in ('Gjensidige','Tryg','Sampo','Protector','Storebrand','Alm. Brand'):
            p=presentation_policy(company,[])
            self.assertTrue(p['presentation_required'])
            self.assertIsNone(p['presentation_exception'])
    def test_newsweb_id_name_attachment(self):
        from audit_nine_issuer_documents import attachment_url
        self.assertEqual(attachment_url(684673,{'id':1234,'name':'Interim presentation Q3 2026.pdf'}),
            'https://api3.oslo.oslobors.no/v1/newsreader/attachment?messageId=684673&attachmentId=1234')
        self.assertEqual(attachment_url(684673,{'id':'../x'}),'')
        self.assertEqual(attachment_url(True,{'id':1}),'')
    def test_protector_period_labelled_income_statement(self):
        from reconcile_issuer_presentation_metrics import extract,number_columns
        text='''Income statement
All figures in NOKm unless otherwise stated.
NOKm Q3 2026 Q3 2025 Q1-Q3 2026 Q1-Q3 2025 FY 2025
Insurance revenue 3 864 3 529 11 258 10 197 13 756
Net result from reinsurance contracts held (161) (198) (513) (523) (541)
Insurance service result 670 598 1 912 1 571 2 106
Profit/(loss) before tax 1 120 640 2 402 2 541 3 438
Loss ratio 67.5% 66.6% 67.6% 68.5% 69.7%
Loss ratio, net of reinsurance 71.7% 72.2% 72.2% 73.6% 73.6%
Cost ratio 10.9% 10.9% 10.8% 11.0% 11.1%
Combined ratio 82.7% 83.1% 83.0% 84.6% 84.7%'''
        result={(x['metric'],x['period_type']):x['value'] for x in extract('Protector',[text],2026,3)}
        self.assertEqual(result['insurance_revenue','quarter'],3864)
        self.assertEqual(result['insurance_revenue','ytd'],11258)
        self.assertEqual(result['loss_ratio','quarter'],71.7)
        self.assertEqual(result['combined_ratio','ytd'],83.0)
        self.assertEqual(extract('Protector',[text],2027,3),[])
        self.assertIsNone(number_columns('1 234 567',2))
    def test_alm_financial_results_excludes_segment_and_forecast(self):
        from reconcile_issuer_presentation_metrics import extract
        text='''Financial highlights, Q3
Financial results
DKKm
Q3 2026 Q3 2025
Insurance revenue 3,054 3,006
Insurance service result 755 535
Combined ratio 75.3 82.2'''
        vals={x['metric']:x['value'] for x in extract('Alm. Brand',[text],2026,3)}
        self.assertEqual(vals,{'insurance_revenue':3054.,'insurance_service_result':755.,'combined_ratio':75.3})
        self.assertEqual(extract('Alm. Brand',[text.replace('Financial results','Guidance')],2026,3),[])
    def test_issuer_quarter_table_requires_group_year_and_correct_column(self):
        from audit_nine_issuer_documents import gjensidige_quarter_table
        page='https://www.gjensidige.com/no/investorinformasjon/rapporter-og-presentasjoner'
        table='''<h2>2026 - Gjensidige Forsikring Konsern</h2>
        <table><tr><th></th><th>Hele året</th><th>Q1</th><th>Q2</th><th>Q3</th><th>Q4</th></tr>
        <tr><th>Rapport</th><td></td><td></td><td></td><td><a href="/r3.pdf">PDF</a></td><td></td></tr>
        <tr><th>Presentasjon</th><td></td><td><a href="/p1.pdf">PDF</a></td><td><a href="/p2.pdf">PDF</a></td>
        <td><a href="https://mb.cision.com/Public/1122/abc.pdf">PDF</a></td><td></td></tr></table>'''
        self.assertEqual([x['url'] for x in gjensidige_quarter_table(table,page,2026,3)],['https://mb.cision.com/Public/1122/abc.pdf'])
        self.assertEqual(gjensidige_quarter_table(table,page,2027,3),[])
        self.assertEqual(gjensidige_quarter_table(table.replace('Forsikring Konsern','Pensjonsforsikring'),page,2026,3),[])
    def test_protector_issuer_detail_link_and_legal_attribution(self):
        from audit_nine_issuer_documents import issuer_detail_links,archive_links,verify_pdf_identity
        page='https://investor.protectorforsikring.no/press-releases'
        body='<a href="/pressreleases/q3-2026-results-abc">Q3 2026 results</a><a href="https://evil.test/pressreleases/q3-2026-results">Q3 2026 results</a>'
        self.assertEqual(issuer_detail_links('Protector',body,page,2026,3),['https://investor.protectorforsikring.no/pressreleases/q3-2026-results-abc'])
        detail='<a href="https://storage.mfn.se/id/investor-presentation-q3-2026-prot.pdf">Investor Presentation Q3 2026 (PROT)</a>'
        self.assertEqual(len(archive_links('Protector',detail,page,2026,3)),1)
        pages=['Investor Presentation\nQ3 2026 Interim results','Highlights','Claims',
               'This presentation has been prepared by and is the sole responsibility of Protector Forsikring ASA']
        self.assertTrue(verify_pdf_identity('Protector',pages,2026,3,'results_presentation'))
        with self.assertRaises(ValueError):verify_pdf_identity('Protector',pages[:-1]+['Mentions Protector Forsikring ASA'],2026,3,'results_presentation')
        with self.assertRaises(ValueError):verify_pdf_identity('Protector',pages,2026,2,'results_presentation')
    def test_alm_issuer_archive_discovers_both_types_and_rejects_other_periods(self):
        from audit_nine_issuer_documents import alm_archive_documents
        page='https://investorrelations.almbrand.dk/English/financials/default.aspx'
        prefix='https://s29.q4cdn.com/228553818/files/content_files/'
        markup=''.join(f'<a href="{prefix}{name}">{label}</a>' for name,label in [
            ('AB-GROUP-3Q-2026.pdf','Report'),
            ('Investor-presentation-Q3-2026.pdf','Presentation'),
            ('AB-GROUP-2Q-2026.pdf','Report'),
            ('Investor-presentation-Q3-2025.pdf','Presentation'),
            ('Preliminary-statement-Q3-2026.pdf','Report'),
            ('Roadshow-presentation-Q3-2026.pdf','Presentation'),
            ('Annual-report-2026.pdf','Report')])
        markup+='<a href="https://evil.test/Investor-presentation-Q3-2026.pdf">Presentation</a>'
        markup+='<a href="https://s29.q4cdn.com/999999/files/AB-GROUP-3Q-2026.pdf">Report</a>'
        docs=alm_archive_documents(markup,page,2026,3)
        self.assertEqual({(d['document_type'],d['url']) for d in docs},{
            ('quarterly_report',prefix+'AB-GROUP-3Q-2026.pdf'),
            ('results_presentation',prefix+'Investor-presentation-Q3-2026.pdf')})
        self.assertTrue(all(d['origin']==page and d['exchange'] is False for d in docs))
        self.assertEqual(alm_archive_documents(markup,page,2027,3),[])
        self.assertEqual(alm_archive_documents(markup,'https://evil.test/financials',2026,3),[])
        self.assertEqual(alm_archive_documents(markup,page,2026,2)[0]['url'],prefix+'AB-GROUP-2Q-2026.pdf')
    def test_alm_danish_archive_and_future_period(self):
        from audit_nine_issuer_documents import alm_archive_documents
        page='https://investorrelations.almbrand.dk/Danish/rapporter/default.aspx'
        prefix='https://s29.q4cdn.com/228553818/files/doc_financials/2027/q1/'
        markup=f'<h2>Q1 2027</h2><a href="{prefix}r.pdf">Rapport</a><a href="{prefix}Investor-pr%C3%A6sentation-Q1-2027.pdf">Præsentation</a>'
        markup+=f'<a href="{prefix}Investor-presentation-Q1-2026.pdf">Presentation</a>'
        docs=alm_archive_documents(markup,page,2027,1)
        self.assertEqual({d['document_type'] for d in docs},{'quarterly_report','results_presentation'})
        self.assertEqual(len(docs),2)
if __name__=='__main__':unittest.main()



