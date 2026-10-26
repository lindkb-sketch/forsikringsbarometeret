#!/usr/bin/env python3
"""Fail-closed independent Protector issuer KPI verification (no publication)."""
import hashlib, html, json, re, urllib.request
from html.parser import HTMLParser

URL = "https://investor.protectorforsikring.no/data"
PERIOD_RE = re.compile(r"^Q([1-4]) (\d{2})$")
METRICS = {
    "Insurance revenue": "insurance_revenue",
    "Insurance service result": "insurance_service_result",
    "Loss ratio, net of reinsurance": "loss_ratio",
    "Cost ratio": "expense_ratio",
    "Combined ratio": "combined_ratio",
}
class Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []
    def handle_data(self, data):
        value = html.unescape(data).strip()
        if value: self.parts.append(value)

def extract(markup, include_history=False):
    parser = Text(); parser.feed(markup)
    tokens = parser.parts
    result = {}
    for scope, title in (("group", "Protector"), ("norway", "Norway")):
        # Locate a period header with the five quarter columns, then read KPI rows.
        candidates = []
        for i in range(len(tokens)-5):
            if not all(PERIOD_RE.fullmatch(t) for t in tokens[i:i+3]): continue
            parsed_periods = [(2000+int(PERIOD_RE.fullmatch(t).group(2)), int(PERIOD_RE.fullmatch(t).group(1))) for t in tokens[i:i+3]]
            if len(set(parsed_periods)) != 3: continue
            window = tokens[i:i+105]
            if not all(metric in window for metric in METRICS): continue
            candidates.append((i, window, parsed_periods))
        # Scope is established by the closest preceding geographical heading.
        qualified = []
        for i, window, parsed_periods in candidates:
            previous = [t for t in tokens[max(0,i-140):i] if t in ("Protector", "Norway", "Sweden", "United Kingdom", "Denmark", "France")]
            if previous and previous[-1] == title: qualified.append((window, parsed_periods))
        if not qualified:
            raise ValueError(f"Missing {scope} KPI table")
        window, parsed_periods = qualified[0]
        for label, metric in METRICS.items():
            positions = [i for i,v in enumerate(window) if v == label]
            if not positions: raise ValueError(f"Missing {scope} {label}")
            values = window[positions[0]+1:positions[0]+6]
            if len(values) != 5 or any(not re.fullmatch(r"-?\d+(?:[.,]\d+)?%?|\(-?\d+(?:[.,]\d+)?\)", v) for v in values):
                raise ValueError(f"Invalid values for {scope} {label}: {values}")
            periods_to_read = [(2000+int(PERIOD_RE.fullmatch(t).group(2)), int(PERIOD_RE.fullmatch(t).group(1))) for t in window[:5]] if include_history else parsed_periods
            for (year, q), value in zip(periods_to_read, values[:5] if include_history else values[:3]):
                numeric = float(value.strip("()%").replace(",","."))
                if value.startswith("("): numeric = -numeric
                result[(scope,year,q,metric)] = numeric
    if len(result) != (50 if include_history else 30): raise ValueError(f"Expected {50 if include_history else 30} KPI values, found {len(result)}")
    return result

def main():
    request=urllib.request.Request(URL,headers={"User-Agent":"Forsikringsbarometeret/1.0"})
    with urllib.request.urlopen(request,timeout=35) as response:
        if response.status != 200 or response.geturl().split("/")[2] != "investor.protectorforsikring.no":
            raise ValueError("Untrusted issuer response")
        blob=response.read(4_000_001)
    if len(blob)>4_000_000: raise ValueError("Issuer page too large")
    result=extract(blob.decode("utf-8"))
    print(json.dumps({"source":URL,"sha256":hashlib.sha256(blob).hexdigest(),"values":[{"scope":s,"year":y,"quarter":q,"metric":m,"value":v} for (s,y,q,m),v in sorted(result.items())]},indent=2))
if __name__=="__main__": main()
