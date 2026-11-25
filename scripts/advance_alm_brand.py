#!/usr/bin/env python3
"""Advance only from a verified Alm. Brand period; write atomically."""
import json
from pathlib import Path
from publish_geographic_workbooks import atomic_write
from rolling_alm_brand_reports import advance,validate_rolling

DATA=Path(__file__).resolve().parents[1]/'data/extended_insurer_financials.json'
def run(path=DATA):
    data=json.loads(path.read_text(encoding='utf-8'))
    original=data['insurers']['Alm. Brand']
    updated=advance(original)
    if updated==original:return False
    errors=validate_rolling(updated)
    if errors:raise ValueError('; '.join(errors))
    data['insurers']['Alm. Brand']=updated
    atomic_write(path,data)
    print('ALM_BRAND_ROLLING_IMPORT',updated['year'],updated['quarter'],flush=True)
    return True

if __name__=='__main__':run()
