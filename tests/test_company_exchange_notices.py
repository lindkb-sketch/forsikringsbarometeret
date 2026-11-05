"""Exercise the actual production renderer, not literal source-code spellings."""
import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'index.html').read_text(encoding='utf-8')


class ExchangeNoticesTests(unittest.TestCase):
    def test_feed_contract_allows_empty_or_verified_notices(self):
        data = json.loads((ROOT / 'data/newsweb_notices.json').read_text(encoding='utf-8'))
        self.assertEqual(data['source'], 'NewsWeb')
        self.assertEqual(set(data['notices']), {'Fremtind', 'Gjensidige', 'Tryg', 'Sampo', 'Frende', 'Protector', 'Storebrand'})
        for rows in data['notices'].values():
            self.assertIsInstance(rows, list)
            self.assertLessEqual(len(rows), 1)
            for row in rows:
                self.assertEqual(row['source'], 'NewsWeb')
                self.assertRegex(row['url'], r'^https://newsweb\.oslobors\.no/message/[1-9][0-9]*$')
                self.assertTrue(row['title'].strip())

    def test_company_pages_include_newsweb_renderer(self):
        self.assertIn("${stockMarketSection(c)}${stockMarketConfig[c]?'':companyExchangeNotices(c)}${companyMediaNews(c)}", HTML)
        self.assertIn('data/newsweb_notices.json', HTML)

    def test_renderer_behavior_in_javascript(self):
        start = HTML.index('function companyExchangeNotices(')
        end = HTML.index('function company(c)', start)
        source = HTML[start:end]
        script = r'''
const vm = require('node:vm'), assert = require('node:assert/strict');
const now = Date.parse('2026-11-05T12:00:00Z');
class FixedDate extends Date {
  constructor(...args) { super(...(args.length ? args : [now])); }
  static now() { return now; }
}
const sandbox = {window: {FBNewsWeb: {notices: {}}}, Date: FixedDate};
vm.createContext(sandbox);
vm.runInContext(SOURCE, sandbox);
const render = rows => {
  sandbox.window.FBNewsWeb.notices = {Gjensidige: rows};
  return sandbox.companyExchangeNotices('Gjensidige');
};
const n = {source:'NewsWeb', title:'New <title> & value', url:'https://newsweb.oslobors.no/message/123', published_at:'2026-11-04T10:00:00Z'};
assert.equal(render([]), '');
assert.equal(sandbox.companyExchangeNotices('Sampo'), '');
assert.equal(render([{...n, published_at:'2026-07-01T10:00:00Z'}]), '');
assert.equal(render([{...n, published_at:'2026-11-06T10:00:00Z'}]), '');
assert.equal(render([{...n, published_at:'bad'}]), '');
assert.equal(render([{...n, source:'Another source'}]), '');
assert.equal(render([{...n, url:'https://newsweb.oslobors.no.evil.test/message/123'}]), '');
assert.equal(render([{...n, url:'javascript:alert(1)'}]), '');
assert.equal(render([{...n, title:' '}]), '');
const html = render([n, {...n, title:'Older message', published_at:'2026-11-03T10:00:00Z'}]);
assert.ok(html.includes('New &lt;title&gt; &amp; value'));
assert.ok(!html.includes('Older message'));
assert.equal((html.match(/<section /g)||[]).length, 1);
assert.ok(html.includes('noopener noreferrer'));
assert.equal(render([n]), render([n]));
const cutoff = new Date(now - 92*24*60*60*1000).toISOString();
assert.ok(render([{...n, published_at:cutoff}]).includes('<section'));
assert.equal(render([{...n, published_at:new Date(Date.parse(cutoff)-1).toISOString()}]), '');
console.log('NEWSWEB_RENDERER_PASS 16 assertions');
'''
        result = subprocess.run(['node', '-e', script.replace('SOURCE', json.dumps(source))],
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('NEWSWEB_RENDERER_PASS', result.stdout)


if __name__ == '__main__':
    unittest.main()
