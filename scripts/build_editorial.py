#!/usr/bin/env python3
"""Generate factual brief and rule-based interpretations, never invent news."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def build(feed,news):
 rows=feed['observations']; periods=sorted({(r['year'],r['quarter']) for r in rows},reverse=True)
 if not periods:return {'period':None,'brief':[],'implications':[],'news':[],'coverage':'no_verified_data'}
 year,q=periods[0]; brief=[]; implications=[]
 for r in sorted(rows,key=lambda x:(x['company'],x['year'],x['quarter'],x['scope'],x['metric'])):
  if (r['year'],r['quarter'])!=(year,q) or r['period_type']!='quarter':continue
  metric=r['metric']
  if metric not in ('insurance_revenue','insurance_service_result','combined_ratio'):continue
  label={'insurance_revenue':'forsikringsinntekter','insurance_service_result':'forsikringsresultat','combined_ratio':'combined ratio'}[metric]
  if metric=='insurance_revenue' and any(
      token in r.get('source_definition','').lower()
      for token in ('not ifrs insurance revenue','segment premiums','premiums f.o.a.')):
   label='segmentpremier (APM, ikke IFRS-forsikringsinntekter)'
  unit='%' if metric=='combined_ratio' else r.get('unit','')
  brief.append({'text':f"{r['company']} ({r['scope']}): {label} {r['value']:g} {unit} i Q{q} {year}.",'source_url':r['source_url']})
  if metric=='combined_ratio' and r['scope']=='group':
   prior_q=4 if q==1 else q-1
   prior_y=year-1 if q==1 else year
   prior=next((x for x in rows if x['company']==r['company'] and
       x['scope']=='group' and x['metric']=='combined_ratio' and
       x['period_type']=='quarter' and (x['year'],x['quarter'])==(prior_y,prior_q)
       and x.get('status') in ('reported','calculated')),None)
   if prior:
    diff=round(r['value']-prior['value'],2)
    direction='forbedret' if diff<0 else 'svekket' if diff>0 else 'uendret'
    message=(f"{r['company']}: combined ratio {r['value']:g} % i Q{q} {year}, "
      f"{direction} med {abs(diff):g} prosentpoeng fra Q{prior_q} {prior_y} ({prior['value']:g} %).")
   else:
    message=(f"{r['company']}: kombinert skade- og kostnadsprosent "
      f"{r['value']:g} % i Q{q} {year}. Ingen verifisert sammenlignbar forrige kvartalsverdi.")
   implications.append({'text':message,'source_url':r['source_url'],
       'type':'rule_based_interpretation'})
 approved=[{'headline':n['headline'],'published_at':n['published_at'],'source_url':n['source_url'],'publisher':n.get('publisher','')} for n in news.get('items',[]) if n.get('approved') is True and n.get('headline') and n.get('published_at') and n.get('source_url','').startswith('https://')]
 return {'period':f'Q{q} {year}','brief':brief,'implications':implications,'news':sorted(approved,key=lambda n:n['published_at'],reverse=True),'coverage':'complete' if feed.get('coverage_complete') else 'partial','method':'verified financial feed and approved news only'}
def main():
 feed=json.loads((ROOT/'data/verified_financial_feed.json').read_text());news=json.loads((ROOT/'data/official_news.json').read_text());result=build(feed,news)
 (ROOT/'data/quarterly_editorial.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print('Editorial:',len(result['brief']),'facts,',len(result['implications']),'implications,',len(result['news']),'news')
if __name__=='__main__':main()
