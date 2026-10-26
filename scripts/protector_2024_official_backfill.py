#!/usr/bin/env python3
"""Import Protector Q3 and YTD 2024 comparators from issuer's Q3 2025 PDF.

A historical 2025 report exposes both Q3 2024 and Q1-Q3 2024 IFRS
insurance-revenue comparison columns. This backfill is source-verified and
idempotent, and it never substitutes gross written premiums.
"""
import hashlib,json,re,sys
from pathlib import Path
# Support both `python scripts/...py` and `python -m unittest ...`.
SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
from audit_financials import audit,DATA
from publish_geographic_workbooks import atomic_write
from protector_publish import download,parse_pdf

SOURCE='https://storage.mfn.se/34613cd2-9b91-47d8-bae6-1c5274fa1298/interim-report-q3-2025-prot.pdf'
COLUMNS=('2025_quarter','2024_quarter','2025_ytd','2024_ytd','2024_full_year')
def parse(pages):
    choices=[]
    for page,text in pages:
        if not (re.search(r'Income overview',text,re.I)
                and re.search(r'Q3\s*2025\s+Q3\s*2024\s+Q1.Q3\s*2025\s+Q1.Q3\s*2024',text,re.I)):
            continue
        for line in text.splitlines():
            match=re.match(r'^\s*Insurance revenue\s+((?:\d[\d, ]*\s+){4}\d[\d, ]*)$',line,re.I)
            if not match:continue
            values=re.findall(r'(?<!\d)\d{1,3}(?:,\d{3})*(?!\d)',match.group(1))
            if len(values)!=5:continue
            numbers=[int(v.replace(',','')) for v in values]
            choices.append((page,dict(zip(COLUMNS,numbers))))
    if len(choices)!=1:raise ValueError('Protector official insurance revenue row missing/ambiguous: '+str(len(choices)))
    return choices[0]

def run(path=DATA,fetch=download):
    blob=fetch(SOURCE)
    pages=parse_pdf(blob,2025,3)
    page,values=parse(pages)
    before=json.loads(Path(path).read_text(encoding='utf-8'))
    if not audit(before)['ok']:raise ValueError('Existing financial baseline failed audit')
    rows=before['observations']
    def existing(year,kind):
        return [x for x in rows if x.get('company')=='Protector' and x.get('scope')=='group'
                and x.get('year')==year and x.get('quarter')==3
                and x.get('period_type')==kind and x.get('metric')=='insurance_revenue']
    # Q3 2025 is already source-verified in the live quarterly importer.
    published=existing(2025,'quarter')
    if len(published)!=1 or published[0]['value']!=values['2025_quarter'] or published[0].get('unit')!='MNOK':
        raise ValueError('Official Protector Q3 2025 PDF conflicts with published report')
    sha=hashlib.sha256(blob).hexdigest()
    added=0
    for year,kind,col in ((2024,'quarter','2024_quarter'),
                          (2025,'ytd','2025_ytd'),(2024,'ytd','2024_ytd')):
        match=existing(year,kind)
        amount=values[col]
        if match:
            if len(match)!=1 or match[0]['value']!=amount:
                raise ValueError('Protector official historical comparator conflicts with existing observation')
            continue
        rows.append(dict(company='Protector',year=year,quarter=3,scope='group',
            period_type=kind,metric='insurance_revenue',value=amount,unit='MNOK',
            status='reported',source_type='official_quarterly_report',
            source_url=SOURCE,source_page=page,source_sha256=sha,
            source_entity='Protector Forsikring ASA',
            source_document_period='Q3 2025',source_definition='IFRS insurance revenue; official Q3 2025 income overview comparison column'))
        added+=1
    if added:
        if not audit(before)['ok']:raise ValueError('Protector historical additions failed audit')
        atomic_write(Path(path),before)
    print(json.dumps({'company':'Protector','year':2024,'quarter':3,'added':added,
                      'quarter_revenue':values['2024_quarter'],'ytd_revenue':values['2024_ytd'],
                      'source_sha256':sha,'source_page':page}))
if __name__=='__main__':run()
