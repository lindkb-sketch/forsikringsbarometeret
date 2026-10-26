#!/usr/bin/env python3
"""Backfill 2024 Storebrand ASA Insurance segment Q3 + YTD revenue.

The *official* Q3 2025 Storebrand supplementary report, linked by Storebrand's
2025 reporting archive, includes Table 23 comparison columns for 2024.
No standalone Storebrand Forsikring AS figures are used for this group segment.
"""
import hashlib,io,json,re,urllib.request
from pathlib import Path
import pdfplumber
from audit_financials import DATA,audit
from publish_geographic_workbooks import atomic_write

ROOT=Path(__file__).resolve().parents[1]
SOURCE='https://www.storebrand.com/welcome/investor-relations/quarterly-reporting/storebrand-asa/2025/_/attachment/inline/da62402f-d597-4d26-afc6-ad0ca6ab8039%3A0f32ecf07056118e0a078d4f6cd3a1de100f16e6/2025-3q-supplementary-information.pdf'
BASIS='APM: Insurance segment premiums f.o.a.; not IFRS insurance revenue'
AMOUNT=re.compile(r'(?<!\d)(?:\d{1,3}(?:[ ,]\d{3})+|\d+)(?!\d)')

def parse(pages):
    matches=[]
    for page,text in pages:
        if not re.search(r'Table\s*23\s*:?\s*Insurance\b',text,re.I):continue
        for line in text.splitlines():
            m=re.search(r'^\s*Insurance premiums f\.o\.a\.\s+(.+)$',line,re.I)
            if not m:continue
            vals=[int(v.replace(' ','').replace(',','')) for v in AMOUNT.findall(m.group(1))]
            # Columns: 2025 Q3 Q2 Q1, 2024 Q4 Q3, YTD 2025, YTD 2024, FY2024.
            if len(vals)!=8:continue
            if vals[0]!=2475 or vals[5]!=7140:continue
            matches.append((page,vals))
    if len(matches)!=1:
        excerpts=[]
        for page,text in pages:
            if re.search(r'insurance premiums f.o.a|Table 23',text,re.I):
                for line in text.splitlines():
                    if re.search(r'premiums f.o.a|Table 23',line,re.I):
                        excerpts.append((page,line[:240]))
        print('SOURCE_PDF_TABLE_DIAGNOSTIC',repr(excerpts[:15]),flush=True)
        for page,text in pages:
            if page==13:print('SOURCE_PDF_PAGE_13',repr(text[:3500]),flush=True)
        raise ValueError('Official Storebrand Insurance Table 23 missing or ambiguous: '+str(len(matches)))
    page,v=matches[0]
    return page,{(2025,'quarter'):v[0],(2024,'quarter'):v[4],
                 (2025,'ytd'):v[5],(2024,'ytd'):v[6]}

def run(target=DATA,fetch=None):
    if fetch is None:
        def fetch(url):
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 Forsikringsbarometeret'})
            with urllib.request.urlopen(req,timeout=45) as response:
                if not response.geturl().startswith('https://www.storebrand.com/'):raise ValueError('Untrusted Storebrand redirect')
                return response.read(35_000_001)
    blob=fetch(SOURCE)
    if len(blob)>35_000_000 or not blob.startswith(b'%PDF-'):raise ValueError('Not bounded Storebrand PDF')
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        if len(pdf.pages)>250:raise ValueError('Oversized Storebrand supplement')
        pages=[(i+1,p.extract_text() or '') for i,p in enumerate(pdf.pages)]
    page,values=parse(pages)
    baseline=json.loads(Path(target).read_text(encoding='utf-8'))
    if not audit(baseline)['ok']:raise ValueError('Invalid existing financial baseline')
    rows=baseline['observations']
    def existing(year,kind):
        return [x for x in rows if x.get('company')=='Storebrand'
                and x.get('scope')=='group' and x.get('year')==year
                and x.get('quarter')==3 and x.get('period_type')==kind
                and x.get('metric')=='insurance_revenue']
    sha=hashlib.sha256(blob).hexdigest()
    for kind in ('quarter','ytd'):
        old=existing(2025,kind)
        if len(old)!=1 or old[0]['value']!=values[(2025,kind)] or old[0].get('unit')!='MNOK':
            raise ValueError('Official 2025 Storebrand Insurance comparator conflicts with published values')
    added=0
    for kind in ('quarter','ytd'):
        amount=values[(2024,kind)]
        old=existing(2024,kind)
        if old:
            if len(old)!=1 or old[0]['value']!=amount:
                raise ValueError('2024 Storebrand official comparator conflict')
            continue
        rows.append(dict(company='Storebrand',year=2024,quarter=3,scope='group',
             period_type=kind,metric='insurance_revenue',value=amount,unit='MNOK',
             status='reported',source_type='official_quarterly_report',
             source_url=SOURCE,source_page=page,source_sha256=sha,
             source_entity='Storebrand ASA Insurance segment',
             source_document_period='Q3 2025',
             source_definition=BASIS+' (2024 comparative column)'))
        added+=1
    if added:
        if not audit(baseline)['ok']:raise ValueError('Backfill failed full financial audit')
        atomic_write(Path(target),baseline)
    print(json.dumps({'status':'verified','company':'Storebrand','new_rows':added,
         'year':2024,'quarter':3,'source_page':page,'source_sha256':sha,
         'q3':values[(2024,'quarter')],'ytd':values[(2024,'ytd')]}))
    return values

if __name__=='__main__':run()
