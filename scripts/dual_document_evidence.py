"""Evidence gate for quarterly reports AND issuer presentations.

Use this module before publishing any sourced metric. A slide is valid evidence
only when its official document URL, PDF digest, page and period are recorded.
"""
from math import isfinite
from urllib.parse import urlparse

DOCUMENT_TYPES = frozenset(("quarterly_report", "results_presentation"))
COMPANIES = frozenset(("Fremtind", "Gjensidige", "Tryg", "Sampo",
    "Frende", "Protector", "Storebrand", "KLP Skadeforsikring", "Alm. Brand"))
RATIO_METRICS = frozenset(("combined_ratio", "loss_ratio", "expense_ratio",
    "solvency_ratio", "return_on_equity", "insurance_revenue_growth"))

def validate_evidence(record):
    """Reject unsourced values and cross-period/scope ambiguity."""
    if record.get("company") not in COMPANIES:
        raise ValueError("Unknown insurer")
    if record.get("document_type") not in DOCUMENT_TYPES:
        raise ValueError("Report or presentation type required")
    url = record.get("source_url", "")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("Official HTTPS document URL required")
    if not record.get("issuer_verified"):
        raise ValueError("Document issuer must be verified independently")
    digest = record.get("source_sha256", "")
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("SHA256 evidence required")
    if type(record.get("source_page")) is not int or record["source_page"] < 1:
        raise ValueError("Page number required")
    if type(record.get("year")) is not int or type(record.get("quarter")) is not int or record["quarter"] not in (1,2,3,4):
        raise ValueError("Explicit quarter required")
    if record.get("period_type") not in ("quarter", "ytd"):
        raise ValueError("Quarter versus YTD required")
    if record.get("scope") not in ("group", "company", "norway", "reported_segment"):
        raise ValueError("Reporting scope required")
    value = record.get("value")
    if isinstance(value, bool) or not isinstance(value, (int,float)) or not isfinite(value):
        raise ValueError("Finite numeric value required")
    if not record.get("metric") or not record.get("unit"):
        raise ValueError("Metric and unit required")
    if record["metric"] in RATIO_METRICS and record["unit"] != "percent":
        raise ValueError("Ratio must use percent")
    return record

def reconcile_documents(records, tolerance=0.05):
    """Merge complementary official sources; block conflicting duplicates.

    Missing metrics remain absent until both source types have been searched.
    This does not itself prove source discovery or authorize publication.
    """
    merged = {}
    for record in records:
        validate_evidence(record)
        key = tuple(record[k] for k in ("company","year","quarter","period_type","scope","metric","unit"))
        if key in merged and abs(merged[key]["value"] - record["value"]) > tolerance:
            raise ValueError("Conflicting official sources for " + repr(key))
        if key not in merged:
            merged[key] = {"value": record["value"], "sources": []}
        merged[key]["sources"].append({k:record[k] for k in
            ("document_type","source_url","source_sha256","source_page")})
    return merged

def missing_after_both_checked(metric, report_checked, presentation_checked):
    """Only classify an absent KPI as missing after both documents were checked."""
    if not report_checked or not presentation_checked:
        raise ValueError("Both report and presentation must be checked before declaring missing: "+metric)
    return None
