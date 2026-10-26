#!/usr/bin/env python3
"""Fail closed if GitHub Pages checkout lacks a required site dependency."""
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ESSENTIAL=(
 'index.html',
 'scripts/financial_model.js',
 'scripts/quarterly_runtime.js',
 'data/verified_financial_feed.json',
 'data/financial_observations.json',
 'data/live.json',
 'data/quarterly_editorial.json',
 'data/official_news.json',
 'data/stock_prices.json',
 'data/strategic_market.json',
 'data/investor_readiness.json',
 'data/profitability_coverage.json',
)
def verify(root=ROOT):
 root=Path(root)
 missing=[name for name in ESSENTIAL if not (root/name).is_file() or (root/name).stat().st_size==0]
 html=(root/'index.html').read_text(encoding='utf-8') if (root/'index.html').is_file() else ''
 for src in re.findall(r'<script[^>]*\\bsrc=[\\'"]([^\\'"]+)',html):
  if re.match(r'^https?://',src):continue
  path=src.split('?',1)[0].lstrip('/')
  if path and not (root/path).is_file():missing.append(path)
 if missing:raise ValueError('Missing required published site assets: '+', '.join(sorted(set(missing))))
 return {'required_assets':len(ESSENTIAL),'scripts_validated':len(re.findall(r'<script[^>]*\\bsrc=',html))}
if __name__=='__main__':
 print('DEPLOYMENT_TREE_VALID',verify())
