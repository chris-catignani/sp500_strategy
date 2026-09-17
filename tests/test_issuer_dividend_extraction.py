import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class TestIssuerDividendExtraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.output_path = ROOT / "data" / "raw" / "ground_truth" / "issuer_dividend_tables.json"
        cls.splits_path = ROOT / "data" / "raw" / "corporate_actions" / "splits.json"
        cls.pinned_path = ROOT / "data" / "raw" / "ground_truth" / "issuer_filing_manifest.json"

        with open(cls.output_path, "r", encoding="utf-8") as f:
            cls.payload = json.load(f)

        with open(cls.splits_path, "r", encoding="utf-8") as f:
            cls.splits_data = json.load(f)

        with open(cls.pinned_path, "r", encoding="utf-8") as f:
            cls.pinned_filings = json.load(f)["filings_by_ticker"]

    def test_output_file_exists_and_valid(self):
        self.assertTrue(self.output_path.exists(), "issuer_dividend_tables.json does not exist")
        self.assertIn("metadata", self.payload)
        self.assertIn("tickers", self.payload)
        self.assertIn("refusals", self.payload)
        self.assertIn("structural_rejects", self.payload)

    def test_reconcile_or_withhold_rule(self):
        """Every published quarter with a dividend belongs to a year that reconciled clean."""
        for ticker, t_data in self.payload["tickers"].items():
            quarters = t_data.get("quarters", {})
            reconciled_years = {
                yr for yr, r_val in t_data.get("reconciliation", {}).items()
                if r_val.get("reconciled") is True
            }
            for q_key, q_val in quarters.items():
                if q_val.get("dividend_declared_per_share") is not None:
                    yr = q_key.split("-")[0]
                    self.assertIn(
                        yr,
                        reconciled_years,
                        f"{ticker} {q_key} published with dividend but year {yr} did not reconcile"
                    )

    def test_no_inverted_prices(self):
        """No published row has high < low."""
        for ticker, t_data in self.payload["tickers"].items():
            for q_key, q_val in t_data.get("quarters", {}).items():
                h = q_val.get("high")
                low = q_val.get("low")
                if h is not None and low is not None:
                    self.assertGreaterEqual(h, low, f"Inverted prices in {ticker} {q_key}: high={h} < low={low}")

    def test_dividend_sanity_bound(self):
        """No published dividend exceeds 25% of its own close or low price."""
        for ticker, t_data in self.payload["tickers"].items():
            for q_key, q_val in t_data.get("quarters", {}).items():
                div = q_val.get("dividend_declared_per_share")
                close = q_val.get("quarter_end_close")
                low = q_val.get("low")
                ref_price = close if close is not None else low
                if div is not None and ref_price is not None and ref_price > 0:
                    self.assertLessEqual(
                        div,
                        0.25 * ref_price,
                        f"Dividend {div} exceeds 25% of price {ref_price} in {ticker} {q_key}"
                    )

    def test_no_completely_null_rows(self):
        """No published row has both dividend and close null."""
        for ticker, t_data in self.payload["tickers"].items():
            for q_key, q_val in t_data.get("quarters", {}).items():
                div = q_val.get("dividend_declared_per_share")
                close = q_val.get("quarter_end_close")
                self.assertFalse(
                    div is None and close is None,
                    f"Row {ticker} {q_key} has both dividend and close null"
                )

    def test_refusals_and_withheld_provenance(self):
        """Every refusal and withheld entry carries a reason."""
        for ref in self.payload.get("refusals", []):
            self.assertIn("reason", ref)
            self.assertTrue(bool(ref["reason"].strip()))
            self.assertIn("accession_number", ref)

        for ticker, t_data in self.payload["tickers"].items():
            for w in t_data.get("withheld", []):
                self.assertIn("reason", w)
                self.assertTrue(bool(w["reason"].strip()))

    def test_pinning_att_1994_and_bellsouth_1996(self):
        """Regression test pinning AT&T 1994 and BellSouth 1996 quarters."""
        att_quarters = self.payload["tickers"]["T_CORP"]["quarters"]
        for q in range(1, 5):
            k = f"1994-Q{q}"
            self.assertIn(k, att_quarters)
            self.assertEqual(att_quarters[k]["dividend_declared_per_share"], 0.33)
            self.assertEqual(att_quarters[k]["accession_number"], "0000005907-95-000026")

        bls_quarters = self.payload["tickers"]["BLS"]["quarters"]
        for q in range(1, 5):
            k = f"1996-Q{q}"
            self.assertIn(k, bls_quarters)
            self.assertEqual(bls_quarters[k]["dividend_declared_per_share"], 0.36)
            self.assertEqual(bls_quarters[k]["accession_number"], "0000912057-97-007016")


if __name__ == "__main__":
    unittest.main()
