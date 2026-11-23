#!/usr/bin/env python3
"""Real Q3 issuer-PDF provenance and metric reconciliation, strictly diagnostic.

Download known issuer reports and discovered presentations, check bytes, issuer,
period, SHA256, source pages, then extract only unambiguous label/value lines.
Never use previously published numbers as extracted PDF evidence. Never publish
values or assert dual-document completeness when either document is missing.
"""
import hashlib
import io
import json
import re
from collections import defaultdict
from pathlib import Path

from verify_nine_document_bytes import COMPANIES, approved, download, period_matches, ISSUER_TEXT

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'data/nine_document_metric_reconciliation.json'
CORE=('insurance_revenue','insurance_service_result','combined_ratio',
      'loss_ratio','expense_ratio','solvency_ratio','return_on_equity')
LABELS={
 'insurance_revenue':(r'insurance (?:service )?revenue',r'inntekter fra forsikringstjenester',r'forsikringsinntekter'),
 'insurance_service_result':(r'insurance service result',r'resultat fra forsikringstjenester'),
 'combined_ratio':(r'combined ratio',r'kombinert(?:prosent| ratio)'),
 'loss_ratio':(r'loss ratio',r'skadeprosent'),
 'expense_ratio':(r'expense ratio',r'kostnadsprosent'),
 'solvency_ratio':(r'solvency (?:capital )?ratio',r'solvens(?:kapital)?dekning',r'solvency ii ratio'),
 'return_on_equity':(r'return on equity',r'egenkapitalavkastning'),
}
NUMBER=re.compile(r'(?<![A-Za-z0-9])[-+]?\d{1,3}(?:[ .]\d{3})*(?:[,.]\d+)?(?![A-Za-z0-9])|(?<![A-Za-z0-9])[-+]?\d+(?:[,.]\d+)?(?![A-Za-z0-9])')

def parse_number(token):
    s=token.replace(' ','').replace('\u00a0','')
    if ',' in s and '.' in s:
        s=s.replace('.','').replace(',','.') if s.rfind(',')>s.rfind('.') else s.replace(',','')
    elif ',' in s:s=s.replace(',','.')
    elif s.count('.')==1 and len(s.split('.')[1])==3:s=s.replace('.','')
    return float(s)

def extract_unambiguous(lines,metric,expected=None):
    """Only accept a standalone metric row with one bounded numeric value.

    PDF text extraction can glue chart ticks, period columns or footnote numbers
    into a single enormous token. A single regex match is not proof of a KPI.
    """
    labels=LABELS.get(metric,())
    matches=[]
    for line in lines:
        found=[m for p in labels for m in re.finditer(p,line,re.I)]
        if not found:continue
        # The KPI must begin the row; chart prose and other metrics are not rows.
        first=min(found,key=lambda m:m.start())
        if line[:first.start()].strip(' :–—\\t•-'):continue
        tail=line[first.end():].strip(' :–—\\t')
        # Never parse values from a line containing another KPI label.
        if any(re.search(p,tail,re.I) for patterns in LABELS.values() for p in patterns):
            continue
        tokens=[m.group() for m in NUMBER.finditer(tail)]
        if len(tokens)!=1:continue
        token=tokens[0]
        # Reject raw unseparated runs before parsing; the number regex may
        # split a glued PDF token into shorter matches or keep it intact.
        if re.search(r'(?<![\d])\d{7,}(?!\d)',tail):
            continue
        # Exclude adjacent letters/digits and concatenated numeric columns.
        if re.search(r'\\d{7,}',token.replace(' ','').replace(',','').replace('.','')):
            continue
        value=parse_number(token)
        if metric in ('combined_ratio','loss_ratio','expense_ratio','solvency_ratio','return_on_equity'):
            if not (0<=value<=1000):continue
            # Percentage metrics require an explicit percent sign on standalone rows.
            if '%' not in tail:continue
        matches.append(value)
    unique=sorted(set(matches))
    return unique[0] if len(unique)==1 else None

def extract_explicit_quarter_column(lines,metric,year,quarter):
    """Extract only a table value under an explicit quarter/year column header.

    Never choose a value based on previously published figures or column order.
    """
    labels=LABELS.get(metric,())
    heading=re.compile(r'(?<!\w)(?:Q'+str(quarter)+r'\s*[-/ ]?\s*'+str(year)+r'|'+str(year)+r'\s*[-/ ]?\s*Q'+str(quarter)+r')(?!\w)',re.I)
    matches=[]
    for i,line in enumerate(lines):
        columns=re.split(r'\s{2,}|\t+',line.strip())
        indices=[j for j,c in enumerate(columns) if heading.fullmatch(c.strip())]
        if len(indices)!=1 or len(columns)<2:continue
        target=indices[0]
        if not any(re.search(r'Q[1-4]|20\d\d',c,re.I) for j,c in enumerate(columns) if j!=target):
            continue
        for candidate in lines[i+1:i+35]:
            cells=re.split(r'\s{2,}|\t+',candidate.strip())
            if len(cells)!=len(columns):continue
            if not any(re.search(p,cells[0],re.I) for p in labels):continue
            if re.fullmatch(r'[-+]?\d+(?:[.,]\d+)?\s*%?',cells[target].strip()):
                matches.append(parse_number(cells[target].replace('%','').strip()))
    unique=sorted(set(matches))
    return unique[0] if len(unique)==1 else None

PERCENT_METRICS={'combined_ratio','loss_ratio','expense_ratio','solvency_ratio','return_on_equity'}
QUARTER_CELL=re.compile(r'^Q([1-4])\s*[-/ ]?\s*(20\d{2})$|^(20\d{2})\s*[-/ ]?\s*Q([1-4])$',re.I)
NUMERIC_CELL=re.compile(r'^[-+]?(?:\d{1,3}(?:[ .]\d{3})+|\d+)(?:[.,]\d+)?\s*%?$')

def extract_structured_table_metrics(tables,year,quarter):
    """Read only explicitly period-labelled, aligned PDF table cells.

    Do not infer quarter from page heading, row position, prior published
    values or a YTD column. Return empty on duplicate/ambiguous evidence.
    """
    evidence={}
    rejected=set()
    for table in tables:
        if not table or len(table)<2:continue
        for hi,header in enumerate(table[:-1]):
            cells=[re.sub(r'\s+',' ',str(v or '')).strip() for v in header]
            targets=[]
            for j,cell in enumerate(cells):
                m=QUARTER_CELL.fullmatch(cell)
                if m:
                    q,y=(int(m.group(1)),int(m.group(2))) if m.group(1) else (int(m.group(4)),int(m.group(3)))
                    if (q,y)==(quarter,year):targets.append(j)
            if len(targets)!=1 or not any(QUARTER_CELL.fullmatch(c) for k,c in enumerate(cells) if k!=targets[0]):
                continue
            target=targets[0]
            for row in table[hi+1:]:
                if not row or len(row)!=len(cells) or target==0:continue
                label=re.sub(r'\s+',' ',str(row[0] or '')).strip()
                raw=re.sub(r'\s+',' ',str(row[target] or '')).strip()
                if not NUMERIC_CELL.fullmatch(raw):continue
                matches=[metric for metric,patterns in LABELS.items()
                         if any(re.fullmatch(r'(?:'+pattern+r')\s*(?:\(%\)|%|\(percent\))?',label,re.I) for pattern in patterns)]
                if len(matches)!=1:continue
                metric=matches[0]
                value=parse_number(raw.rstrip('%').strip())
                if metric in PERCENT_METRICS and (not 0<=value<=1000 or ('%' not in raw and '%' not in label)):
                    continue
                if metric in rejected:continue
                if metric in evidence and evidence[metric]!=value:
                    rejected.add(metric)
                    evidence.pop(metric,None)
                else:evidence[metric]=value
    return evidence

def discover_presentation_metrics(pages,year,quarter):
    """Extract only single-value Q3-labelled GROUP presentation pages.

    No inference from other slides, historical columns, or group/segment ambiguity.
    This is independent of previously committed report values.
    """
    evidence=[]
    for page_number,page in pages:
        lines=page.splitlines()
        if not period_matches(page,year,quarter):continue
        if not re.search(r'\b(?:group|konsern)\b',page,re.I):continue
        if re.search(r'\b(?:norway only|norge alene|segment only)\b',page,re.I):continue
        for metric in CORE:
            value=extract_unambiguous(lines,metric)
            method='single_label_period_and_group_page'
            if value is None:
                value=extract_explicit_quarter_column(lines,metric,year,quarter)
                method='explicit_quarter_table_column_on_group_page'
            if value is None:continue
            if metric in ('insurance_revenue','insurance_service_result'):
                # Currency/scale is not unambiguously identifiable on arbitrary slides.
                continue
            evidence.append({'metric':metric,'scope':'group','period_type':'quarter',
                'unit':'percent','source_page':page_number,
                'document_type':'results_presentation','value':value,
                'status':'extracted_unambiguous','committed_value':None,
                'committed_value_matches':None,'extraction_method':method})
    return evidence

def source_documents(feed,extended,candidates,year,quarter):
    docs=defaultdict(dict)
    rows=feed.get('observations',[])
    for x in rows:
        if x.get('company') not in COMPANIES or (x.get('year'),x.get('quarter'))!=(year,quarter):continue
        if x.get('source_type')!='official_quarterly_report':continue
        company,url=x['company'],x.get('source_url','')
        if not approved(company,url):continue
        doc=docs[company].setdefault(('quarterly_report',url),{
            'company':company,'document_type':'quarterly_report','url':url,
            'expected_hashes':set(),'observations':[]})
        if x.get('source_sha256'):doc['expected_hashes'].add(x['source_sha256'])
        doc['observations'].append(x)
    for company,x in extended.get('insurers',{}).items():
        if company not in COMPANIES or (x.get('year'),x.get('quarter'))!=(year,quarter):continue
        for kind,record in [('quarterly_report',x),('results_presentation',x.get('presentation_evidence',{}))]:
            url=record.get('source_url','')
            if not approved(company,url):continue
            if kind=='quarterly_report' and record.get('source_type') not in ('official_quarterly_report',):continue
            if kind=='results_presentation' and record.get('source_type')!='official_results_presentation':continue
            doc=docs[company].setdefault((kind,url),{'company':company,'document_type':kind,
                'url':url,'expected_hashes':set(),'observations':[]})
            if record.get('source_sha256'):doc['expected_hashes'].add(record['source_sha256'])
            if kind=='results_presentation':
                for metric,value in record.get('metrics',{}).items():
                    if metric in CORE:
                        doc['observations'].append({'metric':metric,'value':value,
                            'source_page':record.get('source_page'),'scope':record.get('scope','group'),
                            'period_type':'quarter','unit':'percent' if metric in ('solvency_ratio','return_on_equity','combined_ratio','loss_ratio','expense_ratio') else record.get('currency','unknown')})
    for x in candidates.get('candidates',[]):
        company,kind,url=x.get('company'),x.get('document_type'),x.get('document_url','')
        if company not in COMPANIES or kind not in ('quarterly_report','results_presentation'):continue
        if not approved(company,url):continue
        label=x.get('link_text','')+' '+url
        if not period_matches(label,year,quarter):continue
        docs[company].setdefault((kind,url),{'company':company,'document_type':kind,
            'url':url,'expected_hashes':set(),'observations':[]})
    return docs

def reconcile_extracted(records,tolerance=0.05):
    """Compare independently extracted same-metric, same-scope, same-period values."""
    grouped=defaultdict(dict)
    for r in records:
        if r.get('status')!='extracted_unambiguous':continue
        key=(r['metric'],r['scope'],r['period_type'],r.get('unit','unknown'))
        grouped[key].setdefault(r['document_type'],[]).append(r['value'])
    results=[]
    for key,by_type in sorted(grouped.items()):
        if not {'quarterly_report','results_presentation'}.issubset(by_type):continue
        report=sorted(set(by_type['quarterly_report']))
        presentation=sorted(set(by_type['results_presentation']))
        if len(report)!=1 or len(presentation)!=1:
            status='ambiguous'
        else:
            status='match' if abs(report[0]-presentation[0])<=tolerance else 'conflict'
        results.append({'metric':key[0],'scope':key[1],'period_type':key[2],'unit':key[3],
                        'report_values':report,'presentation_values':presentation,'status':status})
    return results

def verify_document(doc,year,quarter):
    company,url=doc['company'],doc['url']
    raw,final=download(company,url)
    if not raw.startswith(b'%PDF-'):raise ValueError('Not PDF bytes')
    digest=hashlib.sha256(raw).hexdigest()
    if doc['expected_hashes'] and digest not in doc['expected_hashes']:
        raise ValueError('Source SHA256 differs from committed financial provenance')
    import pdfplumber
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        opening='\n'.join((p.extract_text() or '') for p in pdf.pages[:min(len(pdf.pages),12)])
        if not re.search(ISSUER_TEXT[company],opening,re.I):raise ValueError('Issuer not confirmed')
        if not period_matches(opening,year,quarter):raise ValueError('Quarter not confirmed')
        page_text={}
        for row in doc['observations']:
            p=row.get('source_page')
            if type(p) is int and 1<=p<=len(pdf.pages):
                page_text[p]=pdf.pages[p-1].extract_text() or ''
        # Presentation metric extraction must be anchored to a real source page.
        extracted=[]
        table_diagnostics=[]
        for row in doc['observations']:
            p=row.get('source_page')
            if p not in page_text:continue
            metric=row.get('metric')
            if metric not in CORE:continue
            val=extract_unambiguous(page_text[p].splitlines(),metric)
            method='single_labelled_value'
            if val is None:
                val=extract_explicit_quarter_column(page_text[p].splitlines(),metric,year,quarter)
                method='explicit_quarter_table_column' if val is not None else 'ambiguous_or_not_found'
            extracted.append({'metric':metric,'scope':row.get('scope','group'),
                'period_type':row.get('period_type','quarter'),
                'unit':row.get('unit','percent' if metric in ('solvency_ratio','return_on_equity','combined_ratio','loss_ratio','expense_ratio') else 'unknown'),
                'source_page':p,
                'document_type':doc['document_type'],'value':val,
                'status':'extracted_unambiguous' if val is not None else 'ambiguous_or_not_found',
                'extraction_method':method,'committed_value':row.get('value'),
                'committed_value_matches':val is not None and abs(val-row.get('value',float('inf')))<0.05})
        if doc['document_type']=='results_presentation':
            pages=[(i+1,p.extract_text() or '') for i,p in enumerate(pdf.pages)]
            extracted.extend(discover_presentation_metrics(pages,year,quarter))
        # Prefer aligned cells extracted from PDF table geometry. Both document
        # types use the same independent extraction path, never committed values.
        for page_number,page in enumerate(pdf.pages,1):
            if doc['document_type']=='quarterly_report' and page_number not in page_text:
                continue
            page_body=page.extract_text() or ''
            # Table headers carry the period independently; requiring the page's
            # narrative text to repeat it discards valid financial statement tables.
            if doc['document_type']=='results_presentation':
                if not re.search(r'\\b(?:group|konsern)\\b',page_body,re.I):continue
                if re.search(r'\\b(?:norway only|norge alene|segment only)\\b',page_body,re.I):continue
            try: tables=page.extract_tables() or []
            except (ValueError,TypeError):continue
            if company in ('Tryg','Sampo') and (page_number in page_text or (doc['document_type']=='results_presentation' and page_number<=12)):
                # Capture bounded layout evidence once per run, not a new CI
                # iteration for every guess about how the PDF was typeset.
                words=page.extract_words() or []
                layout=[{'text':str(w.get('text',''))[:48],
                         'x0':round(w['x0'],1),'top':round(w['top'],1)}
                        for w in words[:450]]
                table_diagnostics.append({'page':page_number,
                    'page_width':round(page.width,1),
                    'layout_words':layout,
                    'text_lines':page_body.splitlines()[:65]})
            if tables and (company in ('Tryg','Sampo')):
                table_diagnostics.append({'page':page_number,'tables':len(tables),
                    'headers':[[str(v or '')[:65] for v in (table[0] or [])][:9]
                               for table in tables[:6] if table],
                    'row_samples':[[str(v or '')[:65] for v in (row or [])][:9]
                                   for table in tables[:2] for row in table[1:5]]})
            for metric,value in extract_structured_table_metrics(tables,year,quarter).items():
                if metric in ('insurance_revenue','insurance_service_result'):continue
                extracted.append({'metric':metric,'scope':'group','period_type':'quarter',
                    'unit':'percent','source_page':page_number,
                    'document_type':doc['document_type'],'value':value,
                    'status':'extracted_unambiguous','extraction_method':'structured_pdf_table',
                    'committed_value':None,'committed_value_matches':None})
    return {'company':company,'document_type':doc['document_type'],'url':final,
            'source_sha256':digest,'status':'verified_pdf_bytes','metric_evidence':extracted,
            'table_diagnostics':table_diagnostics[:30] if company in ('Tryg','Sampo') else []}

def run(year=2026,quarter=3):
    def load(path):return json.loads((ROOT/path).read_text(encoding='utf-8'))
    docs=source_documents(load('data/verified_financial_feed.json'),
        load('data/extended_insurer_financials.json'),load('data/report_candidates.json'),year,quarter)
    output={'schema_version':1,'year':year,'quarter':quarter,
            'metrics_published':False,'investor_use_approved':False,'companies':[]}
    for company in COMPANIES:
        checked=[]
        for doc in list(docs[company].values())[:12]:
            try:checked.append(verify_document(doc,year,quarter))
            except Exception as exc:
                checked.append({'company':company,'document_type':doc['document_type'],
                    'url':doc['url'],'status':'unverified','error':type(exc).__name__+': '+str(exc)[:200]})
        types={x['document_type'] for x in checked if x['status']=='verified_pdf_bytes'}
        metrics=[dict(row,source_sha256=x['source_sha256']) for x in checked
                 if x['status']=='verified_pdf_bytes' for row in x['metric_evidence']]
        matches=reconcile_extracted(metrics)
        conflicts=[m for m in matches if m['status']!='match']
        verified={'quarterly_report','results_presentation'}.issubset(types)
        # Even matching overlapping metrics do not establish full extraction of all KPIs.
        output['companies'].append({'company':company,'documents':checked,
            'report_verified':'quarterly_report' in types,
            'presentation_verified':'results_presentation' in types,
            'both_documents_verified':verified,'metric_evidence':metrics,
            'cross_document_matches':matches,'conflicts':conflicts,
            'metric_extraction_status':'partial_reconciliation' if verified and matches and not conflicts
                                        else 'not_certified'})
    output['all_nine_dual_document_verified']=all(c['both_documents_verified'] for c in output['companies'])
    OUTPUT.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('NINE_DOCUMENT_METRIC_AUDIT',json.dumps({x['company']:{
        'report':x['report_verified'],'presentation':x['presentation_verified'],
        'matched_metrics':len(x['cross_document_matches']),'conflicts':len(x['conflicts'])}
        for x in output['companies']},ensure_ascii=False))
    return output

if __name__=='__main__':run()
