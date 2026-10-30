"""Dry-run rollover contracts: synthetic data never enters published feeds."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import gjensidige_publish as gj
import sampo_publish as sampo
import import_frende_holding as frende
from discover_frende_fremtind import candidates


class Page:
    def __init__(self, text): self.text = text
    def extract_text(self): return self.text


class PDF:
    def __init__(self, texts): self.pages = [Page(t) for t in texts]
    def __enter__(self): return self
    def __exit__(self, *args): pass


class RolloverTests(unittest.TestCase):
    def test_gjensidige_q4_2026_synthetic_pdf_isolated_from_real_data(self):
        labels = {
            "Insurance revenue from general insurance": [11000.1, 10800.1, 43000.1, 42000.1],
            "Insurance service result general insurance": [2200.1, 2100.1, 9000.1, 8500.1],
            "Combined ratio": [80.1, 81.1, 81.1, 82.1],
            "Cost ratio": [11.7, 12.0, 11.8, 12.1],
            "Loss ratio, net of reinsurance": [68.4, 69.1, 69.3, 70.0],
        }
        page = "NOK millions\n" + "\n".join(k + " " + " ".join(map(str, v)) for k, v in labels.items())
        rows = gj.parse_group_table([(4, page)], 2026, 4,
                                    "https://example.org/synthetic-q4.pdf", "synthetic")
        self.assertEqual(len(rows), 20)
        self.assertEqual({r["period_type"] for r in rows}, {"quarter", "ytd"})
        self.assertEqual({r["year"] for r in rows}, {2025, 2026})
        self.assertEqual({r["quarter"] for r in rows}, {4})

    def test_sampo_q3_2026_synthetic_new_pdf(self):
        overview = ("Interim Statement Q3 2026\nFinancial overview\n"
                    "Insurance revenue (incl. brokerage), net EURm 2363 2188\n"
                    "Underwriting result EURm 368 336\n"
                    "Risk ratio % 59.6 58.9\nCost ratio % 24.8 25.7\n"
                    "Combined ratio % 84.4 84.6\nNordic underlying development")
        def segment(name):
            return (name + "\nInsurance revenue, net EURm 1048 1010\n"
                    "Underwriting result EURm 179 160\nRisk ratio % 61.6 60.0\n"
                    "Cost ratio % 21.4 23.0\nCombined ratio % 83.0 83.0")
        with patch.object(sampo.pdfplumber, "open", return_value=PDF([
            overview, segment("Private Nordic"), segment("Nordic Commercial")])):
            rows = sampo.parse(b"%PDF-synthetic", "https://www.sampo.com/report.pdf", 2026, 3)
        self.assertEqual(len(rows), 15)
        self.assertEqual({r["metric"] for r in rows}, set(sampo.LABELS))
        self.assertEqual({r["year"] for r in rows}, {2026})
        self.assertEqual({r["quarter"] for r in rows}, {3})

    def test_frende_q3_discovery_and_publisher_parsing(self):
        url = "https://frende.wrep.it/q3-2026-frende-holding-as"
        archive = '<a href="' + url + '">3. kvartal Frende Holding AS 2026</a>'
        found = candidates("Frende", archive)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["source_format"], "publisher_html")
        header = "<tr><th>Tall i 1000</th><th>Q3 2026</th><th>Pr Q3 2026</th></tr>"
        ratios = ("<tr><td>Kostnads %</td><td>20,0%</td><td>20,0%</td></tr>"
                  "<tr><td>Skadeprosent f.e.r</td><td>65,0%</td><td>65,0%</td></tr>"
                  "<tr><td>Combined ratio</td><td>85,0%</td><td>85,0%</td></tr>"
                  "<tr><td>Resultat før skatt</td><td>100</td><td>300</td></tr>")
        rows = frende.extract("Nøkkeltall konsern<table>" + header + ratios + "</table>",
                              url + "/sec/6", 2026, 3)
        self.assertEqual(len(rows), 6)
        self.assertEqual({r["period_type"] for r in rows}, {"quarter", "ytd"})
        self.assertEqual({r["metric"] for r in rows},
                         {"expense_ratio", "loss_ratio", "combined_ratio"})
        income_header = ("<tr><th>Resultatregnskap</th><th>3. kv 2026</th>"
                         "<th>3. kv 2025</th><th>30.09.26</th><th>30.09.25</th></tr>")
        income_rows = "".join(
            f"<tr><td>{label}</td><td>{a}</td><td>{b}</td><td>{c}</td><td>{d}</td></tr>"
            for label, a, b, c, d in (
                ("Sum driftsinntekter", "120000", "110000", "360000", "330000"),
                ("Sum erstatningskostnader og endring forsikringstekniske avsetninger",
                 "-60000", "-55000", "-180000", "-165000"),
                ("Sum driftskostnader", "-20000", "-18000", "-60000", "-54000")))
        html = "<table>" + income_header + income_rows + "</table>"
        revenues = frende.extract_revenue("Resultatregnskap" + html, url + "/sec/7", 2026, 3)
        insurance = frende.extract_insurance_result(html, url + "/sec/7", 2026, 3)
        self.assertEqual({r["period_type"] for r in revenues}, {"quarter", "ytd"})
        self.assertTrue(any(r["year"] == 2026 and r["quarter"] == 3
                            and r["metric"] == "insurance_service_result" for r in insurance))


if __name__ == "__main__":
    unittest.main()
