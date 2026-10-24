#!/usr/bin/env python3
"""Source-backed financial briefs for every reported quarter and every insurer.

Publish transparent observations and arithmetic comparisons only: never invent
the cause of a movement or infer an unpublished report from a calendar date.
"""
import json
from pathlib import Path
from synthesize_report_commentary import synthesize

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


def thematic_brief(by_company, rows, year, quarter):
 """Qualitative, grounded patterns only. No metrics or causal explanations invented."""
 current={(r['company'],r['metric']):r for r in rows if r.get('year')==year and
          r.get('quarter')==quarter and r.get('scope')=='group' and
          r.get('period_type')=='quarter' and r.get('status','reported') in ('reported','calculated')}
 previous={(r['company'],r['metric']):r for r in rows if r.get('year')==(year if quarter>1 else year-1) and
          r.get('quarter')==(quarter-1 if quarter>1 else 4) and
          r.get('scope')=='group' and r.get('period_type')=='quarter' and
          r.get('status','reported') in ('reported','calculated')}
 patterns={'better':[],'worse':[],'growing':[],'slowing':[]}
 sources={}
 for company in COMPANIES:
  sources[company]=by_company.get(company,{}).get('source_url')
  now=current.get((company,'combined_ratio'))
  old=previous.get((company,'combined_ratio'))
  if now and old and now.get('unit')==old.get('unit'):
   delta=now['value']-old['value']
   if delta < -0.25:patterns['better'].append(company)
   elif delta > 0.25:patterns['worse'].append(company)
  rev=current.get((company,'insurance_revenue'))
  prior=previous.get((company,'insurance_revenue'))
  if rev and prior and same_basis(rev,prior) and rev['value']>0 and prior['value']>0:
   delta=rev['value']-prior['value']
   if delta>0:patterns['growing'].append(company)
   elif delta<0:patterns['slowing'].append(company)
 def emit(text,names,theme):
  valid=[n for n in names if sources.get(n)]
  if not valid:return
  output.append({'text':text,'source_url':sources[valid[0]],
    'source_urls':[sources[n] for n in valid],
    'companies':valid,'period':f'Q{quarter} {year}',
    'type':'qualitative_quarter_theme','theme':theme})
 output=[]
 if patterns['better'] and patterns['worse']:
  emit('Kvartalet viser ulike lønnsomhetsretninger: '+', '.join(patterns['better'])+
       ' forbedrer forsikringsdriften sammenlignet med foregående kvartal, mens '+
       ', '.join(patterns['worse'])+' har en svakere utvikling. Dette viser et tydelig skille mellom selskapene, uten at rapporttallene alene forklarer årsaken.',
       patterns['better']+patterns['worse'],'diverging_underwriting')
 elif patterns['better']:
  emit('Et fellestrekk er forbedret forsikringslønnsomhet fra foregående kvartal hos '+
       ', '.join(patterns['better'])+'. Utviklingen er basert på sammenlignbare rapporterte forsikringsmåltall; årsakene må vurderes i selskapenes egne rapportkommentarer.',
       patterns['better'],'underwriting_improvement')
 elif patterns['worse']:
  emit('Forsikringslønnsomheten er svekket fra foregående kvartal hos '+
       ', '.join(patterns['worse'])+'. Rapporttallene viser utviklingen, men fastslår ikke alene hvilke hendelser som ligger bak.',
       patterns['worse'],'underwriting_pressure')
 if patterns['growing']:
  emit('Den rapporterte premie- eller inntektsutviklingen peker oppover hos '+
       ', '.join(patterns['growing'])+'. Selskapenes rapporteringsdefinisjoner er ulike, så dette er ikke en rangering av sammenlignbar vekst.',
       patterns['growing'],'revenue_direction')
 if patterns['slowing']:
  emit('Samtidig viser rapporterte inntekter eller segmentpremier en nedgang fra foregående kvartal hos '+
       ', '.join(patterns['slowing'])+'. Ulikt rapporteringsgrunnlag gjør at utviklingen bør vurderes selskap for selskap.',
       patterns['slowing'],'revenue_decline')
 if not output:
  names=list(by_company)
  emit('Kvartalsrapportene er registrert, men det finnes foreløpig ikke tilstrekkelig sammenlignbare opplysninger til å trekke dokumenterte fellestrekk eller forklare utviklingen. Les selskapenes rapporter for den kvalitative ledelsesgjennomgangen.',
       names,'insufficient_comparatives')
 return output

def documented_report_insights(label, available_companies):
 """Use only source-linked issuer commentary for this precise quarter."""
 path=ROOT/'data/quarterly_insights.json'
 if not path.exists():return None
 dataset=json.loads(path.read_text(encoding='utf-8'))
 rows=dataset.get('periods',{}).get(label)
 if not rows:return None
 # Curated claims cannot be transplanted onto arbitrary synthetic or unrelated report feeds.
 if any('example.org' in x.get('source_url','') or 'simulation.invalid' in x.get('source_url','') for x in available_companies.values()):return None
 result=[]
 for row in rows:
  # Literal extracted PDF fragments are evidence, not publish-ready analysis.
  if row.get('basis')=='issuer_pdf_verbatim':
   converted=synthesize(row)
   if not converted:continue
   row={**converted,'period':label}
  elif ' omtaler i kvartalsrapporten:' in row.get('text',''):continue
  linked=[x for x in row.get('sources',[]) if x.get('company') in available_companies and
          x.get('url','').startswith('https://') and x.get('kind') in ('official_company_release','issuer_interim_report_announcement','official_quarterly_report')]
  if not linked or not row.get('text') or not row.get('companies'):continue
  if not set(row['companies']).issubset(set(x['company'] for x in linked)):continue
  result.append({'text':row['text'],'source_url':linked[0]['url'],
       'source_urls':[x['url'] for x in linked], 'companies':row['companies'],
       'period':label,'type':'qualitative_quarter_theme','theme':row.get('theme','report_commentary'),
       'basis':row.get('basis','issuer_commentary'),'sources':linked})
 return result or None

def concise_brief(items, limit=220, max_paragraphs=4):
 """Keep a compact, source-backed executive briefing. Archive retains all findings."""
 priority={'large_claims':0,'weather':1,'reserves':2,'profitability':3,
           'diverging_underwriting':3,'underwriting_improvement':3,
           'underwriting_pressure':3,'growth':4,'revenue_direction':4,
           'revenue_decline':4,'strategy':5,'reinsurance':5,'competition':5,
           'inflation':5,'additional_insurers':2,'operations':6,'investment':6,'regulation':6}
 order=sorted(enumerate(items),key=lambda e:(0 if e[1].get('basis') in ('issuer_commentary','rule_verified_issuer_narrative') else 1,
   priority.get(e[1].get('theme'),7),e[0]))
 selected=[];total=0;themes=set();featured=set()
 pending=list(order)
 while pending and len(selected)<max_paragraphs:
  eligible=[(idx,item) for idx,item in pending if item.get('theme') not in themes
            and len(item['text'].split())<=limit-total]
  if not eligible:break
  if not selected:
   # Lead with the most material reported event, rather than issuer order.
   idx,item=eligible[0]
  else:
   # A new company with a genuinely different, source-backed finding can
   # replace repetitive coverage of already-featured companies.
   idx,item=min(eligible,key=lambda pair:(
    -len(set(pair[1].get('companies',[]))-featured),
    0 if pair[1].get('basis') in ('issuer_commentary','rule_verified_issuer_narrative') else 1,
    priority.get(pair[1].get('theme'),7), pair[0]))
  selected.append(item)
  total+=len(item['text'].split());themes.add(item.get('theme'))
  featured.update(item.get('companies',[]))
  pending=[pair for pair in pending if pair[0]!=idx]
 if not selected and items:
  # Never silently lose every source-backed observation to the display limit.
  selected=[min(items,key=lambda item:len(item['text'].split()))]
 return selected

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
  documented=documented_report_insights(label,by_company) or []
  baseline=thematic_brief(by_company,rows,year,q)
  # Preserve published issuer commentary while adding new arrivals, and use
  # audited comparative context only for themes not already explained by sources.
  covered={x.get('theme') for x in documented}
  brief=list(documented)
  for item in baseline:
   category='profitability' if item.get('theme') in ('diverging_underwriting','underwriting_improvement','underwriting_pressure') else (
     'growth' if item.get('theme') in ('revenue_direction','revenue_decline') else item.get('theme'))
   if category not in covered and documented and item.get('theme')!='insufficient_comparatives':
    brief.append(item)
  if not documented:brief=baseline
  # Use only same-basis verified underwriting changes for currently unfeatured
  # insurers; this creates no unsupported explanation of the movement.
  if year>=2026 and len(by_company)>=4:
   already={name for item in documented for name in item.get('companies',[])}
   changes={'better':[],'worse':[],'same':[]}
   references=[]
   old_q=4 if q==1 else q-1
   old_year=year-1 if q==1 else year
   for name in COMPANIES:
    if name not in by_company or name in already:continue
    current=get(name,year,q,'quarter','combined_ratio')
    previous=get(name,old_year,old_q,'quarter','combined_ratio')
    if not current or not previous or current.get('unit')!=previous.get('unit'):continue
    delta=current['value']-previous['value']
    kind='better' if delta < -0.25 else 'worse' if delta > 0.25 else 'same'
    changes[kind].append(name)
    references.append(current)
   parts=[]
   if changes['better']:parts.append(', '.join(changes['better'])+' har forbedret forsikringslønnsomheten fra foregående kvartal')
   if changes['worse']:parts.append(', '.join(changes['worse'])+' har svakere forsikringslønnsomhet')
   if changes['same']:parts.append(', '.join(changes['same'])+' viser omtrent uendret forsikringslønnsomhet')
   links=list(dict.fromkeys(x['source_url'] for x in references if x.get('source_url')))
   if parts and links:
    brief.append({'text':'; '.join(parts)+'. Utviklingen er basert på sammenlignbare rapporterte måltall, uten påstander om årsaker.',
                  'source_url':links[0],'source_urls':links,
                  'companies':changes['better']+changes['worse']+changes['same'],
                  'period':label,'type':'qualitative_quarter_theme',
                  'theme':'additional_insurers','basis':'verified_financial_comparison'})
  brief=concise_brief(brief)
  # Diagnostic coverage is separate from editorial selection: do not force
  # every issuer into a finite-size cross-market synthesis.
  mentioned={name for item in brief for name in item.get('companies',[])}
  evidence={name for item in documented for name in item.get('companies',[])}
  issuer_status={name:('featured' if name in mentioned else
                       'source_commentary_not_selected' if name in evidence else
                       'awaiting_curated_commentary')
                 for name in by_company}
  periods[label]={'brief':brief,'implications':implications,'by_company':by_company,
                  'issuer_brief_status':issuer_status,
                  'reported_company_count':len(by_company)}
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
         'method':'qualitative cross-company quarter themes from audited same-basis observations, without unverified causal explanations; source-attributed news'}

def main():
 feed=json.loads((ROOT/'data/verified_financial_feed.json').read_text(encoding='utf-8'))
 news=json.loads((ROOT/'data/official_news.json').read_text(encoding='utf-8'))
 result=build(feed,news)
 (ROOT/'data/quarterly_editorial.json').write_text(
  json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('Editorial',result['period'],len(result['brief']),'insurer briefs')

if __name__=='__main__':main()
