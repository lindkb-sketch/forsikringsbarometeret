"""Sampo group financial overview: period-labelled supplemental issuer KPIs.

Only the original financial-overview columns qualify. A dash is missing,
not a zero. RoEOF uses its reported period; solvency is a quarter-end snapshot.
"""
import re

DASHES = '\u2010\u2011\u2012\u2013\u2014\u2015\u2212'
PERIOD = re.compile(r'\b(\d{1,2})\s*-\s*(\d{1,2})\s*/\s*(20\d{2})\b|\b(20\d{2})\b')
CELL = re.compile(r'(?:-|\u2013|\u2014|[-\u2212]?\d[\d,]*(?:\.\d+)?)')
ROWS = (
    ('profit_before_tax', r'Profit before tax(?:es)?', 'EURm', 'Profit before taxes'),
    ('solvency_ratio', r'Solvency II ratio\s*\(incl\.\s*(?:distribution|dividend) accrual\)', '%', 'Group Solvency II ratio including accrual (quarter-end snapshot)'),
    ('return_on_equity', r'Return on equity own funds', '%', 'Return on equity own funds (RoEOF; issuer definition)'),
)

def _columns(block, year, quarter):
    """Return exactly one header with explicitly labelled quarter and HIÅ."""
    start, end = 3 * quarter - 2, 3 * quarter
    current = (start, end, year)
    ytd = (1, end, year) if quarter != 4 else year
    candidates = []
    for line in block.splitlines():
        normalized = line.translate(str.maketrans(DASHES, '-' * len(DASHES)))
        tokens = []
        for m in PERIOD.finditer(normalized):
            tokens.append(tuple(map(int, m.group(1, 2, 3))) if m.group(1) else int(m.group(4)))
        if current not in tokens or ytd not in tokens:
            continue
        if tokens.count(current) != 1 or tokens.count(ytd) != 1:
            continue
        candidates.append((len(tokens), tokens.index(current), tokens.index(ytd)))
    return candidates[0] if len(candidates) == 1 else None

def parse_overview(pages, url, year, quarter, sha):
    """Return source observations; refuse ambiguous column counts or labels."""
    candidates = []
    for page, text in pages:
        if 'Insurance revenue' not in text or 'Nordic underlying development' not in text:
            continue
        block = text.split('Nordic underlying development', 1)[0]
        if 'Underwriting result' not in block or 'Financial overview' not in block:
            continue
        header = _columns(block, year, quarter)
        if header:
            candidates.append((page, block, header))
    if len(candidates) != 1:
        raise ValueError('Sampo supplemental KPI financial overview period header missing or ambiguous')
    page, block, (count, qcol, ycol) = candidates[0]
    result = []
    for metric, label, unit, definition in ROWS:
        pattern = re.compile(r'^\s*' + label + r'[¹²³*]*\s+' + re.escape(unit) + r'\s+(.+?)\s*$', re.I)
        matches = [m.group(1) for line in block.splitlines() if (m := pattern.fullmatch(line))]
        if not matches:
            continue  # not disclosed or changed label; no guessing
        if len(matches) != 1:
            raise ValueError('Ambiguous Sampo financial overview row: ' + metric)
        cells = matches[0].split()
        if len(cells) != count or not all(CELL.fullmatch(c) for c in cells):
            raise ValueError('Sampo financial overview column mismatch: ' + metric)
        def append(col, period):
            raw = cells[col]
            if raw in ('-', '\u2013', '\u2014'):
                return
            value = float(raw.replace(',', '').replace('\u2212', '-'))
            if metric == 'solvency_ratio' and value <= 0:
                raise ValueError('Invalid Sampo solvency ratio')
            result.append(dict(company='Sampo', year=year, quarter=quarter, scope='group',
                segment=None, source_scope='group', period_type=period, metric=metric,
                value=value, unit='EURm' if unit=='EURm' else 'percent', status='reported',
                source_url=url, source_page=page, source_type='official_quarterly_report',
                source_sha256=sha, source_document_period=f'Q{quarter} {year}',
                source_definition=definition))
        if metric == 'solvency_ratio':
            # The reported cumulative column is the end-of-period snapshot.
            # It is valid for the quarter-end view, not a quarterly average.
            append(ycol, 'quarter')
        elif metric == 'return_on_equity':
            # Q1 quarter and HIÅ coincide; Q2-Q4 must not relabel the YTD figure.
            if quarter != 1:
                append(qcol, 'quarter')
            append(ycol, 'ytd')
        else:
            append(qcol, 'quarter')
            append(ycol, 'ytd')
    return result
