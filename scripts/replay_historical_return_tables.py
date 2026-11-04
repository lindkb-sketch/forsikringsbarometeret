#!/usr/bin/env python3
"""Independently extract five historical returns with previously unhandled PDF layouts.

Only for historical replay of original fingerprinted issuer reports, never
a generic replacement for live/new-quarter import. The calling replay checks
original SHA-256, exact source page and equality with published evidence.
"""
import io
import re

import pdfplumber
from import_reported_returns import extract as standard_extract

SPECIAL={('Fremtind',2025,3),('Fremtind',2025,4),
         ('Gjensidige',2025,4),('Tryg',2025,4),('Tryg',2026,3)}

def number(text):
    return float(text.replace(',','.'))

def from_page(text,company,year,quarter):
    if (company,year,quarter) not in SPECIAL:
        raise ValueError('No approved historical layout for this period')
    candidates=[]
    if company=='Fremtind':
        if not re.search(r'Fremtind Holding',text,re.I):
            raise ValueError('Missing Fremtind Holding entity')
        if not re.search(r'\bQ'+str(quarter)+r'\s+2025\b',text,re.I):
            raise ValueError('Missing verified Fremtind report quarter')
        lines=text.splitlines()
        for i,line in enumerate(lines):
            if not re.search(r'Annualisert\s+egenkapitalavkastning\s+justert\s+for\b',line,re.I):
                continue
            # Only the row completing the Eika-adjusted caption is eligible.
            # Footnotes can intervene; avoid unadjusted ROE or unrelated ratios.
            block='\n'.join(lines[i:i+12])
            values=re.findall(
                r'(?im)^\s*(?:transaksjonen\s+med\s+)?(?:Eika\s+)?Forsikring\s+AS\s+'
                r'(-?\d{1,3}(?:[.,]\d{1,2})?)\s*%',
                block)
            candidates.extend(map(number,values))
        definition='Annualisert egenkapitalavkastning justert for transaksjonen med Eika Forsikring AS'
    elif company=='Gjensidige':
        if 'Gjensidige Forsikring Group' not in text:
            raise ValueError('Expected Gjensidige group table')
        if not re.search(r'Q4\s+2025\s+Q4\s+2024',text):
            raise ValueError('Expected Q4 2025/2024 group table header')
        # The identical subsidiary table starts later on the same PDF page.
        group=text.split('Gjensidige Forsikring ASA',1)[0]
        matches=re.findall(
            r'(?im)^\s*Return\s+on\s+equity,\s*annualised\s*[¹²³*]?\s*%\s+'
            r'(-?\d{1,3}(?:[.,]\d{1,2})?)\s+'
            r'-?\d{1,3}(?:[.,]\d{1,2})?\s*$',
            group)
        candidates.extend(map(number,matches))
        definition='Gjensidige group annualised ROE; full-year 2025 year-end observation'
    elif (year,quarter)==(2025,4):
        if not re.search(r'(?m)^\s*Q4\s+Q4\s*$',text):
            raise ValueError('Tryg Q4 table header missing')
        if not re.search(r'DKKm\s+2025\s+2024\s+2025\s+2024\s+2023',text):
            raise ValueError('Tryg quarter/full-year column ordering missing')
        for line in text.splitlines():
            match=re.match(r'^\s*Return\s+on\s+Own\s+Funds\s*\(%\)\s+(.+)$',line,re.I)
            if not match:continue
            values=re.findall(r'-?\d{1,3}(?:[.,]\d{1,2})?',match.group(1))
            if len(values)!=5:raise ValueError('Tryg ROOF five-quarter source columns ambiguous')
            candidates.append(number(values[0]))  # explicitly isolated Q4 2025
        definition='Return on Own Funds (ROOF), isolated Q4 2025 column, not full-year'
    else:
        if not re.search(r'Q1\s*-\s*Q3\s+2026|Q3\s+2026',text,re.I):
            raise ValueError('Tryg Q3 2026 header not verified')
        matches=re.findall(
            r'own\s+funds\s*\(\s*ROOF\s*\)\s*was\s*'
            r'(-?\d{1,3}(?:[.,]\d{1,2})?)\s*%',
            text,re.I)
        candidates.extend(map(number,matches))
        definition='Reported return on own funds (ROOF), Q3 2026'
    distinct={round(value,4) for value in candidates}
    if len(candidates)!=1 or len(distinct)!=1:
        raise ValueError('Original historical reported-return row missing or ambiguous: '+str(candidates))
    value=candidates[0]
    if not -100<=value<=200:
        raise ValueError('Historical return outside plausible range')
    return value,definition

def extract(blob,company,year,quarter):
    # For five audited historical layouts the generic prose parser may return
    # a DIFFERENT valid period's value (e.g. FY 2025 instead of Q4 2025).
    # Prefer the explicitly quarter-labelled table; never accept a generic
    # result merely because it appeared earlier in the document.
    if (company,year,quarter) not in SPECIAL:
        return standard_extract(blob,company,year,quarter)
    if not blob.startswith(b'%PDF-'):
        raise ValueError('Original historical source not PDF')
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        hits=[]
        for page,p in enumerate(pdf.pages,1):
            text=p.extract_text() or ''
            try:
                value,definition=from_page(text,company,year,quarter)
                hits.append((page,value,definition))
            except ValueError:
                continue
    if len(hits)!=1:
        raise ValueError('Historical source page or return value ambiguous: '+str(hits[:4]))
    return hits[0]
