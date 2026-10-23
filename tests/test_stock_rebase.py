import copy,datetime as dt,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from resolve_stock_rebase import merge,resolve
TODAY=dt.datetime.now(dt.timezone.utc).date()
def row(symbol,currency,days,close):
 return {'symbol':symbol,'currency':currency,'trading_date':(TODAY-dt.timedelta(days=days)).isoformat(),'close':close,'source_url':f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=10d','price_type':'delayed_daily_close'}
def snapshot(g,p,updated):
 return {'updated_at':updated,'prices':{'Gjensidige':g,'Protector':p},'unlisted':['Fremtind','Frende'],'errors':{},'source':'Yahoo Finance public chart endpoint'}
class StockRebaseTests(unittest.TestCase):
 def test_newest_date_per_ticker(self):
  a=snapshot(row('GJF.OL','NOK',1,100),row('PROT.OL','NOK',0,200),'2026-10-22T20:00:00+00:00')
  b=snapshot(row('GJF.OL','NOK',0,101),row('PROT.OL','NOK',1,199),'2026-10-22T19:00:00+00:00')
  c=merge(a,b);self.assertEqual(c['prices']['Gjensidige']['close'],101);self.assertEqual(c['prices']['Protector']['close'],200)
 def test_conflicting_same_date_rejected(self):
  a=snapshot(row('GJF.OL','NOK',0,100),row('PROT.OL','NOK',0,200),'2026-10-22T20:00:00+00:00')
  b=copy.deepcopy(a);b['prices']['Gjensidige']['close']=101
  with self.assertRaisesRegex(ValueError,'same trading date'):merge(a,b)
 def test_currency_mismatch_rejected(self):
  a=snapshot(row('GJF.OL','USD',0,100),row('PROT.OL','NOK',0,200),'2026-10-22T20:00:00+00:00')
  with self.assertRaisesRegex(ValueError,'currency'):merge(a,a)
 def test_real_git_rebase_conflict_stock_only(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'data').mkdir()
   def run(*args,ok=True,env=None):
    return subprocess.run(['git',*args],cwd=root,text=True,capture_output=True,check=ok,env={**os.environ,**(env or {})})
   def write(d):(root/'data/stock_prices.json').write_text(json.dumps(d,indent=2)+'\n')
   run('init','-b','main');run('config','user.email','ci@example.test');run('config','user.name','Synthetic Test')
   base=snapshot(row('GJF.OL','NOK',2,98),row('PROT.OL','NOK',2,198),'2026-10-20T10:00:00+00:00')
   write(base);(root/'data/financial_observations.json').write_text('{"observations":[{"verified":true}]}\n')
   run('add','.');run('commit','-m','base');run('branch','worker')
   main=snapshot(row('GJF.OL','NOK',1,100),row('PROT.OL','NOK',0,200),'2026-10-22T20:00:00+00:00')
   write(main);run('add','data/stock_prices.json');run('commit','-m','upstream');run('checkout','worker')
   worker=snapshot(row('GJF.OL','NOK',0,101),row('PROT.OL','NOK',1,199),'2026-10-22T19:00:00+00:00')
   write(worker);run('add','data/stock_prices.json');run('commit','-m','worker')
   rb=run('rebase','main',ok=False);self.assertNotEqual(rb.returncode,0,rb.stdout+rb.stderr)
   result=resolve(root);self.assertEqual(result['prices']['Gjensidige']['close'],101);self.assertEqual(result['prices']['Protector']['close'],200)
   run('rebase','--continue',env={'GIT_EDITOR':'true'})
   self.assertEqual(json.loads((root/'data/stock_prices.json').read_text())['prices'],result['prices'])
   self.assertEqual((root/'data/financial_observations.json').read_text(),'{"observations":[{"verified":true}]}\n')
if __name__=='__main__':unittest.main()
