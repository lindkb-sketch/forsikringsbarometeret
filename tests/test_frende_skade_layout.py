"""Check Frende Skade report layout remains responsive and avoids an unbounded report list."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class FrendeSkadeLayoutTests(unittest.TestCase):
    def test_report_history_collapses(self):
        js=(ROOT/'scripts/quarterly_runtime.js').read_text(encoding='utf-8')
        self.assertIn('frende-skade-history',js)
        self.assertIn('<details class="frende-skade-history">',js)
        self.assertIn('recent.map(link)',js)
        self.assertNotIn("'<ul>'+links+'</ul>'",js)
    def test_scoped_responsive_styles_exist(self):
        html=(ROOT/'index.html').read_text(encoding='utf-8')
        for selector in ('.frende-skade-report-links','.frende-skade-history',
                         '.frende-skade-pdf-disclosure .tablewrap',
                         '@media(max-width:600px)'):
            self.assertIn(selector,html)
if __name__=='__main__':unittest.main()
