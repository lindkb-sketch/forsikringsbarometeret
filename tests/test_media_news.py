import datetime as dt,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from ingest_media_news import parse_rss,merge,relevant
NOW=dt.datetime(2026,10,20,tzinfo=dt.timezone.utc)
XML="""<rss><channel><item><title>Gjensidige øker forsikringsprisene - E24</title><link>https://news.google.com/rss/articles/abc</link><pubDate>Mon, 19 Oct 2026 10:00:00 GMT</pubDate><source url="https://e24.no">E24</source></item><item><title>Gjensidige</title><link>https://other.com/x</link><pubDate>Mon, 19 Oct 2026 10:00:00 GMT</pubDate><source url="https://unknown.com">Unknown</source></item></channel></rss>""".encode("utf-8")
class MediaTests(unittest.TestCase):
 def test_trusted_media_only(self):
  rows=parse_rss(XML,NOW);self.assertEqual(len(rows),1);self.assertEqual(rows[0]['publisher'],'E24')
 def test_dedup(self):
  rows=parse_rss(XML,NOW);self.assertEqual(len(merge({'items':rows},rows)['items']),1)
 def test_near_duplicate_cross_publisher_news_is_shown_only_once(self):
  story={'id':'nrk1','headline':'Storbrannen i Krokstadelva kostet Gjensidige 100 millioner kroner',
         'publisher':'NRK','published_at':'2026-10-23T07:00:00+00:00',
         'source_url':'https://news.google.com/rss/articles/a','approved':True}
  other={'id':'ap1','headline':'Storbrannen i Krokstadelva kosta Gjensidige 100 millionar kroner',
         'publisher':'Aftenposten','published_at':'2026-10-23T06:00:00+00:00',
         'source_url':'https://news.google.com/rss/articles/b','approved':True}
  self.assertEqual(len(merge({'items':[story]},[other])['items']),1)
 def test_different_insurer_headlines_are_not_collapsed(self):
  a={'id':'1','headline':'Gjensidige øker forsikringspremiene etter Q3 rapport',
      'published_at':'2026-10-23T07:00:00+00:00','source_url':'https://news.google.com/rss/articles/one'}
  b={'id':'2','headline':'Tryg øker forsikringspremiene etter Q3 rapport',
      'published_at':'2026-10-23T06:00:00+00:00','source_url':'https://news.google.com/rss/articles/two'}
  self.assertEqual(len(merge({'items':[a]},[b])['items']),2)
 def test_rejects_equity_noise(self):
  for headline in ('GJENSIDIGE FORSIKRING (GJF)',
                   'Storebrand styremedlem kjøpt 1.000 aksjer',
                   'STOREBRAND ASA: Notice of transaction by PDMR',
                   'Gjensidige kvartalsrapport'):
   self.assertFalse(relevant(headline),headline)
 def test_accepts_material_developments(self):
  for headline in ('Gjensidige øker forsikringsprisene',
                   'Fremtind kjøper opp forsikringsportefølje',
                   'Storebrand inngår distribusjonsavtale om forsikring',
                   'Tryg rammet av store naturskader'):
   self.assertTrue(relevant(headline),headline)
 def test_nynorsk_bokmal_duplicates(self):
  a={'id':'a','headline':'Gjensidige øker forsikringsprisene etter storbrannen',
     'published_at':'2026-10-23T09:00:00+00:00','source_url':'https://example.org/1'}
  b={'id':'b','headline':'Gjensidige aukar forsikringsprisane etter storbrannen',
     'published_at':'2026-10-23T08:00:00+00:00','source_url':'https://example.org/2'}
  self.assertEqual(len(merge({'items':[a]},[b])['items']),1)
 def test_old_irrelevant_stories_removed_on_merge(self):
  old={'items':[{'id':'bad','headline':'STOREBRAND ASA: Notice of transaction by PDMR',
                  'published_at':'2026-10-23T08:00:00+00:00','source_url':'https://example.org/bad'}]}
  self.assertEqual(merge(old,[])['items'],[])
 def test_no_unrelated(self):
  self.assertEqual(parse_rss(XML.replace('Gjensidige øker forsikringsprisene'.encode('utf-8'),b'Brod og mat'),NOW),[])
