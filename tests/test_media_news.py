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
 def test_near_duplicate_cross_publisher_news_is_shown_only_once(self):
  story={'id':'nrk1','headline':'Brannen i Krokstadelva kostet Gjensidige 100 millioner kroner',
         'publisher':'NRK','published_at':'2026-10-23T07:00:00+00:00',
         'source_url':'https://news.google.com/rss/articles/a','approved':True}
  other={'id':'ap1','headline':'Brannen i Krokstadelva kosta Gjensidige 100 millionar kroner',
         'publisher':'Aftenposten','published_at':'2026-10-23T06:00:00+00:00',
         'source_url':'https://news.google.com/rss/articles/b','approved':True}
  self.assertEqual(len(merge({'items':[story]},[other])['items']),1)
 def test_different_insurer_headlines_are_not_collapsed(self):
  a={'id':'1','headline':'Gjensidige øker forsikringspremiene etter Q3 rapport',
      'published_at':'2026-10-23T07:00:00+00:00','source_url':'https://news.google.com/rss/articles/one'}
  b={'id':'2','headline':'Tryg øker forsikringspremiene etter Q3 rapport',
      'published_at':'2026-10-23T06:00:00+00:00','source_url':'https://news.google.com/rss/articles/two'}
  self.assertEqual(len(merge({'items':[a]},[b])['items']),2)
 def test_no_unrelated(self):
  self.assertEqual(parse_rss(XML.replace(b'Gjensidige og forsikring',b'Brod og mat'),NOW),[])
