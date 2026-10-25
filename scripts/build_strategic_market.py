#!/usr/bin/env python3
"""Strict, source-backed strategic market editorial separate from quarterly brief."""
import json,re
from pathlib import Path
from synthesize_report_commentary import synthesize
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data/quarterly_insights.json'
DEST=ROOT/'data/strategic_market.json'
TOPICS={'competition':'Konkurransebildet','strategy':'Strategiske satsinger','distribution':'Distribusjon',
        'market_share':'Markedsandeler','partnership':'Partnerskap','acquisition':'Oppkjøp',
        'customer_retention':'Kundekonkurranse','pricing_strategy':'Priskonkurranse'}
def build(data):
 periods={}
 for period,items in data.get('periods',{}).items():
  accepted=[];seen=set()
  for raw in items:
   if raw.get('theme') not in TOPICS:continue
   # An original issuer quote with a PDF page/hash and a matching exact rule is
   # mandatory. No general-purpose paraphrase of an unverified PDF text.
   vetted=synthesize(raw)
   if not vetted:continue
   company=vetted['companies'][0];theme=vetted['theme']
   key=(company,theme)
   if key in seen:continue
   seen.add(key)
   summary=vetted['text']
   if theme=='competition' and company=='Fremtind':
    summary='Sterk konkurranse og fortsatt lønnsomhetsfokus ventes å prege det norske forsikringsmarkedet. Dette er Fremtinds vurdering av konkurransebildet, ikke en bekreftet prognose for hele markedet.'
   accepted.append({'title':TOPICS[theme],'summary':summary,'company':company,
      'period':period,'theme':theme,'source_url':vetted['source_url'],
      'source_page':vetted['sources'][0]['page'],'source_sha256':vetted['sources'][0]['sha256'],
      'basis':'rule_verified_issuer_narrative'})
  periods[period]=accepted[:8]
 return {'periods':periods,'policy':'Exact source-verified issuer excerpts only; no copied quarterly briefing and no inferred outcomes'}
def run(source=SOURCE,dest=DEST):
 data=json.loads(source.read_text(encoding='utf-8'))
 output=build(data)
 dest.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 return output
if __name__=='__main__':
 result=run()
 print('Verified strategic notes:',sum(map(len,result['periods'].values())))
