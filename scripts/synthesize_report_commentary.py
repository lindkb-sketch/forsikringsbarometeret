#!/usr/bin/env python3
"""Conservative, source-traceable narrative synthesis.

Only supported, unambiguous statements are turned into Norwegian editorial copy.
This is NOT an open-ended language model and cannot certify all future PDFs.
Unrecognized or garbled excerpts remain evidence-only.
"""
import re

# Deliberately narrow descriptions: the source must explicitly contain the
# driver AND its direction; never infer financial causation from a keyword.
PATTERNS=(
 ('large_claims',r'\bfewer large claims than budgeted\b',
  'opplyser at omfanget av storskader var lavere enn budsjettert'),
 ('reinsurance',r'\blower reinsurance prices\b',
  'viser til lavere priser på reassuranse'),
 ('competition',r'\bsterk konkurranse og fortsatt fokus på lønnsomhet\b',
  'forventer sterk konkurranse og fortsatt fokus på lønnsomhet'),
 ('inflation',r'\bværhendelser og skadeinflasjon\b',
  'fremhever værhendelser og skadeinflasjon som forhold det følger tett'),
 ('growth',r'\bpremium rate increases and growth in customer numbers\b',
  'viser til både premieøkninger og vekst i antall kunder'),
 ('operations',r'\bdisciplined pricing measures and high cost efficiency\b',
  'peker på disiplinert prising og høy kostnadseffektivitet'),
 ('inflation',r'\b(?:lønnsvekst, reparasjonskostnader, leverandørpriser og erstatningsnivåer)\b',
  'peker på lønnsvekst, reparasjonskostnader og leverandørpriser som påvirkninger på skadeutviklingen'),
 ('reinsurance',r'\blower reinsurance prices, driven by favourable market conditions\b',
  'melder om lavere reassuransepriser, blant annet som følge av gunstige markedsforhold'),
 ('weather',r'\bfavourable weather conditions\b',
  'beskriver gunstige værforhold i kvartalet'),
)
def synthesize(row):
 if row.get('basis')!='issuer_pdf_verbatim':return None
 sources=row.get('sources') or []
 if len(row.get('companies',[]))!=1 or len(sources)!=1:return None
 evidence=sources[0]
 if not all([evidence.get('url','').startswith('https://'),
             evidence.get('page'), evidence.get('sha256')]):return None
 original=row.get('text','')
 if '«' not in original or '»' not in original:return None
 quote=original.split('«',1)[1].split('»',1)[0]
 # Reject PDF multi-column joining, fragments and mislabeled sections.
 if len(quote)>250 or quote.count('.')>1 or quote.count('  '):return None
 if re.search(r'\b(?:contents|--|annual report|table of contents)\b',quote,re.I):return None
 if re.search(r'\b(?:contents|page|prospects|in the first quarter|second quarter|third quarter)\b',quote,re.I):return None
 matches=[(theme,phrase) for theme,needle,phrase in PATTERNS
          if theme==row.get('theme') and re.search(needle,quote,re.I)]
 if len(matches)!=1:return None
 company=row['companies'][0]
 theme,phrase=matches[0]
 return {'text':f'{company} {phrase}.',
         'source_url':evidence['url'],'source_urls':[evidence['url']],
         'companies':[company],'period':None,'type':'qualitative_quarter_theme',
         'theme':theme,'basis':'rule_verified_issuer_narrative',
         'sources':sources,'source_excerpt':quote}
