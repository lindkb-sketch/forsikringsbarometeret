import datetime as dt,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from ingest_media_news import parse_rss,merge,relevant
NOW=dt.datetime(2026,10,25,tzinfo=dt.timezone.utc)
XML="""<rss><channel><item><title>Gjensidige øker forsikringsprisene - E24</title><link>https://news.google.com/rss/articles/abc</link><pubDate>Mon, 19 Oct 2026 10:00:00 GMT</pubDate><source url="https://e24.no">E24</source></item><item><title>Gjensidige</title><link>https://other.com/x</link><pubDate>Mon, 19 Oct 2026 10:00:00 GMT</pubDate><source url="https://unknown.com">Unknown</source></item></channel></rss>""".encode("utf-8")
class MediaTests(unittest.TestCase):
 def test_trusted_media_only(self):
  rows=parse_rss(XML,NOW);self.assertEqual(len(rows),1);self.assertEqual(rows[0]['publisher'],'E24')
 def test_dedup(self):
  rows=parse_rss(XML,NOW);self.assertEqual(len(merge({'items':rows},rows,now=NOW)['items']),1)
 def test_near_duplicate_cross_publisher_news_is_shown_only_once(self):
  story={'id':'nrk1','headline':'Storbrannen i Krokstadelva kostet Gjensidige 100 millioner kroner',
         'publisher':'NRK','published_at':'2026-10-23T07:00:00+00:00',
         'source_url':'https://news.google.com/rss/articles/a','approved':True}
  other={'id':'ap1','headline':'Storbrannen i Krokstadelva kosta Gjensidige 100 millionar kroner',
         'publisher':'Aftenposten','published_at':'2026-10-23T06:00:00+00:00',
         'source_url':'https://news.google.com/rss/articles/b','approved':True}
  self.assertEqual(len(merge({'items':[story]},[other],now=NOW)['items']),1)
 def test_different_insurer_headlines_are_not_collapsed(self):
  a={'id':'1','headline':'Gjensidige øker forsikringspremiene etter Q3 rapport',
      'published_at':'2026-10-23T07:00:00+00:00','source_url':'https://news.google.com/rss/articles/one'}
  b={'id':'2','headline':'Tryg øker forsikringspremiene etter Q3 rapport',
      'published_at':'2026-10-23T06:00:00+00:00','source_url':'https://news.google.com/rss/articles/two'}
  self.assertEqual(len(merge({'items':[a]},[b],now=NOW)['items']),2)
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
 def test_recent_insurance_claims_safety_and_customer_news(self):
  for headline in ('Gjensidige registrerte 513 skademeldinger i trafikken',
                   'Tryg advarer mot falsk trygghet fra adaptiv cruisekontroll på glatt føre',
                   'Frende: 3 av 4 bilister har mistet kontrollen på glatt føre',
                   'Storebrand slapp å dekke økt vannforbruk etter rørbrudd',
                   'EPSI-måling: DNB/Fremtind havner sist blant forsikringsselskaper'):
   self.assertTrue(relevant(headline),headline)
  for headline in ('Storebrand aksjekurs stiger etter kjøpsanbefaling',
                   'Tryg kvartalsrapport publisert','Vinterføre på fjellet'):
   self.assertFalse(relevant(headline),headline)
 def test_ntb_attributed_news_allowed_but_untrusted_source_rejected(self):
  xml=b'<rss><channel><item><title>Tryg advarer om vinterf\xc3\xb8re</title><link>https://news.google.com/rss/articles/ntb</link><pubDate>Sat, 24 Oct 2026 10:00:00 GMT</pubDate><source url="https://kommunikasjon.ntb.no">NTB Kommunikasjon</source></item></channel></rss>'
  self.assertEqual(parse_rss(xml,NOW)[0]['publisher'],'NTB Kommunikasjon')
 def test_nynorsk_bokmal_duplicates(self):
  a={'id':'a','headline':'Gjensidige øker forsikringsprisene etter storbrannen',
     'published_at':'2026-10-23T09:00:00+00:00','source_url':'https://example.org/1'}
  b={'id':'b','headline':'Gjensidige aukar forsikringsprisane etter storbrannen',
     'published_at':'2026-10-23T08:00:00+00:00','source_url':'https://example.org/2'}
  self.assertEqual(len(merge({'items':[a]},[b],now=NOW)['items']),1)
 def test_same_fire_loss_with_different_wording_not_duplicated(self):
  a={'id':'fire1','headline':'Storbrannen i Drammen koster Gjensidige 100 millioner',
     'published_at':'2026-10-23T09:00:00+00:00','source_url':'https://example.org/1'}
  b={'id':'fire2','headline':'Sommerens storbrann: Gjensidige tar kostnad på 100 millioner',
     'published_at':'2026-10-23T08:00:00+00:00','source_url':'https://example.org/2'}
  self.assertEqual(len(merge({'items':[a]},[b],now=NOW)['items']),1)
 def test_old_irrelevant_stories_removed_on_merge(self):
  old={'items':[{'id':'bad','headline':'STOREBRAND ASA: Notice of transaction by PDMR',
                  'published_at':'2026-10-23T08:00:00+00:00','source_url':'https://example.org/bad'}]}
  self.assertEqual(merge(old,[],now=NOW)['items'],[])
 def test_expire_old_stories_and_retain_fresh_stories(self):
  old={'items':[
   {'id':'stale','headline':'Gjensidige øker forsikringsprisene','published_at':'2026-09-01T08:00:00+00:00','source_url':'https://example.org/stale'},
   {'id':'fresh','headline':'Tryg rammet av store naturskader','published_at':'2026-10-24T08:00:00+00:00','source_url':'https://example.org/fresh'}]}
  self.assertEqual([x['id'] for x in merge(old,[],now=NOW)['items']],['fresh'])
 def test_refresh_metadata_and_discovery(self):
  from ingest_media_news import feed_urls
  result=merge({'items':[]},[],now=NOW)
  self.assertEqual(result['last_checked_at'],NOW.isoformat())
  self.assertIsNone(result['latest_headline_at'])
  self.assertEqual(len(feed_urls()),3)
 def test_no_unrelated(self):
  self.assertEqual(parse_rss(XML.replace('Gjensidige øker forsikringsprisene'.encode('utf-8'),b'Brod og mat'),NOW),[])
