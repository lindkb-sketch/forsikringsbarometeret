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
    for segment,pattern in SEGMENTS.items():
        sheets=[(name,cells) for name,cells in load_sheets(path).items()
                if re.search(pattern,name,re.I)]
        if len(sheets)!=1:raise ValueError(f"Missing/ambiguous segment sheet: {segment}")
        name,cells=sheets[0]
        # Require an exact period header; never assume that column B is current quarter.
        headers=[addr for addr,v in cells.items() if isinstance(v,str)
                 and re.fullmatch(rf"(?:Q\\s*{quarter}\\s*[-/ ]\\s*{year}|{year}\\s*[-/ ]\\s*Q\\s*{quarter})",v.strip(),re.I)]
        if len(headers)!=1:raise ValueError(f"Ambiguous period header in {name}: {year} Q{quarter}")
        col=column(headers[0])
        for metric,regex in ROWS.items():
            candidates=[(addr,v) for addr,v in cells.items()
                        if isinstance(v,str) and re.fullmatch(regex,v.strip(),re.I)]
            if len(candidates)!=1:raise ValueError(f"Ambiguous/missing {metric} label in {name}")
            addr,_=candidates[0]
            value=cells.get(f"{col}{rownum(addr)}")
            if type(value) not in (float,int):raise ValueError(f"Missing cached numeric {metric} in {name}")
            results.append(dict(company="Gjensidige",year=year,quarter=quarter,
                scope="reported_segment",segment=segment,period_type="quarter",
                metric=metric,value=value,unit="percent" if metric.endswith("ratio") else "MNOK",
                status="reported",source_type="official_investor_tables",
                source_url=workbook_url,source_document_url=report_pdf_url,
                source_sheet=name,source_cell=f"{col}{rownum(addr)}"))
    return results
