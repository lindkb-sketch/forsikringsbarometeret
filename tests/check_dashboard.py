from pathlib import Path
import re,subprocess,tempfile
html=Path(__file__).resolve().parents[1].joinpath('index.html').read_text()
assert 'kpi-final-correction-20261020' in html
assert 'market-minor-row' in html and "mini('PM',m.pm)" in html and "mini('BM',m.bm)" in html
assert 'Sammenligning ikke registrert' in html
scripts=re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>',html,re.S)
for i,script in enumerate(scripts):
 if script.strip():
  with tempfile.NamedTemporaryFile(suffix='.js',mode='w') as f:
   f.write(script);f.flush();r=subprocess.run(['node','--check',f.name],capture_output=True,text=True)
   assert r.returncode==0,(i,r.stderr)
print(f'OK: {len(scripts)} scripts, PM/BM, return delta and layout selectors')
