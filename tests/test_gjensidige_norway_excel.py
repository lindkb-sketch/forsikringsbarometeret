import io,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import openpyxl
from gjensidige_norway_excel import parse

class NorwaySegments(unittest.TestCase):
    def test_private_and_commercial_sum_and_weighted_ratios(self):
        wb=openpyxl.Workbook();wb.remove(wb.active)
        for name,revenue,result,loss,cost in [
            ('General Insurance Private Norwa',4000,1000,.6,.1),
            ('General Insurance Commercial No',6000,2000,.5,.15)]:
            ws=wb.create_sheet(name)
            ws['A3']='NOK millions';ws['B3']='Q2 2026';ws['D3']='YTD 2026'
            for row,label,value in [(5,'Insurance revenue',revenue),(11,'Insurance service result',result),
                 (20,'Loss ratio, net of reinsurance²',loss),(21,'Cost ratio²',cost),(22,'Combined ratio²',loss+cost)]:
                ws.cell(row,1,label);ws.cell(row,2,value);ws.cell(row,4,value*2 if row in (5,11) else value)
            for row,label,value in [(8,'Incurred claims and changes in past and future service',-revenue*loss),
                (9,'Other incurred insurance service expenses',-revenue*cost),
                (12,'Reinsurance premiums',0),(13,'Amounts recovered from reinsurance',0)]:
                ws.cell(row,1,label);ws.cell(row,2,value);ws.cell(row,4,value*2)
        buf=io.BytesIO();wb.save(buf)
        aggregate,segments=parse(buf.getvalue(),'https://gjensidige.com/2026-Q2-keyfigures.xlsx',2,include_segments=True)
        quarter={r['metric']:r['value'] for r in aggregate if r['period_type']=='quarter'}
        self.assertAlmostEqual(quarter['insurance_revenue'],10000)
        self.assertAlmostEqual(quarter['insurance_service_result'],3000)
        self.assertAlmostEqual(quarter['loss_ratio'],54)
        self.assertAlmostEqual(quarter['expense_ratio'],13)
        self.assertAlmostEqual(quarter['combined_ratio'],67)
        self.assertEqual({r['segment'] for r in segments},{'PM Norge','BM Norge'})
        self.assertEqual(len(segments),20)

if __name__=='__main__':unittest.main()
