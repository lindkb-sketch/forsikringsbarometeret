import datetime as dt
import importlib.util
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('newsweb',ROOT/'scripts/update_newsweb_notices.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class NewsWebImportTests(unittest.TestCase):
    def test_exact_issuer_and_newest_first(self):
        now=dt.datetime(2026,11,5,12,tzinfo=dt.timezone.utc)
        page='''<table><tr><th>Date/time</th><th>Market</th><th>IssuerID</th><th>Message title</th></tr>
<tr><td>04.11.2026 10:00</td><td>XOSL</td><td>GJF</td><td><a href="/message/123">Ny melding</a></td></tr>
<tr><td>03.11.2026 10:00</td><td>XOSL</td><td>PROT</td><td><a href="/message/456">Feil selskap</a></td></tr>
<tr><td>01.07.2026 10:00</td><td>XOSL</td><td>GJF</td><td><a href="/message/789">For gammel</a></td></tr></table>'''
        rows=mod.parse(page,'GJF',now)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['url'],'https://newsweb.oslobors.no/message/123')

    def test_no_unverified_issuer_mapping(self):
        self.assertEqual(set(mod.ISSUERS),{'Gjensidige','Protector','Storebrand'})
        self.assertNotIn('Frende',mod.ISSUERS)
        self.assertNotIn('Fremtind',mod.ISSUERS)

if __name__=='__main__':
    unittest.main()
