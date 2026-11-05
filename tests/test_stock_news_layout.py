"""Test the production stock/news renderer without network or third-party packages."""
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')


class StockNewsLayoutTests(unittest.TestCase):
    def test_actual_stock_and_news_renderer(self):
        news_start = HTML.index('function companyExchangeNotices(')
        news_end = HTML.index('function company(c)', news_start)
        stock_start = HTML.rindex(' stockMarketSection=function(c){')
        stock_end = HTML.index('\n const prevHome=home;', stock_start)
        source = HTML[news_start:news_end] + '\n' + HTML[stock_start:stock_end]
        script = r'''
const vm=require('node:vm'), assert=require('node:assert/strict');
const now=Date.parse('2026-11-05T12:00:00Z');
class FixedDate extends Date {
  constructor(...args){super(...(args.length?args:[now]));}
  static now(){return now;}
}
const listed=['Gjensidige','Tryg','Sampo','Protector','Storebrand'];
const symbols=['GJF.OL','TRYG.CO','SAMPO.HE','PROT.OL','STB.OL'];
const currencies=['NOK','DKK','EUR','NOK','NOK'];
const sandbox={window:{FBNewsWeb:{notices:{}}},Date:FixedDate,
  stockMarketConfig:{}, stocks:{prices:{}},stockCSV:{},stockRangeSelection:{},
  esc:s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))};
listed.forEach((c,i)=>{
 sandbox.stockMarketConfig[c]={ticker:symbols[i],currency:currencies[i]};
 sandbox.stocks.prices[c==='Sampo'?'Sampo / If':c]={symbol:symbols[i],currency:currencies[i],
   availability:'available',observed_at:'2026-11-05T10:00:00Z',close:102,provisional:true,
   history:[{date:'2026-11-04',price:100},{date:'2026-11-05',price:102}]};
 sandbox.window.FBNewsWeb.notices[c]=[{source:'NewsWeb',title:'Latest <notice>',
   url:'https://newsweb.oslobors.no/message/123',published_at:'2026-11-04T10:00:00Z'}];
});
vm.createContext(sandbox);vm.runInContext(SOURCE,sandbox);
for(const c of listed){
 const html=sandbox.stockMarketSection(c);
 assert.ok(html.includes('Kursutvikling og børsnytt'));
 assert.equal((html.match(/class="panel company-exchange-notices"/g)||[]).length,1);
 assert.equal((html.match(new RegExp('id="stock-plot-'+c+'"','g'))||[]).length,1);
 assert.equal((html.match(new RegExp('id="stock-stats-'+c+'"','g'))||[]).length,1);
 assert.ok(html.indexOf('class="stock-market-sidebar"')<html.indexOf('class="panel company-exchange-notices"'));
 assert.ok(html.includes('<h3>Siste børsmelding</h3>'));
 assert.ok(html.includes('Latest &lt;notice&gt;'));
 // The stats div is replaced on range selection; news must be its sibling, not its child.
 assert.ok(html.includes('class="stock-figures"></div></div><section class="panel company-exchange-notices"'));
 sandbox.window.FBNewsWeb.notices[c]=[];
 assert.ok(!sandbox.stockMarketSection(c).includes('company-exchange-notices'));
 assert.ok(sandbox.stockMarketSection(c).includes('stock-stats-'+c));
}
for(const c of ['Fremtind','Frende'])assert.equal(sandbox.stockMarketSection(c),'');
const n={source:'NewsWeb',title:'Retained news',url:'https://newsweb.oslobors.no/message/124',published_at:'2026-11-04T10:00:00Z'};
sandbox.window.FBNewsWeb.notices.Tryg=[n];
sandbox.stocks.prices.Tryg.availability='stale';
let html=sandbox.stockMarketSection('Tryg');
assert.ok(html.includes('Retained news'));assert.ok(!html.includes('id="stock-plot-Tryg"'));
assert.ok(!('Tryg' in sandbox.stockCSV));
sandbox.window.FBNewsWeb.notices.Tryg=[{...n,published_at:'2026-07-01T10:00:00Z'}];
html=sandbox.stockMarketSection('Tryg');
assert.ok(!html.includes('company-exchange-notices'));
assert.ok(html.includes('stock-news-no-sidebar'));
console.log('STOCK_NEWS_RENDERER_PASS');
'''
        result = subprocess.run(['node', '-e', script.replace('SOURCE', json.dumps(source))],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('STOCK_NEWS_RENDERER_PASS', result.stdout)

    def test_responsive_layout_and_no_duplicate_company_news(self):
        self.assertIn('id="stock-news-layout"', HTML)
        self.assertIn('@media(max-width:1100px)', HTML)
        self.assertIn('@media(max-width:650px)', HTML)
        self.assertIn("${stockMarketConfig[c]?'':companyExchangeNotices(c)}", HTML)
        self.assertIn('grid-template-columns:minmax(0,1fr) minmax(260px,29%)', HTML)


if __name__ == '__main__':
    unittest.main()
