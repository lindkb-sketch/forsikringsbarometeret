#!/usr/bin/env python3
"""Conservative Tryg Norway extraction from its official quarterly PDF.

Only the explicitly labelled 'Norwegian general insurance' geography section
is accepted. The selected quarter/year must appear in the same table.
"""
import hashlib
import io
import re
import pdfplumber

NUM = r"-?\d[\d,]*(?:\.\d+)?"
LABELS = {
    "insurance_revenue": "Insurance revenue",
    "insurance_service_result": "Insurance service result",
    "loss_ratio": "Claims ratio, net of reinsurance",
    "expense_ratio": "Expense ratio",
    "combined_ratio": "Combined ratio",
}

def parse_norway_pdf(blob, year, quarter, url):
    if not blob.startswith(b"%PDF-"):
        raise ValueError("Not a PDF")
    digest = hashlib.sha256(blob).hexdigest()
    matches = []
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        for page_number, page in enumerate(pdf.pages, 1):
            text = page.extract_text(layout=False) or ""
            if ("Quarterly outline" not in text or "Geography" not in text
                or "Norwegian general insurance" not in text):
                continue
            before, after = text.split("Norwegian general insurance", 1)
            headers = re.findall(r"Q([1-4])\s+(20\d\d)", before)
            if (str(quarter), str(year)) not in headers:
                # Tryg also prints quarter and year on separate header rows.
                lines=before.splitlines()
                for i,line in enumerate(lines):
                    qs=re.findall(r"\bQ([1-4])\b",line)
                    if not qs or i+1>=len(lines):continue
                    yrs=re.findall(r"\b20\d{2}\b",lines[i+1])
                    if len(qs)==len(yrs) and len(qs)>=2:
                        headers=list(zip(qs,yrs))
                        break
            if (str(quarter), str(year)) not in headers:
                continue
            section = after.split("Swedish general insurance", 1)[0]
            section = section.split("Other general insurance", 1)[0]
            matches.append((page_number, headers, section))
    if len(matches) != 1:
        raise ValueError("Missing or ambiguous Tryg Norway geography PDF table")
    page_number, headers, section = matches[0]
    current_index = headers.index((str(quarter), str(year)))
    prior = (str(quarter), str(year-1))
    if prior not in headers:
        raise ValueError("Tryg Norway PDF lacks prior-year same-quarter column")
    prior_index = headers.index(prior)
    if len(headers) != len(set(headers)):
        raise ValueError("Ambiguous Tryg quarter headings")
    output = []
    for metric, label in LABELS.items():
        rows = [line.strip() for line in section.splitlines()
                if re.match(r"^"+re.escape(label)+r"\s+", line.strip(), re.I)]
        if len(rows) != 1:
            raise ValueError("Tryg Norway row absent/ambiguous: "+label)
        raw = rows[0][len(label):]
        values = re.findall(NUM, raw)
        if len(values) < len(headers):
            raise ValueError("Missing Tryg Norway comparative values: "+label)
        for observation_year, pos in ((year,current_index),(year-1,prior_index)):
            value = float(values[pos].replace(",", ""))
            output.append(dict(company="Tryg",year=observation_year,quarter=quarter,
                scope="norway",source_scope="norway",period_type="quarter",metric=metric,
                value=value,unit="percent" if metric.endswith("ratio") else "DKKm",
                status="reported",source_type="official_quarterly_report",source_url=url,
                source_page=page_number,source_sha256=digest,
                source_document_period=f"Q{quarter} {year}",
                source_section="Quarterly outline - Geography / Norwegian general insurance"))
    by_metric = {r["metric"]:r["value"] for r in output if r["year"] == year}
    if by_metric["insurance_revenue"] <= 0:
        raise ValueError("Invalid Norwegian insurance revenue")
    if abs(by_metric["loss_ratio"] + by_metric["expense_ratio"] - by_metric["combined_ratio"]) > 0.2:
        raise ValueError("Tryg Norway CR does not reconcile")
    return output
