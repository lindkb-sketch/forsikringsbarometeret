"""Public site only links to the separately authenticated private broker portal."""
import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class PrivateBrokerPortalWiringTests(unittest.TestCase):
    def test_public_admin_config_is_disabled_until_real_access_provisioning(self):
        config=json.loads((ROOT/'data/broker_admin_config.json').read_text(encoding='utf-8'))
        self.assertEqual(config,{'enabled':False,'url':''})
        html=(ROOT/'index.html').read_text(encoding='utf-8')
        self.assertIn('scripts/broker_admin_link.js',html)
        script=(ROOT/'scripts/broker_admin_link.js').read_text(encoding='utf-8')
        self.assertIn("config.enabled!==true",script)
        self.assertIn("url.protocol!=='https:'",script)
        self.assertIn("new URLSearchParams(location.search).get('admin')!=='1'",script)
        self.assertNotIn('OPENAI_API_KEY',html)
        self.assertNotIn('GITHUB_TOKEN',html)
    def test_public_publisher_requires_broker_summary_but_not_pdfs(self):
        tree=(ROOT/'scripts/verify_deployment_tree.py').read_text()
        self.assertIn('data/broker_commentary.json',tree)
        self.assertIn('data/broker_admin_config.json',tree)
        self.assertIn('scripts/broker_admin_link.js',tree)
        self.assertNotIn('.pdf',tree)
        feed=json.loads((ROOT/'data/broker_commentary.json').read_text())
        for row in feed['entries']:
            self.assertNotIn('pdf',row)
            self.assertNotIn('filename',row)
        self.assertNotIn('broker-admin',json.dumps(feed))
    def test_public_browser_link_js_syntax(self):
        result=subprocess.run(['node','--check',str(ROOT/'scripts/broker_admin_link.js')],
                              capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
