#!/usr/bin/env python3
"""Fail closed when published quarterly briefs repeat financial KPIs or use stale periods."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
a=json.loads((ROOT/"data/quarterly_editorial.json").read_text())
feed=json.loads((ROOT/"data/verified_financial_feed.json").read_text())
periods={(x["year"],x["quarter"]) for x in feed["observations"] if x.get("scope")=="group" and x.get("period_type")=="quarter" and x.get("status","reported") in ("reported","calculated")}
if not periods:raise SystemExit("No verified quarterly data")
y,q=max(periods)
expected=f"Q{q} {y}"
if a["period"]!=expected:raise SystemExit(f"Stale brief {a['period']}; verified quarter {expected}")
if a["brief"]!=a["periods"][expected]["brief"]:raise SystemExit("Top level and selected period briefs differ")
for label,section in a["periods"].items():
    if len(section['brief'])>4 or sum(len(item['text'].split()) for item in section['brief'])>220:
        raise SystemExit(f'Editorial too long in {label}')
    for item in section["brief"]:
        if item.get("theme")=="additional_insurers" or item.get("basis")=="verified_financial_comparison":
            raise SystemExit(f"Uninformative restatement of KPI figures in {label}")
        if item.get("basis")=="issuer_pdf_verbatim" or " omtaler i kvartalsrapporten:" in item["text"]:
            raise SystemExit(f"Raw PDF quote in {label} publication")
        if item.get("type")!="qualitative_quarter_theme" or item.get("period")!=label:
            raise SystemExit(f"Non-thematic or wrong-period brief in {label}")
        if not item.get("source_url","").startswith("https://"):
            raise SystemExit(f"Missing cited source in {label}")
        if re.search(r"\d+(?:[,.]\d+)?\s*(?:%|MNOK|NOKm|MDKK|DKKm)\b",item["text"]):
            raise SystemExit(f"Numeric KPI in {label} editorial")
print("QUALITATIVE_QUARTER_BRIEF PASS",expected,len(a["brief"]))
