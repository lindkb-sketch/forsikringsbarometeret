#!/usr/bin/env python3
"""Read actual investor XLSX files; stage precise observations with workbook hash and cell.
No guessed remote URL or PDF link is asserted. Staging is separate from verified feed.
"""
import argparse,hashlib,json,re,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
BASE='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
METRICS={'Insurance revenue':'insurance_revenue','Insurance service result':'insurance_service_result','Combined ratio':'combined_ratio','Claims ratio, net of reinsurance':'loss_ratio','Loss ratio, net of reinsurance²':'loss_ratio','Expense ratio':'expense_ratio','Cost ratio²':'expense_ratio','Combined ratio²':'combined_ratio'}
def sheets(path):
 with zipfile.ZipFile(path) as z:
  ss=[]
  if 'xl/sharedStrings.xml' in z.namelist():
   for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',NS):
    ss.append(''.join(t.text or '' for t in si.findall('.//m:t',NS)))
  wb=ET.fromstring(z.read('xl/workbook.xml'))
  for idx,sh in enumerate(wb.findall('.//m:sheet',NS),1):
   xml=f'xl/worksheets/sheet{idx}.xml'
   if xml not in z.namelist():continue
   cells={}
   for c in ET.fromstring(z.read(xml)).findall('.//m:sheetData/m:row/m:c',NS):
    v=c.find('m:v',NS); ins=c.find('m:is',NS)
    if v is None and ins is None:continue
    val=v.text if v is not None else ''.join(t.text or '' for t in ins.findall('.//m:t',NS))
    if c.attrib.get('t')=='s':val=ss[int(val)]
    elif c.attrib.get('t') not in ('str','inlineStr'):
     try:val=float(val)
     except (ValueError,TypeError):pass
    cells[c.attrib['r']]=val
   yield sh.attrib['name'],cells
try:
    from .quarterly_ytd import add_tryg_ytd
except ImportError:
    from quarterly_ytd import add_tryg_ytd

def parse_tryg(path):
 found=[]
 for name,c in sheets(path):
  if not name.startswith('Geographical - Quarterly'):continue
  if c.get('C22')!='Norwegian general insurance':raise ValueError('Norway heading changed')
  for col in 'DEFGHIJKLMNO':
   q=c.get(f'{col}5');year=c.get(f'{col}6')
   if not isinstance(q,str) or not re.fullmatch(r'Q[1-4]',q) or not isinstance(year,(int,float)):continue
   for row,label in [(24,'insurance_revenue'),(25,'insurance_service_result'),(31,'loss_ratio'),(32,'expense_ratio'),(33,'combined_ratio')]:
    value=c.get(f'{col}{row}')
    if not isinstance(value,(int,float)):continue
    if c.get(f'C{row}') not in METRICS or METRICS[c[f'C{row}']]!=label:raise ValueError(f'Unexpected metric row {row}')
    found.append(dict(company='Tryg',year=int(year),quarter=int(q[1]),scope='norway',period_type='quarter',metric=label,value=round(value/1e6,6) if row in (24,25) else round(value,6),unit='DKKm' if row in (24,25) else 'percent',source_sheet=name,source_cell=f'{col}{row}'))
 if not found:raise ValueError('Tryg Norway sheet not found')
 return found

def parse_gjensidige(path):
 byperiod={}
 sections=0
 for name,c in sheets(path):
  if not (name.startswith('General Insurance Private Norwa') or name.startswith('General Insurance Commercial No')):continue
  sections+=1
  if 'Norway' not in str(c.get('A1')):raise ValueError('Unexpected Gjensidige section')
  for col in 'BCDE':
   h=c.get(f'{col}3')
   m=re.fullmatch(r'(Q[1-4]|YTD) (20\d\d)',str(h))
   if not m:continue
   period='ytd' if m[1]=='YTD' else 'quarter';q=int(m[1][1]) if period=='quarter' else int(re.search(r'Q([1-4])',str(c.get('B3')))[1]);year=int(m[2]);key=(year,q,period)
   metrics=byperiod.setdefault(key,{})
   for row,label in [(5,'insurance_revenue'),(11,'insurance_service_result')]:
    if c.get(f'A{row}') not in METRICS or METRICS[c[f'A{row}']]!=label:raise ValueError('Unexpected metric row')
    v=c.get(f'{col}{row}')
    if not isinstance(v,(float,int)):raise ValueError('Missing Gjensidige number')
    metrics.setdefault(label,[]).append((v/1e6,name,f'{col}{row}'))
   # Combined ratio computed from summed monetary income and expense, not average of segment percentages.
   for row,label in [(20,'loss_ratio'),(21,'expense_ratio')]:
    v=c.get(f'{col}{row}');revenue=c.get(f'{col}5')
    if not isinstance(v,(int,float)) or not isinstance(revenue,(int,float)):raise ValueError('Missing ratio inputs')
    metrics.setdefault(label,[]).append((v,revenue,name,f'{col}{row}'))
 if sections!=2:raise ValueError('Expected exactly Private Norway and Commercial Norway sheets')
 result=[]
 for (year,q,period),metrics in byperiod.items():
  if period != "quarter": continue
  for metric,parts in metrics.items():
   if len(parts)!=2:raise ValueError('Both Norway segments required')
   if metric in ('loss_ratio','expense_ratio'):
    value=100*sum(v*rev for v,rev,_,_ in parts)/sum(rev for _,rev,_,_ in parts)
    unit='percent';cells=[f'{name}!{cell}' for _,_,name,cell in parts]
   else:
    value=sum(v for v,_,_ in parts);unit='NOKm';cells=[f'{name}!{cell}' for _,name,cell in parts]
   result.append(dict(company='Gjensidige',year=year,quarter=q,scope='norway',period_type=period,metric=metric,value=round(value,6),unit=unit,source_sheet='Private Norway + Commercial Norway',source_cell='; '.join(cells),calculation='sum_segments' if metric not in ('loss_ratio','expense_ratio') else 'revenue_weighted_segments'))
  loss=next(r for r in result if r['year']==year and r['quarter']==q and r['period_type']==period and r['metric']=='loss_ratio')
  expense=next(r for r in result if r['year']==year and r['quarter']==q and r['period_type']==period and r['metric']=='expense_ratio')
  result.append(dict(company='Gjensidige',year=year,quarter=q,scope='norway',period_type=period,metric='combined_ratio',value=round(loss['value']+expense['value'],6),unit='percent',source_sheet='Private Norway + Commercial Norway',source_cell=loss['source_cell']+'; '+expense['source_cell'],calculation='sum_weighted_loss_and_cost_ratios'))
 return result
def main():
 a=argparse.ArgumentParser();a.add_argument('--tryg',required=True);a.add_argument('--gjensidige',required=True);a.add_argument('--output',required=True);args=a.parse_args()
 records=[];sources=[]
 for company,path,fn in [('Tryg',Path(args.tryg),parse_tryg),('Gjensidige',Path(args.gjensidige),parse_gjensidige)]:
  digest=hashlib.sha256(path.read_bytes()).hexdigest()
  rows=fn(path)
  for r in rows:r.update(source_type='uploaded_official_investor_workbook',source_file=path.name,source_sha256=digest,verification='original_uploaded_xlsx_parsed; official_publication_url_and_companion_pdf_not_yet_matched')
  records.extend(rows);sources.append({'company':company,'file':path.name,'sha256':digest,'observations':len(rows)})
 out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps({'sources':sources,'observations':records},ensure_ascii=False,indent=2)+'\n');print(json.dumps(sources))
if __name__=='__main__':main()
