#!/usr/bin/env python3
"""Fail-closed PM/BM reconciliation against separately sourced Norway totals.

No missing segment, metric, or mismatched unit may be silently accepted.
"""
import math

METRICS=("insurance_revenue","insurance_service_result","loss_ratio","expense_ratio","combined_ratio")
ADDITIVE=("insurance_revenue","insurance_service_result")

def reconcile(segment_rows,norway_rows,year,quarter):
    def one(rows,metric,segment=None):
        found=[r for r in rows if r.get("company")=="Gjensidige"
               and r.get("year")==year and r.get("quarter")==quarter
               and r.get("period_type")=="quarter" and r.get("metric")==metric
               and (segment is None or r.get("segment")==segment)]
        if len(found)!=1:raise ValueError(f"Missing or ambiguous {metric} for {segment or 'Norway'}")
        row=found[0]
        if not math.isfinite(row["value"]):raise ValueError("Nonfinite value")
        if not row.get("source_cell") or not row.get("source_sheet"):raise ValueError("Missing cell provenance")
        return row
    verified={}
    for metric in METRICS:
        pm=one(segment_rows,metric,"Private Norway")
        bm=one(segment_rows,metric,"Commercial Norway")
        norway=one([r for r in norway_rows if r.get("scope")=="norway"],metric)
        if pm.get("unit")!=bm.get("unit"):
            raise ValueError(f"PM/BM unit mismatch: {metric}")
        if norway.get("unit") and norway["unit"]!=pm["unit"]:
            raise ValueError(f"Norway/segment unit mismatch: {metric}")
        if metric in ADDITIVE:
            expected=pm["value"]+bm["value"]
        else:
            revenue_pm=one(segment_rows,"insurance_revenue","Private Norway")["value"]
            revenue_bm=one(segment_rows,"insurance_revenue","Commercial Norway")["value"]
            if min(revenue_pm,revenue_bm)<=0:raise ValueError("Invalid revenue weighting")
            expected=(pm["value"]*revenue_pm+bm["value"]*revenue_bm)/(revenue_pm+revenue_bm)
        tolerance=max(0.02,abs(norway["value"])*0.0001) if metric in ADDITIVE else 0.25
        if abs(expected-norway["value"])>tolerance:
            raise ValueError(f"Norway reconciliation failed: {metric}, difference={expected-norway['value']:.8g}")
        verified[metric]={"difference":expected-norway["value"],"tolerance":tolerance}
    return verified
