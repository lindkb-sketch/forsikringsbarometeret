#!/usr/bin/env python3
"""Source-backed financial briefs for every reported quarter and every insurer.

Publish transparent observations and arithmetic comparisons only: never invent
the cause of a movement or infer an unpublished report from a calendar date.
"""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
COMPANIES=('Fremtind','Gjensidige','Tryg','Sampo','Frende','Protector','Storebrand')

def revenue_label(row):
 definition=(row.get('source_definition') or '').lower()
 if any(x in definition for x in ('not ifrs insurance revenue','segment premiums','premiums f.o.a.')):
  return 'segmentpremier (APM, ikke IFRS-forsikringsinntekter)'
 return 'forsikringsinntekter'

def same_basis(a,b):
 return (a is not None and b is not None and
  a.get('unit')==b.get('unit') and revenue_label(a)==revenue_label(b))

def build(feed,news):
 rows=[r for r in feed.get('observations',[]) if
       r.get('status','reported') in ('reported','calculated') and r.get('scope')=='group'
       and r.get('period_type') in ('quarter','ytd')]
 dates=sorted({(r['year'],r['quarter']) for r in rows if r['period_type']=='quarter'},reverse=True)
 if not dates:
  return {'period':None,'brief':[],'implications':[],'news':[],
          'periods':{},'coverage':'no_verified_data'}
 by_key={(r['company'],r['year'],r['quarter'],r['period_type'],r['metric']):r for r in rows}
 def get(company,year,quarter,period,metric):
  return by_key.get((company,year,quarter,period,metric))
 periods={}
 for year,q in dates:
  label=f'Q{q} {year}'
  facts=[];implications=[];by_company={}
  for company in COMPANIES:
   cr=get(company,year,q,'quarter','combined_ratio')
   rev=get(company,year,q,'quarter','insurance_revenue')
   result=get(company,year,q,'quarter','insurance_service_result')
   if not any((cr,rev,result)):continue
   source=next(r['source_url'] for r in (cr,rev,result) if r and r.get('source_url'))
   previous_cr=get(company,year-1,q,'quarter','combined_ratio')
   previous_rev=get(company,year-1,q,'quarter','insurance_revenue')
   old_q=4 if q==1 else q-1
   old_year=year-1 if q==1 else year
   last_cr=get(company,old_year,old_q,'quarter','combined_ratio')
   intro=f'{company}: '
   details=[]
   if rev:
    revenue=f'{revenue_label(rev)} {rev["value"]:g} {rev.get("unit","")}'.strip()
    if same_basis(rev,previous_rev) and previous_rev['value']>0:
     growth=(rev['value']/previous_rev['value']-1)*100
     revenue+=f' ({growth:+.1f} % mot Q{q} {year-1})'
    details.append(revenue)
   if result:details.append(f'forsikringsresultat {result["value"]:g} {result.get("unit","")}'.strip())
   if cr:
    ratio=f'combined ratio {cr["value"]:g} %'
    if previous_cr:ratio+=f' (Q{q} {year-1}: {previous_cr["value"]:g} %)'
    details.append(ratio)
   fact={'text':intro+', '.join(details)+f' i {label}.','source_url':source,'company':company,
         'period':label,'type':'reported_summary'}
   facts.append(fact)
   comment=None
   if cr:
    if last_cr:
     diff=round(cr['value']-last_cr['value'],2)
     direction='forbedret' if diff<0 else 'svekket' if diff>0 else 'uendret'
     comment=(f'{company}: combined ratio {cr["value"]:g} % i {label}, '
              f'{direction} med {abs(diff):g} prosentpoeng fra Q{old_q} {old_year} '
              f'({last_cr["value"]:g} %).')
    elif previous_cr:
     diff=round(cr['value']-previous_cr['value'],2)
     direction='lavere' if diff<0 else 'høyere' if diff>0 else 'uendret'
     comment=(f'{company}: combined ratio {cr["value"]:g} % i {label}, '
              f'{abs(diff):g} prosentpoeng {direction} enn Q{q} {year-1} '
              f'({previous_cr["value"]:g} %).')
    else:
     comment=(f'{company}: combined ratio {cr["value"]:g} % i {label}. '
              'Ingen kildeverifisert, sammenlignbar referanseperiode.')
    implications.append({'text':comment,'source_url':cr['source_url'],
                         'company':company,'period':label,'type':'rule_based_interpretation'})
   ytd_rev=get(company,year,q,'ytd','insurance_revenue')
   prior_ytd=get(company,year-1,q,'ytd','insurance_revenue')
   ytd_note=''
   if ytd_rev:
    ytd_note=(f'HIÅ: {revenue_label(ytd_rev)} {ytd_rev["value"]:g} {ytd_rev.get("unit","")}'.strip()+'.')
    if same_basis(ytd_rev,prior_ytd) and prior_ytd['value']>0:
     change=(ytd_rev['value']/prior_ytd['value']-1)*100
     ytd_note=ytd_note[:-1]+f' ({change:+.1f} % mot HIÅ {year-1}).'
   by_company[company]={
    'summary':fact['text'],'comment':comment or fact['text'],
    'ytd':ytd_note,'source_url':source,'period':label,
    'has_comparative':bool(previous_cr or (rev and same_basis(rev,previous_rev)))}
  periods[label]={'brief':facts,'implications':implications,'by_company':by_company}
 current=f'Q{dates[0][1]} {dates[0][0]}'
 approved=[{'headline':n['headline'],'published_at':n['published_at'],
            'source_url':n['source_url'],'publisher':n.get('publisher','')} for n in news.get('items',[])
           if n.get('approved') is True and n.get('headline') and n.get('published_at')
           and n.get('source_url','').startswith('https://')]
 # De-duplicate verbatim headlines independently of publisher for downstream consumers.
 distinct={}
 for n in sorted(approved,key=lambda x:x['published_at'],reverse=True):
  key=' '.join(n['headline'].casefold().split())
  distinct.setdefault(key,n)
 return {'period':current,**periods[current],'periods':periods,
         'news':list(distinct.values()),
         'coverage':'complete' if feed.get('coverage_complete') else 'partial',
         'method':'verified quarterly financial observations, same-scope comparisons and source-attributed news'}

def main():
 feed=json.loads((ROOT/'data/verified_financial_feed.json').read_text(encoding='utf-8'))
 news=json.loads((ROOT/'data/official_news.json').read_text(encoding='utf-8'))
 result=build(feed,news)
 (ROOT/'data/quarterly_editorial.json').write_text(
  json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('Editorial',result['period'],len(result['brief']),'insurer briefs')

if __name__=='__main__':main()
