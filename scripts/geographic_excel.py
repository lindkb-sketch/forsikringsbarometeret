#!/usr/bin/env python3
"""Strict geographical Norway quarter extraction from official issuer XLSX files.
Requires explicit workbook sheet, row label, Norway column, year/quarter header.
Only cached numeric cells are accepted. Ambiguity causes a hard failure.
"""
import re,sys,json,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
NS={'x':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships','p':'http://schemas.openxmlformats.org/package/2006/relationships'}
METRICS={'insurance_revenue':r'insurance revenue|forsikringsinntekter|forsikringsinntekter fra forsikringstjenester','insurance_service_result':r'insurance service result|forsikringsresultat','combined_ratio':r'combined ratio','loss_ratio':r'claims ratio,? net of reinsurance|claims ratio|loss ratio|skadeprosent','expense_ratio':r'expense ratio|kostnadsprosent'}
def load_sheets(path):
    with zipfile.ZipFile(path) as z:
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            root=ET.fromstring(z.read('xl/sharedStrings.xml'))
            strings=[''.join(n.text or '' for n in si.findall('.//x:t',NS)) for si in root.findall('x:si',NS)]
        wb=ET.fromstring(z.read('xl/workbook.xml'))
        rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        targets={r.attrib['Id']:r.attrib['Target'] for r in rels}
        out={}
        for sheet in wb.findall('.//x:sheet',NS):
            name=sheet.attrib['name'];rid=sheet.attrib['{%s}id'%NS['r']]
            target=targets[rid].lstrip('/')
            if not target.startswith('xl/'):target='xl/'+target
            root=ET.fromstring(z.read(target)); cells={}
            for c in root.findall('.//x:sheetData/x:row/x:c',NS):
                addr=c.attrib['r']; typ=c.attrib.get('t');v=c.find('x:v',NS)
                if typ=='inlineStr':value=''.join(t.text or '' for t in c.findall('.//x:t',NS))
                elif v is None:value=None
                elif typ=='s':value=strings[int(v.text)]
                elif typ in ('str','e'):value=v.text
                else:
                    try:value=float(v.text)
                    except (ValueError,TypeError):value=v.text
                cells[addr]=value
            out[name]=cells
        return out
def column(address):return re.match(r'[A-Z]+',address).group()
def rownum(address):return int(re.search(r'\d+',address).group())
def parse(path,company,year,quarter,workbook_url,report_pdf_url):
    if company not in ('Tryg','Gjensidige'):raise ValueError('Only Tryg/Gjensidige geographical workbooks supported')
    if not workbook_url.startswith('https://') or not workbook_url.lower().split('?')[0].endswith('.xlsx'):raise ValueError('Official XLSX URL required')
    if not report_pdf_url.startswith('https://') or not report_pdf_url.lower().split('?')[0].endswith('.pdf'):raise ValueError('Companion official quarterly PDF required')
    sheets=load_sheets(path)
    matches=[(name,cells) for name,cells in sheets.items() if re.search(r'geograph|geografi',name,re.I) and re.search(r'quarter|kvartal',name,re.I)]
    if len(matches)!=1:raise ValueError('Expected exactly one Geographical - Quarterly Outline sheet')
    name,cells=matches[0]
    # Match quarter and year in the SAME column. Official Tryg investor tables
    # place Q3 on row 5 and 2025 on row 6, not in one cell.
    quarter_pattern=re.compile(r'^(?:Q\s*0?'+str(quarter)+r'|0?'+str(quarter)+r'\s*Q|0?'+str(quarter)+r'\s*(?:quarter|kvartal))$',re.I)
    combined_pattern=re.compile(r'^(?:Q\s*0?'+str(quarter)+r'|0?'+str(quarter)+r'\s*Q)\s*[-/ ]\s*'+str(year)+r'$',re.I)
    headers=[]
    for addr,value in cells.items():
        if not isinstance(value,str):
            continue
        label=value.strip()
        if combined_pattern.fullmatch(label):
            headers.append((addr,rownum(addr)))
            continue
        if not quarter_pattern.fullmatch(label):
            continue
        c=column(addr);r=rownum(addr)
        # Some issuer workbooks split quarter and year across adjacent rows.
        year_matches=[yr for yr in range(max(1,r-2),r+3)
                      if yr!=r and str(cells.get(f'{c}{yr}')).strip() in (str(year),str(float(year)))]
        if len(year_matches)==1:
            headers.append((addr,r))
    if len(headers)!=1:
        raise ValueError(f'Quarter/year header missing or ambiguous: {company} {year} Q{quarter}; candidates={headers}')
    haddr,header_row=headers[0];col=column(haddr)
    norway_rows=sorted(rownum(a) for a,v in cells.items() if isinstance(v,str) and re.fullmatch(r'\s*(?:norway|norge|norwegian general insurance)\s*',v,re.I))
    if len(norway_rows)!=1:raise ValueError('Norway section missing or ambiguous')
    start=norway_rows[0]
    # Stop at the next country/section heading in the same label column.
    labelcol=column(next(a for a,v in cells.items() if rownum(a)==start and isinstance(v,str) and re.fullmatch(r'\s*(?:norway|norge|norwegian general insurance)\s*',v,re.I)))
    if start<=header_row:raise ValueError('Unexpected workbook layout')
    end=min([rownum(a) for a,v in cells.items() if column(a)==labelcol and rownum(a)>start and isinstance(v,str) and re.fullmatch(r'\s*(?:sweden|denmark|finland|sverige|danmark|suomi|other|group|total|swedish general insurance|danish general insurance)\s*',v,re.I)] or [start+65])
    observations=[]
    for metric,pattern in METRICS.items():
        candidates=[]
        for addr,v in cells.items():
            r=rownum(addr)
            if not (start<r<end) or not isinstance(v,str) or not re.fullmatch(r'\s*(?:'+pattern+r')\s*',v,re.I):continue
            val=cells.get(f'{col}{r}')
            if type(val) in (int,float):candidates.append((f'{col}{r}',val))
        if len(candidates)>1:raise ValueError(f'Ambiguous metric {metric}')
        if candidates:
            addr,val=candidates[0]
            # Tryg workbook stores monetary cells in DKK while displaying DKKm.
            # Normalize monetary amounts to DKKm; ratios are already percentages.
            if company=='Tryg' and metric in ('insurance_revenue','insurance_service_result'):
                if abs(val)>1_000_000: val=val/1_000_000
            observations.append({'company':company,'year':year,'quarter':quarter,'scope':'norway','period_type':'quarter','metric':metric,'value':val,'unit':('percent' if metric.endswith('ratio') else ('DKKm' if company=='Tryg' else 'MNOK')),'source_url':workbook_url,'source_document_url':report_pdf_url,'source_type':'official_investor_tables','source_sheet':name,'source_cell':addr,'status':'reported','source_scope':'norway'})
    if not observations:raise ValueError('No unambiguous Norway metrics; workbook requires manual adapter')
    return {'source_policy':'official_reports_and_geographic_workbooks','observations':observations}
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('xlsx');p.add_argument('--company',required=True);p.add_argument('--year',type=int,required=True);p.add_argument('--quarter',type=int,required=True);p.add_argument('--workbook-url',required=True);p.add_argument('--report-pdf-url',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();result=parse(a.xlsx,a.company,a.year,a.quarter,a.workbook_url,a.report_pdf_url)
    Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('Staged',len(result['observations']),'Norway observations; run import_quarterly_report.py for audited import')
