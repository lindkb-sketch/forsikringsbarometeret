#!/usr/bin/env python3
"""Fail-closed Norway extraction from issuer-linked Gjensidige key-figures XLSX.

Source is the issuer's own reports index. Never infer geography from group figures.
Values are stored in the workbook as NOK (not NOK millions) and ratios as fractions.
"""
import hashlib,io,json,re,urllib.parse,urllib.request
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
import openpyxl

INDEX='https://www.gjensidige.com/investor-relations/reports-and-presentations'
PDFS={1:'https://mb.cision.com/Public/1122/4341796/af7aaae92042a970.pdf',
      2:'https://mb.cision.com/Public/1122/4373892/b3fb98691b4814f0.pdf'}
APPROVED_XLSX={(2026,1):'https://mb.cision.com/Public/1122/4341797/873c4b7bc89a4c0f.xlsx',
               (2026,2):'https://mb.cision.com/Public/1122/4373899/b0ab985d8284a746.xlsx'}
SHEETS=('General Insurance Private Norway','General Insurance Commercial Norway')
LABELS={'insurance_revenue':'Insurance revenue','insurance_service_result':'Insurance service result',
        'loss_ratio':'Loss ratio, net of reinsurance','expense_ratio':'Cost ratio',
        'combined_ratio':'Combined ratio'}
# Monetary inputs for CR: insurance service expenses and net reinsurance
# result are signed amounts in the source financial statement.
CR_AMOUNT_LABELS={
 'claims':('Incurred claims and changes in past and future service',),
 'expenses':('Other incurred insurance service expenses',),
 'reinsurance_premiums':('Reinsurance premiums',),
 'reinsurance_recoveries':('Amounts recovered from reinsurance',)}
class Links(HTMLParser):
    def __init__(self): super().__init__();self.links=[];self.href=None;self.label=''
    def handle_starttag(self,tag,attrs):
        if tag=='a':self.href=dict(attrs).get('href');self.label=''
    def handle_data(self,data):
        if self.href is not None:self.label+=data
    def handle_endtag(self,tag):
        if tag=='a' and self.href:self.links.append((self.label.strip(),self.href));self.href=None

def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Forsikringsbarometeret/1.0'})
    with urllib.request.urlopen(req,timeout=35) as r:
        if r.status!=200:raise ValueError('HTTP status '+str(r.status))
        blob=r.read(20_000_001)
    if len(blob)>20_000_000:raise ValueError('Source too large')
    return blob

def locate_xlsx(page,quarter,base=INDEX,year=2026):
    """Only direct workbook links anchored in the Qn 2026 key-figures row."""
    from html import unescape
    raw=unescape(page.decode('utf-8','replace'))
    # Dynamic issuer pages sometimes have no anchor in static HTML: refuse to guess.
    candidates=[]
    for match in re.finditer('href="([^"]+[.]xlsx)"',raw,re.I):
        url=urllib.parse.urljoin(base,match.group(1))
        if urllib.parse.urlsplit(url).scheme!='https':continue
        context=raw[max(0,match.start()-1500):match.end()+300].lower()
        if re.search(r'key figures|nøkkeltall',context) and re.search(r'\b'+str(year)+r'\b',context):
            candidates.append(url)
    candidates=list(dict.fromkeys(candidates))
    # A link's proximity alone cannot identify Q1 vs Q2. Require quarter in URL.
    exact=[u for u in candidates if re.search(r'(?i)(?:q|quarter)[_\s%-]*'+str(quarter)+r'(?!\d)',urllib.parse.unquote(u))]
    if len(exact)!=1:raise ValueError(f'Cannot uniquely verify Q{quarter} {year} key-figures XLSX URL: {exact}')
    return exact[0]

def parse(blob,url,quarter,year=2026,include_segments=False):
    if not blob.startswith(b'PK'):raise ValueError('Not an XLSX archive')
    wb=openpyxl.load_workbook(io.BytesIO(blob),read_only=True,data_only=True)
    sheets={}
    for prefix in SHEETS:
        matches=[s for s in wb.sheetnames if s.startswith(prefix[:29])]
        if len(matches)!=1:raise ValueError('Missing or ambiguous Norway worksheet: '+prefix)
        sheets[prefix]=wb[matches[0]]
    output=[]
    segments=[]
    for period,col in [('quarter',2)]+([('ytd',4)] if quarter>1 else []):
        totals={}
        cr_inputs={}
        for prefix,ws in sheets.items():
            unit_header=str(ws.cell(3,1).value or '').lower()
            if 'million' in unit_header:
                monetary_divisor=1
            elif unit_header.strip() in ('nok','norwegian kroner'):
                monetary_divisor=1_000_000
            else:
                raise ValueError('Unrecognized source monetary unit in '+ws.title+': '+unit_header)
            header=str(ws.cell(3,col).value or '')
            expected=('Q'+str(quarter) if period=='quarter' else 'YTD')+' '+str(year)
            if header.strip()!=expected:raise ValueError('Unexpected column heading: '+header+' != '+expected)
            rows={}
            for row in range(1,ws.max_row+1):
                label=re.sub(r'[¹²³⁴⁵⁶⁷⁸⁹⁰]+','',str(ws.cell(row,1).value or '')).strip()
                if label in LABELS.values():rows.setdefault(label,[]).append(row)
            for metric,label in LABELS.items():
                if len(rows.get(label,[]))!=1:raise ValueError('Ambiguous metric '+label+' in '+prefix)
                cell=ws.cell(rows[label][0],col)
                if type(cell.value) not in (int,float):raise ValueError('Non-numeric source cell '+cell.coordinate)
                value=float(cell.value)*(100 if 'ratio' in metric else 1/monetary_divisor)
                totals.setdefault(metric,[]).append((value,ws.title,cell.coordinate))
                segments.append(dict(company='Gjensidige',year=year,quarter=quarter,
                    segment='PM Norge' if 'Private' in prefix else 'BM Norge',
                    period_type=period,metric=metric,value=round(value,6),
                    unit='percent' if 'ratio' in metric else 'MNOK',source_url=url,
                    source_sheet=ws.title,source_cell=cell.coordinate))
            # Compare each segment's reconstructed net CR with its standalone
            # published combined ratio before aggregating Norway.
            for kind,aliases in CR_AMOUNT_LABELS.items():
                hits=[]
                for row in range(1,ws.max_row+1):
                    label=re.sub(r'[¹²³⁴⁵⁶⁷⁸⁹⁰]+','',str(ws.cell(row,1).value or '')).strip()
                    if label in aliases:hits.append(row)
                if len(hits)!=1:
                    raise ValueError('Missing/ambiguous '+kind+' monetary row in '+ws.title)
                cell=ws.cell(hits[0],col)
                if type(cell.value) not in (int,float):
                    raise ValueError('Non-numeric '+kind+' at '+ws.title+'!'+cell.coordinate)
                cr_inputs.setdefault(kind,[]).append((float(cell.value)/monetary_divisor,ws.title,cell.coordinate))
        for i in range(2):
            seg_revenue=totals['insurance_revenue'][i][0]
            if seg_revenue<=0:raise ValueError('Nonpositive segment revenue')
            seg_cr=100*(-cr_inputs['claims'][i][0]-cr_inputs['expenses'][i][0]-cr_inputs['reinsurance_premiums'][i][0]-cr_inputs['reinsurance_recoveries'][i][0])/seg_revenue
            reported_cr=totals['combined_ratio'][i][0]
            if abs(seg_cr-reported_cr)>0.15:
                raise ValueError(f'Standalone PM/BM net CR mismatch in {totals["combined_ratio"][i][1]}: reconstructed={seg_cr:.4f}, reported={reported_cr:.4f}')
        revenue=sum(x[0] for x in totals['insurance_revenue'])
        service=sum(x[0] for x in totals['insurance_service_result'])
        if revenue <= 0:
            raise ValueError('Norway insurance revenue must be positive')
        # Signed expense and reinsurance rows: costs are negative in the
        # statement. The reinsurance net result is added with its source sign.
        claims=sum(x[0] for x in cr_inputs['claims'])
        costs=sum(x[0] for x in cr_inputs['expenses'])
        reinsurance=sum(x[0] for x in cr_inputs['reinsurance_premiums']+cr_inputs['reinsurance_recoveries'])
        if claims > 0 or costs > 0:
            raise ValueError('Unexpected positive claims or expenses; check source signs')
        net_loss=100*(-claims-reinsurance)/revenue
        expense_ratio=100*(-costs)/revenue
        combined=net_loss+expense_ratio
        if not 0 <= combined <= 200:
            raise ValueError('Norway combined ratio outside reasonable range')
        loss_expense={'loss_ratio':net_loss,'expense_ratio':expense_ratio,'combined_ratio':combined}
        for metric,value in [('insurance_revenue',revenue),('insurance_service_result',service)]+list(loss_expense.items()):
            output.append(dict(company='Gjensidige',year=year,quarter=quarter,scope='norway',source_scope='norway',
                period_type=period,metric=metric,value=round(value,6),unit='percent' if 'ratio' in metric else 'MNOK',
                status='reported' if metric in ('insurance_revenue','insurance_service_result') else 'calculated',
                calculation=('Net claims + signed reinsurance, plus operating expenses for CR, divided by summed PM and BM revenue' if 'ratio' in metric else None),
                source_url=url,source_type='official_investor_tables',source_document_url=PDFS.get(quarter) if year==2026 else None,
                source_sheet=' + '.join(x[1] for x in (sum(cr_inputs.values(),[])+totals['insurance_revenue'] if 'ratio' in metric else totals[metric])),
                source_cell=' + '.join(x[2] for x in (sum(cr_inputs.values(),[])+totals['insurance_revenue'] if 'ratio' in metric else totals[metric])),
                source_sha256=hashlib.sha256(blob).hexdigest(),
                source_section='PM Norway + BM Norway; claims, operating expenses, reinsurance premiums and recoveries summed with signs'))
    return (output,segments) if include_segments else output

if __name__=='__main__':
    from audit_financials import DATA,audit
    from build_verified_feed import publish
    page=get(INDEX)
    data=json.loads(DATA.read_text())
    all_segments=[]
    today=date.today()
    keys=lambda r:tuple(r[k] for k in ('company','year','quarter','scope','period_type','metric'))
    old={keys(r):r for r in data['observations']}
    for year in range(2026,today.year+1):
        for q in range(1,5):
            if (year,q)>(today.year,(today.month-1)//3+1):
                continue
            try:
                url=APPROVED_XLSX.get((year,q)) or locate_xlsx(page,q,year=year)
            except ValueError:
                if (year,q)==(today.year,(today.month-1)//3+1):
                    print(f'Gjensidige Norway Q{q} {year}: awaiting official XLSX')
                    continue
                raise
            rows,segment_rows=parse(get(url),url,q,year=year,include_segments=True)
            all_segments.extend(segment_rows)
            for row in rows:
                key=keys(row)
                if key in old and abs(old[key]['value']-row['value'])>0.001:
                    raise ValueError('Conflicting Norway observation')
                old[key]=row
    data['observations']=list(old.values())
    if not audit(data)['ok']:raise ValueError('Audit failed')
    DATA.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    publish()
    (DATA.parent/'gjensidige_norway_segments.json').write_text(json.dumps({'observations':all_segments},ensure_ascii=False,indent=2)+'\n')
