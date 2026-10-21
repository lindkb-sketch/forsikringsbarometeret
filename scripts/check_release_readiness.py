import json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
data=json.loads((root/'data/financial_observations.json').read_text())
companies=set(data['companies'])
covered={r['company'] for r in data['observations']}
missing=sorted(companies-covered)
print('REPORT DATA COVERAGE:',len(covered),'/',len(companies),'companies')
if missing:print('NOT READY - missing:',', '.join(missing))
if missing:sys.exit(2)
