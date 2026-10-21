import json
from pathlib import Path
from source_policy import validate_source_policy
ROOT=Path(__file__).resolve().parents[1]
rows=json.loads((ROOT/'data/financial_observations.json').read_text())['observations']
errors=validate_source_policy(rows)
if errors:
 print('SOURCE POLICY ERRORS:',*errors,sep='\n')
 raise SystemExit(1)
print('Source policy verified')
