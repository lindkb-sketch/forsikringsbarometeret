"""Coordinate-aware extraction for the first page of Frende Skade PDFs."""
import re

def extract_cells(page,labels,year,quarter):
    words=page.extract_words(x_tolerance=2,y_tolerance=2)
    lines={}
    for w in words:
        lines.setdefault(round(w['top']/3)*3,[]).append(w)
    groups=[sorted(g,key=lambda w:w['x0']) for g in lines.values()]
    headers=[g for g in groups if str(year) in ' '.join(w['text'] for w in g)
             and str(year-1) in ' '.join(w['text'] for w in g)
             and ('kv' in ' '.join(w['text'] for w in g).lower())]
    if len(headers)!=1:raise ValueError('Ambiguous PDF year columns')
    centers=[]
    for y in (year,year-1):
        hits=[w for w in headers[0] if w['text']==str(y)]
        if len(hits)!=1:raise ValueError('Missing PDF year column')
        centers.append((hits[0]['x0']+hits[0]['x1'])/2)
    if abs(centers[0]-centers[1])<20:raise ValueError('Overlapping PDF columns')
    values={}
    for label in labels:
        matching=[g for g in groups if label.casefold() in ' '.join(w['text'] for w in g).casefold()]
        if len(matching)!=1:raise ValueError('Missing/ambiguous PDF row '+label)
        row=matching[0]
        numeric=[w for w in row if re.fullmatch(r'-?\d[\d.,]*%?',w['text'])]
        pair=[]
        for center in centers:
            candidates=[w for w in numeric if abs((w['x0']+w['x1'])/2-center)<30]
            if len(candidates)!=1:raise ValueError('Ambiguous PDF numeric cell '+label)
            pair.append(candidates[0]['text'])
        values[label]=pair
    return values
