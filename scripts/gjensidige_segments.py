#!/usr/bin/env python3
"""Extract Norway Private/Commercial quarterly observations from official Gjensidige XLSX.

No financial values are embedded in code. Reject ambiguous columns and missing inputs.
"""
import re
from geographic_excel import load_sheets, column, rownum

SEGMENTS={"Private Norway":r"general insurance private norwa",
          "Commercial Norway":r"general insurance commercial no"}
ROWS={"insurance_revenue":r"insurance revenue",
      "insurance_service_result":r"insurance service result",
      "loss_ratio":r"(?:claims|loss) ratio(?:,? net of reinsurance)?",
      "expense_ratio":r"(?:cost|expense) ratio",
      "combined_ratio":r"combined ratio"}

def extract(path,year,quarter,workbook_url,report_pdf_url):
    if not (workbook_url.startswith("https://") and report_pdf_url.startswith("https://")):
        raise ValueError("Official HTTPS sources required")
    results=[]
    workbook_sheets=load_sheets(path)
    for segment,pattern in SEGMENTS.items():
        sheets=[(name,cells) for name,cells in workbook_sheets.items()
                if re.search(pattern,name,re.I)]
        if len(sheets)!=1:
            sheets=[(name,cells) for name,cells in workbook_sheets.items()
                    if re.fullmatch(r"General Insurance "+segment.split()[0],name,re.I)]
        if len(sheets)!=1:raise ValueError(f"Missing/ambiguous segment sheet: {segment}")
        name,cells=sheets[0]
        if not re.search(pattern,name,re.I):
            sections=[rownum(addr) for addr,v in cells.items()
                      if column(addr)=="A" and isinstance(v,str)
                      and v.strip().casefold()==("General Insurance "+segment).casefold()]
            if len(sections)!=1:raise ValueError(f"Missing/ambiguous Norway section: {segment}")
            begin=sections[0]
            boundaries=[rownum(addr) for addr,v in cells.items()
                        if column(addr)=="A" and isinstance(v,str) and rownum(addr)>begin
                        and re.fullmatch(r"General Insurance (?:Private|Commercial) [A-Za-z ]+",v.strip(),re.I)]
            end=min(boundaries) if boundaries else 999999
            cells={addr:v for addr,v in cells.items() if begin<=rownum(addr)<end}
        headers=[addr for addr,v in cells.items() if isinstance(v,str)
                 and re.fullmatch(rf"(?:Q\s*{quarter}\s*[-/ ]\s*{year}|{year}\s*[-/ ]\s*Q\s*{quarter})",v.strip(),re.I)]
        if len(headers)!=1:raise ValueError(f"Ambiguous period header in {name}: {year} Q{quarter}")
        col=column(headers[0])
        for metric,regex in ROWS.items():
            candidates=[(addr,v) for addr,v in cells.items()
                        if isinstance(v,str) and re.fullmatch(regex,re.sub(r"[¹²³⁴⁵⁶⁷⁸⁹⁰*]+$","",v.strip()).strip(),re.I)]
            if len(candidates)!=1:raise ValueError(f"Ambiguous/missing {metric} label in {name}")
            addr,_=candidates[0]
            value=cells.get(f"{col}{rownum(addr)}")
            if type(value) not in (float,int):raise ValueError(f"Missing cached numeric {metric} in {name}")
            # Official Gjensidige workbook caches NOK amounts and fractional ratios.
            # Normalize to MNOK and percent, matching the separately sourced Norway feed.
            if metric.endswith("ratio"):
                if 0 <= value <= 1: value*=100
                elif not 0 <= value <= 100: raise ValueError(f"Invalid ratio in {name}")
            elif abs(value)>=1_000_000:
                value/=1_000_000
            results.append(dict(company="Gjensidige",year=year,quarter=quarter,
                scope="reported_segment",segment=segment,period_type="quarter",
                metric=metric,value=value,unit="percent" if metric.endswith("ratio") else "MNOK",
                status="reported",source_type="official_investor_tables",
                source_url=workbook_url,source_document_url=report_pdf_url,
                source_sheet=name,source_cell=f"{col}{rownum(addr)}"))
    return results
