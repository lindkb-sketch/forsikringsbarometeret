import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from protector_kpi_check import extract,METRICS

class ProtectorComparativeQuarterTests(unittest.TestCase):
 def test_five_quarter_source_columns_are_labeled_with_actual_year(self):
  def scope(name):
   p=['Q3 26','Q2 26','Q1 26','Q4 25','Q3 25']
   metrics=''.join('<div>'+label+'</div>'+''.join('<span>'+str((3864,3698,3696,3560,3529)[i] if metric=='insurance_revenue' else (670,684,559,535,598)[i] if metric=='insurance_service_result' else (82.7,81.5,84.9,85.0,83.1)[i] if metric=='combined_ratio' else 70+i)+'</span>' for i in range(5)) for label,metric in METRICS.items())
   return '<div>'+name+'</div>'+''.join('<span>'+p1+'</span>' for p1 in p)+metrics
  data=extract(scope('Protector')+scope('Norway'),include_history=True)
  self.assertEqual(len(data),50)
  self.assertEqual(data['group',2026,3,'insurance_revenue'],3864)
  self.assertEqual(data['group',2025,3,'insurance_revenue'],3529)
  self.assertEqual(data['group',2025,3,'insurance_service_result'],598)
  self.assertEqual(data['group',2025,3,'combined_ratio'],83.1)
  self.assertEqual(data['norway',2025,3,'insurance_revenue'],3529)
 def test_publish_uses_source_period_not_delivery_period(self):
  src=(ROOT/'scripts/protector_publish.py').read_text()
  self.assertIn("incoming.append(dict(company='Protector',year=y,quarter=q",src)
if __name__=='__main__':unittest.main()
