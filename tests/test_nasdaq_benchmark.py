import unittest
from engine.data_loader import DataLoader
from engine.metrics import calculate_benchmark_annual_series, calculate_cagr, calculate_tax_drag


class TestNasdaqDataLoader(unittest.TestCase):
    def setUp(self):
        self.loader = DataLoader()

    def test_nasdaq_annual_levels(self):
        pr_1993 = self.loader.get_nasdaq_level(1993)
        tr_1993 = self.loader.get_nasdaq_tr_level(1993)
        pr_2024 = self.loader.get_nasdaq_level(2024)
        tr_2024 = self.loader.get_nasdaq_tr_level(2024)
        self.assertGreater(pr_1993, 0.0)
        self.assertGreater(tr_1993, 0.0)
        self.assertGreater(pr_2024, pr_1993)
        self.assertGreater(tr_2024, tr_1993)

    def test_nasdaq_key_map_aliases(self):
        aliases = ["nasdaq_100", "nasdaq 100", "nasdaq100", "qqq", "^ndx", "ndx", "^ndxt", "ndxt"]
        for alias in aliases:
            self.assertEqual(self.loader.get_benchmark_level(alias, 2024), self.loader.get_nasdaq_level(2024))
            self.assertEqual(self.loader.get_benchmark_tr_level(alias, 2024), self.loader.get_nasdaq_tr_level(2024))

    def test_nasdaq_quarterly_levels(self):
        pr_q4_1993 = self.loader.get_nasdaq_quarterly_level(1993, 4)
        tr_q4_1993 = self.loader.get_nasdaq_tr_quarterly_level(1993, 4)
        alias_tr_q4 = self.loader.get_nasdaq_quarterly_tr_level(1993, 4)
        self.assertEqual(tr_q4_1993, alias_tr_q4)
        self.assertGreater(pr_q4_1993, 0.0)
        self.assertGreater(tr_q4_1993, 0.0)
        self.assertAlmostEqual(pr_q4_1993, self.loader.get_nasdaq_level(1993), places=2)
        self.assertAlmostEqual(tr_q4_1993, self.loader.get_nasdaq_tr_level(1993), places=2)

    def test_nasdaq_dividend_yield_non_negative(self):
        for yr in range(1994, 2025):
            yld = self.loader.get_nasdaq_dividend_yield(yr)
            self.assertGreaterEqual(yld, 0.0)
            self.assertLessEqual(yld, 0.035)

    def test_nasdaq_cagr_horizons(self):
        end_year = 2024
        for horizon in [10, 20, 30]:
            start_year = end_year - horizon
            pr_start = self.loader.get_nasdaq_level(start_year)
            pr_end = self.loader.get_nasdaq_level(end_year)
            tr_start = self.loader.get_nasdaq_tr_level(start_year)
            tr_end = self.loader.get_nasdaq_tr_level(end_year)

            nasdaq_pr_cagr = calculate_cagr(pr_start, pr_end, horizon)
            nasdaq_tr_cagr = calculate_cagr(tr_start, tr_end, horizon)

            self.assertGreater(
                nasdaq_tr_cagr,
                nasdaq_pr_cagr,
                f"Expected TR CAGR > PR CAGR for {horizon}y horizon, got TR={nasdaq_tr_cagr} <= PR={nasdaq_pr_cagr}",
            )

    def test_cli_ndx_choice(self):
        import run_backtest

        parser = run_backtest.build_parser()
        args = parser.parse_args(["--benchmark", "ndx"])
        self.assertEqual(args.benchmark, "ndx")



class TestNasdaqPerformanceCalculations(unittest.TestCase):
    def setUp(self):
        self.loader = DataLoader()

    def test_nasdaq_30y_series_modeling(self):
        years = list(range(1993, 2025))
        pr_series = [self.loader.get_nasdaq_level(y) for y in years]
        tr_series = [self.loader.get_nasdaq_tr_level(y) for y in years]

        res_pre = calculate_benchmark_annual_series(
            pr_levels=pr_series,
            tr_levels=tr_series,
            tax_rate=0.0,
            initial_capital=10000.0,
            is_after_tax=False,
        )
        self.assertEqual(res_pre["total_taxes_paid"], 0.0)
        self.assertEqual(res_pre["post_liquidation_wealth"], res_pre["final_equity"])
        self.assertGreater(res_pre["final_equity"], res_pre["cost_basis"])
        cagr_pre = calculate_cagr(10000.0, res_pre["final_equity"], 31)
        self.assertGreater(cagr_pre, 0.05)

        res_post = calculate_benchmark_annual_series(
            pr_levels=pr_series,
            tr_levels=tr_series,
            tax_rate=0.30,
            initial_capital=10000.0,
            is_after_tax=True,
        )
        self.assertGreater(res_post["total_taxes_paid"], 0.0)
        self.assertLess(res_post["final_equity"], res_pre["final_equity"])
        cagr_post = calculate_cagr(10000.0, res_post["pre_liquidation_wealth"], 31)
        drag = calculate_tax_drag(cagr_pre, cagr_post)
        self.assertGreaterEqual(drag, 0.0)


if __name__ == "__main__":
    unittest.main()
