#!/usr/bin/env python3
"""Fetch registered official geographical XLSX, validate, merge, publish feed.
Strict atomic behavior: if any workbook fails, neither observations nor feed change.
"""
import argparse,json,os,tempfile,urllib.request
from pathlib import Path
from audit_financials import audit,DATA,ROOT
from geographic_excel import parse
from quarterly_ytd import add_tryg_ytd
from build_verified_feed import build,OUT
KEYS=('company','year','quarter','scope','period_type','metric')
REGISTRY=ROOT/'data/geographic_workbooks.json'
def key(r):return tuple(r[k] for k in KEYS)
def download(url):
    if not url.startswith('https://'):raise ValueError('HTTPS required')
    req=urllib.request.Request(url,headers={'User-Agent':'Forsikringsbarometeret/1.0'})
    with urllib.request.urlopen(req,timeout=35) as resp:
        if not resp.geturl().startswith('https://'):raise ValueError('Insecure redirect')
        content=resp.read(25*1024*1024+1)
    if len(content)>25*1024*1024:raise ValueError('Workbook too large')
    if not content.startswith(b'PK\x03\x04'):raise ValueError('Not an XLSX archive')
    return content
def prepare(registry,existing,fetcher=download):
    pending=[];existing_keys={key(r):r for r in existing['observations']}
    for spec in registry.get('workbooks',[]):
        if spec.get('company') not in ('Tryg','Gjensidige'):raise ValueError('Unsupported company')
        if not spec.get('approved',False):continue
        if not spec['workbook_url'].startswith('https://') or not spec['report_pdf_url'].startswith('https://'):
            raise ValueError('Source URLs must be HTTPS')
        content=fetcher(spec['workbook_url'])
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'report.xlsx';p.write_bytes(content)
            batch=parse(p,spec['company'],spec['year'],spec['quarter'],spec['workbook_url'],spec['report_pdf_url'])['observations']
        for r in batch:
            k=key(r)
            if k in existing_keys:
                old=existing_keys[k]
                # A previously reviewed value is immutable; changing it requires manual correction.
                if old!=r:raise ValueError(f'Existing value conflicts with newly parsed workbook: {k}')
            elif any(key(other)==k for other in pending):
                raise ValueError(f'Duplicate staged key: {k}')
            else:pending.append(r)
    merged={**existing,'observations':add_tryg_ytd(existing['observations']+pending)}
    checked=audit(merged)
    if not checked['ok']:raise ValueError('Audit rejected staged observations: '+str(checked['errors']))
    feed=build(merged)
    return merged,feed,len(pending)
def atomic_write(path,payload):
    path=Path(path);fd,tmp=tempfile.mkstemp(prefix='.staged-',suffix='.json',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(payload,f,ensure_ascii=False,indent=2);f.write('\n')
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def run(registry_path=REGISTRY,data_path=DATA,feed_path=OUT,fetcher=download):
    registry=json.loads(Path(registry_path).read_text(encoding='utf-8'))
    existing=json.loads(Path(data_path).read_text(encoding='utf-8'))
    merged,feed,count=prepare(registry,existing,fetcher)
    # Generate the feed first; it is regenerated from the observations in every workflow run.
    # Validation completes before either write, so malformed inputs never publish.
    if count or merged != existing:atomic_write(data_path,merged)
    atomic_write(feed_path,feed)
    return count
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--registry',default=str(REGISTRY));a=p.parse_args()
    count=run(registry_path=a.registry)
    print(f'Imported {count} new geographical observations; published verified feed')
