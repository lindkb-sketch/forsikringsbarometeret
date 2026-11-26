import hashlib
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_market_overview_segments import parse_tryg,parse_gjensidige,parse_alm,build
URL='https://tryg.com/report.pdf'
SHA=hashlib.sha256(b'%PDF-test').hexdigest()

def tryg_block(name,revenue,cr):
    return f'{name}\nInsurance revenue {revenue} 1000 1000 1000 1000\nClaims ratio, net of reinsurance {cr-12} 68 68 68 68\nExpense ratio 12 12 12 12 12\nCombined ratio {cr} 80 80 80 80\n'

def gj_table(revenue,cr):
    return f'NOK millions Q3 2026 Q3 2025 YTD 2026 YTD 2025 FY 2025\nInsurance revenue {revenue} 1000.0 2000.0 2000.0 3000.0\nLoss ratio, net of reinsurance¹ {cr-12}.0 68.0 68.0 68.0 68.0\nCost ratio¹ 12.0 12.0 12.0 12.0 12.0\nCombined ratio¹ {cr}.0 80.0 80.0 80.0 80.0\n'

class MarketSegmentTests(unittest.TestCase):
    def test_tryg_exact_quarter_and_segment(self):
        text='Quarterly outline - Segments\nDKKm Q3 Q2 Q1 Q4 Q3\n2026 2026 2026 2025 2025\n'+tryg_block('Private',2000,75)+tryg_block('Commercial',3000,80)
        rows=parse_tryg([(34,text)],2026,3,URL,SHA)
        self.assertEqual(len(rows),16)
        self.assertEqual({r['segment'] for r in rows},{'Private','Commercial'})
        self.assertEqual(next(r['value'] for r in rows if r['segment']=='Private' and r['year']==2026 and r['metric']=='insurance_revenue'),2000)
        with self.assertRaises(ValueError):parse_tryg([(34,text.replace('Quarterly outline - Segments','Quarterly outline - Geography'))],2026,3,URL,SHA)
        with self.assertRaises(ValueError):parse_tryg([(34,text)],2027,3,URL,SHA)
    def test_gjensidige_group_is_not_norway(self):
        pages=[(9,'General Insurance Private'),(10,gj_table(2000,75)),
               (11,'General Insurance Private Norway\n'+gj_table(1000,70)),
               (13,'General Insurance Commercial'),(14,gj_table(3000,80)),
               (15,'General Insurance Commercial Norway\n'+gj_table(2000,77))]
        rows=parse_gjensidige(pages,2026,3,'https://mb.cision.com/report.pdf',SHA)
        self.assertEqual({r['source_page'] for r in rows},{10,14})
        self.assertEqual(len(rows),16)
        with self.assertRaises(ValueError):parse_gjensidige(pages[2:],2026,3,'https://mb.cision.com/report.pdf',SHA)
    def test_alm_personal_commercial_and_excludes_gross_claims(self):
        def page(label,rev,prior,loss,cost,cr):
            return (label+'\nQ3 Q3\nDKKm 2026 2025 Change\n'
                +f'Insurance revenue {rev} {prior} 10\n'
                +'Gross claims ratio 60.2 64.4 -4.2\n'
                +f'Claims ratio {loss} 66.3 -5.0\nGross expense ratio {cost} 16.7 0.3\nCombined ratio {cr} 83.0 -4.7\n'
                +f'Claims ratio {loss} 66.3 -5.0\n')
        rows=parse_alm([(8,page('Personal Lines',1658,1584,61.3,17.0,78.3)),
                        (9,page('Commercial Lines',1396,1422,56.7,15.0,71.7))],
                       2026,3,'https://almbrand.dk/report.pdf',SHA)
        self.assertEqual(len(rows),16)
        self.assertEqual(next(r['value'] for r in rows if r['segment']=='Private' and r['metric']=='loss_ratio' and r['year']==2026),61.3)
    def test_interleaved_report_columns(self):
        p=gj_table(4964.4,69.7).replace('69.7.0','69.7').replace('57.7.0','57.7')
        p=p.replace('Insurance revenue','the loss and cost ratios. Insurance revenue').replace('Combined ratio¹','than in the previous quarter. Combined ratio¹')+'\nUnderlying frequency loss ratio, net of reinsurance¹ 58.6 % 63.1 % 60.3 % 64.4 % 63.8 %'
        rows=parse_gjensidige([(10,'General Insurance Private (change in local currency)'),(11,p),(14,'General Insurance Commercial'),(15,p)],2026,3,'https://mb.cision.com/report.pdf',SHA)
        self.assertEqual({r['source_page'] for r in rows},{11,15})
    def test_bad_hash_excluded_and_no_stale_segment(self):
        row=dict(company='Tryg',year=2026,quarter=3,scope='group',period_type='quarter',metric='insurance_revenue',source_type='official_quarterly_report',status='reported',source_url=URL,source_sha256='a'*64)
        out=build({'observations':[row]},{'observations':[]},lambda _:b'%PDF-test')
        self.assertEqual(out['observations'],[])
        self.assertEqual(out['status']['Tryg']['status'],'not_verified')

    def test_alm_q1_market_validation_independent_of_group_pbt(self):
        from build_market_overview_context import verify_alm_market_quarter, weighted
        # Isolated segment-table fixture; never used as published data.
        cover='ALM. BRAND GROUP\nInterim report Q1\n2026'
        pm=('Personal Lines\nQ1 Q1\nDKKm 2026 2025 Change\n'
            'Insurance revenue 1,591 1,496 95\n'
            'Claims expenses -1,006 -970 -36\n'
            'Insurance operating expenses -319 -305 -14\n'
            'Profit/loss on reinsurance -20 -30 10\n'
            'Insurance service result 246 191 55\n'
            'Claims ratio 64.5 66.8 -2.3\n'
            'Gross expense ratio 20.0 20.3 -0.3\n'
            'Combined ratio 84.5 87.1 -2.6\n')
        bm=('Commercial Lines\nQ1 Q1\nDKKm 2026 2025 Change\n'
            'Insurance revenue 1,338 1,362 -24\n'
            'Claims expenses -792 -891 99\n'
            'Insurance operating expenses -216 -227 11\n'
            'Profit/loss on reinsurance -80 -98 18\n'
            'Insurance service result 250 146 104\n'
            'Claims ratio 65.1 72.6 -7.5\n'
            'Gross expense ratio 16.2 16.7 -0.5\n'
            'Combined ratio 81.3 89.3 -8.0\n')
        pages=[(1,cover),(7,pm),(8,bm)]
        url='https://attachment.news.eu.nasdaq.com/a8aef29e05c3998da5abf849fa270f731'
        rows=verify_alm_market_quarter(pages,2026,1,url,SHA)
        self.assertEqual(len(rows),16)
        self.assertEqual({(r['segment'],r['source_page']) for r in rows},{('Private',7),('Commercial',8)})
        self.assertEqual(next(r['value'] for r in rows if r['year']==2026 and r['segment']=='Commercial' and r['metric']=='combined_ratio'),81.3)
        anchor=dict(company='Alm. Brand',year=2026,quarter=2,source_url=url,source_sha256=SHA)
        self.assertEqual(weighted(anchor,'reported_segment','Private',rows),[])
        second=[{**r,'quarter':2,'source_document_period':'Q2 2026'} for r in rows]
        ytd=weighted(anchor,'reported_segment','Private',rows+second)
        self.assertEqual(len(ytd),8)
        self.assertEqual(next(r['value'] for r in ytd if r['year']==2026 and r['metric']=='insurance_revenue'),3182)
        for bad in ([(1,cover.replace('2026','2025')),(7,pm),(8,bm)],
                    pages[:2],[(1,cover),(7,pm.replace('246 191 55','346 191 155')),(8,bm)],
                    [(1,cover),(7,pm.replace('64.5 66.8 -2.3','65.5 66.8 -1.3').replace('84.5 87.1 -2.6','85.5 87.1 -1.6')),(8,bm)]):
            with self.assertRaises(ValueError):verify_alm_market_quarter(bad,2026,1,url,SHA)
        with self.assertRaises(ValueError):verify_alm_market_quarter(pages,2026,1,'https://example.com/report.pdf',SHA)

        # A future year has no bootstrap link. Discover the historical report
        # once, then reuse its exact URL/fingerprint on subsequent updates.
        from unittest.mock import patch
        from build_market_overview_context import alm_ytd
        def future_pages(q):
            return [(n,t.replace('Q1',f'Q{q}').replace('2026','2027').replace('2025','2026')) for n,t in pages]
        blobs={1:b'%PDF-fixture-q1',2:b'%PDF-fixture-q2'}
        urls={1:'https://almbrand.dk/q1-fixture.pdf',2:'https://almbrand.dk/q2-fixture.pdf',3:'https://almbrand.dk/q3-fixture.pdf'}
        def anchor(q):
            return dict(company='Alm. Brand',year=2027,quarter=q,source_url=urls[q],source_sha256=hashlib.sha256(blobs.get(q,b'%PDF-fixture-q3')).hexdigest())
        registry={}
        with patch('alm_brand_report_discovery.discover',return_value=[dict(url=urls[1],document_type='quarterly_report')]) as discover, \
             patch('alm_brand_live_pdf.download_report',side_effect=lambda u:blobs[1] if u==urls[1] else blobs[2]), \
             patch('build_market_overview_context.read_pages',side_effect=lambda raw:future_pages(1 if raw==blobs[1] else 2)):
            q2=alm_ytd(anchor(2),future_pages(2),registry)
            self.assertEqual(len(q2),16)
            discover.assert_called_once_with(2027,1)
            self.assertEqual(registry['Q1 2027']['source_sha256'],anchor(1)['source_sha256'])
            self.assertEqual(registry['Q2 2027']['source_url'],urls[2])
            q3=alm_ytd(anchor(3),future_pages(3),registry)
            self.assertEqual(len(q3),16)
            self.assertEqual(discover.call_count,1)
            self.assertEqual(next(r['value'] for r in q3 if r['year']==2027 and r['segment']=='Private' and r['metric']=='insurance_revenue'),4773)
            self.assertEqual({d['quarter'] for d in q3[0]['source_documents']},{1,2,3})
            registry['Q1 2027']['source_sha256']='f'*64
            with self.assertRaisesRegex(ValueError,'fingerprint changed'):
                alm_ytd(anchor(3),future_pages(3),registry)


    def test_market_growth_drivers_are_scoped_and_period_specific(self):
        from build_market_overview_context import growth_drivers
        a=dict(company='Fremtind',year=2026,quarter=3,source_url='https://issuer.invalid/report.pdf',source_sha256=SHA)
        q='Styrets beretning\nResultatutvikling i kvartalet\nprivatmarkedet har en økning og bedriftsmarkedet har en økning. Veksten er hovedsakelig drevet av premiejusteringer.'
        y=q.replace('Resultatutvikling i kvartalet','Resultatutvikling hittil i år')
        out=growth_drivers(a,[(9,q+'\n'+y)])
        self.assertEqual({r['period_type'] for r in out},{'quarter','ytd'})
        self.assertTrue(all(r['driver']=='price' and 'norway/pm' in r['views'] and r['source_page']==9 for r in out))
        self.assertEqual({r['period_type'] for r in growth_drivers(a,[(9,q)])},{'quarter'})
        self.assertEqual(growth_drivers(a,[(9,q.replace('Veksten er hovedsakelig drevet av premiejusteringer.','Ingen forklaring.'))]),[])
        a['company']='Tryg'
        out=growth_drivers(a,[(9,'Key figures - Private\nResults Q3 2026\nGrowth was positively impacted by portfolio growth in selected segments. Retention rates improved slightly.')])
        self.assertEqual({r['driver'] for r in out},{'portfolio_growth','retention_up'})
        self.assertTrue(all(r['period_type']=='quarter' and 'norway/pm' not in r['views'] for r in out))

if __name__=='__main__':unittest.main()
