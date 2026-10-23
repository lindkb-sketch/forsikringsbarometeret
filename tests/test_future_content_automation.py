"""Cross-domain future automation contracts for stocks, media, quarterly briefs and graphs."""
import copy,datetime as dt,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import update_stock_prices as stocks
from ingest_media_news import parse_rss,merge
from build_editorial import build as editorial
from build_verified_feed import build as verified

class FutureAutomation(unittest.TestCase):
 def test_stock_prices_source_failures_retained_and_logged(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/"stocks.json"
   original={"prices":{"Gjensidige":{"symbol":"GJF.OL","close":200,"currency":"NOK","trading_date":"2026-10-20","source_url":"https://query1.finance.yahoo.com/previous","price_type":"delayed_daily_close"}}}
   path.write_text(json.dumps(original))
   result=stocks.update(fetcher=lambda symbol: (_ for _ in ()).throw(ConnectionError("503")),out=path)
   self.assertEqual(result["prices"]["Gjensidige"],original["prices"]["Gjensidige"])
   self.assertEqual(set(result["errors"]),set(stocks.SYMBOLS))
   self.assertEqual(result["unlisted"],["Fremtind","Frende"])
 def test_stock_prices_new_verified_closes_and_idempotence(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/"stocks.json"
   def sample(symbol):return {"symbol":symbol,"close":101.25,"currency":"NOK","trading_date":"2026-10-23","source_url":"https://query1.finance.yahoo.com/chart","price_type":"delayed_daily_close"}
   a=stocks.update(fetcher=sample,out=path)
   b=stocks.update(fetcher=sample,out=path)
   self.assertEqual(a["prices"],b["prices"])
   self.assertEqual(len(b["prices"]),len(stocks.SYMBOLS))
 def test_news_rejects_untrusted_and_unrelated(self):
  now=dt.datetime(2026,10,23,12,tzinfo=dt.timezone.utc)
  xml=b'<rss><channel><item><title>Gjensidige kvartalsrapport</title><link>https://news.google.com/rss/x</link><pubDate>Fri, 23 Oct 2026 10:00:00 GMT</pubDate><source url="https://untrusted.invalid">Other</source></item></channel></rss>'
  self.assertEqual(parse_rss(xml,now),[])
 def test_news_merge_repeat_does_not_duplicate(self):
  row={"id":"x","headline":"Gjensidige rapporterer nye forsikringstall","publisher":"E24","published_at":"2026-10-23T10:00:00+00:00","source_url":"https://news.google.com/rss/x","approved":True}
  a=merge({"items":[]},[row])
  self.assertEqual(merge(a,[row]),a)
 def test_editorial_new_quarter_rollover_and_source(self):
  observations=[dict(company="Gjensidige",year=2026,quarter=q,scope="group",period_type="quarter",metric="combined_ratio",value=v,status="reported",source_url=f"https://example.org/q{q}.pdf",unit="percent") for q,v in [(3,81),(4,78)]]
  data=editorial({"observations":observations,"coverage_complete":False},{"items":[]})
  self.assertEqual(data["period"],"Q4 2026")
  self.assertEqual(data["periods"]["Q4 2026"]["by_company"]["Gjensidige"]["source_url"],"https://example.org/q4.pdf")
  self.assertIn("forbedret",data["implications"][0]["text"])
  self.assertIn("3 prosentpoeng",data["implications"][0]["text"])
 def test_unapproved_news_excluded_from_editorial(self):
  output=editorial({"observations":[]},{"items":[{"headline":"Fabricated","published_at":"2026-10-23","source_url":"https://example.org","approved":False}]})
  self.assertEqual(output["news"],[])
 def test_existing_feed_and_graph_source_contract(self):
  feed=json.loads((ROOT/"data/verified_financial_feed.json").read_text())
  self.assertEqual(verified(json.loads((ROOT/"data/financial_observations.json").read_text()))["observations"],feed["observations"])
  js=(ROOT/"scripts/quarterly_runtime.js").read_text()
  self.assertIn("verified_financial_feed.json?t=",js)
  self.assertIn("periodList=calcPeriods()",js)
  self.assertIn("profitabilityVerified[name][l]=[loss,cost,cr]",js)
 def test_automatic_workflow_preserved(self):
  workflow=(ROOT/".github/workflows/update.yml").read_text()
  self.assertIn("cron: '17,47 * * * *'",workflow)
  for name in ("ingest_media_news.py","update_stock_prices.py","run_pipeline.py","live_browser_e2e.cjs"):
   self.assertIn(name,workflow)

if __name__=="__main__":unittest.main()
