import io,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import openpyxl
from gjensidige_norway_excel import parse

class NorwaySegments(unittest.TestCase):
    def test_private_and_commercial_sum_and_weighted_ratios(self):
        wb=openpyxl.Workbook();wb.remove(wb.active)
        for name,revenue,result,loss,cost in [
            ('General Insurance Private Norwa',4_000_000_000,1_000_000_000,.6,.1),
            ('General Insurance Commercial No',6_000_000_000,2_000_000_000,.5,.15)]:
            ws=wb.create_sheet(name)
            ws['A3']='NOK millions';ws['B3']='Q2 2026';ws['D3']='YTD 2026'
            for row,label,value in [(5,'Insurance revenue',revenue),(11,'Insurance service result',result),
                 (20,'Loss ratio, net of reinsurance²',loss),(21,'Cost ratio²',cost),(22,'Combined ratio²',loss+cost)]:
                ws.cell(row,1,label);ws.cell(row,2,value);ws.cell(row,4,value*2 if row in (5,11) else value)
        buf=io.BytesIO();wb.save(buf)
        aggregate,segments=parse(buf.getvalue(),'https://gjensidige.com/2026-Q2-keyfigures.xlsx',2,include_segments=True)
        quarter={r['metric']:r['value'] for r in aggregate if r['period_type']=='quarter'}
        self.assertAlmostEqual(quarter['insurance_revenue'],10000)
        self.assertAlmostEqual(quarter['insurance_service_result'],3000)
        self.assertNotIn('loss_ratio',quarter)
        self.assertNotIn('expense_ratio',quarter)
        self.assertAlmostEqual(quarter['combined_ratio'],70)
        self.assertEqual({r['segment'] for r in segments},{'PM Norge','BM Norge'})
        self.assertEqual(len(segments),20)

if __name__=='__main__':unittest.main()
