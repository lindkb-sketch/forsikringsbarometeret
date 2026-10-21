import datetime as dt,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from ingest_media_news import parse_rss,merge
NOW=dt.datetime(2026,10,20,tzinfo=dt.timezone.utc)
XML=b"""<rss><channel><item><title>Gjensidige og forsikring - E24</title><link>https://news.google.com/rss/articles/abc</link><pubDate>Mon, 19 Oct 2026 10:00:00 GMT</pubDate><source url="https://e24.no">E24</source></item><item><title>Gjensidige</title><link>https://other.com/x</link><pubDate>Mon, 19 Oct 2026 10:00:00 GMT</pubDate><source url="https://unknown.com">Unknown</source></item></channel></rss>"""
class MediaTests(unittest.TestCase):
 def test_trusted_media_only(self):
  rows=parse_rss(XML,NOW);self.assertEqual(len(rows),1);self.assertEqual(rows[0]['publisher'],'E24')
 def test_dedup(self):
  rows=parse_rss(XML,NOW);self.assertEqual(len(merge({'items':rows},rows)['items']),1)
 def test_no_unrelated(self):
  self.assertEqual(parse_rss(XML.replace(b'Gjensidige og forsikring',b'Brod og mat'),NOW),[])
