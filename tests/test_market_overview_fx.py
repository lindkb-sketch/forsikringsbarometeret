import datetime as dt
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_market_overview_fx import average,bounds,build,url_for

def sample(currency,value,multiplier,year=2026,quarter=3):
    start,end=bounds(year,quarter)
    lines=['FREQ,BASE_CUR,QUOTE_CUR,TENOR,UNIT_MULT,TIME_PERIOD,OBS_VALUE']
    day=start
    while day<=end:
        if day.weekday()<5:lines.append(f'B,{currency},NOK,SP,{multiplier},{day},{value}')
        day+=dt.timedelta(days=1)
    return '\n'.join(lines)
class MarketFxTests(unittest.TestCase):
    def test_units(self):
        self.assertAlmostEqual(average(sample('DKK',150,2),'DKK',2026,3)['rate'],1.5)
        self.assertAlmostEqual(average(sample('EUR',11,0),'EUR',2026,3)['rate'],11)
    def test_incomplete_or_wrong_currency_rejected(self):
        with self.assertRaises(ValueError):average(sample('EUR',11,0).splitlines()[0]+'\n','EUR',2026,3)
        with self.assertRaises(ValueError):average(sample('DKK',150,2),'EUR',2026,3)
        with self.assertRaises(ValueError):average(sample('DKK',150,0),'DKK',2026,3)
    def test_fx_failure_does_not_invent_rate_or_use_other_period(self):
        f={'observations':[{'scope':'group','metric':'insurance_revenue','period_type':'quarter','status':'reported','year':2026,'quarter':3}]}
        def missing(_):raise OSError()
        x=build(f,{}, {'periods':{'Q2 2026':{'rates':{'DKK':1.5}}}},missing,dt.date(2026,11,26))
        self.assertEqual(x['periods']['Q3 2026']['rates'],{})
        self.assertIn('Q2 2026',x['periods'])
if __name__=='__main__':unittest.main()
