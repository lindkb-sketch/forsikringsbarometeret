#!/usr/bin/env python3
"""Stage page-labelled tables from an OFFICIAL interim-report PDF for review.
No unverified table cell is published as a financial observation.
"""
import argparse,hashlib,json,re,sys
from pathlib import Path
def extract(pdf_path,company,source_url):
    if not source_url.startswith("https://"):
        raise ValueError("Official report URL must use HTTPS")
    raw=Path(pdf_path).read_bytes()
    if not raw.startswith(b"%PDF-"):raise ValueError("Not a PDF")
    try:import pdfplumber
    except ImportError as exc:raise RuntimeError("Install pdfplumber to extract PDF tables") from exc
    pages=[]
    with pdfplumber.open(pdf_path) as pdf:
        for number,page in enumerate(pdf.pages,1):
            text=page.extract_text() or ""
            tables=page.extract_tables() or []
            # Stage only potentially relevant financial pages, not all pages.
            if re.search(r"insurance revenue|insurance service result|combined ratio|loss ratio|expense ratio|return on equity|cash return on equity|solvency|forsikringsinntekt|forsikringsresultat|skadeprosent|kostnadsprosent|egenkapitalavkastning",text,re.I):
                pages.append({"page":number,"matching_lines":[line.strip()[:250] for line in text.splitlines() if re.search(r"insurance revenue|insurance service result|combined ratio|loss ratio|expense ratio|return on equity|cash return on equity|solvency|forsikringsinntekt|forsikringsresultat|skadeprosent|kostnadsprosent|egenkapitalavkastning",line,re.I)][:35],"tables":tables[:12]})
    return {"company":company,"source_url":source_url,"source_type":"official_quarterly_report","pdf_sha256":hashlib.sha256(raw).hexdigest(),"pages_with_financial_terms":pages,"status":"extracted_candidates_require_period_scope_and_value_review","observations":[]}
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("pdf")
    parser.add_argument("--company",required=True)
    parser.add_argument("--source-url",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    result=extract(args.pdf,args.company,args.source_url)
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\\n",encoding="utf-8")
    print(f"Staged {len(result['pages_with_financial_terms'])} pages; published 0 observations")
if __name__=="__main__":main()
