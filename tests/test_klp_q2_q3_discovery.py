import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from klp_q2_q3_discovery import classify,discover

class KLPQ2Q3DiscoveryTests(unittest.TestCase):
    def test_q2_q3_and_other_insurers(self):
        self.assertEqual(classify('https://www.klp.no/Kvartalsrapport%20KLP%20Skadeforsikring%20AS%20Q2%202026.pdf'),2)
        self.assertEqual(classify('https://www.klp.no/Kvartalsrapport%20KLP%20Skadeforsikring%20AS%20Q3%202026.pdf'),3)
        self.assertIsNone(classify('https://www.klp.no/Kvartalsrapport%20KLP%20Bank%20Q3%202026.pdf'))
    def test_archive_section_labels_not_url_names(self):
        html=('KLP Banken 2026 <a href="/bank-Q2-2026.pdf">Kvartalsrapport 2. kvartal</a>'
              '<h2>KLP Skadeforsikring</h2><h3>2026</h3>'
              '<a href="/opaque3.pdf">Kvartalsrapport 3. kvartal</a>'
              '<a href="/opaque2.pdf">Kvartalsrapport 2. kvartal</a>'
              '<h3>2025</h3><a href="/old.pdf">Kvartalsrapport 2. kvartal</a>')
        found=discover(html)
        self.assertEqual(len(found[2]),1)
        self.assertEqual(len(found[3]),1)
        self.assertTrue(found[2][0].endswith('opaque2.pdf'))
    def test_no_cross_company_contamination(self):
        html=('<h2>KLP Skadeforsikring</h2><h3>2026</h3>'
              '<a href="/ok.pdf">Kvartalsrapport 2. kvartal</a>'
              '<h2>KLP Banken</h2><h3>2026</h3>'
              '<a href="/bad.pdf">Kvartalsrapport 3. kvartal</a>')
        found=discover(html)
        self.assertEqual(len(found[2]),1)
        self.assertEqual(found[3],[])
if __name__=='__main__':unittest.main()
