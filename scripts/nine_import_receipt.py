#!/usr/bin/env python3
"""Record observable new-quarter advances after audited public publication.

Only a scheduled run that actually advances a period earns a scheduled
advance receipt. A green repeat of existing data is not evidence of new
import, and neither is a manually dispatched run.
"""
import hashlib
import json
import os
import subprocess
from pathlib import Path
from check_nine_release import COMPANIES, period, VERIFIED

ROOT = Path(__file__).resolve().parents[1]
FILE = "data/nine_insurer_comparison.json"

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                        separators=(",", ":")).encode()).hexdigest()

def build(before, after, public, event, run_id, source_sha):
    if public != after:
        raise ValueError("Public nine-insurer data differs from validated data")
    previous = {r["company"]: r for r in before["companies"]}
    current = {r["company"]: r for r in after["companies"]}
    if any(len(x["companies"]) != 9 for x in (before, after)) or set(previous) != set(COMPANIES) or set(current) != set(COMPANIES):
        raise ValueError("Receipt requires exactly nine issuers")
    companies = []
    for c in COMPANIES:
        a,b = previous[c],current[c]
        p,q = period(a["period"]),period(b["period"])
        if q < p:
            raise ValueError(c + ": period regressed")
        if b.get("status") not in VERIFIED:
            raise ValueError(c + ": nonverified publication")
        advanced = q > p
        if advanced and a.get("source_url") == b.get("source_url"):
            # Some issuers reuse URLs: the underlying source digest must be
            # independently checked by existing provenance gates. Do not
            # certify discovery solely from a URL or the period label.
            discovery = "same_url_requires_independent_discovery_evidence"
        else:
            discovery = "changed_source_url" if advanced else "no_new_period"
        companies.append({"company":c, "previous_period":a["period"],
            "published_period":b["period"], "advanced":advanced,
            "scheduled_advance_observed":advanced and event=="schedule",
            "source_url":b.get("source_url"), "source_change":discovery,
            "published_row_sha256":digest(b)})
    return {"run_id":run_id, "event":event,"validated_source_commit":source_sha,
            "public_parity_verified":True, "comparison_sha256":digest(after),
            "companies":companies,
            "note":"A period advance is observable import/publication evidence; independent issuer discovery and metric extraction still require their own audit. No advance is not proof of future automation."}

def main():
    from verify_public_pages import load_public
    source_sha = os.environ["GITHUB_SHA"]
    if len(source_sha)!=40 or any(c not in "0123456789abcdef" for c in source_sha):
        raise ValueError("Invalid workflow source commit")
    before = json.loads(subprocess.check_output(
        ["git","show",source_sha+":"+FILE],cwd=ROOT,text=True))
    after = json.loads((ROOT/FILE).read_text())
    receipt = build(before,after,load_public("nine_insurer_comparison.json"),
                    os.environ["GITHUB_EVENT_NAME"],os.environ["GITHUB_RUN_ID"],source_sha)
    target=Path(os.environ["RUNNER_TEMP"])/"nine-import-receipt.json"
    target.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
    summary=os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary,"a",encoding="utf-8") as out:
            out.write("### Nine-insurer publication evidence\n\n")
            for r in receipt["companies"]:
                out.write(f"- {r['company']}: {r['previous_period']} → {r['published_period']}; scheduled advance observed: {r['scheduled_advance_observed']}\n")
    print("NINE_IMPORT_RECEIPT", target)

if __name__=="__main__":
    main()
